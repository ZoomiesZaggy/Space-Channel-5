// SPDX-License-Identifier: GPL-2.0-or-later
// Platform hooks for the standalone native host. Window/input/audio events are
// handled by its SDL surfaces, not the emulator frontend.
#include <cstdlib>
[[noreturn]] void os_DebugBreak(){std::abort();}
void os_DoEvents(){}
void os_RunInstance(int,const char*[]){}
void os_SetThreadName(const char*){}
const char *getThreadName(){return "sc5-native";}
