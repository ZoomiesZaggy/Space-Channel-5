// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#ifdef _WIN32
#include <windows.h>
#endif
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <vector>

// Keep the native execution thread on the larger shared cache when Windows
// exposes substantially asymmetric L3 caches. Other threads remain unrestricted.
// This does not change system power settings or the caller's process affinity.
class NativeCpuPlacement {
#ifdef _WIN32
 DWORD_PTR previous=0;
#endif
public:
 NativeCpuPlacement(){
#ifdef _WIN32
  const char *mode=std::getenv("SC5_CPU_PLACEMENT");
  if(mode && std::strcmp(mode,"system")==0)return;
  DWORD bytes=0;GetLogicalProcessorInformation(nullptr,&bytes);
  if(!bytes || bytes%sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION))return;
  std::vector<SYSTEM_LOGICAL_PROCESSOR_INFORMATION> info(bytes/sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION));
  if(!GetLogicalProcessorInformation(info.data(),&bytes))return;
  DWORD largest=0,smallest=std::numeric_limits<DWORD>::max();DWORD_PTR selected=0;
  for(const auto &entry:info)if(entry.Relationship==RelationCache && entry.Cache.Level==3 && entry.Cache.Size){
   smallest=std::min(smallest,entry.Cache.Size);
   if(entry.Cache.Size>largest){largest=entry.Cache.Size;selected=entry.ProcessorMask;}
   else if(entry.Cache.Size==largest)selected|=entry.ProcessorMask;
  }
  if(!largest || static_cast<unsigned long long>(largest)<2ull*smallest)return;
  DWORD_PTR allowed=0,system=0;
  if(!GetProcessAffinityMask(GetCurrentProcess(),&allowed,&system))return;
  selected&=allowed;if(!selected)return;
  previous=SetThreadAffinityMask(GetCurrentThread(),selected);
  if(previous)std::cout<<"Native CPU placement: preferred L3="<<(largest/(1024*1024))
    <<" MiB logical_mask="<<std::hex<<selected<<std::dec<<"\n";
#endif
 }
 ~NativeCpuPlacement(){
#ifdef _WIN32
 if(previous)SetThreadAffinityMask(GetCurrentThread(),previous);
#endif
 }
};
