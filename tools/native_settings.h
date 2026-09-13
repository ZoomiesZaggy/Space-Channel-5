// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "native_host_os.h"
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <cstdlib>
#include <stdexcept>

inline std::string nativeTrim(std::string value){
 const auto first=value.find_first_not_of(" \t\r\n");
 return first==std::string::npos?"":value.substr(first,value.find_last_not_of(" \t\r\n")-first+1);
}
inline int nativeNumber(const char *name,int fallback,int low,int high){
 const char *text=std::getenv(name);if(!text)return fallback;
 size_t used=0;int value=std::stoi(text,&used);
 if(used!=std::string(text).size()||value<low||value>high)throw std::runtime_error(std::string("Invalid setting: ")+name);
 return value;
}
inline void loadNativeSettings(const std::filesystem::path &path){
 std::ifstream file(path);if(!file){if(std::filesystem::exists(path))throw std::runtime_error("Cannot read settings");return;}
 const std::map<std::string,std::string> names={
  {"display_mode","SC5_DISPLAY_MODE"},{"motion_interpolation","SC5_MOTION_INTERPOLATION"},{"rhythm_offset_ms","SC5_RHYTHM_OFFSET_MS"},{"native_mod","SC5_NATIVE_MOD"},{"gdi","SC5_GDI"},{"volume","SC5_VOLUME"},{"audio_buffer_ms","SC5_AUDIO_BUFFER_MS"},{"texture_packs","SC5_TEXTURE_PACKS"},{"fullscreen","SC5_FULLSCREEN"},{"window_scale","SC5_WINDOW_SCALE"},{"vsync","SC5_VSYNC"},
  {"key_start","SC5_KEY_START"},{"key_up","SC5_KEY_UP"},{"key_down","SC5_KEY_DOWN"},{"key_left","SC5_KEY_LEFT"},{"key_right","SC5_KEY_RIGHT"},
  {"key_a","SC5_KEY_A"},{"key_b","SC5_KEY_B"},{"key_x","SC5_KEY_X"},{"key_y","SC5_KEY_Y"},
  {"pad_start","SC5_PAD_START"},{"pad_up","SC5_PAD_UP"},{"pad_down","SC5_PAD_DOWN"},{"pad_left","SC5_PAD_LEFT"},{"pad_right","SC5_PAD_RIGHT"},
  {"pad_a","SC5_PAD_A"},{"pad_b","SC5_PAD_B"},{"pad_x","SC5_PAD_X"},{"pad_y","SC5_PAD_Y"}};
 std::string line;while(std::getline(file,line)){
  line=nativeTrim(line);if(line.empty()||line[0]=='#')continue;
  auto eq=line.find('=');if(eq==std::string::npos)throw std::runtime_error("Malformed settings line");
  auto name=nativeTrim(line.substr(0,eq)),value=nativeTrim(line.substr(eq+1));
  auto found=names.find(name);if(found==names.end())throw std::runtime_error("Unknown setting: "+name);
  if(!value.empty()&&!std::getenv(found->second.c_str()))nativeSetEnvironment(found->second.c_str(),value.c_str());
 }
 nativeNumber("SC5_DISPLAY_MODE",0,0,4);nativeNumber("SC5_MOTION_INTERPOLATION",0,0,1);
 nativeNumber("SC5_RHYTHM_OFFSET_MS",0,-250,250);
 nativeNumber("SC5_VOLUME",100,0,100);nativeNumber("SC5_FULLSCREEN",0,0,1);
 nativeNumber("SC5_AUDIO_BUFFER_MS",64,32,128);
 nativeNumber("SC5_TEXTURE_PACKS",0,0,1);
 nativeNumber("SC5_WINDOW_SCALE",1,1,4);nativeNumber("SC5_VSYNC",0,0,1);
}
