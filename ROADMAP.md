# Public release work

This tracks the requested progression toward a polished PC port. It does not claim that every item is finished.

## Implemented

- Repository-local builds with explicit toolchain/work-directory overrides.
- Disc selection, guided builds and persistent settings in a launcher.
- Volume, audio buffering, display options and keyboard/controller remapping.
- A standalone input/audio probe for physical-measurement recordings.
- Optional texture replacement through the existing renderer.
- Source-only CI checks and settings persistence tests.

## Completed acceptance

The clean four-DLL build, 64 native test passes, settings tests and matched replay checks are recorded in [release validation](RELEASE-VALIDATION.md). A repeated per-game NVIDIA threading comparison reduced the worst measured interval, but did not eliminate all stalls.

## Remaining comparison goals

- Remove remaining long frame stalls under isolated workloads.
- Identify and patch rhythm-judgement timing for an actual calibration offset.
- Record physical controller-to-speaker latency and complete a manual playthrough.
- Test on additional, less powerful PCs.
- Implement game-aware widescreen, including backgrounds, HUD and clipping fixes.
- Implement high-refresh interpolation while preserving game logic and rhythm timing.
- Establish executable-mod hooks and compatibility/version checks.
- Port Windows host interfaces and validate Linux/macOS builds on those platforms.
- Provide installation without a compiler, using an appropriate asset-import/local-generation design.

The launcher and native host remain Windows development software. Tests on the development PC cannot establish other hardware/platform compatibility.
