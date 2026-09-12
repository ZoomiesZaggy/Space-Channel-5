// SPDX-License-Identifier: GPL-2.0-or-later
// Shared timing data only; instruction execution remains ahead-of-time code.
#pragma once
#include <stdint.h>
typedef struct NativeOpcodeTiming {uint8_t unit,issue,mem,padding;} NativeOpcodeTiming;
typedef struct NativeFastClock {
 int32_t *counter;
 const NativeOpcodeTiming *timing;
 uint32_t last_unit,initial_mem_ops;
 void (*boundary)(uint32_t,uint32_t,uint32_t);
} NativeFastClock;

// SH4 execution-unit values are checked against the pinned host definitions.
static inline __attribute__((always_inline)) void native_fast_count(NativeFastClock *clock,uint32_t opcode){
 const NativeOpcodeTiming info=clock->timing[opcode];
 if(clock->last_unit==5 || info.unit==5 || (clock->last_unit==info.unit && clock->last_unit!=0)){
  clock->last_unit=info.unit;*clock->counter-=info.issue;
 }else clock->last_unit=5;
}
