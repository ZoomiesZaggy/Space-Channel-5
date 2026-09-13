# Player settings and texture packs

Run `Configure-and-play.cmd` with Python 3.10+ installed. Select your original USA GDI. Choose **Build from my disc** if you have not built the port. The launcher downloads the pinned portable LLVM-MinGW compiler automatically, verifies its SHA-256, and keeps it under work/toolchain. Git and Python must be installed. The launcher invokes extraction, dependency setup, generation and compilation. Build failures appear in its log; the original disc is read-only.

Settings are saved atomically to `userdata/settings.ini` and read by the native executable, including through Steam. Environment variables override saved settings; `--gdi` overrides the saved disc path. Diagnostic runners can set `SC5_IGNORE_SETTINGS=1`.

- Volume: 0–100; zero mutes, 100 preserves the original mix.
- Audio buffer: 32–128 ms, default 64. Smaller buffers provide less protection against stalls. This is not a rhythm-judgement offset.
- Fullscreen, resizable window, and 1×–4× initial window size retain the original aspect ratio.
- VSync is optional and off by default; it can add latency.
- Keyboard and controller actions can be remapped independently. Default Space/Backspace aliases remain available unless reassigned.

Settings apply on the next launch. Launch through Steam to retain Steam Input's controller translation. The launcher does not modify Steam configuration.

## Physical timing measurement

Choose **Input/audio measurement test**, or run `build/sc5-native-dev.exe --latency-test`. Each key/controller press requests a brief tone and flashes the display. Escape or the close button exits. The launcher writes `userdata/latency-test.log`.

Use a synchronized recording of physical button movement, display and audible output to measure your setup. Logs only record event handling, presentation submission and the audio callback. They exclude transport, display scanout and speaker delay. This separate probe does not run the game and cannot establish its full rhythm response latency. Automatic gameplay calibration remains pending.

## Texture packs

Place PNG/JPEG replacements at `userdata/mods/MK-51051/<hexadecimal-texture-hash>.png`, then enable texture packs and restart the game. This uses Flycast's texture-hash mechanism. Packs are off by default.

For local authoring, set `SC5_DUMP_TEXTURES=1`. Encountered textures are written to `userdata/texture-dumps/MK-51051/`; filenames identify replacement hashes. These private, game-derived files are ignored by Git. Put your own replacement artwork in the mod directory; do not publish dumped originals.

This supports texture replacement, not executable mods or game-logic hooks. Synthetic replacements were used to verify changed rendering with unchanged machine state.
