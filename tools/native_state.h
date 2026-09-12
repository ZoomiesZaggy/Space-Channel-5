#pragma once
#include <stdint.h>
typedef struct {
 uint32_t r[16],pc,pr,t,fault,sr,bank[8],gbr,vbr,ssr,spc,sgr,dbr,fpul,fpscr,fr[16],xf[16],mach,macl;
} State;
