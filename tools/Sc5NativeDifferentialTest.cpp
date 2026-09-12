// SPDX-License-Identifier: GPL-2.0-or-later
#include "native_device_runtime.h"
#include "gtest/gtest.h"

TEST(Sc5NativeDifferential, ActualStartupMatchesReference) {
 const char *dllPath=std::getenv("SC5_NATIVE_DLL");
 const char *imagePath=std::getenv("SC5_IMAGE");
 ASSERT_NE(dllPath,nullptr);ASSERT_NE(imagePath,nullptr);
 std::ifstream input(imagePath,std::ios::binary);
 std::vector<unsigned char> image((std::istreambuf_iterator<char>(input)),{});
 ASSERT_EQ(image.size(),0x260000u);
 HMODULE library=LoadLibraryA(dllPath);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto reset=(void(*)(const unsigned char*))GetProcAddress(library,"sc5_reset");
 auto run=(void(*)(u32))GetProcAddress(library,"sc5_run");
 auto state=(u32(*)(u32))GetProcAddress(library,"sc5_state");
 auto ram=(const unsigned char*(*)())GetProcAddress(library,"sc5_ram");
 ASSERT_TRUE(reset&&run&&state&&ram);
 reset(image.data());run(5090311);
 ASSERT_EQ(state(16),0x8c032cfcu);ASSERT_EQ(state(20),0u);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);
 auto *ctx=&p_sh4rcb->cntx;
 auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 memset(GetMemPtr(0x8c000000,0x1000000),0,0x1000000);
 memcpy(GetMemPtr(0x8c010000,0x260000),image.data(),image.size());
 memset(ctx->r,0,sizeof(ctx->r));memset(ctx->r_bank,0,sizeof(ctx->r_bank));
 ctx->pc=0x8c010000;ctx->pr=0xac00e0b0;ctx->r[15]=0x8c00f400;
 ctx->sr.setFull(0x700000f0);ctx->old_sr.status=ctx->sr.status;UpdateSR();
 unsigned int calls=0;
 while(ctx->pc!=0x8c032cfc && calls<6000000){interpreter->Step();calls++;}
 ASSERT_EQ(ctx->pc,0x8c032cfcu)<<"Reference did not reach boundary";
 for(unsigned int j=0;j<16;j++)EXPECT_EQ(ctx->r[j],state(j))<<"Register "<<j;
 EXPECT_EQ(ctx->pr,state(17));EXPECT_EQ(ctx->sr.getFull(),state(18));
 const unsigned char *reference=GetMemPtr(0x8c000000,0x1000000);
 size_t differences=0;size_t first=0;
 for(size_t j=0;j<0x1000000;j++)if(reference[j]!=ram()[j]){if(!differences)first=j;differences++;}
 EXPECT_EQ(differences,0u)<<"First RAM difference at offset "<<first;
 auto runChunk=(u32(*)(u32))GetProcAddress(library,"sc5_run_chunk");ASSERT_TRUE(runChunk);
 reset(image.data());u32 total=0;
 while(total<5090311){u32 completed=runChunk(std::min(100003u,5090311u-total));ASSERT_GT(completed,0u);total+=completed;}
 EXPECT_EQ(state(16),ctx->pc);EXPECT_EQ(state(17),ctx->pr);EXPECT_EQ(state(18),ctx->sr.getFull());
 for(u32 j=0;j<16;j++)EXPECT_EQ(state(j),ctx->r[j]);
 EXPECT_EQ(memcmp(reference,ram(),0x1000000),0)<<"Relative execution chunks changed startup state";
 std::cout<<"Reference Step calls="<<calls<<" native retired="<<total<<" full RAM bytes compared=16777216; relative chunks also match\n";
}

TEST(Sc5NativeDifferential, NativeExecutionUsesDeviceBus){auto result=runNativeDeviceHarness();EXPECT_GT(result.retired,5095138u);if(!std::getenv("SC5_CHECKPOINT_LOAD"))EXPECT_GT(busWrites,4u);EXPECT_NE(result.pc,0x8c07ff6au);}

