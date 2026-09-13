// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <SDL.h>
#include <atomic>
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>

// A physical-measurement aid. Callback/submission timestamps are software
// boundaries, never presented as controller-to-speaker measurements.
inline int runNativeLatencyProbe(){
 struct Probe{
  std::atomic<Uint64> requested{0},callback{0};unsigned remaining=0;
  static void audio(void *data,Uint8 *bytes,int count){
   auto &p=*static_cast<Probe*>(data);SDL_memset(bytes,0,count);
   if(p.requested.exchange(0)){p.remaining=441;p.callback=SDL_GetPerformanceCounter();}
   auto *samples=reinterpret_cast<Sint16*>(bytes);
   for(int j=0;j<count/4&&p.remaining;j++,p.remaining--){
    auto value=static_cast<Sint16>(5000*std::sin((441-p.remaining)*6.283185307179586*1000/44100));
    samples[j*2]=samples[j*2+1]=value;
   }
  }
 } probe;
 if(SDL_InitSubSystem(SDL_INIT_VIDEO|SDL_INIT_AUDIO|SDL_INIT_GAMECONTROLLER))throw std::runtime_error(SDL_GetError());
 struct Quit{~Quit(){SDL_QuitSubSystem(SDL_INIT_VIDEO|SDL_INIT_AUDIO|SDL_INIT_GAMECONTROLLER);}} quit;
 SDL_Window *window=SDL_CreateWindow("Input/audio test: press a key or controller button; Esc closes",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,640,480,SDL_WINDOW_SHOWN);
 if(!window)throw std::runtime_error(SDL_GetError());
 struct Window{SDL_Window *p;~Window(){SDL_DestroyWindow(p);}} windowGuard{window};
 SDL_Renderer *renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED);
 if(!renderer)throw std::runtime_error(SDL_GetError());
 struct Renderer{SDL_Renderer *p;~Renderer(){SDL_DestroyRenderer(p);}} rendererGuard{renderer};
 SDL_AudioSpec wanted{},obtained{};wanted.freq=44100;wanted.format=AUDIO_S16SYS;wanted.channels=2;wanted.samples=256;wanted.callback=Probe::audio;wanted.userdata=&probe;
 SDL_AudioDeviceID audio=SDL_OpenAudioDevice(nullptr,0,&wanted,&obtained,0);
 if(!audio)throw std::runtime_error(SDL_GetError());
 struct Audio{SDL_AudioDeviceID id;~Audio(){SDL_CloseAudioDevice(id);}} audioGuard{audio};
 SDL_GameController *controller=nullptr;
 struct Controller{SDL_GameController *&p;~Controller(){if(p)SDL_GameControllerClose(p);}} controllerGuard{controller};
 std::cout<<"Input/audio measurement aid. A press flashes white and requests a short tone.\n"
  <<"Film the physical button, display and speaker to measure hardware delay.\n"
  <<"Logged values exclude physical input transport, display scanout and speaker output; this is not gameplay calibration.\n"
  <<"qpc_hz="<<SDL_GetPerformanceFrequency()<<" callback_frames="<<obtained.samples<<"\n";
 SDL_PauseAudioDevice(audio,0);bool running=true,white=false,drawBlack=true;Uint64 press=0,until=0;unsigned sample=0;
 const bool autoTest=std::getenv("SC5_LATENCY_AUTOTEST")!=nullptr;
 const auto testStart=SDL_GetTicks64();bool injected=false,observed=false;
 while(running){
  if(autoTest&&!injected&&SDL_GetTicks64()-testStart>=250){SDL_Event event{};event.type=SDL_KEYDOWN;event.key.keysym.sym=SDLK_SPACE;SDL_PushEvent(&event);injected=true;}
  if(autoTest&&SDL_GetTicks64()-testStart>=1500){if(!observed)throw std::runtime_error("Diagnostic callback test failed");running=false;}
  if(controller&&!SDL_GameControllerGetAttached(controller)){SDL_GameControllerClose(controller);controller=nullptr;}
  if(!controller)for(int j=0;j<SDL_NumJoysticks();j++)if(SDL_IsGameController(j)){controller=SDL_GameControllerOpen(j);if(controller)break;}
  SDL_Event event;while(SDL_PollEvent(&event)){
   if(event.type==SDL_QUIT||(event.type==SDL_KEYDOWN&&event.key.keysym.sym==SDLK_ESCAPE))running=false;
   else if(((event.type==SDL_KEYDOWN&&!event.key.repeat)||event.type==SDL_CONTROLLERBUTTONDOWN)&&!white&&!press){
    press=SDL_GetPerformanceCounter();probe.requested=press;white=true;until=SDL_GetTicks64()+250;
    SDL_SetRenderDrawColor(renderer,255,255,255,255);SDL_RenderClear(renderer);SDL_RenderPresent(renderer);
    std::cout<<"sample="<<++sample<<" input_qpc="<<press<<" present_return_qpc="<<SDL_GetPerformanceCounter()<<"\n";
   }
  }
  if(press){const auto callback=probe.callback.exchange(0);if(callback){std::cout<<"sample="<<sample<<" callback_qpc="<<callback<<" input_to_callback_ms="<<(callback-press)*1000.0/SDL_GetPerformanceFrequency()<<"\n";press=0;observed=true;}}
  if(white&&SDL_GetTicks64()>=until){white=false;drawBlack=true;}
  if(drawBlack&&!white){SDL_SetRenderDrawColor(renderer,0,0,0,255);SDL_RenderClear(renderer);SDL_RenderPresent(renderer);drawBlack=false;}
  SDL_Delay(1);
 }
 return 0;
}
