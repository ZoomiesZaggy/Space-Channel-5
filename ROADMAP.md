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

## Completed acceptance

The clean four-DLL build, 64 native test passes, settings tests and matched replay checks are recorded in [release validation](RELEASE-VALIDATION.md). A repeated per-game NVIDIA threading comparison reduced the worst measured interval, but did not eliminate all stalls.

## Remaining comparison goals

- Address remaining game-frame gaps: the traced 72 ms interval includes 66.79 ms of emulated time between game frames; presentation takes about 0.5 ms.
- Complete hands-on calibration checks across a full manual playthrough; the timing patch and automated boundary tests are implemented.
- Record physical controller-to-speaker latency and complete a manual playthrough.
- Test on additional, less powerful PCs.
- Implement game-aware widescreen, including backgrounds, HUD and clipping fixes.
- Implement high-refresh interpolation while preserving game logic and rhythm timing.
- Expand the initial native mod API with guest-function hooks, mod management and checkpoint state support.
- Port Windows host interfaces and validate Linux/macOS builds on those platforms.
- Provide installation without a compiler, using an appropriate asset-import/local-generation design.

The launcher and native host remain Windows development software. Tests on the development PC cannot establish other hardware/platform compatibility.