TEST(Sc5NativeDifferential, NativeSdlInputWithoutPhysicalHardware){
 const char *visible=std::getenv("SC5_VISIBLE"),*script=std::getenv("SC5_INPUT_SCRIPT");
 struct Restore{std::string visible,script;~Restore(){_putenv_s("SC5_VISIBLE",visible.c_str());_putenv_s("SC5_INPUT_SCRIPT",script.c_str());}} restore{visible?visible:"",script?script:""};
 _putenv_s("SC5_VISIBLE","1");_putenv_s("SC5_INPUT_SCRIPT","");SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS,"1");
 ASSERT_EQ(SDL_InitSubSystem(SDL_INIT_GAMECONTROLLER),0);
 struct Quit{~Quit(){SDL_QuitSubSystem(SDL_INIT_GAMECONTROLLER);}} quit;
 for(int index=0;index<SDL_NumJoysticks();index++)if(SDL_IsGameController(index))GTEST_SKIP()<<"A physical or pre-existing controller is attached; leave it undisturbed";
 int index=SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER,SDL_CONTROLLER_AXIS_MAX,SDL_CONTROLLER_BUTTON_MAX,0);ASSERT_GE(index,0);
 SDL_Joystick *joystick=SDL_JoystickOpen(index);ASSERT_TRUE(joystick);
 struct Detach{SDL_Joystick *joystick;int index;~Detach(){SDL_JoystickClose(joystick);SDL_JoystickDetachVirtual(index);}} detach{joystick,index};
 NativeInput host(0);host.events();host.update(0);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 const std::pair<SDL_Keycode,u32> keys[]={{SDLK_RETURN,DC_BTN_START},{SDLK_UP,DC_DPAD_UP},{SDLK_DOWN,DC_DPAD_DOWN},{SDLK_LEFT,DC_DPAD_LEFT},{SDLK_RIGHT,DC_DPAD_RIGHT},{SDLK_z,DC_BTN_A},{SDLK_x,DC_BTN_B},{SDLK_a,DC_BTN_X},{SDLK_s,DC_BTN_Y}};
 for(auto key:keys){
  SDL_Event event{};event.type=SDL_KEYDOWN;event.key.keysym.sym=key.first;ASSERT_EQ(SDL_PushEvent(&event),1);host.events();host.update(0);ASSERT_EQ((~kcode[0])&0xffffu,key.second);
  event.type=SDL_KEYUP;ASSERT_EQ(SDL_PushEvent(&event),1);host.events();host.update(0);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 }
 // A complete tap between controller polls must survive intervening CPU ticks.
 SDL_Event tap{};tap.type=SDL_KEYDOWN;tap.key.keysym.sym=SDLK_z;ASSERT_EQ(SDL_PushEvent(&tap),1);
 tap.type=SDL_KEYUP;ASSERT_EQ(SDL_PushEvent(&tap),1);host.events();
 host.update(0,false);ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);
 host.update(1,false);ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);
 host.update(2);ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);
 host.update(3);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 for(auto symbol:{SDLK_SPACE,SDLK_BACKSPACE}){
  tap={};tap.type=SDL_KEYDOWN;tap.key.keysym.sym=symbol;SDL_PushEvent(&tap);tap.type=SDL_KEYUP;SDL_PushEvent(&tap);host.events();host.update(0);
  ASSERT_EQ((~kcode[0])&0xffffu,symbol==SDLK_SPACE?DC_BTN_A:DC_BTN_B);host.update(1);
 }
 tap={};tap.type=SDL_KEYDOWN;tap.key.keysym.sym=0x44f;tap.key.keysym.scancode=SDL_SCANCODE_Z;SDL_PushEvent(&tap);tap.type=SDL_KEYUP;SDL_PushEvent(&tap);host.events();host.update(0);
 ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);host.update(1);
 tap={};tap.type=SDL_TEXTINPUT;tap.text.text[0]='z';tap.text.text[1]=0;SDL_PushEvent(&tap);host.events();host.update(0);
 ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);host.update(61ull*200000ull);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 // SDL text generated by a physical key must not extend its released hold.
 tap={};tap.type=SDL_KEYDOWN;tap.key.keysym.sym=SDLK_z;SDL_PushEvent(&tap);
 tap={};tap.type=SDL_TEXTINPUT;tap.text.text[0]='z';SDL_PushEvent(&tap);
 tap={};tap.type=SDL_KEYUP;tap.key.keysym.sym=SDLK_z;SDL_PushEvent(&tap);host.events();
 host.update(62ull*200000ull);ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);
 host.update(63ull*200000ull);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 SDL_Event event{};event.type=SDL_KEYDOWN;event.key.keysym.sym=SDLK_z;SDL_PushEvent(&event);host.events();host.update(0);ASSERT_EQ((~kcode[0])&0xffffu,DC_BTN_A);
 event={};event.type=SDL_WINDOWEVENT;event.window.event=SDL_WINDOWEVENT_FOCUS_LOST;SDL_PushEvent(&event);host.events();host.update(0);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 const std::pair<SDL_GameControllerButton,u32> buttons[]={{SDL_CONTROLLER_BUTTON_START,DC_BTN_START},{SDL_CONTROLLER_BUTTON_A,DC_BTN_A},{SDL_CONTROLLER_BUTTON_B,DC_BTN_B},{SDL_CONTROLLER_BUTTON_X,DC_BTN_X},{SDL_CONTROLLER_BUTTON_Y,DC_BTN_Y},{SDL_CONTROLLER_BUTTON_DPAD_UP,DC_DPAD_UP},{SDL_CONTROLLER_BUTTON_DPAD_DOWN,DC_DPAD_DOWN},{SDL_CONTROLLER_BUTTON_DPAD_LEFT,DC_DPAD_LEFT},{SDL_CONTROLLER_BUTTON_DPAD_RIGHT,DC_DPAD_RIGHT}};
 for(auto button:buttons){
  ASSERT_EQ(SDL_JoystickSetVirtualButton(joystick,button.first,1),0);SDL_JoystickUpdate();host.events();host.update(0);ASSERT_EQ((~kcode[0])&0xffffu,button.second);
  ASSERT_EQ(SDL_JoystickSetVirtualButton(joystick,button.first,0),0);SDL_JoystickUpdate();host.events();host.update(0);ASSERT_EQ(kcode[0]&0xffffu,0xffffu);
 }
 ASSERT_EQ(SDL_JoystickSetVirtualAxis(joystick,SDL_CONTROLLER_AXIS_LEFTX,-12345),0);ASSERT_EQ(SDL_JoystickSetVirtualAxis(joystick,SDL_CONTROLLER_AXIS_LEFTY,23456),0);
 SDL_JoystickUpdate();host.events();host.update(0);ASSERT_EQ(joyx[0],-12345);ASSERT_EQ(joyy[0],23456);
 std::cout<<"Synthetic SDL keyboard, focus release, virtual controller buttons and axes reach native Maple input state; physical hardware not tested\n";
}

