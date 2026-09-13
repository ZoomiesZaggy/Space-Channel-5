#pragma once
// SPDX-License-Identifier: GPL-2.0-or-later
// Shared device host driven exclusively by the native AOT execution library.
#include "emulator.h"
#include "hw/sh4/sh4_mem.h"
#include "hw/sh4/sh4_interpreter.h"
#include "hw/sh4/sh4_core.h"
#include "hw/sh4/sh4_cycles.h"
#include "hw/sh4/sh4_interrupts.h"
#include "hw/sh4/sh4_sched.h"
#include "hw/flashrom/nvmem.h"
#include "hw/maple/maple_cfg.h"
#include "imgread/common.h"
#include "reios/reios.h"
#include "reios/gdrom_hle.h"
#include "serialize.h"
#include "stdclass.h"
#include "native_state.h"
#include "native_host_os.h"
#include <SDL_loadso.h>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdlib>
#include <map>
#include <chrono>
#include <limits>
#include "native_render_surface.h"
#include "native_audio_capture.h"
#include "native_input.h"
#include "native_cycle_model.h"
#include "native_mod_runtime.h"
#include "native_rhythm_calibration.h"
#include "native_dispatch_trace.h"
#include "rend/CustomTexture.h"

static u32 (*nativeState)(u32);
static u64 busReads,busWrites;
static State *nativeContext;
static NativeInput *nativeInput;
static void pollNativeInput(){if(nativeInput){nativeInput->events();nativeInput->update(sh4_sched_now64());}}
static NativeCycleModel nativeCycles;
static bool clockActive;
static u64 ticks;
static u64 serviceCalls;
static u64 queueWrites;
static unsigned int discReadLogLimit=24;
static std::map<u32,u32> discCommands;
struct DiscReadRequest{u32 fad,sectors,destination;bool log;};
static std::map<u32,DiscReadRequest> pendingDiscReads;
static u32 pendingModule=0,activeModule=1;
static void pushContext(){
 auto *ctx=&p_sh4rcb->cntx;auto *n=nativeContext;
 memcpy(ctx->r,n->r,sizeof(n->r));memcpy(ctx->r_bank,n->bank,sizeof(n->bank));
 memcpy(ctx->fr,n->fr,sizeof(n->fr));memcpy(ctx->xf,n->xf,sizeof(n->xf));
 ctx->pc=n->pc;ctx->pr=n->pr;ctx->sr.setFull((n->sr&~1u)|n->t);ctx->old_sr.status=ctx->sr.status;
 ctx->mac.h=n->mach;ctx->mac.l=n->macl;
 ctx->gbr=n->gbr;ctx->vbr=n->vbr;ctx->ssr=n->ssr;ctx->spc=n->spc;ctx->sgr=n->sgr;ctx->dbr=n->dbr;ctx->fpul=n->fpul;ctx->fpscr.full=n->fpscr;
 UpdateSR();
}
static void pullContext(){
 auto *ctx=&p_sh4rcb->cntx;auto *n=nativeContext;
 memcpy(n->r,ctx->r,sizeof(n->r));memcpy(n->bank,ctx->r_bank,sizeof(n->bank));
 memcpy(n->fr,ctx->fr,sizeof(n->fr));memcpy(n->xf,ctx->xf,sizeof(n->xf));
 n->pc=ctx->pc;n->pr=ctx->pr;n->sr=ctx->sr.getFull();n->t=ctx->sr.T;
 n->mach=ctx->mac.h;n->macl=ctx->mac.l;
 n->gbr=ctx->gbr;n->vbr=ctx->vbr;n->ssr=ctx->ssr;n->spc=ctx->spc;n->sgr=ctx->sgr;n->dbr=ctx->dbr;n->fpul=ctx->fpul;n->fpscr=ctx->fpscr.full;
}
static NativeRhythmCalibration nativeRhythmCalibration;
static NativeDispatchTrace nativeDispatchTrace;
static int nativeService(u32 pc){
 nativeRhythmCalibration.dispatch(pc,*nativeContext);
 nativeDispatchTrace.record(pc,*nativeContext);
 const u32 address=(pc&0x1fffffffu)|0x80000000u;
 switch(address){case 0x8c001002:case 0x8c001004:case 0x8c001006:case 0x8c001008:case 0x8c0010f0:break;default:return 0;}
 const bool gdService=(address==0x8c001006||address==0x8c0010f0)&&nativeContext->r[6]==0;
 const u32 function=nativeContext->r[7],argument=nativeContext->r[4];bool queuedRead=false;DiscReadRequest newRead{};
 if((address==0x8c001006||address==0x8c0010f0)&&nativeContext->r[6]==0&&nativeContext->r[7]==GDROM_REQ_CMD){
  u32 command=nativeContext->r[4];discCommands[command]++;
  if(command==GDCC_PIOREAD||command==GDCC_DMAREAD){
   auto *params=GetMemPtr(nativeContext->r[5],16);
   if(params){u32 words[4];memcpy(words,params,16);
    const bool roundRead=words[0]==119124u||words[0]==258003u||words[0]==349238u||words[0]==422138u;
    newRead={words[0],words[1],words[2],roundRead||discCommands[command]<=discReadLogLimit};queuedRead=true;
    if(newRead.log)std::cout<<"Game disc read command="<<command<<" FAD="<<words[0]<<" sectors="<<words[1]<<" destination="<<std::hex<<words[2]<<std::dec<<"\n";
   }
  }
 }
 pushContext();auto *ctx=&p_sh4rcb->cntx;ctx->pc=pc+2;
 // Direct native BIOS service dispatch; never an SH4 instruction executor.
 reios_trap(ctx,REIOS_OPCODE);pullContext();serviceCalls++;
 if(queuedRead&&nativeContext->r[0]!=0)pendingDiscReads[nativeContext->r[0]]=newRead;
 if(gdService&&function==GDROM_GET_CMD_STAT&&nativeContext->r[0]==GDC_COMPLETE){
  auto read=pendingDiscReads.find(argument);
  if(read!=pendingDiscReads.end()){
   auto request=read->second;u64 length=static_cast<u64>(request.sectors)*2048;
   const u8 *data=length<=0x1000000?GetMemPtr(request.destination,static_cast<u32>(length)):nullptr;
   if(data&&request.log){u64 hash=14695981039346656037ull;for(u64 i=0;i<length;i++){hash^=data[i];hash*=1099511628211ull;}std::cout<<"Completed disc read FAD="<<request.fad<<" sectors="<<request.sectors<<" FNV64="<<std::hex<<hash<<std::dec<<"\n";}
   // GD-ROM FADs are absolute sector numbers; disc.json stores file LBAs,
   // which are 150 sectors earlier than the values delivered by the game.
   const u32 module=(request.fad==119124u)?1u:(request.fad==258003u)?2u:(request.fad==349238u)?3u:(request.fad==422138u)?4u:0u;
   if(module&&module!=activeModule){pendingModule=module;nativeContext->fault=13;std::cout<<"Round module ready="<<module<<"; pausing native AOT for module switch\n";}
   pendingDiscReads.erase(read);
  }
 }
 return 1;
}
static void nativeQueueWrite(u32 address){
 pushContext();auto *ctx=&p_sh4rcb->cntx;ctx->doSqWrite(address,ctx);pullContext();queueWrites++;
}
static void clockBoundary(u32 opcode,u32 slot,u32 count){
 auto *ctx=&p_sh4rcb->cntx;
 if(ctx->cycle_counter<=0){pushContext();do{ctx->cycle_counter+=SH4_TIMESLICE;if(nativeInput)nativeInput->update(sh4_sched_now64(),false);UpdateSystem_INTC();ticks++;}while(ctx->cycle_counter<=0);pullContext();}
 else {
  auto changesSR=[](u32 word){return word==0x002bu||(word&0xf0ffu)==0x400eu||(word&0xf0ffu)==0x4007u;};
  if(changesSR(opcode)||(count==2&&changesSR(slot))){pushContext();UpdateINTC();pullContext();}
 }
}
static void retire(u32 opcode,u32 slot,u32 count){
 nativeCycles.executeCycles((u16)opcode);if(count==2)nativeCycles.executeCycles((u16)slot);
 clockBoundary(opcode,slot,count);
}
static void configureNativeFastClock(void * library){
 auto attach=(void(*)(NativeFastClock*))SDL_LoadFunction(library,"sc5_set_fast_clock");
 if(attach){
  const bool enabled=std::getenv("SC5_DISABLE_FAST_CLOCK")==nullptr;
  attach(enabled?nativeCycles.fastClock(clockBoundary):nullptr);
  std::cout<<"Native inline cycle accounting="<<(enabled?"enabled":"disabled")<<"\n";
 }
}
static void syncContext(){
 auto *ctx=&p_sh4rcb->cntx;ctx->pc=nativeContext->pc;ctx->sr.setFull((nativeContext->sr&~1u)|nativeContext->t);
}
static u32 readDevice(u32 address,u32 size){
 syncContext();busReads++;
 if(clockActive)nativeCycles.addReadAccessCycles(address,size);
 switch(size){case 1:return addrspace::read8(address);case 2:return addrspace::read16(address);case 4:return addrspace::read32(address);default:throw std::runtime_error("Invalid bus width");}
}
static void writeDevice(u32 address,u32 value,u32 size){
 syncContext();busWrites++;
 if(clockActive)nativeCycles.addWriteAccessCycles(address,size);
 switch(size){case 1:addrspace::write8(address,value);break;case 2:addrspace::write16(address,value);break;case 4:addrspace::write32(address,value);break;default:throw std::runtime_error("Invalid bus width");}
}


