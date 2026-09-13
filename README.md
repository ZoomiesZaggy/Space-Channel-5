# Space Channel 5 — native desktop port

An unofficial ahead-of-time (AOT) port project for the USA Dreamcast version of Space Channel 5. Gameplay runs through offline-generated native modules; the gameplay path does not use an SH4 interpreter or dynamic recompiler fallback. Flycast supplies device, rendering and audio components.

**You must supply your own original USA GDI and its tracks.** Download packages contain the launcher, native host and precompiled translated modules. Players do not install Python, Git or a compiler: extract the package, run SpaceChannel5, select the GDI and choose Play. Original disc assets and private saves are not distributed. This unofficial preview is not affiliated with Sega. See [releases](https://github.com/ZoomiesZaggy/Space-Channel-5/releases) and [platform status](PLATFORM-STATUS.md) for available builds and validation limits.

## Status

The local build completed all four reports, full credits and return to title in an uninterrupted assist-mode run with zero execution faults. Keyboard and Steam Controller operation were confirmed by the tester. The latest frontend passed matched opening and later-report replays and all 16 regression tests on each of four rebuilt modules. This is not a claim of a complete manual playthrough or exhaustive game-path coverage.

Original presentation is approximately 30 FPS. Optional geometry interpolation adds intermediate presentations without advancing game logic, music or input. Display choices include original framing, widescreen fit, crop, stretch and experimental expanded geometry. Prerecorded backgrounds remain 4:3. Interpolation can add up to one 60 Hz interval of visual delay and is off by default. See [the player guide](PLAYER-GUIDE.md) and [performance notes](PERFORMANCE-NOTES.md).

## Developer build on Windows

For a guided build, run `Configure-and-play.cmd`, select your disc, and choose **Build from my disc**. The pinned portable compiler downloads automatically with SHA-256 verification; Git and Python must already be installed. The launcher also saves input, audio and display preferences. See [the player guide](PLAYER-GUIDE.md) and [remaining release work](ROADMAP.md).

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

The extractor opens the supplied disc read-only and writes local ignored files. The AOT generator checks executable hashes and stops on an unsupported revision. Building all four DLLs is resource intensive. The reference and frontend now build in a fresh repository-local workspace. All four modules rebuilt and passed validation; see [release validation](RELEASE-VALIDATION.md).

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