TEST(Sc5NativeDifferential, DiagnosticAssistProducesExactControllerChord){
 const char *enabled=std::getenv("SC5_CHEAT_100"),*start=std::getenv("SC5_CHEAT_100_START_MS"),*interval=std::getenv("SC5_CHEAT_100_INTERVAL_MS"),*visible=std::getenv("SC5_VISIBLE");
 struct Restore{std::string enabled,start,interval,visible;~Restore(){_putenv_s("SC5_CHEAT_100",enabled.c_str());_putenv_s("SC5_CHEAT_100_START_MS",start.c_str());_putenv_s("SC5_CHEAT_100_INTERVAL_MS",interval.c_str());_putenv_s("SC5_VISIBLE",visible.c_str());}} restore{enabled?enabled:"",start?start:"",interval?interval:"",visible?visible:""};
 _putenv_s("SC5_VISIBLE","");_putenv_s("SC5_CHEAT_100","1");_putenv_s("SC5_CHEAT_100_START_MS","1000");_putenv_s("SC5_CHEAT_100_INTERVAL_MS","10000");
 NativeInput host(0);const u64 ticksPerMs=200000ull;
 host.update(1000*ticksPerMs);EXPECT_EQ((~kcode[0])&0xffffu,DC_BTN_START);EXPECT_EQ(lt[0],0);EXPECT_EQ(rt[0],0);
 host.update(1300*ticksPerMs);EXPECT_EQ((~kcode[0])&0xffffu,0u);EXPECT_EQ(lt[0],0xffff);EXPECT_EQ(rt[0],0xffff);
 const u32 sequence[]={DC_DPAD_UP,DC_DPAD_LEFT,DC_BTN_A,DC_DPAD_LEFT,DC_BTN_A,DC_DPAD_DOWN,DC_DPAD_RIGHT,DC_BTN_B,DC_DPAD_RIGHT,DC_BTN_B};
 for(unsigned int index=0;index<10;index++){
  host.update((1500ull+index*260ull)*ticksPerMs);EXPECT_EQ((~kcode[0])&0xffffu,sequence[index]);EXPECT_EQ(lt[0],0xffff);EXPECT_EQ(rt[0],0xffff);
 }
 host.update(5500*ticksPerMs);EXPECT_EQ((~kcode[0])&0xffffu,DC_BTN_START);EXPECT_EQ(lt[0],0);EXPECT_EQ(rt[0],0);
 host.update(11000*ticksPerMs);EXPECT_EQ((~kcode[0])&0xffffu,DC_BTN_START)<<"assist interval did not repeat";
 std::cout<<"Diagnostic assist emits pause, full L+R trigger chord, exact ten-button sequence, unpause and configured repeat\n";
}

// Explicitly separate offline analysis. Its execution is never gameplay evidence
// and none of its instruction results are substituted into a native run.
static void collectOfflineReferenceCoverage(){
 const char *outputPath=std::getenv("SC5_REFERENCE_TRACE");ASSERT_NE(outputPath,nullptr);
 pushContext();auto *ctx=&p_sh4rcb->cntx;Sh4Context savedContext=*ctx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();*ctx=savedContext;
 std::map<u32,u16> visited;u32 calls=0;
 const char *stepText=std::getenv("SC5_REFERENCE_STEPS");u32 limit=stepText?static_cast<u32>(std::stoul(stepText)):1000000u;ASSERT_LE(limit,1000000000u);
 for(;calls<limit;calls++){
  pullContext();if(nativeService(ctx->pc))continue;
  u32 physical=ctx->pc&0x1fffffffu;
  if(physical<0x0c000000u||physical>=0x0d000000u||(ctx->pc&1u))break;
  u16 word=addrspace::read16(ctx->pc);visited[(ctx->pc&0x1fffffffu)|0x80000000u]=word;
  interpreter->Step();
  while(ctx->cycle_counter<=0){ctx->cycle_counter+=SH4_TIMESLICE;UpdateSystem_INTC();}
 }
 std::ofstream output(outputPath);for(auto &entry:visited)output<<std::hex<<entry.first<<" "<<entry.second<<"\n";
 ASSERT_TRUE(output.good());ASSERT_GT(visited.size(),0u);std::cout<<"OFFLINE REFERENCE ONLY steps="<<calls<<" unique PCs="<<visited.size()<<" stop="<<std::hex<<ctx->pc<<std::dec<<"\n";
 if(const char *frame=std::getenv("SC5_REFERENCE_FRAME_OUTPUT")){
  std::cout<<"OFFLINE REFERENCE ONLY frame capture (not native evidence): ";NativeRenderSurface::capture(frame);
 }
 if(const char *path=std::getenv("SC5_REFERENCE_RAM_DUMP")){
  std::ofstream dump(path,std::ios::binary);dump.write(reinterpret_cast<const char*>(GetMemPtr(0x8c000000,0x1000000)),0x1000000);ASSERT_TRUE(dump.good());
 }
}
TEST(Sc5NativeDifferential, OfflineReferenceCoverageOnly){
 if(!std::getenv("SC5_REFERENCE_TRACE"))GTEST_SKIP()<<"Offline reference tracing not requested";
 runNativeDeviceHarness(collectOfflineReferenceCoverage);
}

