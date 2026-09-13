# Rhythm calibration — 2026-09-12

Validated frontend SHA-256: `71c639ea7aedc29f54e0026cd252be11fa1349839537457d5c6cc3408138c44c`.

The host now offers a manual −250..+250 ms rhythm offset, defaulting to zero.
It changes the beat-clock value consumed by the USA game's input task, using
the current tempo. It leaves the shared music clock and input-delivery path
unchanged. This is a judging-time adjustment, not a scripted-input delay.

## Identified game path

Matched no-input and shoot-input RAM traces first diverged at the raw controller
buffers, `8c18fe48` and `8c190248`. Static references and dispatcher observations
then located the input task and note-judgment paths:

- `8c022340`: input-task update.
- `8c01e6e2`: shared beat-clock getter.
- `8c022362`: return to the input task, before its private clock copy is made.
- `8c02192e` and `8c021b2c`: note-processing paths.
- `8c021740`: judgment result update; the tested single direction note used
  result 2 for a miss and 3 for a correct response.

The calibration hook validates the consumer instructions and return address.
It reads the music state through `8c10a998`, then the active tempo queue slot.
The command's numerator/denominator specify beats per nominal song frame.
The offset in beat units is `milliseconds * 0.03 * numerator / denominator`.
Only the returned floating-point clock value is adjusted. At zero, the hook
does not inspect or modify game memory or registers.

This moves input-task phase and missed-note processing as well as response
windows; input-related feedback follows that timing. It does not interpolate
frames or remove the original frame-level timing granularity.

## Gameplay boundary tests

Starting from the same paused Report 1 checkpoint, tests unpaused at 1000 ms and
injected a Right pulse for the first response. A pulse at 1900 ms produced a
miss at 0 ms calibration and a correct response at +100 ms, with judgment at
1943.863 and 1943.865 ms of emulated time respectively.

An initial 63-case sweep and a 12-case final-build boundary check exercised
negative, zero and positive offsets. On the 25 ms sampling grid:

| Calibration | First accepted pulse | Last accepted pulse | Adjacent rejected pulses |
|---|---:|---:|---|
| −100 ms | 1575 ms | 1775 ms | 1550, 1800 ms |
| 0 ms | 1675 ms | 1875 ms | 1650, 1900 ms |
| +100 ms | 1775 ms | 1975 ms | 1750, 2000 ms |

The sampled acceptance range shifted by exactly 100 ms without changing its
sampled width. This establishes behavior for the tested note, not physical
controller/display/speaker latency or every note in a manual playthrough.

## Regression and defensive checks

- Zero-offset opening replay: CPU state, all RAM, PCM and final image exactly
  match the preceding validated build.
- Report 3 completed six billion instructions with +100 ms enabled.
- Final-build Report 2 at −250 ms and Report 4 at +250 ms each completed two
  billion instructions without a native coverage fault or calibration error.
- Fourteen asset-free C++ checks cover both signs, bounds of the supported
  offset range, a different tempo, preservation of other CPU state, zero-offset
  bypass, wrong call site/code, bad queue index, zero denominator and invalid
  music/command pointers. Run `python tools/test_native_calibration.py`.
- Final zero-offset Report 3 replay also matches CPU state, RAM, PCM and image exactly, with zero audio underruns. Its maximum frame interval remains 72.86 ms; calibration does not resolve the game-frame gap.
- Loading +100 ms from saved settings reproduced the correct judgment; a saved 251 ms value was rejected.
- Settings tests cover negative persistence and rejection of malformed or
  out-of-range offsets.

The asset-free checks can also compile with a platform C++ compiler using
`--compiler c++`. Their Linux/macOS CI jobs validate this small component;
they are not native game builds or evidence of a completed platform port.

## Reproducing dispatcher observations

Set `SC5_PC_TRACE` to a local CSV path and optionally `SC5_PC_TRACE_MIN` and
`SC5_PC_TRACE_MAX` to an exclusive address range. The trace records registers
and emulated cycles at AOT dispatcher entries. Intra-page execution can bypass
the dispatcher, so this is not a complete instruction trace. The output is
capped at 100,000 entries and the log reports dropped entries. Traces and game
memory snapshots remain local and are not included in the source repository.
