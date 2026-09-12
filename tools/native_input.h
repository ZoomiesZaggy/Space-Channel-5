// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "input/gamepad_device.h"
#include <SDL.h>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <atomic>

class NativeInput {
 struct Pulse {u64 first,last;u32 buttons;};
 std::vector<Pulse> script;
 u32 keyboard=0;
 u32 pendingKeyboard=0;
 u32 textButtons=0;
 u64 latestTick=0,textUntil=0;
 u32 controllerButtons=0;
 u16 controllerLt=0,controllerRt=0;
 SDL_GameController *controller=nullptr;
 bool controllerEnabled=false;
 bool cheat100=false;
 u64 cheatStart=300000ull*200000ull;
 u64 cheatInterval=0;
 bool logInput=false;
 u32 lastLoggedButtons=0;
 u16 lastLoggedLt=0,lastLoggedRt=0;
 bool haveLoggedInput=false;
 u64 origin;
 u64 offset=0;
 size_t scriptCursor=0;
 std::thread latencyProbe;
 std::atomic<bool> stopProbe{false};
 std::atomic<u64> probeDownCounter{0};
 std::atomic<int> probePushResult{0};
 static u32 key(SDL_Keycode key){
  switch(key){case SDLK_RETURN:return DC_BTN_START;case SDLK_UP:return DC_DPAD_UP;case SDLK_DOWN:return DC_DPAD_DOWN;
   case SDLK_LEFT:return DC_DPAD_LEFT;case SDLK_RIGHT:return DC_DPAD_RIGHT;case SDLK_z:case SDLK_SPACE:return DC_BTN_A;case SDLK_x:case SDLK_BACKSPACE:return DC_BTN_B;
   case SDLK_a:return DC_BTN_X;case SDLK_s:return DC_BTN_Y;default:return 0;}
 }
 static u32 eventKey(const SDL_KeyboardEvent &event){
  switch(event.keysym.scancode){case SDL_SCANCODE_Z:return DC_BTN_A;case SDL_SCANCODE_X:return DC_BTN_B;
   case SDL_SCANCODE_A:return DC_BTN_X;case SDL_SCANCODE_S:return DC_BTN_Y;default:return key(event.keysym.sym);}
 }
public:
 bool quit=false;
 explicit NativeInput(u64 start):origin(start){
  kcode[0]=~0u;
  if(const char *offsetText=std::getenv("SC5_INPUT_OFFSET_MS"))offset=std::stoull(offsetText,nullptr,0)*200000ull;
  if(std::getenv("SC5_CHEAT_100")){
   cheat100=true;
   if(const char *startText=std::getenv("SC5_CHEAT_100_START_MS"))cheatStart=std::stoull(startText,nullptr,0)*200000ull;
   if(const char *intervalText=std::getenv("SC5_CHEAT_100_INTERVAL_MS"))cheatInterval=std::stoull(intervalText,nullptr,0)*200000ull;
  }
  logInput=std::getenv("SC5_LOG_INPUT")!=nullptr;
  if(std::getenv("SC5_VISIBLE")){
   if(SDL_InitSubSystem(SDL_INIT_GAMECONTROLLER)!=0)throw std::runtime_error(SDL_GetError());controllerEnabled=true;
   SDL_StartTextInput();
   if(logInput)std::cout<<"Native SDL joystick devices="<<SDL_NumJoysticks()<<"\n";
  }
  if(const char *path=std::getenv("SC5_INPUT_SCRIPT")){
   std::ifstream input(path);if(!input)throw std::runtime_error("Cannot open native input script");
    std::string line;while(std::getline(input,line)){
    if(line.empty()||line[0]=='#')continue;
    std::istringstream fields(line);std::string firstText,extra;u64 first,last;u32 buttons;
    if(!(fields>>firstText))throw std::runtime_error("Invalid native input pulse");
    if(firstText=="repeat"){
     u64 interval,width; if(!(fields>>first>>last>>interval>>width>>std::hex>>buttons)||(fields>>extra)||!interval||!width||first>=last||last>3600000||width>last-first||buttons>0xffffu)throw std::runtime_error("Invalid native input repeat");
     for(u64 start=first;start<last;start+=interval){u64 finish=std::min(start+width,last);script.push_back({start*200000ull,finish*200000ull,buttons});}
    }else{
     try{first=std::stoull(firstText);}catch(...){throw std::runtime_error("Invalid native input pulse");}
     if(!(fields>>last>>std::hex>>buttons)||(fields>>extra)||first>=last||last>3600000||buttons>0xffffu)throw std::runtime_error("Invalid native input pulse");
     script.push_back({first*200000ull,last*200000ull,buttons});
    }
   }
   std::stable_sort(script.begin(),script.end(),[](const Pulse &a,const Pulse &b){return a.first<b.first;});
   std::cout<<"Scripted controller pulses="<<script.size()<<" (milliseconds of nominal device time)\n";
  }
  // Opt-in diagnostic: asynchronous SDL key delivery, without OS input injection
  // or a physical-device latency claim. Normal play never creates this thread.
  if(const char *value=std::getenv("SC5_TEST_KEY_EVENT_MS")){
   const u64 delay=std::stoull(value);if(delay<100||delay>10000)throw std::runtime_error("Invalid latency probe delay");
   latencyProbe=std::thread([this,delay]{
    auto waitUntil=[this](u64 end){while(!stopProbe && SDL_GetTicks64()<end)SDL_Delay(1);return !stopProbe;};
    if(!waitUntil(SDL_GetTicks64()+delay))return;
    SDL_Event event{};event.type=SDL_KEYDOWN;event.key.state=SDL_PRESSED;event.key.keysym.sym=SDLK_DOWN;event.key.keysym.scancode=SDL_SCANCODE_DOWN;
    event.key.timestamp=SDL_GetTicks();probeDownCounter=SDL_GetPerformanceCounter();probePushResult=SDL_PushEvent(&event);
    if(!waitUntil(SDL_GetTicks64()+100))return;
    event.type=SDL_KEYUP;event.key.state=SDL_RELEASED;event.key.timestamp=SDL_GetTicks();SDL_PushEvent(&event);
   });
  }
 }
 ~NativeInput(){stopProbe=true;if(latencyProbe.joinable()){latencyProbe.join();std::cout<<"Native latency probe down_qpc="<<probeDownCounter<<" qpc_hz="<<SDL_GetPerformanceFrequency()<<" push_result="<<probePushResult<<"\n";}kcode[0]=~0u;joyx[0]=joyy[0]=joyrx[0]=joyry[0]=0;lt[0]=rt[0]=0;
  if(controller)SDL_GameControllerClose(controller);if(controllerEnabled){SDL_StopTextInput();SDL_QuitSubSystem(SDL_INIT_GAMECONTROLLER);}
 }
 void events(){
  SDL_Event event;while(SDL_PollEvent(&event)){
   if(event.type==SDL_QUIT)quit=true;
   else if(event.type==SDL_WINDOWEVENT&&event.window.event==SDL_WINDOWEVENT_FOCUS_LOST)keyboard=pendingKeyboard=textButtons=0;
   else if(event.type==SDL_KEYDOWN){keyboard|=eventKey(event.key);pendingKeyboard|=eventKey(event.key);if(logInput)std::cout<<"Native key down sym="<<event.key.keysym.sym<<" scan="<<event.key.keysym.scancode<<" mapped="<<eventKey(event.key)<<"\n";}
   else if(event.type==SDL_KEYUP)keyboard&=~eventKey(event.key);
   else if(event.type==SDL_TEXTINPUT&&event.text.text[0]&&!event.text.text[1]){
    const unsigned char character=static_cast<unsigned char>(event.text.text[0]);
    const u32 button=key(character>='A'&&character<='Z'?character+('a'-'A'):character);
    // Text injection has no key-up duration. Supply a short, bounded pulse
    // spanning the game's 30 Hz input sampling interval.
    // Physical key-down already supplies its own release timing. Only add a
    // text pulse when there is no corresponding held physical action key.
    if(!(keyboard&button)){textButtons|=button;textUntil=latestTick+60ull*200000ull;}
    if(logInput)std::cout<<"Native text input mapped="<<button<<"\n";
   }
  }
  controllerButtons=0;
  if(controller && !SDL_GameControllerGetAttached(controller)){SDL_GameControllerClose(controller);controller=nullptr;}
  if(controllerEnabled && !controller)for(int j=0;j<SDL_NumJoysticks();j++)if(SDL_IsGameController(j)){controller=SDL_GameControllerOpen(j);if(controller){if(logInput)std::cout<<"Native controller connected="<<SDL_GameControllerName(controller)<<"\n";break;}}
  if(controller){
   const std::pair<SDL_GameControllerButton,u32> buttons[]={{SDL_CONTROLLER_BUTTON_START,DC_BTN_START},{SDL_CONTROLLER_BUTTON_A,DC_BTN_A},{SDL_CONTROLLER_BUTTON_B,DC_BTN_B},
    {SDL_CONTROLLER_BUTTON_X,DC_BTN_X},{SDL_CONTROLLER_BUTTON_Y,DC_BTN_Y},{SDL_CONTROLLER_BUTTON_DPAD_UP,DC_DPAD_UP},{SDL_CONTROLLER_BUTTON_DPAD_DOWN,DC_DPAD_DOWN},
    {SDL_CONTROLLER_BUTTON_DPAD_LEFT,DC_DPAD_LEFT},{SDL_CONTROLLER_BUTTON_DPAD_RIGHT,DC_DPAD_RIGHT}};
   for(auto button:buttons)if(SDL_GameControllerGetButton(controller,button.first))controllerButtons|=button.second;
   joyx[0]=SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_LEFTX);joyy[0]=SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_LEFTY);
   joyrx[0]=SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_RIGHTX);joyry[0]=SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_RIGHTY);
   controllerLt=static_cast<u16>(std::max(0,static_cast<int>(SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_TRIGGERLEFT)))*2);
   controllerRt=static_cast<u16>(std::max(0,static_cast<int>(SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_TRIGGERRIGHT)))*2);
  }else {joyx[0]=joyy[0]=joyrx[0]=joyry[0]=0;controllerLt=controllerRt=0;}
 }
 void update(u64 now,bool controllerPoll=true){
  latestTick=now;if(now>=textUntil)textButtons=0;
  // SDL can deliver down and up together between Maple polls. Preserve the
  // press until the game actually samples it, not merely until a CPU tick.
  u32 pressed=keyboard|pendingKeyboard|textButtons|controllerButtons;
  if(controllerPoll)pendingKeyboard=0;
  lt[0]=controllerLt;rt[0]=controllerRt;u64 time=now-origin;
  time+=offset;
  // Pulses are parsed in time order.  Advance past expired entries once and
  // inspect only the small active window; long repeat scripts must not turn
  // every scheduler tick into an O(number-of-pulses) scan.
  while(scriptCursor<script.size()&&script[scriptCursor].last<=time)scriptCursor++;
  for(size_t j=scriptCursor;j<script.size()&&script[j].first<=time;j++)if(time<script[j].last)pressed|=script[j].buttons;
  if(cheat100){
   // Retail Dreamcast 100% assist: pause, hold L+R, then enter
   // Up, Left, A, Left, A, Down, Right, B, Right, B.
   // This path is opt-in for native progression diagnostics; ordinary
   // keyboard/gamepad input remains unchanged when SC5_CHEAT_100 is absent.
   const u64 tickPerMs=200000ull;
   u64 pauseStart=cheatStart;
   if(cheatInterval&&time>=cheatStart)pauseStart=cheatStart+((time-cheatStart)/cheatInterval)*cheatInterval;
   const u64 pauseEnd=pauseStart+4000ull*tickPerMs;
   if(time>=pauseStart&&time<pauseStart+200ull*tickPerMs)pressed|=DC_BTN_START;
   if(time>=pauseStart+300ull*tickPerMs&&time<pauseEnd){
    lt[0]=rt[0]=0xffff;
    static const u32 sequence[]={DC_DPAD_UP,DC_DPAD_LEFT,DC_BTN_A,DC_DPAD_LEFT,DC_BTN_A,DC_DPAD_DOWN,DC_DPAD_RIGHT,DC_BTN_B,DC_DPAD_RIGHT,DC_BTN_B};
    for(unsigned int index=0;index<10;index++){
     const u64 first=pauseStart+500ull*tickPerMs+static_cast<u64>(index)*260ull*tickPerMs;
     if(time>=first&&time<first+150ull*tickPerMs){pressed|=sequence[index];break;}
    }
   }
   if(time>=pauseStart+4500ull*tickPerMs&&time<pauseStart+4700ull*tickPerMs)pressed|=DC_BTN_START;
  }
  kcode[0]=~pressed;
  if(logInput&&(!haveLoggedInput||pressed!=lastLoggedButtons||lt[0]!=lastLoggedLt||rt[0]!=lastLoggedRt)){
   std::cout<<"Native input ms="<<(time/200000ull)<<" buttons="<<std::hex<<pressed<<" lt="<<lt[0]<<" rt="<<rt[0]<<std::dec
     <<" qpc="<<SDL_GetPerformanceCounter()<<" qpc_hz="<<SDL_GetPerformanceFrequency()<<" controller_poll="<<controllerPoll<<"\n";
   lastLoggedButtons=pressed;lastLoggedLt=lt[0];lastLoggedRt=rt[0];haveLoggedInput=true;
  }
 }
};
