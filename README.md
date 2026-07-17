# Benge Property CAD

This project uses `model.py`, `config.py`, and `drawing_annotations.py` as its authoritative design source. One headless build generates exact STEP, IFC4, GLB, conceptual SVG/DXF/PDF drawings, quantities, validation reports, and manifests without FreeCAD or Blender.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements/runtime-macos-arm64-py313.lock
python-cad build
```

On Windows, use the executables under `.venv\Scripts`.

Edit project dimensions and materials in `config.py` and build shared elements in `model.py`. Preserve stable semantic IDs.

Useful commands:

```bash
python-cad build --format step
python-cad build --format ifc --format quantities
python-cad validate
python-cad clean
```

`generated/` is ignored by Git except for `.gitkeep`. CI should upload generated artifacts instead of committing them.

## Review in the browser

The managed `viewer/` is a static, read-only Babylon.js review app for generated artifacts.

```bash
python-cad build
python-cad prepare-site --destination site --base-path /
python-cad serve --build
```

Run `npm test && npm run build` for production viewer verification. The managed Pages workflow rebuilds the Python artifacts before deploying the viewer. In GitHub, set **Settings → Pages → Source** to **GitHub Actions**. See `viewer/README.md` for offline behavior and full deployment details.

FCStd is optional and truthful: `--include-fcstd` requires FreeCADCmd, creates a compatibility import from shared STEP, and is never the design authority.

Conceptual drawings are not for construction or permitting. This project does not provide engineering, code, permit, survey, or licensed-trade approval.
