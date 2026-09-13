// SPDX-License-Identifier: GPL-2.0-or-later
#define SDL_MAIN_HANDLED
#include "native_device_runtime.h"
#include "native_cpu_placement.h"
#include "native_settings.h"
#include "native_latency_probe.h"
#include <filesystem>

int main(int argc,char **argv){
 try {
  SDL_SetMainReady();
  std::cout<<std::unitbuf;
  if(argc==2&&std::string(argv[1])=="--latency-test")return runNativeLatencyProbe();
  NativeAwakeGuard awake;
  std::cout<<std::unitbuf;
  NativeCpuPlacement cpuPlacement;
  auto root=std::filesystem::absolute(argv[0]).parent_path().parent_path();
  const auto userRoot=std::getenv("SC5_USER_ROOT")?std::filesystem::path(std::getenv("SC5_USER_ROOT")):root;
  if(!std::getenv("SC5_IGNORE_SETTINGS"))loadNativeSettings(userRoot/"userdata/settings.ini");
  auto defaultEnv=[](const char *name,const std::string &value){if(!std::getenv(name))nativeSetEnvironment(name,value.c_str());};
  defaultEnv("SC5_NATIVE_DLL",(root/(std::string("build/native-diff")+nativeLibrarySuffix())).string());
  defaultEnv("SC5_MODULE_DLL_DIR",(root/"build").string());
  defaultEnv("SC5_IMAGE",(userRoot/"extracted/1ST_READ.BIN").string());
  defaultEnv("SC5_RUNTIME_DATA",(userRoot/"userdata").string()+"/");
  defaultEnv("SC5_INSTRUCTION_BUDGET","0");
  defaultEnv("SC5_VISIBLE","1");defaultEnv("SC5_PLAY_AUDIO","1");
  defaultEnv("SC5_DEFER_SILENT_AUDIO","1");
  const std::map<std::string,const char*> options={{"--gdi","SC5_GDI"},{"--image","SC5_IMAGE"},{"--dll","SC5_NATIVE_DLL"},{"--data","SC5_RUNTIME_DATA"},
   {"--native-mod","SC5_NATIVE_MOD"},{"--budget","SC5_INSTRUCTION_BUDGET"},{"--input-script","SC5_INPUT_SCRIPT"},{"--frame","SC5_FRAME_OUTPUT"},{"--audio-capture","SC5_AUDIO_OUTPUT"},
   {"--checkpoint-load","SC5_CHECKPOINT_LOAD"},{"--checkpoint-save","SC5_CHECKPOINT_SAVE"},{"--stop-file","SC5_STOP_FILE"}};
  for(int j=1;j<argc;j++){
   std::string option=argv[j];
   if(option=="--help"){
    std::cout<<"Space Channel 5 native development build\nUsage: sc5-native-dev.exe --gdi <original USA .gdi> [--hidden] [--silent]\n"
     <<"Options: --native-mod <absolute DLL path> --image --dll --data --budget --input-script --frame --audio-capture --checkpoint-load --checkpoint-save --stop-file\n"
     <<"Creating the optional stop file requests a graceful stop and checkpoint save.\n"
     <<"Normal play has no instruction limit; --budget sets a diagnostic limit (0 means unlimited).\n"
     <<"Controls: Enter=Start, arrows=direction pad, Z/Space=A, X/Backspace=B, A=X, S=Y; SDL gamepad supported.\n";return 0;
   }
   if(option=="--hidden"){nativeSetEnvironment("SC5_VISIBLE","");continue;}
   if(option=="--silent"){nativeSetEnvironment("SC5_PLAY_AUDIO","");continue;}
   auto found=options.find(option);if(found==options.end()||j+1==argc)throw std::runtime_error("Unknown or incomplete option: "+option);
   std::string value=argv[++j];if(option=="--data")value+="/";nativeSetEnvironment(found->second,value.c_str());
  }
  if(!std::getenv("SC5_GDI"))throw std::runtime_error("Specify the original Space Channel 5 USA disc with --gdi <path>");
  std::filesystem::create_directories(std::getenv("SC5_RUNTIME_DATA"));
  std::cout<<"Space Channel 5 native development build\n";
  auto result=runNativeDeviceHarness();
  if(result.fault){std::cerr<<"Native execution stopped at "<<std::hex<<result.pc<<" with unsupported-path fault "<<result.fault<<". Development remains unfinished.\n";return 2;}
  return 0;
 }catch(const std::exception &error){std::cerr<<"Native startup failed: "<<error.what()<<"\n";return 1;}
}
