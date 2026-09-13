// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "native_mod_api.h"
#include <SDL_loadso.h>
#include <filesystem>
#include <iostream>
#include <stdexcept>

class NativeModSession {
    void *library=nullptr;
    const Sc5Mod *mod=nullptr;
    bool started=false;
    static bool validRange(uint32_t offset,uint32_t bytes){
        return offset<0x1000000u && bytes<=0x1000000u-offset;
    }
    static int readRam(uint32_t offset,void *destination,uint32_t bytes){
        if(!destination||!validRange(offset,bytes))return 0;
        memcpy(destination,GetMemPtr(0x8c000000u+offset,bytes),bytes);return 1;
    }
    static int writeRam(uint32_t offset,const void *source,uint32_t bytes){
        if(!source||!validRange(offset,bytes))return 0;
        memcpy(GetMemPtr(0x8c000000u+offset,bytes),source,bytes);return 1;
    }
    static void log(const char *message){if(message)std::cout<<"Native mod: "<<message<<'\n';}
    const Sc5ModHost host{sizeof(Sc5ModHost),SC5_MOD_ABI_VERSION,SC5_GAME_USA_VERSION,readRam,writeRam,log};
public:
    NativeModSession(){
        const char *path=std::getenv("SC5_NATIVE_MOD");if(!path||!*path)return;
        if(!std::filesystem::path(path).is_absolute())throw std::runtime_error("Native mod path must be absolute");
        library=SDL_LoadObject(path);
        if(!library)throw std::runtime_error(std::string("Native mod load failed: ")+SDL_GetError());
        try {
            auto query=reinterpret_cast<Sc5ModQuery>(SDL_LoadFunction(library,"sc5_mod_query"));
            if(!query)throw std::runtime_error("Native mod must export sc5_mod_query");
            mod=query();
            if(!mod||mod->size!=sizeof(Sc5Mod)||mod->abi_version!=SC5_MOD_ABI_VERSION||mod->game_version!=SC5_GAME_USA_VERSION)
                throw std::runtime_error("Native mod ABI or game version mismatch");
            if(!mod->name||!mod->start||!mod->frame||!mod->stop)throw std::runtime_error("Incomplete native mod descriptor");
            if(!mod->start(&host))throw std::runtime_error("Native mod initialization rejected");
            started=true;std::cout<<"Loaded native mod: "<<mod->name<<'\n';
        } catch(...){SDL_UnloadObject(library);library=nullptr;throw;}
    }
    ~NativeModSession(){if(started)mod->stop();if(library)SDL_UnloadObject(library);}
    NativeModSession(const NativeModSession&)=delete;
    NativeModSession& operator=(const NativeModSession&)=delete;
    void frame(uint32_t module,uint32_t frames,uint64_t cycles){
        if(started){const Sc5ModFrame value{sizeof(Sc5ModFrame),module,frames,cycles};mod->frame(&value);}
    }
};
