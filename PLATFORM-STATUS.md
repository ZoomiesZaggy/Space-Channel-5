# Platform work

The playable release remains Windows-only. The host now uses SDL shared-library loading, platform module suffixes, portable environment management and a monotonic clock. Checkpoints use atomic replacement on Windows and POSIX. Windows cache placement and sleep prevention remain Windows-specific, guarded at compilation.

Texture memory write tracking has Windows exception and POSIX SIGSEGV/SIGBUS implementations. The asset-free host test writes to a protected page, verifies repair, checks checkpoint replacement and environment removal, and on POSIX checks unrelated-signal forwarding and handler restoration. CI runs this component test on Linux and macOS. These checks do not establish that the complete game runs there.

The staged Windows frontend completed a one-billion-instruction opening replay with CPU state, RAM, captured audio and rendered image byte-identical to the preceding calibration build. The installed playable package is not replaced by this infrastructure change.

Still required for complete platform ports: portable device-library build/link integration, native module generation and loading on each target, ARM64 floating-point semantics, launcher/packaging changes, and full game validation on those targets. The current AOT generator still uses SSE and Windows build conventions.

The other requested release features remain open: game-aware widescreen with background/HUD/clipping handling, high-refresh motion interpolation that preserves rhythm timing, and compiler-free installation. None is enabled or claimed by this host portability change. Shipping only a prebuilt frontend does not remove the current requirement to compile the user's game modules locally.
