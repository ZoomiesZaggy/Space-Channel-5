// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "audio/audiostream.h"
#include "cfg/option.h"
#include <fstream>
#include <iostream>
#include <stdexcept>

// Captures the device mix produced by native execution, with optional playback.
// PCM statistics alone do not verify fidelity.
class NativeAudioCapture final : public AudioBackend {
 std::ofstream output;
 u32 bytes=0,peak=0;
 u64 nonzero=0;
 AudioBackend *playback=nullptr;
 void word(u32 value,u32 width){for(u32 j=0;j<width;j++)output.put(static_cast<char>(value>>(j*8)));}
 void header(){
  output.seekp(0);output.write("RIFF",4);word(36+bytes,4);output.write("WAVEfmt ",8);word(16,4);word(1,2);word(2,2);
  word(44100,4);word(44100*4,4);word(4,2);word(16,2);output.write("data",4);word(bytes,4);
 }
public:
 NativeAudioCapture():AudioBackend("sc5-native-capture","Native game mix capture"){}
 bool init() override {
  const char *path=std::getenv("SC5_AUDIO_OUTPUT");if(!path)throw std::runtime_error("Audio capture path is missing");
  bytes=peak=0;nonzero=0;output.open(path,std::ios::binary|std::ios::trunc);
  if(!output)throw std::runtime_error("Cannot open native audio capture");header();
  if(std::getenv("SC5_PLAY_AUDIO")){playback=AudioBackend::getBackend("sdl2");if(!playback||!playback->init())throw std::runtime_error("SDL audio playback initialization failed");}
  return true;
 }
 u32 push(const void *data,u32 frames,bool) override {
  if(frames>(0xffffffffu-36u-bytes)/4)throw std::runtime_error("Native WAV exceeds RIFF capacity");
  const auto *samples=static_cast<const s16*>(data);
  for(u32 j=0;j<frames*2;j++){int value=samples[j];if(value)nonzero++;peak=std::max(peak,static_cast<u32>(value<0?-value:value));}
  output.write(static_cast<const char*>(data),frames*4);bytes+=frames*4;
  if(playback)playback->push(data,frames,true);
  if(!output)throw std::runtime_error("Cannot write native audio capture");return frames;
 }
 void term() override {
  if(playback){playback->term();playback=nullptr;}
  if(!output.is_open())return;header();output.close();
  std::cout<<"Native audio captured frames="<<bytes/4<<" nonzero samples="<<nonzero<<" peak="<<peak<<" at 44100 Hz stereo\n";
 }
};

class NativeAudioSession {
public:
 NativeAudioSession(){static NativeAudioCapture backend;config::AudioBackend=std::getenv("SC5_AUDIO_OUTPUT")?backend.slug:"sdl2";InitAudio();}
 ~NativeAudioSession(){TermAudio();}
};