TEST(Sc5NativeDifferential, RelocatedExceptionReturnMatchesReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");const char *imagePath=std::getenv("SC5_IMAGE");ASSERT_TRUE(path&&imagePath);
 HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto reset=(void(*)(const unsigned char*))GetProcAddress(library,"sc5_reset");auto run=(void(*)(u32))GetProcAddress(library,"sc5_run");
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto ram=(unsigned char*(*)())GetProcAddress(library,"sc5_ram");ASSERT_TRUE(reset&&run&&context&&ram);
 std::ifstream input(imagePath,std::ios::binary);std::vector<unsigned char> image((std::istreambuf_iterator<char>(input)),{});ASSERT_EQ(image.size(),0x260000u);
 reset(image.data());memcpy(ram()+0xf400,image.data()+0xace3c,4);auto *n=context();n->pc=0x8c00f400;n->spc=0x8c123456;n->ssr=0x400000f1;n->sr=0x700000f0;n->t=0;
 for(u32 j=0;j<16;j++)n->r[j]=0x11110000+j;for(u32 j=0;j<8;j++)n->bank[j]=0x22220000+j;
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;
 auto *interpreter=Get_Sh4Interpreter();interpreter->Init();memcpy(ctx->r,n->r,sizeof(n->r));memcpy(ctx->r_bank,n->bank,sizeof(n->bank));
 ctx->pc=n->pc;ctx->spc=n->spc;ctx->ssr=n->ssr;ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();
 addrspace::write16(ctx->pc,0x002b);addrspace::write16(ctx->pc+2,0x0009);run(2);interpreter->Step();
 ASSERT_EQ(n->fault,0u);ASSERT_EQ(n->pc,ctx->pc);ASSERT_EQ((n->sr&~1u)|n->t,ctx->sr.getFull());
 for(u32 j=0;j<16;j++)ASSERT_EQ(n->r[j],ctx->r[j]);for(u32 j=0;j<8;j++)ASSERT_EQ(n->bank[j],ctx->r_bank[j]);
 // A later code-byte change must stop at execution even with relocation writes permitted.
 n->pc=0x8c00f400;ram()[0xf400]^=1;run(4);ASSERT_EQ(n->fault,7u);
}

TEST(Sc5NativeDifferential, InstructionByteGuardsPreserveAliasesAndDelaySlots){
 const char *path=std::getenv("SC5_NATIVE_DLL"),*imagePath=std::getenv("SC5_IMAGE");ASSERT_TRUE(path&&imagePath);
 HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto reset=(void(*)(const unsigned char*))GetProcAddress(library,"sc5_reset");
 auto run=(u32(*)(u32))GetProcAddress(library,"sc5_run_chunk");
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto ram=(unsigned char*(*)())GetProcAddress(library,"sc5_ram");ASSERT_TRUE(reset&&run&&context&&ram);
 std::ifstream input(imagePath,std::ios::binary);std::vector<unsigned char> image((std::istreambuf_iterator<char>(input)),{});ASSERT_EQ(image.size(),0x260000u);
 for(u32 alias:{0x0c00f400u,0x8c00f400u,0xac00f400u})for(int corrupt:{-1,0,2}){
  reset(image.data());memcpy(ram()+0xf400,image.data()+0xace3c,4);auto *n=context();
  n->pc=alias;n->spc=0x8c123456;n->ssr=0x400000f1;n->sr=0x700000f0;n->t=0;
  if(corrupt>=0)ram()[0xf400+corrupt]^=1;
  const u32 retired=run(2);
  if(corrupt<0){EXPECT_EQ(retired,2u);EXPECT_EQ(n->fault,0u);EXPECT_EQ(n->pc,0x8c123456u);}
  else {EXPECT_EQ(retired,0u);EXPECT_EQ(n->fault,7u);EXPECT_EQ(n->pc,alias);}
 }
}

