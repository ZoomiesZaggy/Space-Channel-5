// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <vector>
#include <string>
#include <fstream>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

// AOT dispatcher observations, not an instruction-by-instruction trace. Intra-
// page branches can run without re-entering this dispatcher.
class NativeDispatchTrace {
 struct Entry {u32 pc,pr;u64 cycles;u32 regs[16],fr[16];};
 std::vector<Entry> entries;
 std::string path;
 u32 first=0,last=0;
 u64 dropped=0;
 static u32 address(const char *name,u32 fallback){
  const char *text=std::getenv(name);if(!text)return fallback;
  size_t used=0;const auto value=std::stoull(text,&used,0);
  if(used!=strlen(text)||value>0xffffffffull)throw std::runtime_error("Invalid dispatcher trace address");
  return static_cast<u32>(value);
 }
public:
 void configure(){
  first=last=0;dropped=0;entries.clear();path.clear();
  const char *value=std::getenv("SC5_PC_TRACE");if(!value)return;
  path=value;first=address("SC5_PC_TRACE_MIN",0x8c010000);last=address("SC5_PC_TRACE_MAX",0x8c2f0000);
  if(first<0x8c000000 || last>0x8d000000 || first>=last)throw std::runtime_error("Invalid dispatcher trace range");
  entries.reserve(100000);
 }
 void record(u32 pc,const State &state){
  if(!first||pc<first||pc>=last)return;
  if(entries.size()==100000){++dropped;return;}
  Entry entry{};entry.pc=pc;entry.pr=state.pr;entry.cycles=sh4_sched_now64();
  memcpy(entry.regs,state.r,sizeof(entry.regs));memcpy(entry.fr,state.fr,sizeof(entry.fr));entries.push_back(entry);
 }
 void finish(u64 origin){
  first=last=0;if(path.empty())return;
  std::ofstream out(path);out<<"pc,pr,cycles";
  for(int i=0;i<16;i++)out<<",r"<<i;
  for(int i=0;i<16;i++)out<<",fr"<<i;
  out<<'\n';
  for(const auto &entry:entries){
   out<<std::hex<<entry.pc<<','<<entry.pr<<std::dec<<','<<(entry.cycles-origin);
   for(auto value:entry.regs)out<<','<<std::hex<<value;
   for(auto value:entry.fr)out<<','<<std::hex<<value;
   out<<std::dec<<'\n';
  }
  if(!out.good())throw std::runtime_error("Cannot write dispatcher trace");
  std::cout<<"Native dispatcher trace entries="<<entries.size()<<" dropped="<<dropped<<'\n';
 }
};
