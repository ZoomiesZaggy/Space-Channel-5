// SPDX-License-Identifier: GPL-2.0-or-later
#include "../native_mod_api.h"
#include <stdio.h>
static const Sc5ModHost *host;
static unsigned callbacks;
static int start(const Sc5ModHost *value){
    unsigned char byte, changed, check;
    if(value->size!=sizeof(*value)||value->abi_version!=SC5_MOD_ABI_VERSION)return 0;
    host=value;callbacks=0;
    if(!host->read_ram(0,&byte,1)||host->read_ram(0x1000000,&byte,1)||host->read_ram(0xfffffff0,&byte,32))return 0;
    // Exercise a reversible write before the game resumes; restore even on failure.
    changed=byte^0xff;
    if(!host->write_ram(0,&changed,1))return 0;
    check=byte;host->read_ram(0,&check,1);
    host->write_ram(0,&byte,1);
    if(check!=changed||host->write_ram(0xfffffff0,&byte,32))return 0;
    host->log("frame counter started; RAM read/write bounds checks passed");return 1;
}
static void frame(const Sc5ModFrame *value){(void)value;++callbacks;}
static void stop(void){char message[100];snprintf(message,sizeof(message),"frame counter stopped: callbacks=%u",callbacks);host->log(message);}
#ifndef SC5_EXAMPLE_ABI
#define SC5_EXAMPLE_ABI SC5_MOD_ABI_VERSION
#endif
SC5_MOD_EXPORT const Sc5Mod *sc5_mod_query(void){
    static const Sc5Mod mod={sizeof(Sc5Mod),SC5_EXAMPLE_ABI,SC5_GAME_USA_VERSION,"Frame counter",start,frame,stop};return &mod;
}
