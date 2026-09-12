# Audio, pacing and response measurements

The 2026-09-12 frontend update starts playback after the first audio block containing sound, using the existing 64 ms buffer. Initial all-zero output is still paced. Generated audio is unchanged. The 44.1 kHz callback now requests 256 frames, and the host checks input/presentation every 100,000 native instructions.

| Measurement | Before | Updated |
|---|---:|---:|
| Fresh opening audio underruns | 3,072 silent frames | 0 |
| Fresh opening 95th-percentile presentation interval | 48.85 ms | 40.33 ms |
| Earlier isolated Report 3 mechanism test, 95th percentile | 46.38 ms | 39.86 ms |
| Same Report 3 test, intervals over 50 ms | 9 | 2 |

The opening comparison uses the exact updated executable. The Report 3 mechanism test uses an earlier staged frontend with the accepted callback and execution-batch changes. Rare long presentation stalls remain; these are scene-specific results, not a guarantee of a perfectly even frame rate throughout the game. Held images during opening transitions also produce long presentation intervals by design.

Six asynchronous SDL key-event probes measured **65.2–105.0 ms** to the callback containing the first changed menu sound. A separate unassisted Report 1 shoot probe changed generated audio after **47.8 ms of game time**. The shoot probe's wall timing was affected by another game and is not an isolated result. The game-time input log has up to 1 ms quantization.

These measurements do **not** measure physical controller transport, Steam Input, Windows endpoint processing or speaker output. They do not establish end-to-end hardware latency.

The opening and Reports 2, 3 and 4 match the previous build in generated PCM, final image, CPU state, device cycles and frame count. Identical-start replays also match all 16 MiB of RAM. Separate fresh boots differ only in the generated flash-settings timestamp and checksum. All 15 CPU, math, disc and input regression tests pass. The AOT game DLLs are unchanged from the completed four-report/credits clean run; the new frontend was checked with matched replays rather than another complete manual playthrough.

Another game started during the later comparisons and consumed substantial CPU/GPU capacity. Those runs remain valid for deterministic equivalence, but their performance numbers are explicitly marked as contended. NVIDIA threading trials were inconclusive for the same reason. Their temporary per-game profile was removed and its absence verified. No graphics-driver override or experimental presentation change is retained.

These measurements describe the local validated build. Raw diagnostic captures and private test artifacts are not published in this source repository.
