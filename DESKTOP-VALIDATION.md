# Desktop preview validation

Windows frontend SHA-256: `457a68af8808411a86252b7fd6f72b6e57765314ee01ea8ba5890aa393fb5be3`.

- Rebuilt all four native modules with portable floating-point control and contraction disabled. All 64 native regression tests passed, with zero skips. All four modules passed ABI, unsupported-disc and floating-point checks.
- The seeded opening replay matched the previous validated build exactly in CPU state, all RAM, captured PCM and image.
- The six-billion-instruction Report 3 replay matched CPU state, RAM and PCM between the previous installed build, the new default renderer and interpolation. Image comparison is not claimed across interpolation settings; prior captures showed variation limited to the rightmost pixel column.
- A fresh frozen Windows package imported the original USA disc and executed one billion instructions with zero faults while PATH contained only Windows system directories and Python environment overrides were removed. No compiler or external Python was needed.
- Four settings tests and native host OS contracts passed. The packaged launcher also checks its bundled Tcl runtime, native module files and native executable dependencies without opening a window or importing assets.
- Installation preserved all eight existing private data files, including saves, settings and Steam configuration; the previous binaries were backed up.

## Isolated presentation and audio

Both tests start at the same Report 3 checkpoint, execute six billion instructions and use live audio with the default buffer. Local compilation and the competing game were stopped. These are development-PC measurements, not physical input-to-speaker latency or whole-game performance guarantees.

| Mode | Wall time | Nominal game time | Median presentation interval | 95th percentile | Maximum | Audio underrun frames |
|---|---:|---:|---:|---:|---:|---:|
| Original | 32.210 s | 32.216 s | 32.661 ms | 39.755 ms | 73.194 ms | 0 |
| Interpolation | 32.220 s | 32.216 s | 16.770 ms | 21.446 ms | 54.680 ms | 0 |

Interpolation generated and presented 947 midpoints and their 947 completed frames; 17 frames used fallback. Each run had one interval over 50 ms. Interpolation changes presentation only and remains optional because it can add visual delay and matching artifacts. Earlier tests with another game running produced underruns in both the old and new builds; those were not treated as isolated measurements.

## Platform evidence

The full Linux/macOS host has built in CI. The downloadable-build matrix additionally compiles each platform's actual four native modules, exercises their ABI and FP behavior, freezes the launcher, verifies its installation and uploads archives. Consult the linked run results and release assets for final matrix status. CI build and ABI checks do not establish a full game playthrough, graphics, audio or controller acceptance on Linux/macOS hardware. Those builds remain previews.

The earlier four-report assist-mode playthrough through credits and return to title is recorded in the existing validation history. The new rendering options have matched-scene acceptance, not a fresh exhaustive full-game manual playthrough.
