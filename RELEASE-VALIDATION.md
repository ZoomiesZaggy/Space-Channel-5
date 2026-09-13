# Release-preparation validation — 2026-09-12

The launcher, persistent settings, optional texture replacement and measurement probe are implemented. The complete comparison roadmap is **not finished**; see ROADMAP.md.

## Build and correctness

- Built the pinned reference and frontend in a fresh repository-local workspace.
- Regenerated and compiled all four AOT DLLs from the supplied USA disc. Their generated C files match the previously validated sources byte for byte.
- Ran the complete bootstrap command successfully, including a cached rebuild. The automatic portable compiler download separately passed its pinned SHA-256 check.
- All 16 native regression tests pass for each of four modules: **64 passes, zero skips**. Tests include short remapped keyboard taps and virtual-controller shoulder-button remapping.
- All four Python settings tests pass. Native settings loading, numeric-value rejection and environment precedence were exercised separately.
- The rebuilt application passed a fresh one-billion-instruction boot.
- The final default frontend replay matches the earlier build's PCM, image, CPU state and all 16 MiB RAM.
- Muting produced 560,128 stereo frames with no nonzero samples and preserved CPU state.
- Synthetic texture replacement changed the rendered image while preserving RAM and the full checkpoint bytes.
- The timing probe's synthetic event reached its audio callback and the bounded test exited successfully. This is not a physical latency result.

Frontend SHA-256: `119f807e6f1d7df8b58461619e4292da4c8ba51fd3fa42da6ebc7acfb0a2ff6b`.

## Isolated Report 3 pacing comparison

Each run starts from the same checkpoint and executes six billion native instructions. Compilation and the other game were stopped. These are scene-specific measurements on the development PC, not whole-game or other-hardware guarantees.

| Setting | Worst interval | Intervals >50 ms | Audio underrun frames |
|---|---:|---:|---:|
| Automatic NVIDIA threading, 64 ms buffer | 127.71 ms | 2 | 1792 |
| Automatic threading, 32 ms buffer | 125.59 ms | 2 | 3328 |
| Threading off, 64 ms buffer | 72.60 ms | 1 | 0 |
| Threading off, repeated | 72.21 ms | 1 | 0 |
| Automatic threading, repeated | 128.47 ms | 2 | 1792 |

PCM, RAM and full checkpoint bytes match across all five runs. Initial final-frame captures differ only in the rightmost pixel column: 43 channels for the 32 ms run and 552 for the driver runs, out of 921,600 RGB channels. Both threading-off captures and the restored automatic-threading capture are byte-identical to each other. This edge variation is recorded rather than described as exact image equality across all runs.

The 64 ms buffer remains the default. The 32 ms option produced more underrun frames in this scene and is not a recommended default.

After the repeated comparison, the development PC's per-application NVIDIA profile was set to disable OpenGL threaded optimization for `sc5-native-dev.exe`. This is local to that PC; the launcher does not modify drivers. Other users can evaluate the per-program option in NVIDIA Control Panel and restore its default to undo it. No driver SDK/helper is distributed here.

A roughly 72 ms stall remains. Actual gameplay calibration, physical latency measurement, a full manual playthrough, other PCs, game-aware widescreen, interpolation, executable mods and native Linux/macOS support remain pending.