TEST(Sc5NativeDifferential, LocalBranchLinksRespectRetirementRedirects){
 const char *path=std::getenv("SC5_NATIVE_DLL"),*imagePath=std::getenv("SC5_IMAGE");ASSERT_TRUE(path&&imagePath);
 HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto reset=(void(*)(const unsigned char*))GetProcAddress(library,"sc5_reset");
 auto run=(u32(*)(u32))GetProcAddress(library,"sc5_run_chunk");
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto ram=(unsigned char*(*)())GetProcAddress(library,"sc5_ram");
 auto setRetire=(void(*)(void(*)(u32,u32,u32)))GetProcAddress(library,"sc5_set_retire");ASSERT_TRUE(reset&&run&&context&&ram&&setRetire);
 std::ifstream input(imagePath,std::ios::binary);std::vector<unsigned char> image((std::istreambuf_iterator<char>(input)),{});ASSERT_EQ(image.size(),0x260000u);
 // Retail BT at 8C010096 chooses MOV #20,R0 or FLDI0 FR0. Redirecting
 // retirement to a different NOP models an interrupt changing the next PC.
 ASSERT_EQ(image[0x96],0x02);ASSERT_EQ(image[0x97],0x89);
 static State *callbackState;static unsigned char *callbackRam;static u32 callbackMode,callbackCount;
 for(u32 segment:{0u,0x80000000u,0xa0000000u})for(u32 taken:{0u,1u})for(u32 mode=0;mode<5;mode++){
  reset(image.data());auto *n=context();n->pc=segment|0x0c010096u;n->t=taken;n->r[0]=0x12345678;n->fr[0]=0x3f800000;
  callbackState=n;callbackRam=ram();callbackMode=mode;callbackCount=0;
  setRetire(+[](u32,u32,u32){
   if(++callbackCount!=1)return;
   if(callbackMode==1)callbackState->pc=(callbackState->pc&0xe0000000u)|0x0c0100a2u;
   else if(callbackMode==2)callbackState->fault=9;
   else if(callbackMode==3)callbackRam[(callbackState->pc&0x1fffffffu)-0x0c000000u]^=1;
  });
  const u32 retired=run(mode==4?1:2);const u32 target=segment|(taken?0x0c01009eu:0x0c010098u);
  if(mode==2||mode==3){EXPECT_EQ(retired,1u);EXPECT_EQ(n->fault,mode==2?9u:7u);EXPECT_EQ(n->pc,target);}
  else if(mode==4){EXPECT_EQ(retired,1u);EXPECT_EQ(n->pc,target);EXPECT_EQ(n->fault,0u);}
  else {EXPECT_EQ(retired,2u);EXPECT_EQ(n->fault,0u);EXPECT_EQ(n->pc,mode==1?(segment|0x0c0100a4u):target+2);}
  EXPECT_EQ(n->r[0],mode==0&&!taken?20u:0x12345678u);
  EXPECT_EQ(n->fr[0],mode==0&&taken?0u:0x3f800000u);
 }
}

TEST(Sc5NativeDifferential, NativeDiscServicesReadOriginalSectors){
 const char *discPath=std::getenv("SC5_GDI");if(!discPath)GTEST_SKIP()<<"SC5_GDI not supplied";
 const char *dataPath=std::getenv("SC5_RUNTIME_DATA");const char *imagePath=std::getenv("SC5_IMAGE");ASSERT_TRUE(dataPath&&imagePath);
 set_user_config_dir(dataPath);set_user_data_dir(dataPath);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);
 ASSERT_TRUE(gdr::initDrive(discPath));ASSERT_TRUE(nvmem::loadHle());
 State state{};nativeContext=&state;state.sr=0x40000000u;
 struct Cleanup{~Cleanup(){nativeContext=nullptr;}} cleanup;
 auto call=[&](u32 function){state.pc=0x8c001006;state.pr=0x8c123456;state.r[6]=0;state.r[7]=function;return nativeService(state.pc);};
 ASSERT_EQ(call(GDROM_INIT_SYSTEM),1);ASSERT_EQ(state.pc,0x8c123456u);
 const u32 params=0x8c300000,dest=0x8c310000;
 addrspace::write32(params,547784u+150u);addrspace::write32(params+4,1);addrspace::write32(params+8,dest);addrspace::write32(params+12,0);
 state.r[4]=GDCC_PIOREAD;state.r[5]=params;ASSERT_EQ(call(GDROM_REQ_CMD),1);u32 request=state.r[0];ASSERT_GT(request,0u);
 ASSERT_EQ(call(GDROM_EXEC_SERVER),1);
 state.r[4]=request;state.r[5]=params+16;ASSERT_EQ(call(GDROM_GET_CMD_STAT),1);ASSERT_EQ(state.r[0],GDC_COMPLETE);
 std::ifstream input(imagePath,std::ios::binary);std::vector<unsigned char> sectorBytes(2048);input.read(reinterpret_cast<char*>(sectorBytes.data()),2048);ASSERT_EQ(input.gcount(),2048);
 ASSERT_EQ(memcmp(GetMemPtr(dest,2048),sectorBytes.data(),2048),0);
 std::cout<<"Native BIOS PIO read: original executable sector matches all 2048 extracted bytes\n";
}

TEST(Sc5NativeDifferential, FloatingArithmeticMatchesReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_NE(path,nullptr);
 HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");
 auto arithmetic=(void(*)(u32,u32,u32))GetProcAddress(library,"sc5_float");ASSERT_TRUE(context&&arithmetic);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);
 auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 const float values[]={1.f,-1.f,2.f,3.f,0.1f,-0.1f,12345.67f,0.00001f};unsigned int cases=0;
 for(u32 rounding=0;rounding<2;rounding++)for(u32 kind=0;kind<6;kind++)for(float x:values)for(float y:values){
  auto *n=context();memset(n,0,sizeof(*n));n->sr=0x40000000u;n->fpscr=0x40000u|rounding;
  memcpy(&n->fr[1],&x,4);memcpy(&n->fr[2],&y,4);
  ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=n->fpscr;ctx->restoreHostRoundingMode();
  ctx->fr[1]=x;ctx->fr[2]=y;ctx->pc=0x8c200000;addrspace::write16(ctx->pc,0xf120u|kind);
  arithmetic(1,2,kind);interpreter->Step();ASSERT_EQ(n->fault,0u);
  u32 expected;memcpy(&expected,&ctx->fr[1],4);
  ASSERT_EQ(n->fr[1],expected)<<"kind="<<kind<<" rounding="<<rounding<<" x="<<x<<" y="<<y;
  ASSERT_EQ(n->t,ctx->sr.T);cases++;
 }
 std::cout<<"Floating result/reference cases="<<cases<<" (finite single precision; exception flags excluded)\n";
}

