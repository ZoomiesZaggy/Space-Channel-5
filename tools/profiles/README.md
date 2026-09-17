# Windows native execution profile

`windows-x64.profdata.gz` contains LLVM execution counts from a six-billion-instruction Report 3 replay (32.21585472 seconds of device time). It contains function names and profiling metadata/counters, not game assets, RAM, saves or the private checkpoint. Internal function names use relative C filenames; local checkout paths have been removed.

It was collected with the pinned llvm-mingw Clang 23.1.1 compiler, `-O2`, portable x86-64, normal math-errno behavior and `-ffp-contract=off`. The profile helps the compiler arrange and optimize frequently executed branches; it does not skip instructions, change clocks, enable fast-math or introduce runtime compilation.

Uncompressed SHA-256: `f3e0192fa99be1ba10508a0f522a9bbd8a9d2806155ac1458aae5cc19ca8fc0d`.

`build_aot_split.py` automatically uses this profile for the matching default Windows x64 configuration with Clang 23. `--no-profile` disables it for comparisons. `--profile-use` accepts either a raw `.profdata` or a gzip-compressed profile. Other compiler versions and platforms receive the shared-state and clock optimizations without this Windows profile.

To collect new data, build a module using `build_aot_split.py --profile-generate` and otherwise matching release options. Set `LLVM_PROFILE_FILE` to a private directory with `%m` in the filename, then exercise representative scenes using the instrumented modules. Close the game normally to flush the counts. Keep these raw profiles private, then merge them with the matching compiler's `llvm-profdata`:

```text
python tools/merge_native_profiles.py --llvm-profdata <path-to-llvm-profdata> --output tools/profiles/windows-x64.profdata.gz <profile1.profraw> <profile2.profraw>
```

Rebuild all four modules, run `test_release_modules.py` and the native reference suite, and compare matched replays before distributing a replacement profile. The current training scene does not establish a speedup in every scene or on other hardware.
