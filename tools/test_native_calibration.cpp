// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdint>
#include <cstring>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include "native_state.h"
using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;
static unsigned char ram[0x1000000];
static int offset;
static int nativeNumber(const char*,int,int,int){return offset;}
static unsigned char *GetMemPtr(u32 address,u32){return ram+(address-0x8c000000);}
#include "native_rhythm_calibration.h"
template<class T> static void put(u32 address,T value){memcpy(GetMemPtr(address,sizeof(T)),&value,sizeof(T));}
static void require(bool value){if(!value)throw std::runtime_error("Calibration contract failed");}
static State initial(){
 memset(ram,0,sizeof(ram));
 put<u16>(0x8c022362,0xd21d);put<u16>(0x8c022364,0x420b);put<u16>(0x8c022366,0xff0c);
 put<u32>(0x8c0223d4,0x8c01e6e2);put<u32>(0x8c10a998,0x8c100000);
 put<u32>(0x8c100054,0);put<u32>(0x8c1000c0,0x8c110000);
 put<int16_t>(0x8c110004,4);put<int16_t>(0x8c110006,50);
 State state{};state.pr=0x8c022362;const float beat=10;memcpy(&state.fr[0],&beat,4);return state;
}
int main(){
 try {
  unsigned passed=0;
  for(int ms:{-250,-100,0,100,250}){
   auto state=initial(),before=state;offset=ms;NativeRhythmCalibration c;c.configure();c.dispatch(0x8c022362,state);
   float value;memcpy(&value,&state.fr[0],4);require(std::abs(value-(10-ms*0.0024))<0.00001);
   state.fr[0]=before.fr[0];require(memcmp(&state,&before,sizeof(state))==0);++passed;
  }
  {auto state=initial();offset=100;NativeRhythmCalibration c;c.configure();put<int16_t>(0x8c110004,8);put<int16_t>(0x8c110006,60);c.dispatch(0x8c022362,state);float value;memcpy(&value,&state.fr[0],4);require(std::abs(value-9.6f)<0.00001f);++passed;}
  {auto state=initial(),before=state;offset=100;NativeRhythmCalibration c;c.configure();c.dispatch(0x8c022364,state);require(memcmp(&state,&before,sizeof(state))==0);++passed;}
  {auto state=initial(),before=state;offset=0;NativeRhythmCalibration c;c.configure();put<u32>(0x8c10a998,0xffffffff);c.dispatch(0x8c022362,state);require(memcmp(&state,&before,sizeof(state))==0);++passed;}
  for(int error=0;error<6;error++){
   auto state=initial();offset=100;NativeRhythmCalibration c;c.configure();
   switch(error){case 0:state.pr=0;break;case 1:put<u16>(0x8c022362,0);break;case 2:put<u32>(0x8c100054,8);break;case 3:put<int16_t>(0x8c110006,0);break;case 4:put<u32>(0x8c10a998,0xffffffff);break;case 5:put<u32>(0x8c1000c0,0xffffffff);break;}
   bool rejected=false;try{c.dispatch(0x8c022362,state);}catch(const std::runtime_error&){rejected=true;}require(rejected);++passed;
  }
  std::cout<<"Calibration contract checks passed="<<passed<<'\n';return 0;
 }catch(const std::exception &e){std::cerr<<e.what()<<'\n';return 1;}
}
