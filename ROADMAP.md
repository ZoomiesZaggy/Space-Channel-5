# Public release work

This tracks the requested progression toward a polished PC port. It does not claim that every item is finished.

## Implemented

- Repository-local builds with explicit toolchain/work-directory overrides.
- Disc selection, guided builds and persistent settings in a launcher.
- Volume, audio buffering, display options and keyboard/controller remapping.
- Manual rhythm calibration that shifts the game’s input-task beat clock using the active tempo; default 0 ms.
- A standalone input/audio probe for physical-measurement recordings.
- Optional texture replacement through the existing renderer.
- Experimental native mod ABI with compatibility checks, RAM access and lifecycle/frame callbacks (see NATIVE-MODS.md).
- Source-only CI checks and settings persistence tests.
- Portable host, Windows/POSIX texture protection, ARM64 floating-point control, full Linux/macOS build integration and native module ABI tests.
- Frozen disc-import launcher and packaging with precompiled modules; players need no compiler or development tools.
- Original, fit, crop, stretch and experimental expanded-geometry display modes.
- Optional geometry midpoint interpolation with unchanged game logic and rhythm clocks.

## Completed acceptance

The clean four-DLL build, 64 native test passes, settings tests and matched replay checks are recorded in [release validation](RELEASE-VALIDATION.md). A repeated per-game NVIDIA threading comparison reduced the worst measured interval, but did not eliminate all stalls.

## Remaining comparison goals

- Address remaining game-frame gaps: the traced 72 ms interval includes 66.79 ms of emulated time between game frames; presentation takes about 0.5 ms.
- Complete hands-on calibration checks across a full manual playthrough; the timing patch and automated boundary tests are implemented.
- Record physical controller-to-speaker latency and complete a manual playthrough.
- Test on additional, less powerful PCs.
- Expand geometry coverage beyond game-side culling and improve background presentation without replacing original artwork.
- Broaden interpolation scene coverage and evaluate refresh targets beyond 60 Hz.
- Expand the initial native mod API with guest-function hooks, mod management and checkpoint state support.
- Complete hands-on game, audio and controller acceptance on Linux/macOS hardware beyond CI build and module checks.

Preview packages target Windows, Linux and macOS. Tests on the development PC cannot establish other hardware/platform compatibility; platform evidence is documented separately in PLATFORM-STATUS.md.
