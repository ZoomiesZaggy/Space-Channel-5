# Native mod API (experimental, version 1)

The launcher’s Mods tab can save one native mod selection. The Windows host can also explicitly load one native mod with
`--native-mod C:\absolute\path\example.dll` or `SC5_NATIVE_MOD`.
Nothing is automatically loaded from texture directories. Native mods run code
with the same access as the game; use mods you trust. Compatibility checks are
not a sandbox and happen after the operating system loads the library.

Build `tools/examples/frame_counter_mod.c` as a shared library with the same
x86-64 LLVM MinGW toolchain used for the host:

```powershell
clang -shared -O2 tools/examples/frame_counter_mod.c -o frame-counter.dll
```

The public C interface is `tools/native_mod_api.h`. Export `sc5_mod_query` with
C linkage and return a static `Sc5Mod` descriptor. The host rejects a missing
export, different structure size, ABI version or game version, missing callbacks,
and a failed startup. Version 1 targets the supported USA game build. A new
incompatible API or game revision requires a new version identifier.

- `start` receives a host API valid until `stop` returns. Startup happens after
  machine initialization and checkpoint restoration, before the main run loop.
- `frame` runs synchronously after an AOT chunk which produced a game frame,
  before presentation. It receives the active round, frame count and elapsed
  emulated cycles. It is not an instruction-level hook or a monitor-refresh hook.
- `stop` runs once after a successful start, while the library is still loaded.
  It also runs when the host unwinds after an execution error.
- RAM access uses byte offsets into the 16 MiB main RAM and rejects out-of-range
  or overflowing ranges. Callbacks and RAM access must stay on the host thread.
  Mods must not throw exceptions across this C interface or retain frame pointers.

Changing game data is supported. Changing SH4 instructions does not regenerate
AOT code: unsupported code changes still halt at the normal coverage guard.
There is no CPU fallback, arbitrary guest-function dispatch, mod manager,
dependency resolution or checkpoint serialization for a mod's private state.
Do not assume an unmodified game's saves or deterministic replay remain valid
after a mod changes data. This API is an initial native extension interface,
not parity with BanjoRecomp's established mod ecosystem.

The example only counts frames and checks RAM read bounds. On the seeded opening
replay it received all 326 frame callbacks, shut down normally, and preserved RAM,
PCM audio and final image byte-for-byte. An example compiled with ABI 999 was
rejected before its `start` callback.
