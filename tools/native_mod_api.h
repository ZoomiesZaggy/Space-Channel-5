// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>

#define SC5_MOD_ABI_VERSION 1u
#define SC5_GAME_USA_VERSION 0x55534101u
#ifdef _WIN32
#define SC5_MOD_EXPORT __declspec(dllexport)
#else
#define SC5_MOD_EXPORT __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
typedef struct Sc5ModHost {
    uint32_t size, abi_version, game_version;
    // RAM offsets are 0..0xffffff, not guest virtual addresses. Zero means failure.
    int (*read_ram)(uint32_t offset, void *destination, uint32_t bytes);
    int (*write_ram)(uint32_t offset, const void *source, uint32_t bytes);
    void (*log)(const char *message);
} Sc5ModHost;
typedef struct Sc5ModFrame {
    uint32_t size, module, frame_count;
    uint64_t device_cycles;
} Sc5ModFrame;
typedef struct Sc5Mod {
    uint32_t size, abi_version, game_version;
    const char *name;
    int (*start)(const Sc5ModHost *host);
    void (*frame)(const Sc5ModFrame *frame);
    void (*stop)(void);
} Sc5Mod;
// Export this function using C linkage. Its descriptor must live until unload.
typedef const Sc5Mod *(*Sc5ModQuery)(void);
#ifdef __cplusplus
}
#endif
