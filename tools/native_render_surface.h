// SPDX-License-Identifier: GPL-2.0-or-later
// Optional hidden rendering surface for the native CPU/device integration test.
#pragma once
#include "wsi/gl_context.h"
#include "hw/pvr/Renderer_if.h"
#include "ui/imgui_driver.h"
#include "rend/TexCache.h"
#include "rend/gles/gles.h"
#include <windows.h>
#include <SDL.h>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <algorithm>

class NativeRenderSurface final : public GLGraphicsContext {
 SDL_Window *surface=nullptr;
 SDL_GLContext context=nullptr;
 PVOID textureWriteHandler=nullptr;
 Uint64 firstPresent=0,lastPresent=0;
 std::vector<double> frameIntervals;
 static LONG WINAPI textureWriteFault(EXCEPTION_POINTERS *exception){
  auto *record=exception->ExceptionRecord;
  if(record->ExceptionCode==EXCEPTION_ACCESS_VIOLATION && record->NumberParameters>=2 && record->ExceptionInformation[0]==1 &&
     VramLockedWrite(reinterpret_cast<u8*>(record->ExceptionInformation[1])))return EXCEPTION_CONTINUE_EXECUTION;
  return EXCEPTION_CONTINUE_SEARCH;
 }
public:
 NativeRenderSurface():GLGraphicsContext(nullptr,nullptr){
  std::cout<<"Render surface: SDL initialization"<<std::endl;
  if(SDL_InitSubSystem(SDL_INIT_VIDEO)!=0)throw std::runtime_error(SDL_GetError());
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION,3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION,3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK,SDL_GL_CONTEXT_PROFILE_CORE);
  SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER,1);
  surface=SDL_CreateWindow("Space Channel 5 native development",SDL_WINDOWPOS_UNDEFINED,SDL_WINDOWPOS_UNDEFINED,640,480,SDL_WINDOW_OPENGL|(std::getenv("SC5_VISIBLE")?SDL_WINDOW_SHOWN:SDL_WINDOW_HIDDEN));
  if(!surface)throw std::runtime_error(SDL_GetError());
  window=surface;context=SDL_GL_CreateContext(surface);
  if(!context)throw std::runtime_error(SDL_GetError());
  std::cout<<"Render surface: OpenGL context created"<<std::endl;
  if(!gladLoadGL((GLADloadfunc)SDL_GL_GetProcAddress)||!GLAD_GL_VERSION_3_0)throw std::runtime_error("OpenGL 3 required");
  SDL_GL_SetSwapInterval(0);settings.display.width=640;settings.display.height=480;
  // No emulator UI: only the GL capabilities and native game renderer are needed.
  findGLVersion();
  config::RendererType=RenderType::OpenGL;config::ThreadedRendering=false;
  std::cout<<"Render surface: PVR renderer initialization"<<std::endl;
  if(!rend_init_renderer())throw std::runtime_error("Native device renderer initialization failed");
  if(std::getenv("SC5_QUAD_PRESENT"))gl.bogusBlitFramebuffer=true;
  // Texture caching protects VRAM pages. Handle only writes to those pages;
  // unrelated access violations remain real faults, with no CPU/JIT fallback.
  textureWriteHandler=AddVectoredExceptionHandler(1,textureWriteFault);
  if(!textureWriteHandler)throw std::runtime_error("Texture write tracking initialization failed");
  std::cout<<"Render surface: ready"<<std::endl;
 }
 ~NativeRenderSurface(){
  if(!frameIntervals.empty()){
   std::sort(frameIntervals.begin(),frameIntervals.end());
   const auto n=frameIntervals.size();size_t slow=0;
   for(double ms:frameIntervals)if(ms>50.0)slow++;
   std::cout<<"Native frame pacing warmup_ms=5000 samples="<<n<<" p50_ms="<<frameIntervals[(n-1)/2]
     <<" p95_ms="<<frameIntervals[(n-1)*95/100]<<" p99_ms="<<frameIntervals[(n-1)*99/100]
     <<" max_ms="<<frameIntervals.back()<<" over_50_ms="<<slow<<"\n";
  }
  rend_term_renderer();
  if(textureWriteHandler)RemoveVectoredExceptionHandler(textureWriteHandler);
  if(context)SDL_GL_DeleteContext(context);if(surface)SDL_DestroyWindow(surface);
  SDL_QuitSubSystem(SDL_INIT_VIDEO);
 }
 void swap() override {SDL_GL_SwapWindow(surface);}
 bool present(){
  SDL_GL_GetDrawableSize(surface,&settings.display.width,&settings.display.height);
  GLint previousDraw=0,previousRead=0;
  glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&previousDraw);glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,&previousRead);
  glBindFramebuffer(GL_FRAMEBUFFER,0);
  const bool available=renderer->RenderLastFrame();
  if(std::getenv("SC5_LOG_PRESENT")){
   static unsigned samples=0;
   if(samples++<10){
    GLint drawBuffer=0,readBuffer=0;glGetIntegerv(GL_DRAW_BUFFER,&drawBuffer);glGetIntegerv(GL_READ_BUFFER,&readBuffer);
    std::vector<u8> probe(640*480*4);glReadPixels(0,0,640,480,GL_RGBA,GL_UNSIGNED_BYTE,probe.data());
    u64 sum=0;for(size_t j=0;j<probe.size();j+=4)sum+=probe[j]+probe[j+1]+probe[j+2];
    std::cout<<"Native present drawable="<<settings.display.width<<"x"<<settings.display.height<<" previous_draw="<<previousDraw<<" previous_read="<<previousRead<<" error="<<glGetError()<<" available="<<available<<" draw_buffer="<<drawBuffer<<" read_buffer="<<readBuffer<<" rgb_sum="<<sum<<"\n";
   }
  }
  if(available)swap();
  if(available && std::getenv("SC5_LOG_PACING")){
   const Uint64 now=SDL_GetPerformanceCounter(),frequency=SDL_GetPerformanceFrequency();
   if(!firstPresent)firstPresent=now;
   if(lastPresent && now-firstPresent>=frequency*5)frameIntervals.push_back((now-lastPresent)*1000.0/frequency);
   lastPresent=now;
  }
  if(std::getenv("SC5_LOG_PRESENT")){
   static unsigned frontSamples=0;
   if(frontSamples++<3){
    glReadBuffer(GL_FRONT);std::vector<u8> probe(640*480*4);glReadPixels(0,0,640,480,GL_RGBA,GL_UNSIGNED_BYTE,probe.data());
    u64 sum=0;for(size_t j=0;j<probe.size();j+=4)sum+=probe[j]+probe[j+1]+probe[j+2];
    glReadBuffer(GL_BACK);std::cout<<"Native front rgb_sum="<<sum<<" error="<<glGetError()<<" SDL_error="<<SDL_GetError()<<"\n";
   }
  }
  glBindFramebuffer(GL_DRAW_FRAMEBUFFER,previousDraw);glBindFramebuffer(GL_READ_FRAMEBUFFER,previousRead);
  return available;
 }
 static bool capture(const char *path){
  std::vector<u8> pixels;int width=0,height=0;
  if(!renderer->GetLastFrame(pixels,width,height))return false;
  if(width<=0||height<=0||pixels.size()!=static_cast<size_t>(width)*height*3)throw std::runtime_error("Unexpected frame dimensions");
  std::ofstream output(path,std::ios::binary);output<<"P6\n"<<width<<" "<<height<<"\n255\n";
  output.write(reinterpret_cast<const char*>(pixels.data()),pixels.size());
  if(!output.good())throw std::runtime_error("Frame write failed");
  std::cout<<"Renderer captured "<<width<<"x"<<height<<" RGB frame\n";return true;
 }
};
