# Performance update — 2026-09-17

This update reduces CPU overhead investigated after [issue #1](https://github.com/ZoomiesZaggy/Space-Channel-5/issues/1). It is not a confirmed fix on the reporters' Steam Deck or Ryzen 5950X/RTX 3090 systems; neither machine was available for testing.

## What changed

- Clock setup is checked once per generated code page. Every instruction still accounts for its original cycles, and interrupt boundaries, instruction-byte guards and instruction budgets remain active.
- Windows modules access their shared state directly through coalesced definitions. Linux/macOS module internals use hidden linkage, avoiding unnecessary symbol indirection.
- Portable Windows x64 builds use a measured LLVM execution profile to optimize frequently executed paths. There is no new AVX2 requirement, fast-math setting, runtime compiler or change to game/music speed. The profile and reproduction instructions are in [tools/profiles](tools/profiles/README.md).
- The launch log records graphics details and game-speed measurements. Frame intervals and audio underruns are included when `SC5_LOG_PACING` and `SC5_LOG_AUDIO` are set. See [reporting slow gameplay](PLAYER-GUIDE.md#reporting-slow-gameplay-or-crackling-audio).

## Windows measurements

Measured on a Ryzen 9 9950X3D / RTX 5090 system with Windows, original display mode and interpolation disabled. The long Report 3 replay executes six billion native instructions, produces 964 game frames and advances 32.21585472 seconds of device time. Baseline and optimized modules use the same host, input script and starting checkpoint. Local compilation was stopped during measurement.

Two runs per version were alternated in A/B/B/A order. Unpaced runs generate audio without waiting for playback, measuring processing headroom rather than changing the game's intended frame rate.

| CPU placement | Baseline processing time | Optimized processing time | Processing throughput increase |
|---|---:|---:|---:|
| Default, preferred cache chiplet | 25.906 / 26.429 s | 20.614 / 21.300 s | 24.9% |
| Second chiplet on the same PC | 25.689 / 25.833 s | 20.425 / 20.390 s | 26.2% |

Percentages compare the mean times of each pair. Typical unpaced frame intervals improved from 34.9–35.9 ms to 27.2–28.0 ms. The second-chiplet experiment is not a Steam Deck or Ryzen 5950X simulation.

With normal audio-paced playback and a 64 ms buffer:

| Measurement in the same Report 3 replay | Baseline | Optimized |
|---|---:|---:|
| Audio underrun frames | 23,808 | 0 |
| Audio underrun callbacks | 93 | 0 |
| Wall time | 33.014 s | 32.356 s |
| Steady five-second game-speed samples | 0.964–0.997× | 0.998–1.001× |

This is one paired playback measurement, not a guarantee of zero underruns elsewhere. A roughly 73 ms presentation gap remains in both versions, along with uneven presentation intervals; this update does not claim perfect frame pacing. The original game logic remains at its original cadence.

## Correctness and scope

- All 64 native reference regression tests pass, with zero skips, on the final Windows modules. The bounded fresh boot also passes.
- All four modules pass ABI, invalid-disc and floating-point checks, plus 240 additional checks covering clock callbacks, branch targets, alias addresses, code mutation, faults and budget boundaries.
- All eight long unpaced runs and the paired audio-paced replay match CPU state, all 16 MiB of RAM, generated PCM, device cycles and frame count. Images match exactly in the default-placement unpaced pairs. Other comparisons differ only in the previously observed rightmost pixel column; no broader image equality is claimed.
- Bounded matched replays of Reports 1, 2 and 4 also preserve CPU state, RAM and PCM. Their image differences are absent or confined to the same rightmost column. These checks do not replace another complete manual playthrough.
- Settings and native host-OS tests pass. The frozen Windows package passes its installation check without requiring player development tools.

The [Linux/macOS build workflow](https://github.com/ZoomiesZaggy/Space-Channel-5/actions/runs/35258152460) builds the shared optimizations and runs module/installation checks for both x64 and ARM64. The Windows profile is not applied to those platforms. No Linux, macOS, Steam Deck or reporter-hardware gameplay speedup has been measured here. Issue #1 remains open for hardware confirmation.
