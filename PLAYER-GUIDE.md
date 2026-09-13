# Player settings and texture packs

For a download package, extract it and run **SpaceChannel5** (the application bundle on macOS). Select your original USA GDI, keeping all its track files together, then choose **Play**. The launcher validates and imports the supported executable files automatically. No Python, Git or compiler is required, and the original disc is read-only. Keep the disc available for background video, music and other assets during play.

Windows downloads keep imported files and `userdata` beside the launcher. macOS uses `~/Library/Application Support/SpaceChannel5`; Linux uses `$XDG_DATA_HOME/SpaceChannel5` or `~/.local/share/SpaceChannel5`. Preserve `userdata` when updating. Only one game can use a save directory at once.

Developers running the source launcher through `Configure-and-play.cmd` need Python and Git; **Build from my disc** downloads and verifies the portable compiler and builds locally.

Settings are saved atomically to `userdata/settings.ini` and read by the native executable, including through Steam. Environment variables override saved settings; `--gdi` overrides the saved disc path. Diagnostic runners can set `SC5_IGNORE_SETTINGS=1`.

- Volume: 0–100; zero mutes, 100 preserves the original mix.
- Audio buffer: 32–128 ms, default 64. Smaller buffers provide less protection against stalls. This is not a rhythm-judgement offset.
- Fullscreen, resizable window, and 1×–4× initial window size are configurable.
- VSync is optional and off by default; it can add latency.
- Keyboard and controller actions can be remapped independently. Default Space/Backspace aliases remain available unless reassigned.

Settings apply on the next launch. Launch through Steam to retain Steam Input's controller translation. The launcher does not modify Steam configuration.

## Display options

Original 4:3 is the default. Widescreen fit preserves the whole picture with sidebars. Fill crops the top and bottom and can hide HUD elements. Stretch fills the window with altered proportions. Expanded 16:9 is experimental: it widens the geometry projection and clipping region while keeping the HUD centered. It can reveal geometry the game already submitted, but cannot restore objects culled by game logic. Prerecorded backgrounds retain their original 4:3 image; no new background artwork is generated.

Optional motion interpolation inserts matched geometry midpoints for a 60 Hz presentation target. Videos retain their original cadence, and unmatched or discontinuous geometry falls back to the original frame. It does not change game logic, input or music timing. It can add up to about 17 ms of visual delay; leave it off if you prefer the original response or notice artifacts. It is not arbitrary-refresh interpolation.

## Physical timing measurement

Choose **Input/audio measurement test**, or run `build/sc5-native-dev.exe --latency-test`. Each key/controller press requests a brief tone and flashes the display. Escape or the close button exits. The launcher writes `userdata/latency-test.log`.

Use a synchronized recording of physical button movement, display and audible output to measure your setup. Logs only record event handling, presentation submission and the audio callback. They exclude transport, display scanout and speaker delay. This separate probe does not run the game and cannot establish its full rhythm response latency. Automatic gameplay calibration remains pending.

## Texture packs

Place PNG/JPEG replacements at `userdata/mods/MK-51051/<hexadecimal-texture-hash>.png`, then enable texture packs and restart the game. This uses Flycast's texture-hash mechanism. Packs are off by default.

For local authoring, set `SC5_DUMP_TEXTURES=1`. Encountered textures are written to `userdata/texture-dumps/MK-51051/`; filenames identify replacement hashes. These private, game-derived files are ignored by Git. Put your own replacement artwork in the mod directory; do not publish dumped originals.

This supports texture replacement, not executable mods or game-logic hooks. Synthetic replacements were used to verify changed rendering with unchanged machine state.

## Native mods (experimental)

The launcher’s Mods tab lets you choose one trusted native mod DLL. Leave the field empty, or select Disable native mod and save, for ordinary play. Restart the game after changing this selection. See NATIVE-MODS.md for the developer API and its current limits.

## Rhythm calibration

Use **Rhythm timing offset** in the launcher, save, and restart the game. The default is **0 ms**. Positive values move the response window later; negative values move it earlier. Try small changes such as 25 ms while playing a familiar section. The supported range is −250 to +250 ms.

This adjusts the game’s input-task timing against its current music tempo. It does not speed up the game or change the music playback clock, and it does not intentionally widen the original note windows. Judgments still have the original game-frame granularity. Input-related feedback and missed-note processing follow the shifted input timing.

The separate Input/audio measurement test is a measurement aid; it does not choose this setting automatically. The automated tests establish that the judging window moves, not the right value for your display, speakers or controller.
