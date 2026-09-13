Current desktop preview evidence is in [DESKTOP-VALIDATION.md](DESKTOP-VALIDATION.md). The results below describe earlier builds.

# Earlier release-preparation validation — 2026-09-12

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

## Follow-up: frame timing and native mods

Follow-up frontend SHA-256: `50e2c450b5a7e85e83e6960c6aa22d1357454aa99ad4ec9ceb3256ed17afbcf1`.

Host traces now separate AOT execution from presentation, retaining the original CSV fields and appending `run_end_qpc`. `tools/analyze_host_timing.py` reports the longest intervals and their emulated duration.

Two matched Report 3 traces measured 72.3196 and 72.3351 ms for the longest interval. Both contain exactly 66.79456 ms of emulated time between completed game frames; presentation accounts for 0.5010 and 0.4930 ms. No individual traced chunk exceeded 20 ms in the first run. This is a game/device-side frame-production gap, not evidence of a remaining 72 ms OpenGL call. Whether original hardware drops the same frame is still unverified. Do not change rhythm speed to hide the gap.

The two traced builds preserved captured PCM and all RAM exactly and reported zero audio underruns. Their final images also match each other. Complete serialized checkpoints contain host-dependent state and are not claimed byte-identical across these frontend builds.

An initial native mod interface now provides version/size/game checks, bounded RAM reads and writes, and startup/frame/shutdown callbacks. The example received 326 callbacks in the opening replay, validated read/write bounds with a restored temporary write, and preserved final RAM, PCM and image exactly. An ABI-999 DLL was rejected before its startup callback. See NATIVE-MODS.md for limitations.

Actual gameplay calibration, physical latency measurement, a full manual playthrough, other PCs, game-aware widescreen, interpolation and native Linux/macOS support remain pending.

Final follow-up checks: saved mod selection loaded successfully; missing-export and incompatible-ABI libraries were rejected. The final default Report 3 replay preserved RAM and PCM. Its final image differs in 509 RGB channels, all at x=639 (y=75..336), consistent with the previously recorded right-edge variation. The opening replay with the example mod remains byte-identical in RAM, PCM and image.

## Rhythm calibration follow-up

Manual rhythm calibration is now implemented and tested. The latest frontend is `71c639ea7aedc29f54e0026cd252be11fa1349839537457d5c6cc3408138c44c`. See [calibration validation](CALIBRATION-VALIDATION.md) for the judging-window sweep, exact zero-offset replay checks, later-round smoke tests and remaining physical-test limitations.
