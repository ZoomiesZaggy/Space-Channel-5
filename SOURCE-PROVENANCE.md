# Source provenance

This source publication comes from the locally validated native Windows development project dated 2026-09-12.

- Device/render/audio reference: https://github.com/flyinghead/flycast at `eddf2635867f0f16f64bebd3185db151c99c551c`.
- `tools/setup_reference.py` fetches that revision and applies `reports/flycast-reference.patch`. The complete upstream checkout is reconstructed locally; upstream license notices are retained in `licenses/flycast-source/`.
- The bundled Forge decoder and supporting sources retain their original MIT notice in `prototype/Dreamcast-Forge/LICENSE`.
- Host, generator, timing tables and build tools are included under `tools/`. Per-file notices and third-party licenses take precedence where applicable.
- The publication changes build workspace paths to repository-local `work/`, removes the private default disc path, and deduplicates observed instruction addresses. Runtime source behavior is unchanged.

Release packages include precompiled translated native modules. Their corresponding generated C is supplied separately as `native-aot-source.tar.gz`; `tools/build_release_modules.py` verifies the archive and builds it. The source repository contains the generator, host modifications, pinned dependency fetch scripts and build instructions. No original disc tracks, extracted executables, private VMUs, checkpoints, audiovisual captures, machine-specific launch logs or credentials are published. Players import supported assets from their own disc. The user's playable installation is separate from this source checkout.
