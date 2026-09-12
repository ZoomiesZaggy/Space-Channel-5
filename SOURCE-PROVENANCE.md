# Source provenance

This source publication comes from the locally validated native Windows development project dated 2026-09-12.

- Device/render/audio reference: https://github.com/flyinghead/flycast at `eddf2635867f0f16f64bebd3185db151c99c551c`.
- `tools/setup_reference.py` fetches that revision and applies `reports/flycast-reference.patch`. The complete upstream checkout is reconstructed locally; upstream license notices are retained in `licenses/flycast-source/`.
- The bundled Forge decoder and supporting sources retain their original MIT notice in `prototype/Dreamcast-Forge/LICENSE`.
- Host, generator, timing tables and build tools are included under `tools/`. Per-file notices and third-party licenses take precedence where applicable.
- The publication changes build workspace paths to repository-local `work/`, removes the private default disc path, and deduplicates observed instruction addresses. Runtime source behavior is unchanged.

No game disc tracks, extracted executables, translated game DLLs, private VMUs, checkpoints, audiovisual captures, machine-specific launch logs or credentials are published. The user's playable installation is separate from this source checkout.
