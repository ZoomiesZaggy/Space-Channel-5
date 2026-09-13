# Contributing

Bug reports, documentation improvements and platform testing are welcome. For code changes, describe the problem, resulting behavior and validation. Keep unrelated changes separate.

## Report a problem

Use the repository's bug report form. Include the release version, operating system, CPU/GPU, input device, affected report or menu, and reproduction steps. State whether the problem also occurs with original framing and interpolation disabled. Logs can contain local paths; review them before sharing. Do not attach disc images, extracted game files or private saves.

## Build and test

See [BUILDING.md](BUILDING.md). Run checks appropriate to the change. Settings changes should pass `python -m unittest discover -s tools -p test_player_config.py`; host portability changes should pass `python tools/test_native_host_os.py`. Native game/module changes need relevant regression and matched-replay evidence using your own supported disc.

Describe the hardware and platform actually tested. A successful compile or module check is not a complete gameplay test. Preserve the original game timing when changing presentation, and document experimental behavior clearly.

## Source and assets

Retain existing licenses and attribution. Do not commit original game assets, disc tracks, extracted executables, VMUs, checkpoints, credentials or personal settings. See [source provenance](SOURCE-PROVENANCE.md).
