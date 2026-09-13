// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
#include <fenv.h>
#if defined(__x86_64__) || defined(__i386__)
#include <xmmintrin.h>
typedef unsigned NativeFpState;
static inline NativeFpState nativeFpBegin(uint32_t fpscr){
 unsigned previous=_mm_getcsr();
 _mm_setcsr((previous&~0x603fu)|((fpscr&1u)?0x6000u:0u));
 return previous;
}
static inline int nativeFpFlags(void){return (_mm_getcsr()&0x20u)?FE_INEXACT:0;}
static inline void nativeFpEnd(NativeFpState previous){_mm_setcsr(previous);}
#elif defined(__aarch64__)
typedef struct {uint64_t control,status;} NativeFpState;
static inline NativeFpState nativeFpBegin(uint32_t fpscr){
 NativeFpState previous;
 __asm__ volatile("mrs %0, fpcr":"=r"(previous.control));
 __asm__ volatile("mrs %0, fpsr":"=r"(previous.status));
 uint64_t control=(previous.control&~(3ull<<22))|((fpscr&1u)?(3ull<<22):0);
 uint64_t status=previous.status&~0x9full;
 __asm__ volatile("msr fpcr, %0"::"r"(control):"memory");
 __asm__ volatile("msr fpsr, %0"::"r"(status):"memory");
 return previous;
}
static inline int nativeFpFlags(void){
 uint64_t status;__asm__ volatile("mrs %0, fpsr":"=r"(status));
 return (status&16)?FE_INEXACT:0;
}
static inline void nativeFpEnd(NativeFpState previous){
 __asm__ volatile("msr fpcr, %0"::"r"(previous.control):"memory");
 __asm__ volatile("msr fpsr, %0"::"r"(previous.status):"memory");
}
#else
#error Native floating point requires x86 or AArch64
#endif
