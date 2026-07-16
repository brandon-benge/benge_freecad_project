# Python CAD Project

This project uses `model.py` and `config.py` as its authoritative design source. One headless build generates exact STEP, IFC4, GLB, conceptual SVG/DXF/PDF drawings, quantities, validation reports, and manifests without FreeCAD or Blender.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r .tools/requirements/runtime.lock
python build.py
```

On Windows, use the executables under `.venv\Scripts`.

Edit project dimensions and materials in `config.py` and build shared elements in `model.py`. Preserve stable semantic IDs. Do not edit `.tools/`, the managed root `build.py` launcher, or files under `generated/`.

Useful commands:

```bash
python build.py --format step
python build.py --format ifc --format quantities
python build.py --validate-only
python build.py --clean
python .tools/update_tools.py
```

The updater entry point lives exclusively under `.tools/`. A normal update preserves project-owned files. Use `python .tools/update_tools.py --force` to restore the template versions of `README.md`, `pyproject.toml`, `.gitignore`, `AGENTS.md`, `opencode.jsonc`, and `.agents/`. Even with force, `model.py`, `config.py`, `project_tests/`, generated outputs, and unknown files are never replaced. Managed-tool fixes must be made in the upstream template repository, not in this installed project.

`generated/` is ignored by Git except for `.gitkeep`. CI should upload generated artifacts instead of committing them.

## Review in the browser

The managed `viewer/` is a static, read-only Babylon.js review app for generated artifacts. It does not use project Python as an input and does not write to `generated/`.

```bash
./start.sh
```

The launcher builds the latest CAD artifacts, installs viewer dependencies on first use, prepares the generated model, and starts the local Vite server. Pass additional Vite options directly, such as `./start.sh --host`.

Run `npm test && npm run build` for production verification. The managed Pages workflow rebuilds the Python artifacts before deploying the viewer. In GitHub, set **Settings → Pages → Source** to **GitHub Actions**. See `viewer/README.md` for offline behavior and full deployment details.

FCStd is optional and truthful: `--include-fcstd` requires FreeCADCmd, creates a compatibility import from shared STEP, and is never the design authority.

Conceptual drawings are not for construction or permitting. This project does not provide engineering, code, permit, survey, or licensed-trade approval.
