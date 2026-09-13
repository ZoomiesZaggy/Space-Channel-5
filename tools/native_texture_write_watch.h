// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <csignal>
#endif

// A single renderer owns the watch. Only protected texture writes are repaired;
// unrelated faults are forwarded to the previously installed handler.
class NativeTextureWriteWatch {
 using Callback=bool(*)(unsigned char*);
 inline static NativeTextureWriteWatch *active=nullptr;
 Callback callback;
#ifdef _WIN32
 PVOID handler=nullptr;
 static LONG WINAPI fault(EXCEPTION_POINTERS *exception){
  const auto *record=exception->ExceptionRecord;
  if(active && record->ExceptionCode==EXCEPTION_ACCESS_VIOLATION && record->NumberParameters>=2 &&
     record->ExceptionInformation[0]==1 && active->callback(reinterpret_cast<unsigned char*>(record->ExceptionInformation[1])))
   return EXCEPTION_CONTINUE_EXECUTION;
  return EXCEPTION_CONTINUE_SEARCH;
 }
#else
 struct sigaction previousSegv{},previousBus{};
 static void fault(int signal,siginfo_t *info,void *context){
  auto *watch=active;
  if(watch && info && info->si_code>0 && watch->callback(static_cast<unsigned char*>(info->si_addr)))return;
  const auto &previous=signal==SIGBUS?watch->previousBus:watch->previousSegv;
  if(previous.sa_handler==SIG_DFL || previous.sa_handler==SIG_IGN){
   // Ignoring a synchronous memory fault would retry the failing instruction.
   struct sigaction action{};action.sa_handler=SIG_DFL;sigemptyset(&action.sa_mask);
   sigaction(signal,&action,nullptr);raise(signal);return;
  }
  if(previous.sa_flags&SA_SIGINFO)previous.sa_sigaction(signal,info,context);
  else previous.sa_handler(signal);
 }
#endif
public:
 explicit NativeTextureWriteWatch(Callback onWrite):callback(onWrite){
  if(active || !callback)throw std::runtime_error("Texture write watch already active or missing callback");
  active=this;
#ifdef _WIN32
  handler=AddVectoredExceptionHandler(1,fault);
  if(!handler){active=nullptr;throw std::runtime_error("Texture write watch initialization failed");}
#else
  struct sigaction action{};action.sa_sigaction=fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);
  if(sigaction(SIGSEGV,&action,&previousSegv)){active=nullptr;throw std::runtime_error("SIGSEGV watch initialization failed");}
  if(sigaction(SIGBUS,&action,&previousBus)){
   sigaction(SIGSEGV,&previousSegv,nullptr);active=nullptr;throw std::runtime_error("SIGBUS watch initialization failed");
  }
#endif
 }
 NativeTextureWriteWatch(const NativeTextureWriteWatch&)=delete;
 NativeTextureWriteWatch &operator=(const NativeTextureWriteWatch&)=delete;
 ~NativeTextureWriteWatch(){
#ifdef _WIN32
  RemoveVectoredExceptionHandler(handler);
#else
  sigaction(SIGBUS,&previousBus,nullptr);sigaction(SIGSEGV,&previousSegv,nullptr);
#endif
  active=nullptr;
 }
};
