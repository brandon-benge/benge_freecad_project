# File Template CAD

This project uses `model.py`, `config.py`, and `drawing_annotations.py` as its
authoritative design source. One headless build generates exact STEP, IFC4, GLB,
conceptual SVG/DXF/PDF drawings, quantities, validation reports, and manifests
without FreeCAD or Blender.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements/locks/dev-py313-macos-arm64.lock
python-cad build
python-cad verify
```

Edit project dimensions and materials in `config.py` and build shared elements in
`model.py`. Preserve stable semantic IDs.

## Installed commands

```text
python-cad validate --project-root PATH [--format FORMAT ...]
python-cad build --project-root PATH [--format FORMAT ...]
python-cad verify --project-root PATH
python-cad clean --project-root PATH
python-cad prepare-site --project-root PATH --destination PATH --base-path PATH
python-cad serve --project-root PATH --host 127.0.0.1 --port PORT [--build]
```

All commands use the installed `python-cad-tools` package. No root build launcher,
start script, or vendored `.tools/` directory is used.

Static analysis and tests:

```bash
ruff check config.py model.py drawing_annotations.py tests/
ruff format --check config.py model.py drawing_annotations.py tests/
mypy config.py model.py drawing_annotations.py tests/
python -m pytest -q
```

## Dependency management

The project pins `python-cad-tools==0.1.0rc1` with four native reproducible locks:

| Lock | Cell |
|------|------|
| `requirements/locks/dev-py312-ubuntu-x86_64.lock` | Ubuntu x86_64, Python 3.12 |
| `requirements/locks/dev-py313-ubuntu-x86_64.lock` | Ubuntu x86_64, Python 3.13 |
| `requirements/locks/dev-py312-macos-arm64.lock` | macOS arm64, Python 3.12 |
| `requirements/locks/dev-py313-macos-arm64.lock` | macOS arm64, Python 3.13 |

Each lock is generated natively in its named cell using `pip-tools` and contains
exact transitive versions and hashes. CI installs only its matching lock.

### Candidate upgrade procedure

1. Obtain the checksum-verified wheel/sdist for the new `python-cad-tools` version.
2. Set `PIP_FIND_LINKS` to the ephemeral directory containing the candidate wheel.
3. Regenerate all four native locks with cache disabled.
4. Verify no lock contains a `file:`, path, or source reference to the candidate.
5. Run the full local static analysis, test, build, verify, site, and browser matrix.
6. Update `pyproject.toml` dependency version and commit all lock changes.
7. After registry publication, regenerate locks from the registry (no `PIP_FIND_LINKS`),
   verify downloaded hashes match the certified handoff, and rerun the full matrix.

## Local-first, remote-deferred

Static analysis, tests, builds, and site preparation all run locally without
contacting GitHub. CI and Pages workflows are defined for remote execution but
every check can be run with the commands above. Workflow-policy and symlink
tests (`tests/test_workflow_policy.py`) run locally without network access.

## Conceptual limitations

Generated drawings are conceptual and not for construction or permitting. This
project does not provide engineering, code, permit, survey, or licensed-trade
approval.

`generated/` is ignored by Git except for `.gitkeep`. CI uploads generated
artifacts instead of committing them.

## Agent governance

See `AGENTS.md` for separation of duties, writable scope, and build/verification
commands. The project uses five roles:

- **file-design-maintainer**: config/model/annotation/test edits
- **file-artifact-reviewer**: read-only artifact review
- **cad-compatibility-verifier**: independent verification
- **save**: exclusive autocommit persistence
