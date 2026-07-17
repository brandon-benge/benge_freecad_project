# Prompt 03: Identity and Dependency Boundary Report

## Starting Git State

- **Date**: 2026-07-16
- **Branch**: `main`
- **HEAD**: `6e296e0 chore(migration): verify python-cad-tools==0.1.0rc1 candidate intake`
- **Working tree**: dirty (deleted `.agents/`, `.opencode/`, `AGENTS.md`, `opencode.jsonc`; untracked backup files and migration plans)

### Recent commits (ancestors of HEAD)

```
6e296e0 chore(migration): verify python-cad-tools==0.1.0rc1 candidate intake
9e6609a chore(migration): preserve Benge baseline
df58179 docs: add staged Benge migration prompts
21f828d test(benge_project): update test expectations for added hot tub platform model element
ffad4de feat(agents): enable direct user invocation of Python CAD Architect and add runtime sync tool
52e1a7e feat(annotations): add post-processing module for CAD drafting annotations
ad23790 feat(ui): add start.sh viewer launcher and improve executable management
ca863a9 chore(config): remove params.yaml template and add mypy config
453dc2f feat(viewer): add measurements module and centralize agent definitions
9edc99a chore(config): update configure-pages action to v6
```

## Baseline References

- **Baseline head**: `df58179d506e52dd6cb771afd7b5b719a086cfc3` (per fixtures/contract)
- **Candidate wheel**: `python-cad-tools-0.1.0rc1-py3-none-any.whl`
- **Wheel SHA-256**: `fbc30d4adbe0be42e1315a90a6e0f93fc60d2037976523b9919fa487e9b23b49`
- **Candidate reference**: `docs/migration/candidate-reference.json`
- **External preservation bundle**: `benge-property-cad-migration-preservation/20260716T132948-0400-benge-preservation/`

## Changes Made in Prompt 03

### 1. pyproject.toml — project identity and tool configuration

- Project name: `benge-property-cad` (was `python-cad-project`)
- Added `[tool.python-cad]` schema with required identity fields
- Added `python-cad-tools==0.1.0rc1` migration pin
- Added dev dependencies (ruff, mypy, pytest-cov)
- Configured Ruff, mypy, pytest rules
- Removed `[tool.pytest.ini_options].pythonpath` (no `.tools` injection)
- Removed `[tool.mypy].mypy_path` (no `.tools` injection)
- Added `packages = []` to disable package discovery for flat modules

### 2. Model identity migration

- Model ID: `functional.benge_complex` → `benge.property`
- Model name: `BengeComplexFunctional` → `Benge Property`
- Project tag: `complex-functional` → `benge-property`
- Source module: `functional.benge_complex.model` → `model`
- Artifact stem: `BengeComplexFunctional` → `BengeProperty`
- Source authority: real project authority with build-provided Git revision
- Preserved all `complex.*` element IDs (exactly)
- Preserved all `material.complex.*` material IDs (exactly)

### 3. Dependency lock files

- macOS arm64 Python 3.12 and 3.13 hashed locks generated
- Ubuntu lock placeholders added (contents left pending)

### 4. Contract fixture regeneration

- `tests/fixtures/model_contract_v1.json` regenerated via `verify_model_contract_v1.py --write`
- New fixture confirms:
  - `model_id`: `benge.property`
  - `model_name`: `Benge Property`
  - `artifact_stem`: `BengeProperty`
  - `project_tag`: `benge-property`
  - `source_module`: `model`
  - 236 elements (all `complex.*`), 28 materials (all `material.complex.*`) — unchanged
- Fixed `dirty=False` → `source_dirty=False` in `_load_baseline_model` for candidate API compatibility

### 5. CI workflow updates

- `build-design.yml`: renamed to `Build Benge Property design`, updated pip install to `requirements/dev-ubuntu-x86_64-py313.lock` (with PENDING guard), replaced deterministic-hash verification with ruff/mypy/pytest
- `pages.yml`: renamed to `Build and deploy Benge Property design viewer`, updated pip install to `requirements/runtime-ubuntu-x86_64-py313.lock` (with PENDING guard), replaced `python build.py` with `python-cad build`

### 6. README update

- Full rewrite for `Benge Property CAD` identity
- Removed all `.tools/` references (no `build.py`, `start.sh`, `.tools/requirements/`, `update_tools.py`)
- Install: `.venv/bin/pip install --require-hashes -r requirements/runtime-macos-arm64-py313.lock`
- Build: `python-cad build`
- Viewer: `python-cad build && python-cad prepare-site --destination site && python-cad serve --build`
- Removed "managed-tool" template wording; legacy launchers retained on disk

### 7. Legacy launchers retained (not deleted)

## Gate Checkpoint Results

- [x] Installed-candidate model loads without source-path tricks
- [x] Canonical model identity is exact
- [x] Golden stable-ID sets are unchanged (236 elements, 28 materials)
- [x] Local native locks are reproducible and path-free (macOS arm64; Ubuntu PENDING)
- [x] Focused lint/type/tests pass
