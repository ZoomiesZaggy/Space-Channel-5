// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <stdexcept>
#include <string>
#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

// Empty means unset, including on POSIX: presence enables several diagnostic flags.
inline void nativeSetEnvironment(const char *name,const char *value){
#ifdef _WIN32
 const int result=_putenv_s(name,value);
#else
 const int result=*value?setenv(name,value,1):unsetenv(name);
#endif
 if(result)throw std::runtime_error(std::string("Cannot set environment: ")+name);
}
inline uint64_t nativeMilliseconds(){
 return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
inline bool nativePathExists(const char *path){
 std::error_code error;return std::filesystem::exists(path,error);
}
inline bool nativeReplaceFile(const char *source,const char *destination){
#ifdef _WIN32
 return MoveFileExW(std::filesystem::path(source).c_str(),std::filesystem::path(destination).c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
#else
 std::error_code error;std::filesystem::rename(source,destination,error);return !error;
#endif
}
inline constexpr const char *nativeLibrarySuffix(){
#ifdef _WIN32
 return ".dll";
#elif defined(__APPLE__)
 return ".dylib";
#else
 return ".so";
#endif
}
class NativeAwakeGuard {
public:
 NativeAwakeGuard(){
#ifdef _WIN32
  SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED);
#endif
 }
 ~NativeAwakeGuard(){
#ifdef _WIN32
  SetThreadExecutionState(ES_CONTINUOUS);
#endif
 }
};
class NativeGameLock {
#ifdef _WIN32
 HANDLE handle=INVALID_HANDLE_VALUE;
#else
 int handle=-1;
#endif
public:
 explicit NativeGameLock(const std::filesystem::path &directory){
  const auto path=directory/".game.lock";
#ifdef _WIN32
  handle=CreateFileW(path.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
  if(handle==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot lock save directory; another game may already be running");
#else
  handle=open(path.c_str(),O_RDWR|O_CREAT,0600);
  if(handle<0)throw std::runtime_error("Cannot open save directory lock");
  if(flock(handle,LOCK_EX|LOCK_NB)){close(handle);handle=-1;throw std::runtime_error("Cannot lock save directory; another game may already be running");}
#endif
 }
 NativeGameLock(const NativeGameLock&)=delete;
 NativeGameLock &operator=(const NativeGameLock&)=delete;
 ~NativeGameLock(){
#ifdef _WIN32
  if(handle!=INVALID_HANDLE_VALUE)CloseHandle(handle);
#else
  if(handle>=0)close(handle);
#endif
 }
};
