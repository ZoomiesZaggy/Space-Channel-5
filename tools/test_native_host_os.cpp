// SPDX-License-Identifier: GPL-2.0-or-later
#include "native_host_os.h"
#include "native_cpu_placement.h"
#include "native_texture_write_watch.h"
#include <fstream>
#include <iostream>
#ifndef _WIN32
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#endif
static void require(bool result){if(!result)throw std::runtime_error("Host OS contract failed");}
static unsigned char *watched;
static size_t pageSize;
static volatile int repaired=0;
static bool repair(unsigned char *address){
 if(address!=watched)return false;
#ifdef _WIN32
 DWORD old;if(!VirtualProtect(watched,pageSize,PAGE_READWRITE,&old))return false;
#else
 if(mprotect(watched,pageSize,PROT_READ|PROT_WRITE))return false;
#endif
 repaired=1;return true;
}
static void testWriteWatch(){
#ifdef _WIN32
 SYSTEM_INFO info;GetSystemInfo(&info);pageSize=info.dwPageSize;
 watched=static_cast<unsigned char*>(VirtualAlloc(nullptr,pageSize,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 require(watched!=nullptr);DWORD old;require(VirtualProtect(watched,pageSize,PAGE_READONLY,&old)!=0);
#else
 pageSize=sysconf(_SC_PAGESIZE);
 watched=static_cast<unsigned char*>(mmap(nullptr,pageSize,PROT_READ,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));
 require(watched!=MAP_FAILED);
 struct sigaction original{},custom{};custom.sa_handler=[](int){_exit(73);};sigemptyset(&custom.sa_mask);
 require(sigaction(SIGSEGV,&custom,&original)==0);
#endif
 {
  NativeTextureWriteWatch watch(repair);
  *static_cast<volatile unsigned char*>(watched)=42;
  require(repaired==1 && *watched==42);
#ifndef _WIN32
  auto child=fork();require(child>=0);
  if(child==0){raise(SIGSEGV);_exit(74);}
  int status=0;require(waitpid(child,&status,0)==child);require(WIFEXITED(status)&&WEXITSTATUS(status)==73);
#endif
 }
#ifdef _WIN32
 require(VirtualFree(watched,0,MEM_RELEASE)!=0);
#else
 struct sigaction restored{};require(sigaction(SIGSEGV,nullptr,&restored)==0);
 require(restored.sa_handler==custom.sa_handler);require(sigaction(SIGSEGV,&original,nullptr)==0);
 require(munmap(watched,pageSize)==0);
#endif
}
int main(int argc,char **argv){
 require(argc==2);
 testWriteWatch();
 nativeSetEnvironment("SC5_TEST_HOST_ENV","enabled");
 require(std::string(std::getenv("SC5_TEST_HOST_ENV"))=="enabled");
 nativeSetEnvironment("SC5_TEST_HOST_ENV","");
 require(std::getenv("SC5_TEST_HOST_ENV")==nullptr);
 const auto first=nativeMilliseconds();require(nativeMilliseconds()>=first);
 const auto root=std::filesystem::path(argv[1]);
 const auto source=(root/"checkpoint.tmp").string(),destination=(root/"checkpoint.bin").string();
 {std::ofstream file(source);file<<"new";}
 {std::ofstream file(destination);file<<"old";}
 require(nativeReplaceFile(source.c_str(),destination.c_str()));
 require(!nativePathExists(source.c_str()));
 std::string content;{std::ifstream file(destination);file>>content;}require(content=="new");
 require(!nativeReplaceFile(source.c_str(),destination.c_str()));
 {std::ifstream file(destination);file>>content;}require(content=="new");
 nativeSetEnvironment("SC5_CPU_PLACEMENT","system");NativeCpuPlacement placement;
 std::cout<<"Host OS contracts passed; module suffix="<<nativeLibrarySuffix()<<"\n";
}
