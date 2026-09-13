// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cmath>
#include <cstring>
#include <stdexcept>

// USA InputTask's private copy of the beat clock. The shared music clock, CPU
// retirement, audio playback, and physical input delivery are not changed.
class NativeRhythmCalibration {
 int milliseconds=0;
 u64 applied=0;
 template<class T> static T read(u32 address){
  if(address<0x8c000000u || address>0x8d000000u-sizeof(T))
   throw std::runtime_error("Rhythm calibration: unexpected game pointer");
  T value;memcpy(&value,GetMemPtr(address,sizeof(T)),sizeof(T));return value;
 }
public:
 void configure(){milliseconds=nativeNumber("SC5_RHYTHM_OFFSET_MS",0,-250,250);applied=0;}
 void dispatch(u32 pc,State &state){
  if(!milliseconds || pc!=0x8c022362u)return;
  // Return from the USA beat-clock getter into InputTask; validate the exact
  // consumer sequence before modifying its argument, including the call target.
  if(state.pr!=pc || read<u16>(pc)!=0xd21d || read<u16>(pc+2)!=0x420b ||
     read<u16>(pc+4)!=0xff0c || read<u32>(0x8c0223d4u)!=0x8c01e6e2u)
   throw std::runtime_error("Rhythm calibration: unsupported input-task code");
  const u32 music=read<u32>(0x8c10a998u);if(!music)return;
  if(music<0x8c000000u || music>0x8cffff00u)throw std::runtime_error("Rhythm calibration: invalid music state");
  const u32 index=read<u32>(music+0x54);
  if(index>=8)throw std::runtime_error("Rhythm calibration: invalid tempo queue");
  const u32 command=read<u32>(music+0xc0+index*8);if(!command)return;
  if(command<0x8c000000u || command>0x8cfffff8u)throw std::runtime_error("Rhythm calibration: invalid tempo command");
  const int numerator=read<int16_t>(command+4),denominator=read<int16_t>(command+6);
  if(numerator<=0 || denominator<=0)throw std::runtime_error("Rhythm calibration: invalid tempo ratio");
  float original;memcpy(&original,&state.fr[0],sizeof(original));
  // The game converts its nominal 30 Hz song-frame counter into beat units
  // using this tempo ratio. Positive offsets move the response window later.
  const float adjusted=original-static_cast<float>(milliseconds*0.03* numerator/denominator);
  if(!std::isfinite(adjusted))throw std::runtime_error("Rhythm calibration: invalid beat clock");
  memcpy(&state.fr[0],&adjusted,sizeof(adjusted));++applied;
 }
 u64 count() const{return applied;}
};