static void nativeRequire(bool condition,const char *message){if(!condition)throw std::runtime_error(message);}
static u32 identifyLoadedRound(const char *imagePath){
 std::string directory=imagePath;const auto separator=directory.find_last_of("/\\");directory=separator==std::string::npos?"":directory.substr(0,separator+1);
 const u8 *loaded=GetMemPtr(0x8c270000,0x80000);if(!loaded)return 0;
 for(u32 module=1;module<=4;module++){
  std::ifstream input(directory+"ROUND"+std::to_string(module)+".BIN",std::ios::binary);std::vector<u8> roundBytes((std::istreambuf_iterator<char>(input)),{});
  if(roundBytes.size()==0x80000&&memcmp(loaded,roundBytes.data(),roundBytes.size())==0)return module;
 }
 return 0;
}
struct NativeRunResult{u32 pc,fault;u64 retired,cycles;u32 frames;};
struct NativeCheckpointHeader{u32 magic;State state;int32_t cycleCounter;};
struct NativeFullCheckpointHeader{u32 magic;u32 module;u64 serializedSize;State state;};
static void saveNativeFullCheckpoint(const char *checkpointPath,u32 module){
 pushContext();Serializer measure;dc_serialize(measure);std::vector<u8> serialized(measure.size());Serializer writer(serialized.data(),serialized.size());dc_serialize(writer);serialized.resize(writer.size());
 NativeFullCheckpointHeader saved{0x53433545u,module,serialized.size(),*nativeContext};const auto cycleState=nativeCycles.snapshot();std::string temporary=std::string(checkpointPath)+".tmp";
 {std::ofstream checkpoint(temporary,std::ios::binary);checkpoint.write(reinterpret_cast<const char*>(&saved),sizeof(saved));checkpoint.write(reinterpret_cast<const char*>(&cycleState),sizeof(cycleState));checkpoint.write(reinterpret_cast<const char*>(serialized.data()),serialized.size());nativeRequire(bool(checkpoint.good()),"checkpoint write");}
 nativeRequire(bool(nativeReplaceFile(temporary.c_str(),checkpointPath)),"checkpoint atomic replace");
 std::cout<<"Saved full native checkpoint="<<checkpointPath<<" module="<<module<<" bytes="<<serialized.size()<<"\n";
}
static NativeRunResult runNativeDeviceHarness(void (*afterHalt)()=nullptr){
 const char *dllPath=std::getenv("SC5_NATIVE_DLL");const char *imagePath=std::getenv("SC5_IMAGE");
 nativeRequire((dllPath)!=(nullptr),"ASSERT_NE dllPath");nativeRequire((imagePath)!=(nullptr),"ASSERT_NE imagePath");
 std::ifstream input(imagePath,std::ios::binary);std::vector<unsigned char> image((std::istreambuf_iterator<char>(input)),{});nativeRequire((image.size())==(0x260000u),"ASSERT_EQ image.size()");
 void * library=SDL_LoadObject(dllPath);nativeRequire((library)!=(nullptr),"ASSERT_NE library");
 std::vector<void *> moduleLibraries{library};
 struct Cleanup{std::vector<void *> &libraries;~Cleanup(){clockActive=false;os_InputUpdateOverride=nullptr;nativeInput=nullptr;nativeContext=nullptr;nativeState=nullptr;for(auto it=libraries.rbegin();it!=libraries.rend();++it)SDL_UnloadObject(*it);}} cleanup{moduleLibraries};
 void * preloadedModules[5]{};
 // Map the existing native modules before audio starts, avoiding DLL loading
 // stalls when the original game replaces its round executable during play.
 if(const char *directory=std::getenv("SC5_MODULE_DLL_DIR")){
  if(!std::getenv("SC5_LAZY_MODULES")){
   const uint64_t started=nativeMilliseconds();u32 count=0;
   for(u32 module=1;module<=4;module++){
    const std::string path=std::string(directory)+"/native-diff-round"+std::to_string(module)+nativeLibrarySuffix();
    if(!nativePathExists(path.c_str()))continue;
    void * loaded=SDL_LoadObject(path.c_str());nativeRequire(loaded,"native round module preload");
    preloadedModules[module]=loaded;moduleLibraries.push_back(loaded);count++;
   }
   std::cout<<"Preloaded native AOT modules="<<count<<" load_ms="<<(nativeMilliseconds()-started)<<"\n";
  }
 }
 auto reset=(void(*)(const unsigned char*))SDL_LoadFunction(library,"sc5_reset");
 auto run=(void(*)(u32))SDL_LoadFunction(library,"sc5_run");
 auto runChunk=(u32(*)(u32))SDL_LoadFunction(library,"sc5_run_chunk");
 nativeState=(u32(*)(u32))SDL_LoadFunction(library,"sc5_state");
 auto useBus=(void(*)(unsigned char*,u32(*)(u32,u32),void(*)(u32,u32,u32)))SDL_LoadFunction(library,"sc5_use_bus");
 auto attachBus=(void(*)(unsigned char*,u32(*)(u32,u32),void(*)(u32,u32,u32)))SDL_LoadFunction(library,"sc5_attach_bus");
 auto context=(State*(*)())SDL_LoadFunction(library,"sc5_context");auto setRetire=(void(*)(void(*)(u32,u32,u32)))SDL_LoadFunction(library,"sc5_set_retire");
 auto setService=(void(*)(int(*)(u32)))SDL_LoadFunction(library,"sc5_set_service");
 auto setQueueWrite=(void(*)(void(*)(u32)))SDL_LoadFunction(library,"sc5_set_queue_write");
 nativeRequire(bool(reset&&run&&nativeState&&useBus&&attachBus&&context&&setRetire),"reset&&run&&nativeState&&useBus&&attachBus&&context&&setRetire");
 nativeRequire(bool(addrspace::reserve()),"addrspace::reserve()");emu.init();mem_map_default();emu.dc_reset(true);
 config::AudioVolume.set(nativeNumber("SC5_VOLUME",100,0,100));
 if(config::AudioVolume.get()==100)config::AudioVolume.logarithmic_volume_scale=1.0f;
 else config::AudioVolume.calcDbPower();
 config::AudioBufferSize=nativeNumber("SC5_AUDIO_BUFFER_MS",64,32,128)*441/10;
 const char *discPath=std::getenv("SC5_GDI");
 const char *framePath=std::getenv("SC5_FRAME_OUTPUT");
 std::unique_ptr<NativeRenderSurface> surface;
 if(framePath||discPath)surface=std::make_unique<NativeRenderSurface>();
 if(discPath){
  const char *dataPath=std::getenv("SC5_RUNTIME_DATA");nativeRequire((dataPath)!=(nullptr),"ASSERT_NE dataPath");
  set_user_config_dir(dataPath);set_user_data_dir(dataPath);
  if(nativeNumber("SC5_TEXTURE_PACKS",0,0,1)||std::getenv("SC5_DUMP_TEXTURES")){
   settings.content.gameId="MK-51051";
   config::TexturePath=std::vector<std::string>{std::string(dataPath)+"mods"};
   config::CustomTextures=nativeNumber("SC5_TEXTURE_PACKS",0,0,1)!=0;config::PreloadCustomTextures=true;
   config::DumpTextures=std::getenv("SC5_DUMP_TEXTURES")!=nullptr;
   config::TextureDumpPath=std::string(dataPath)+"texture-dumps";
   custom_texture.init();
  }
  std::cout<<"Mounting read-only GDI"<<std::endl;
  nativeRequire(bool(gdr::initDrive(discPath)),"gdr::initDrive(discPath)");std::cout<<"Initializing native BIOS services"<<std::endl;
  nativeRequire(bool(nvmem::loadHle()),"nvmem::loadHle()");std::cout<<"Disc services ready"<<std::endl;
  mcfg_DestroyDevices();
  for(unsigned int port=0;port<4;port++){
   config::MapleMainDevices[port]=port==0?MDT_SegaController:MDT_None;
   config::MapleExpansionDevices[port][0]=port==0?MDT_SegaVMU:MDT_None;
   config::MapleExpansionDevices[port][1]=MDT_None;
  }
  mcfg_CreateDevices();std::cout<<"Controller and private VMU connected on port A"<<std::endl;
 }
 reset(image.data());useBus(GetMemPtr(0x8c000000,0x1000000),readDevice,writeDevice);busReads=busWrites=0;
 // Optional reproducible test clock. Normal launches retain the device RTC.
 if(const char *rtcText=std::getenv("SC5_FIXED_RTC")){
  const u64 requested=std::stoull(rtcText,nullptr,0);nativeRequire(requested<=0xffffffffu,"Fixed RTC exceeds 32 bits");u32 rtc=static_cast<u32>(requested);
  addrspace::write32(0xa0710008,1);addrspace::write32(0xa0710004,rtc&0xffff);addrspace::write32(0xa0710000,rtc>>16);
  nativeRequire(((addrspace::read32(0xa0710000)<<16)|addrspace::read32(0xa0710004))==rtc,"Fixed RTC register verification failed");
  std::cout<<"Fixed diagnostic RTC="<<rtc<<"\n";
 }
 nativeContext=context();nativeCycles.init(&p_sh4rcb->cntx);nativeCycles.reset();ticks=0;clockActive=true;setRetire(retire);configureNativeFastClock(library);
 if(std::getenv("SC5_VALIDATE_CYCLES"))validateNativeCycleModel();
 pendingModule=0;activeModule=1;u32 checkpointModule=1;
 if(const char *checkpointPath=std::getenv("SC5_CHECKPOINT_LOAD")){
  std::ifstream checkpoint(checkpointPath,std::ios::binary);NativeCheckpointHeader saved{};u32 magic=0;
  nativeRequire(bool(checkpoint.read(reinterpret_cast<char*>(&magic),sizeof(magic))),"checkpoint state read");checkpoint.seekg(0);
  if(magic==0x53433544u||magic==0x53433545u){
   NativeFullCheckpointHeader full{};nativeRequire(bool(checkpoint.read(reinterpret_cast<char*>(&full),sizeof(full))),"full checkpoint header read");
   nativeRequire(full.module>=1&&full.module<=4,"full checkpoint module");nativeRequire(full.serializedSize>0&&full.serializedSize<=0x8000000u,"full checkpoint size");
   NativeCycleSnapshot cycleState{CO,0};
   if(magic==0x53433545u)nativeRequire(bool(checkpoint.read(reinterpret_cast<char*>(&cycleState),sizeof(cycleState))),"checkpoint cycle state read");
   std::vector<u8> serialized(static_cast<size_t>(full.serializedSize));checkpoint.read(reinterpret_cast<char*>(serialized.data()),serialized.size());nativeRequire(bool(checkpoint.good()),"full checkpoint data read");
   Deserializer reader(serialized.data(),serialized.size());dc_deserialize(reader);nativeRequire(reader.size()==serialized.size(),"full checkpoint size mismatch");
   // The serialized SH4 context includes a host store-queue function pointer.
   // Recompute it from restored MMU/QACR state after a rebuild or ASLR change.
   setSqwHandler();nativeCycles.restore(cycleState);
   *nativeContext=full.state;checkpointModule=full.module;pushContext();
  } else {
   if(magic==0x53433543u)nativeRequire(bool(checkpoint.read(reinterpret_cast<char*>(&saved),sizeof(saved))),"checkpoint header read");
   else {nativeRequire(bool(checkpoint.read(reinterpret_cast<char*>(&saved.state),sizeof(saved.state))),"legacy checkpoint state read");saved.cycleCounter=0;}
   checkpoint.read(reinterpret_cast<char*>(GetMemPtr(0x8c000000,0x1000000)),0x1000000);
   nativeRequire(bool(checkpoint.good()),"checkpoint RAM read");*nativeContext=saved.state;pushContext();p_sh4rcb->cntx.cycle_counter=saved.cycleCounter;
  }
  // A checkpoint can be captured at an AOT coverage halt.  The halt is a
  // host diagnostic state, so clear it before resuming the saved guest PC.
  nativeContext->fault=0;
  std::cout<<"Loaded native checkpoint="<<checkpointPath<<" module="<<checkpointModule<<" PC="<<std::hex<<nativeContext->pc<<std::dec<<"\n";
 }
 serviceCalls=0;queueWrites=0;discCommands.clear();pendingDiscReads.clear();if(setQueueWrite)setQueueWrite(nativeQueueWrite);
 discReadLogLimit=std::getenv("SC5_LOG_DISC_READS")?std::min(10000ul,std::stoul(std::getenv("SC5_LOG_DISC_READS"))):24;
 if(discPath){
  nativeRequire(bool(setService),"setService");setService(nativeService);
  const u32 vectors[][2]={{0x8c0000b4,0x8c001002},{0x8c0000b8,0x8c001004},{0x8c0000bc,0x8c001006},{0x8c0000c0,0x8c0010f0},{0x8c0000e0,0x8c001008}};
  for(auto &vector:vectors)addrspace::write32(vector[0],vector[1]);
 }
 // No reference interpreter Step/Run calls: the AOT DLL drives the device bus.
 std::unique_ptr<NativeAudioSession> audio;
 const char *budgetText=std::getenv("SC5_INSTRUCTION_BUDGET");
 const u64 requestedBudget=budgetText?std::stoull(budgetText):50000000u;
 nativeRequire(requestedBudget==0 || (requestedBudget>5095138u && requestedBudget<=1000000000000ull),"budget must be 0 (unlimited) or 5095139..1000000000000");
 const u64 budget=requestedBudget?requestedBudget:std::numeric_limits<u64>::max();
 nativeRequire(bool(runChunk),"runChunk");u64 startTicks=sh4_sched_now64(),retired=0;
 const char *checkpointSavePath=std::getenv("SC5_CHECKPOINT_SAVE");u64 checkpointInterval=0,nextCheckpoint=0;
 if(const char *intervalText=std::getenv("SC5_CHECKPOINT_INTERVAL")){checkpointInterval=std::stoull(intervalText);nativeRequire(checkpointInterval>=10000000u,"checkpoint interval too small");nextCheckpoint=checkpointInterval;}
 auto inputHost=std::make_unique<NativeInput>(startTicks);nativeInput=inputHost.get();
 os_InputUpdateOverride=pollNativeInput;
 const u32 startFrame=FrameCount;
 u64 presentedFrames=0;
 const auto wallStart=std::chrono::steady_clock::now();
 struct HostTiming{u64 begin,end,deviceBegin,deviceEnd;u32 frames;u64 runEnd;};
 std::vector<HostTiming> hostTiming;
 const char *hostTimingPath=std::getenv("SC5_HOST_TIMING_CSV");
 if(hostTimingPath)hostTiming.reserve(1000000);
 u32 chunkLimit=100000;
 if(const char *value=std::getenv("SC5_CHUNK_INSTRUCTIONS"))chunkLimit=std::clamp<u32>(std::stoul(value),10000,1000000);
 const char *stopPath=std::getenv("SC5_STOP_FILE");uint64_t lastStopPoll=nativeMilliseconds();
 auto switchModule=[&](u32 module){
  const char *directory=std::getenv("SC5_MODULE_DLL_DIR");nativeRequire(directory,"SC5_MODULE_DLL_DIR");
  nativeRequire(module>=1&&module<=4,"valid round module");
  void * next=preloadedModules[module];
  if(!next){std::string path=std::string(directory)+"/native-diff-round"+std::to_string(module)+nativeLibrarySuffix();next=SDL_LoadObject(path.c_str());nativeRequire(next,"round module DLL");preloadedModules[module]=next;moduleLibraries.push_back(next);}
  auto nextAttach=(void(*)(unsigned char*,u32(*)(u32,u32),void(*)(u32,u32,u32)))SDL_LoadFunction(next,"sc5_attach_bus");
  auto nextRunChunk=(u32(*)(u32))SDL_LoadFunction(next,"sc5_run_chunk");auto nextState=(u32(*)(u32))SDL_LoadFunction(next,"sc5_state");auto nextContext=(State*(*)())SDL_LoadFunction(next,"sc5_context");
  auto nextSetRetire=(void(*)(void(*)(u32,u32,u32)))SDL_LoadFunction(next,"sc5_set_retire");auto nextSetService=(void(*)(int(*)(u32)))SDL_LoadFunction(next,"sc5_set_service");auto nextSetQueue=(void(*)(void(*)(u32)))SDL_LoadFunction(next,"sc5_set_queue_write");
  nativeRequire(bool(nextAttach&&nextRunChunk&&nextState&&nextContext&&nextSetRetire&&nextSetService),"round module exports");
  State snapshot=*nativeContext;snapshot.fault=0;nextAttach(GetMemPtr(0x8c000000,0x1000000),readDevice,writeDevice);*nextContext()=snapshot;
  nextSetRetire(retire);configureNativeFastClock(next);nextSetService(nativeService);if(nextSetQueue)nextSetQueue(nativeQueueWrite);
  library=next;nativeState=nextState;nativeContext=nextContext();runChunk=nextRunChunk;setRetire=nextSetRetire;setService=nextSetService;setQueueWrite=nextSetQueue;activeModule=module;pendingModule=0;
  std::cout<<"Switched native AOT to ROUND"<<module<<" module\n";
 };
 if(checkpointModule!=1)switchModule(checkpointModule);
 nativeDispatchTrace.configure();
 nativeRhythmCalibration.configure();
 NativeModSession mods;
 if(std::getenv("SC5_AUDIO_OUTPUT")||std::getenv("SC5_PLAY_AUDIO"))audio=std::make_unique<NativeAudioSession>();
 while(retired<budget && !nativeState(20) && !inputHost->quit){
  const u32 frameBeforeChunk=FrameCount;
  const u64 traceBegin=hostTimingPath?SDL_GetPerformanceCounter():0,deviceBefore=hostTimingPath?sh4_sched_now64():0;
  u32 amount=static_cast<u32>(std::min<u64>(budget-retired,chunkLimit));u32 completed=runChunk(amount);retired+=completed;
  if(FrameCount!=frameBeforeChunk)mods.frame(activeModule,FrameCount-startFrame,sh4_sched_now64()-startTicks);
  const u64 traceRunEnd=hostTimingPath?SDL_GetPerformanceCounter():0;
  // The standalone host has no ImGui driver to swap the rendered back buffer.
  if(surface&&FrameCount!=frameBeforeChunk&&surface->present())presentedFrames++;
  if(hostTimingPath&&hostTiming.size()<1000000)hostTiming.push_back({traceBegin,SDL_GetPerformanceCounter(),deviceBefore,sh4_sched_now64(),FrameCount-frameBeforeChunk,traceRunEnd});
  if(pendingModule){switchModule(pendingModule);if(checkpointSavePath)saveNativeFullCheckpoint(checkpointSavePath,activeModule);continue;}
  if(nativeState(20)==7&&nativeState(16)>=0x8c270000u&&nativeState(16)<0x8c2f0000u){
   const u32 loadedModule=identifyLoadedRound(imagePath);
   if(loadedModule&&loadedModule!=activeModule){std::cout<<"Detected loaded ROUND"<<loadedModule<<" image after code-verification stop; recovering module switch\n";nativeContext->fault=0;switchModule(loadedModule);if(checkpointSavePath)saveNativeFullCheckpoint(checkpointSavePath,activeModule);continue;}
  }
  if(checkpointSavePath&&checkpointInterval&&retired>=nextCheckpoint){
   saveNativeFullCheckpoint(checkpointSavePath,activeModule);
   std::cout<<"Native progress module="<<activeModule<<" PC="<<std::hex<<nativeState(16)<<" fault="<<nativeState(20)<<std::dec
    <<" retired="<<retired<<" frames="<<(FrameCount-startFrame)<<" presented_frames="<<presentedFrames
    <<" device_seconds="<<((sh4_sched_now64()-startTicks)/200000000.0)
    <<" wall_seconds="<<std::chrono::duration<double>(std::chrono::steady_clock::now()-wallStart).count()<<"\n";
   if(surface&&framePath)surface->capture(framePath);
   do{nextCheckpoint+=checkpointInterval;}while(nextCheckpoint<=retired);
  }
  if(completed==0)break;
  if(surface){surface->pump();inputHost->events();}
  if(stopPath&&nativeMilliseconds()-lastStopPoll>=100){
   lastStopPoll=nativeMilliseconds();
   if(nativePathExists(stopPath)){std::cout<<"Native graceful stop requested by file="<<stopPath<<"\n";break;}
  }
 }
 nativeDispatchTrace.finish(startTicks);
 std::cout<<"Native rhythm calibration applications="<<nativeRhythmCalibration.count()<<"\n";
 const double wallSeconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-wallStart).count();
 clockActive=false;
 os_InputUpdateOverride=nullptr;nativeInput=nullptr;inputHost.reset();
 audio.reset(); // Reference-only analysis below must never enter the native WAV.
 if(hostTimingPath){
  std::ofstream out(hostTimingPath);out<<"begin_qpc,end_qpc,device_begin,device_end,frames,frequency,run_end_qpc\n";
  for(const auto &entry:hostTiming)out<<entry.begin<<','<<entry.end<<','<<entry.deviceBegin<<','<<entry.deviceEnd<<','<<entry.frames<<','<<SDL_GetPerformanceFrequency()<<','<<entry.runEnd<<'\n';
 }
 if(surface&&framePath)std::cout<<"Native frame available="<<surface->capture(framePath)<<"\n";
 if(const char *dumpPath=std::getenv("SC5_RAM_DUMP")){
  std::ofstream dump(dumpPath,std::ios::binary);dump.write(reinterpret_cast<const char*>(GetMemPtr(0x8c000000,0x1000000)),0x1000000);nativeRequire(bool(dump.good()),"dump.good()");
 }
 if(checkpointSavePath)saveNativeFullCheckpoint(checkpointSavePath,activeModule);
 std::cout<<std::hex<<"Native bus halt PC="<<nativeState(16)<<" fault="<<nativeState(20)<<std::dec<<" retired="<<retired<<" reads="<<busReads<<" writes="<<busWrites<<"\n";
 
 std::cout<<"Native renderer frame count="<<(FrameCount-startFrame)<<" (content not automatically validated)\n";
 std::cout<<"Native presented frames="<<presentedFrames<<" average_fps="<<(wallSeconds>0?presentedFrames/wallSeconds:0)<<"\n";
 
 std::cout<<"Device scheduler ticks="<<ticks<<"\n";
 std::cout<<"Device clock cycles elapsed="<<(sh4_sched_now64()-startTicks)<<" (nominal 200 MHz; timing accuracy unverified)\n";
 std::cout<<"Native execution wall seconds="<<wallSeconds<<" nominal device seconds="<<((sh4_sched_now64()-startTicks)/200000000.0)<<" (includes requested audio pacing)\n";
 std::cout<<"Native BIOS service calls="<<serviceCalls<<" mounted disc="<<(discPath?discPath:"none")<<"\n";
 for(auto &entry:discCommands)std::cout<<"GD command "<<entry.first<<" requests="<<entry.second<<"\n";
 std::cout<<"Native store-queue transfers="<<queueWrites<<"\n";
 for(unsigned int j=0;j<16;j++)std::cout<<"r"<<j<<"="<<std::hex<<nativeState(j)<<std::dec<<" ";std::cout<<"\n";
 std::cout<<std::hex<<"SR="<<nativeState(18)<<" FPSCR="<<nativeContext->fpscr<<" SPC="<<nativeContext->spc<<" SSR="<<nativeContext->ssr<<"\n";
 for(unsigned int j=0;j<16;j++)std::cout<<"fr"<<j<<"="<<nativeContext->fr[j]<<" ";std::cout<<std::dec<<"\n";
 NativeRunResult result{nativeState(16),nativeState(20),retired,sh4_sched_now64()-startTicks,FrameCount-startFrame};
 if(afterHalt)afterHalt();
 return result;
}

