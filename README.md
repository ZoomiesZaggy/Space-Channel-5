# Space Channel 5 — native Windows development port

An unofficial Windows x64 ahead-of-time (AOT) port project for the USA Dreamcast version of Space Channel 5. Gameplay runs through offline-generated native DLLs; the gameplay path does not use an SH4 interpreter or dynamic recompiler fallback. Flycast supplies device, rendering and audio components.

**This repository contains source and build tools. You must supply your own original USA GDI and its tracks.** Disc images, extracted game code, generated game DLLs, compiled binaries and private saves are not included. This is a development project, not a ready-to-run download, and is not affiliated with Sega.

## Status

The local build completed all four reports, full credits and return to title in an uninterrupted assist-mode run with zero execution faults. Keyboard and Steam Controller operation were confirmed by the tester. The latest frontend passed matched opening and later-report replays and all 15 regression tests. This is not a claim of a complete manual playthrough or exhaustive game-path coverage.

Tested later-report scenes run at about 30 presented FPS. The latest startup test had zero audio underruns. Occasional long frame stalls remain; physical controller-to-speaker latency has not been measured. See [performance notes](PERFORMANCE-NOTES.md).

## Build on Windows

Requirements: Git, Python 3.10+, and LLVM-MinGW 20260908 x64 UCRT. Extract the portable toolchain below `work/toolchain/` so its compiler is at `work/toolchain/<toolchain-folder>/bin/clang.exe`. The reference setup installs pinned CMake and Ninja into `work/build-tools/` and downloads the pinned upstream source and submodules. Run commands from the repository root.

```powershell
$env:SC5_GDI = 'X:\path\Space Channel 5 (USA).gdi'
python tools/inspect_disc.py "$env:SC5_GDI" --out .
python tools/inspect_assets.py
python tools/setup_reference.py
$sc5cc = (Get-ChildItem 'work/toolchain/*/bin/clang.exe').FullName
python tools/generate_static_timing.py --reference 'work/flycast-reference'
New-Item -ItemType Directory -Force build | Out-Null
python tools/build_round_aot.py --cc $sc5cc --opt 2 --round 1 --round 2 --round 3 --round 4
Copy-Item build/native-diff-round1.dll build/native-diff.dll
python tools/build_native_app.py
.\Start-native-development.cmd "$env:SC5_GDI"
```

The extractor opens the supplied disc read-only and writes local ignored files. The AOT generator checks executable hashes and stops on an unsupported revision. Building all four DLLs is resource intensive. Build scripts were used for the local port; this newly published repository layout has received static checks, not a fresh full rebuild.

`reports/observed-roots.json` contains deduplicated observed instruction addresses used by the generator, not game executable bytes. Unsupported execution targets stop and require an offline coverage expansion and rebuild. Additional diagnostic scripts under `tools/` may require locally generated reports or checkpoints.

## Controls

| Action | Keyboard |
|---|---|
| Start / pause | Enter |
| Directions | Arrow keys |
| Shoot / Dreamcast A | Z or Space |
| Rescue / back / Dreamcast B | X or Backspace |
| Dreamcast X | A |
| Dreamcast Y | S |

SDL game controllers are supported. For Steam Controller, add `build/sc5-native-dev.exe` as a non-Steam game, set launch options to `--gdi "X:\path\Space Channel 5 (USA).gdi"`, enable Steam Input and select a gamepad layout. Disable desktop configuration in the launcher if it replaces gamepad inputs. Launch through Steam. VMU saves are stored locally in `userdata/`.

## Source and licensing

See [source provenance](SOURCE-PROVENANCE.md) and the retained notices in `licenses/` and `prototype/Dreamcast-Forge/LICENSE`. Flycast-derived components are GPL-2.0-or-later; Forge retains its MIT license. The GPL text is included in `LICENSE`. Sega game content is not covered by these source licenses or distributed here.
