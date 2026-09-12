// SPDX-License-Identifier: GPL-2.0-or-later
// Cycle rules adapted from Flycast core/hw/sh4/sh4_cycles.cpp (flyinghead, 2023).
#pragma once
#include "hw/sh4/sh4_cycles.h"
#include "hw/sh4/modules/mmu.h"
#include "native_fast_clock.h"
#include "native_static_timing.h"
#include <stdexcept>

struct NativeCycleSnapshot {u32 lastUnit,initialMemOps;};
class NativeCycleModel : public Sh4Cycles {
 NativeOpcodeTiming timing[65536]{};
 Sh4Context *context=nullptr;
 NativeFastClock clock{};
public:
 NativeCycleModel():Sh4Cycles(1){}
 void init(Sh4Context *ctx){
  static_assert(CO==5&&MT==0,"Native timing unit constants changed");
  context=ctx;Sh4Cycles::init(ctx);clock.counter=&ctx->cycle_counter;clock.timing=timing;
  constexpr bool memory[45]={false,false,true,true,false,true,true,true,false,false,false,false,true,false,false,false,false,true,true,true,false,false,true,true,false,true,false,true,false,true,false,true,false,true,false,true};
  for(unsigned op=0;op<65536;op++){
   const auto *desc=OpDesc[op];
   if(!desc||desc->IssueCycles>255||static_cast<unsigned>(desc->ex_type)>=45)throw std::runtime_error("Invalid opcode timing descriptor");
   timing[op]={static_cast<unsigned char>(desc->unit),static_cast<unsigned char>(desc->IssueCycles),memory[desc->ex_type],0};
   if(native_static_timing[op]!=(static_cast<u32>(desc->unit)|(desc->IssueCycles<<8)))throw std::runtime_error("Offline opcode timing differs from reference");
  }
 }
 void reset(){Sh4Cycles::reset();clock.last_unit=CO;clock.initial_mem_ops=0;}
 NativeFastClock *fastClock(void (*boundary)(u32,u32,u32)){clock.boundary=boundary;return &clock;}
 NativeCycleSnapshot snapshot()const{return {clock.last_unit,clock.initial_mem_ops};}
 void restore(NativeCycleSnapshot saved){
  if(saved.lastUnit>CO||saved.initialMemOps>3)throw std::runtime_error("Invalid checkpoint cycle state");
  clock.last_unit=saved.lastUnit;clock.initial_mem_ops=saved.initialMemOps;
 }
 int countCycles(u16 op){
  const auto info=timing[op];int cycles=0;
#ifndef STRICT_MODE
  // Only the first three memory operations incur this extra cost. Saturating
  // the counter also avoids signed overflow in extremely long native runs.
  if(clock.initial_mem_ops<3&&info.mem){++clock.initial_mem_ops;cycles=mmu_enabled()?5:2;}
#endif
  if(clock.last_unit==CO||info.unit==CO||(clock.last_unit==info.unit&&clock.last_unit!=MT)){
   clock.last_unit=info.unit;cycles+=info.issue;
  }else clock.last_unit=CO;
  return cycles;
 }
 void executeCycles(u16 op){context->cycle_counter-=countCycles(op);}
};

static void validateNativeCycleModel(){
 Sh4Cycles reference(1);NativeCycleModel candidate,fast;Sh4Context context{},fastContext{};
 reference.init(&context);candidate.init(&context);fast.init(&fastContext);auto *fastState=fast.fastClock(nullptr);unsigned checks=0,random=53006;
 for(unsigned pass=0;pass<4;pass++){
  reference.reset();candidate.reset();fast.reset();
  for(unsigned j=0;j<262144;j++){
   random=random*1664525u+1013904223u;
   u16 op=pass==0?static_cast<u16>(j):pass==1?static_cast<u16>(65535-j):static_cast<u16>(random>>16);
   const int expected=reference.countCycles(op);
   if(expected!=candidate.countCycles(op))throw std::runtime_error("Native cycle model differs from reference");
   fastContext.cycle_counter=100;
   if(fastState->initial_mem_ops>=3)native_fast_count(fastState,op);else fast.executeCycles(op);
   if(100-fastContext.cycle_counter!=expected)throw std::runtime_error("Inline native cycle model differs from reference");
   checks++;
  }
 }
 std::cout<<"Native cycle comparisons="<<checks<<" mismatches=0\n";
}