TEST(Sc5NativeDifferential, SquareRootAndFmaMatchReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_NE(path,nullptr);HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto operation=(void(*)(u32,u32,u32))GetProcAddress(library,"sc5_float_extended");ASSERT_TRUE(context&&operation);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 const float values[]={0.f,1.f,2.f,3.f,0.1f,12345.67f,0.00001f};u32 cases=0;
 for(u32 rounding=0;rounding<2;rounding++)for(u32 kind=0;kind<2;kind++)for(float x:values)for(float y:values)for(float z:values){
  auto *n=context();memset(n,0,sizeof(*n));n->sr=0x40000000;n->fpscr=0x40000|rounding;
  memcpy(&n->fr[1],&x,4);memcpy(&n->fr[2],&y,4);memcpy(&n->fr[0],&z,4);
  ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=n->fpscr;ctx->restoreHostRoundingMode();
  ctx->fr[1]=x;ctx->fr[2]=y;ctx->fr[0]=z;ctx->pc=0x8c200000;addrspace::write16(ctx->pc,kind?0xf12e:0xf16d);
  operation(1,2,kind);interpreter->Step();ASSERT_EQ(n->fault,0u);u32 reference;memcpy(&reference,&ctx->fr[1],4);
  ASSERT_EQ(n->fr[1],reference)<<"kind="<<kind<<" rounding="<<rounding;cases++;
 }
 std::cout<<"Square root/FMA finite result cases="<<cases<<"\n";
}

TEST(Sc5NativeDifferential, MatrixTransformMatchesReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_NE(path,nullptr);HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto operation=(void(*)(u32))GetProcAddress(library,"sc5_transform");ASSERT_TRUE(context&&operation);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 u32 seed=5095,cases=0;auto next=[&](){seed=seed*1664525u+1013904223u;return (static_cast<int>(seed>>8)-0x800000)/4096.f;};
 for(u32 rounding=0;rounding<2;rounding++)for(u32 base=0;base<16;base+=4)for(u32 sample=0;sample<128;sample++){
  auto *n=context();memset(n,0,sizeof(*n));n->sr=0x40000000;n->fpscr=0x40000|rounding;
  for(u32 j=0;j<16;j++){float a=next(),b=next();memcpy(&n->fr[j],&a,4);memcpy(&n->xf[j],&b,4);ctx->fr[j]=a;ctx->xf[j]=b;}
  ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=n->fpscr;ctx->restoreHostRoundingMode();
  ctx->pc=0x8c200000;addrspace::write16(ctx->pc,0xf1fd|(base<<8));operation(base);interpreter->Step();ASSERT_EQ(n->fault,0u);
  for(u32 j=0;j<16;j++)ASSERT_EQ(n->fr[j],ctx->fr_hex(j))<<"rounding="<<rounding<<" base="<<base<<" sample="<<sample;cases++;
 }
 std::cout<<"Matrix transform finite reference cases="<<cases<<"\n";
}

