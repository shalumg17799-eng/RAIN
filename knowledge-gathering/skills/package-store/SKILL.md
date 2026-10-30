---
name: package-store
version: 1.0.0
description: Writes an assembled Knowledge Package to the artifact object store under packages/<enterprise>/<version>/ as an immutable release and returns the manifest with uris.
dependencies: [package-assembler]
validation:
  required_input: [package]
  required_output: [manifest, package_version, written]
---

# Package store (plan 5.10)

- Input `package`: output of `package-assembler`; optional `prefix` (default `packages`), `overwrite` (default false).
- Writes every file through the run's artifact store (`DIF_ARTIFACT_STORE`): `packages/<enterprise or platform>/<version>/<path>`.
- Immutable: refuses to write when a manifest already exists for that version unless `overwrite` is true.
- Dry run (or no artifact store configured): nothing is written, `written: false`, uris are the planned locations.
- Output `manifest` satisfies contracts/manifest.v1.json (with `uri` and per-file `uri` filled in).
