# Native desktop platforms

The host, offline native modules and frozen asset-import launcher support Windows x64, Linux x64/ARM64 and macOS x64/ARM64 build targets. The downloadable-build workflow compiles the complete host and all four game modules, checks the module ABI and floating-point behavior on each runner, and packages the launcher with the binaries. See the workflow result and release assets for completed builds.

Windows has game-execution validation on the development PC, including all four reports through credits in an earlier assist-mode build, matched replays, save tests and keyboard/Steam Controller testing. Linux and macOS CI establish build and module-test results, not a full game playthrough or real display/audio/controller testing. Those packages are previews pending hands-on acceptance on their target hardware.

The host uses SDL module loading, monotonic clocks, atomic checkpoints and save-directory locking. Texture write tracking uses Windows exceptions or POSIX SIGSEGV/SIGBUS handling. Contract tests check protected writes and unrelated signal forwarding. AArch64 modules preserve FPCR/FPSR rounding and exception state; compiler floating-point contraction is disabled on all targets.

Packages include precompiled translated modules. Asset import does not compile code and requires no developer tools. macOS bundles use ad-hoc signing; they are not Apple-notarized. Linux packages use system graphics/audio libraries. Builds target the GitHub runner environments specified in `.github/workflows/release-build.yml`; older operating systems are not yet a tested compatibility promise.

Display options retain original 4:3 by default. Experimental expanded geometry cannot replace prerecorded background artwork or undo game-side object culling. Optional midpoint geometry interpolation targets 60 Hz presentation and preserves the game clock; it is not arbitrary-refresh interpolation. See PLAYER-GUIDE.md for choices and limits.