TEST(Sc5NativeDifferential, GraphicsMathMatchesReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_TRUE(path);HMODULE library=LoadLibraryA(path);ASSERT_TRUE(library);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");
 auto sincos=(void(*)(u32))GetProcAddress(library,"sc5_sincos");
 auto inner=(void(*)(u32,u32))GetProcAddress(library,"sc5_inner");
 auto precision=(void(*)(u32,u32))GetProcAddress(library,"sc5_precision");
 auto extended=(void(*)(u32,u32,u32))GetProcAddress(library,"sc5_float_extended");ASSERT_TRUE(context&&sincos&&inner&&precision&&extended);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 u32 cases=0,seed=5095;auto next=[&](){seed=seed*1664525u+1013904223u;return (static_cast<int>(seed>>8)-0x800000)/4096.f;};
 auto prepare=[&](u32 fpscr){auto *n=context();memset(n,0,sizeof(*n));n->sr=0x40000000;n->fpscr=fpscr;ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=fpscr;ctx->restoreHostRoundingMode();return n;};
 auto execute=[&](u16 word){ctx->pc=0x8c200000;addrspace::write16(ctx->pc,word);interpreter->Step();};
 for(u32 angle=0;angle<65536;angle++){
  auto *n=prepare(0x40000);u32 reg=(angle%8)*2;n->fpul=ctx->fpul=angle|0xabcd0000u;sincos(reg);execute(0xf0fd|(reg<<8));ASSERT_EQ(n->fault,0u);
  ASSERT_EQ(n->fr[reg],ctx->fr_hex(reg))<<"angle="<<angle;ASSERT_EQ(n->fr[reg+1],ctx->fr_hex(reg+1))<<"angle="<<angle;cases++;
 }
 for(u32 rounding=0;rounding<2;rounding++)for(u32 ni=0;ni<16;ni+=4)for(u32 mi=0;mi<16;mi+=4)for(u32 sample=0;sample<64;sample++){
  auto *n=prepare(0x40000|rounding);for(u32 j=0;j<16;j++){float value=next();memcpy(&n->fr[j],&value,4);ctx->fr[j]=value;}
  inner(ni,mi);execute(0xf0ed|((ni|(mi/4))<<8));ASSERT_EQ(n->fault,0u);
  for(u32 j=0;j<16;j++)ASSERT_EQ(n->fr[j],ctx->fr_hex(j))<<"FIPR rounding="<<rounding<<" n="<<ni<<" m="<<mi;cases++;
 }
 for(u32 rounding=0;rounding<2;rounding++)for(u32 ni=0;ni<16;ni++)for(u32 sample=0;sample<64;sample++){
  auto *n=prepare(0x40000|rounding);float value=std::abs(next())+0.125f;memcpy(&n->fr[ni],&value,4);ctx->fr[ni]=value;
  extended(ni,0,2);execute(0xf07d|(ni<<8));ASSERT_EQ(n->fault,0u);ASSERT_EQ(n->fr[ni],ctx->fr_hex(ni))<<"FSRRA rounding="<<rounding;cases++;
 }
 for(u32 ni=0;ni<16;ni++)for(u32 bits:{0x00000000u,0x80000000u,0x80000001u,0xbf800000u,0x7f800000u,0xff800000u,0x7fc12345u}){
  auto *n=prepare(0x40000);n->fr[ni]=bits;ctx->fr_hex(ni)=bits;extended(ni,0,2);execute(0xf07d|(ni<<8));ASSERT_EQ(n->fault,0u);ASSERT_EQ(n->fr[ni],ctx->fr_hex(ni))<<"FSRRA special bits="<<std::hex<<bits;cases++;
 }
 for(u32 rounding=0;rounding<2;rounding++)for(u32 ni=0;ni<16;ni+=2)for(u32 direction=0;direction<2;direction++)for(u32 sample=0;sample<128;sample++){
  auto *n=prepare(0xc0000|rounding);float value=next();memcpy(&n->fpul,&value,4);ctx->fpul=n->fpul;
  double wide=static_cast<double>(next())/7.;u64 bits;memcpy(&bits,&wide,8);n->fr[ni]=bits>>32;n->fr[ni+1]=(u32)bits;ctx->setDR(ni/2,wide);
  precision(ni,direction);execute((direction?0xf0bd:0xf0ad)|(ni<<8));ASSERT_EQ(n->fault,0u);
  ASSERT_EQ(n->fpul,ctx->fpul)<<"FCNV direction="<<direction<<" rounding="<<rounding;
  ASSERT_EQ(n->fr[ni],ctx->fr_hex(ni));ASSERT_EQ(n->fr[ni+1],ctx->fr_hex(ni+1));cases++;
 }
 std::cout<<"FSCA exhaustive angles, FIPR, FSRRA and precision conversion reference cases="<<cases<<"\n";
}

TEST(Sc5NativeDifferential, DoubleArithmeticAndCompareMatchReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_TRUE(path);HMODULE library=LoadLibraryA(path);ASSERT_TRUE(library);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto operation=(void(*)(u32,u32,u32))GetProcAddress(library,"sc5_float");ASSERT_TRUE(context&&operation);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 const double values[]={0.0,-0.0,1.0,-1.0,2.5,-3.75,1e100,-1e-100};u32 cases=0;
 for(u32 kind=0;kind<=5;kind++)for(u32 ni=0;ni<8;ni+=2)for(u32 mi=0;mi<8;mi+=2)for(double x:values)for(double y:values){
  auto *n=context();memset(n,0,sizeof(*n));memset(ctx,0,sizeof(*ctx));n->sr=0x40000000;n->fpscr=0xc0000;ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=n->fpscr;ctx->setDR(ni/2,x);ctx->setDR(mi/2,y);
  u64 bx,by;memcpy(&bx,&x,8);memcpy(&by,&y,8);n->fr[(ni/2)*2]=(u32)(bx>>32);n->fr[(ni/2)*2+1]=(u32)bx;n->fr[(mi/2)*2]=(u32)(by>>32);n->fr[(mi/2)*2+1]=(u32)by;
  ctx->pc=0x8c200000;u16 word=0xf000|(ni<<8)|(mi<<4)|kind;addrspace::write16(ctx->pc,word);operation(ni,mi,kind);interpreter->Step();ASSERT_EQ(n->fault,0u);
  ASSERT_EQ(n->t,ctx->sr.T)<<"kind="<<kind;for(u32 j=0;j<16;j++)ASSERT_EQ(n->fr[j],ctx->fr_hex(j))<<"kind="<<kind<<" n="<<ni<<" m="<<mi;cases++;
 }
 std::cout<<"Double arithmetic and FCMP reference cases="<<cases<<"; exception flags not compared\n";
}

TEST(Sc5NativeDifferential, PairedFloatMovesMatchReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_NE(path,nullptr);HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto operation=(void(*)(u32,u32,u32))GetProcAddress(library,"sc5_fmov");
 auto memory=(const unsigned char*(*)())GetProcAddress(library,"sc5_ram");ASSERT_TRUE(context&&operation&&memory);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 u32 cases=0;
 for(u32 kind=6;kind<=12;kind++)for(u32 ni=0;ni<16;ni++)for(u32 mi=0;mi<16;mi++){
  auto *n=context();memset(n,0,sizeof(*n));n->sr=0x40000000;n->fpscr=0x140000;
  for(u32 j=0;j<16;j++){n->r[j]=0x8c300020;n->fr[j]=0x11223300+j;n->xf[j]=0xaabbcc00+j;ctx->r[j]=n->r[j];ctx->fr_hex(j)=n->fr[j];memcpy(&ctx->xf[j],&n->xf[j],4);}
  // Indexed cases use an offset in R0; avoid R0 simultaneously as the base.
  if((kind==6&&mi==0)||(kind==7&&ni==0))continue;
  if(kind==6||kind==7){n->r[0]=16;ctx->r[0]=16;}
  auto *ram=const_cast<unsigned char*>(memory());
  for(u32 j=0;j<64;j++){ram[0x300000+j]=(unsigned char)(j*13+7);addrspace::write8(0x8c300000+j,ram[0x300000+j]);}
  ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=n->fpscr;
  ctx->pc=0x8c200000;addrspace::write16(ctx->pc,0xf000|(ni<<8)|(mi<<4)|kind);
  operation(ni,mi,kind);interpreter->Step();ASSERT_EQ(n->fault,0u);
  for(u32 j=0;j<16;j++){ASSERT_EQ(n->r[j],ctx->r[j]);ASSERT_EQ(n->fr[j],ctx->fr_hex(j));u32 xf;memcpy(&xf,&ctx->xf[j],4);ASSERT_EQ(n->xf[j],xf);}
  ASSERT_EQ(memcmp(ram+0x300000,GetMemPtr(0x8c300000,64),64),0)<<"kind="<<kind<<" n="<<ni<<" m="<<mi;cases++;
 }
 std::cout<<"Paired FMOV reference cases="<<cases<<"\n";
}

TEST(Sc5NativeDifferential, SaturatingFloatToIntegerMatchesReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_TRUE(path);HMODULE library=LoadLibraryA(path);ASSERT_TRUE(library);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto convert=(void(*)(u32,u32))GetProcAddress(library,"sc5_convert");ASSERT_TRUE(context&&convert);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 std::vector<u32> values={0,0x80000000,1,0x80000001,0x3fc00000,0xbfc00000,0x4effffff,0x4f000000,0x4f000001,0x4f00f149,0xceffffff,0xcf000000,0xcf000001,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00000,0xffc00000,0x7f800001,0xff800001};
 u32 seed=5095,cases=0;for(u32 j=0;j<1024;j++){seed=seed*1664525u+1013904223u;values.push_back(seed);}
 for(u32 rounding=0;rounding<2;rounding++)for(u32 ni=0;ni<16;ni++)for(u32 bits:values){
  auto *n=context();memset(n,0,sizeof(*n));n->sr=0x40000000;n->fpscr=0x40000|rounding;n->fr[ni]=bits;
  ctx->sr.setFull(n->sr);ctx->old_sr.status=ctx->sr.status;UpdateSR();ctx->fpscr.full=n->fpscr;ctx->restoreHostRoundingMode();ctx->fr_hex(ni)=bits;
  ctx->pc=0x8c200000;addrspace::write16(ctx->pc,0xf03d|(ni<<8));convert(ni,3);interpreter->Step();ASSERT_EQ(n->fault,0u);ASSERT_EQ(n->fpul,ctx->fpul)<<"input bits="<<std::hex<<bits;cases++;
 }
 std::cout<<"FTRC result comparisons including saturation, infinities, NaNs and random bit patterns="<<cases<<"; exception flags not compared\n";
}

TEST(Sc5NativeDifferential, DivisionStepMatchesReference){
 const char *path=std::getenv("SC5_NATIVE_DLL");ASSERT_NE(path,nullptr);
 HMODULE library=LoadLibraryA(path);ASSERT_NE(library,nullptr);
 struct Cleanup{HMODULE library;~Cleanup(){FreeLibrary(library);}} cleanup{library};
 auto context=(State*(*)())GetProcAddress(library,"sc5_context");auto divide=(void(*)(u32,u32))GetProcAddress(library,"sc5_div1");ASSERT_TRUE(context&&divide);
 ASSERT_TRUE(addrspace::reserve());emu.init();mem_map_default();emu.dc_reset(true);
 auto *ctx=&p_sh4rcb->cntx;auto *interpreter=Get_Sh4Interpreter();interpreter->Init();
 const u32 values[]={0,1,2,0x7fffffff,0x80000000,0xfffffffe,0xffffffff,0x12345678};
 unsigned int cases=0;
 for(bool alias:{false,true})for(u32 qmt=0;qmt<8;qmt++)for(u32 x:values)for(u32 y:values){
  auto *n=context();memset(n,0,sizeof(*n));n->r[1]=x;n->r[2]=y;n->sr=0x40000000u|((qmt&3)<<8);n->t=(qmt>>2)&1;
  memset(ctx->r,0,sizeof(ctx->r));ctx->r[1]=x;ctx->r[2]=y;ctx->sr.setFull(n->sr|n->t);ctx->old_sr.status=ctx->sr.status;UpdateSR();
  ctx->pc=0x8c200000;addrspace::write16(ctx->pc,alias?0x3114:0x3124);
  divide(1,alias?1:2);interpreter->Step();
  ASSERT_EQ(n->r[1],ctx->r[1])<<"alias="<<alias<<" flags="<<qmt;
  ASSERT_EQ((n->sr&0x300u)|n->t,ctx->sr.getFull()&0x301u);cases++;
 }
 std::cout<<"DIV1 independent reference cases="<<cases<<"\n";
}
