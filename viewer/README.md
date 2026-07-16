# Generated Design Viewer

This is a static, read-only Babylon.js viewer for artifacts produced by `python build.py`. It never reads Python source, executes project code, or writes to `generated/`. The preparation step copies supported generated files into the Vite public directory and creates a download manifest from the filenames that actually exist.

## Local development

From the repository root, launch the viewer:

```bash
./start.sh
```

The root launcher builds the latest CAD artifacts, installs dependencies on first use, prepares the generated model, and starts Vite. Open the URL printed by Vite. The viewer supports mouse, keyboard, touch, pinch zoom, two-finger pan, responsive orientation changes, and desktop/mobile property panels. CAD X/Y/Z axes are visible by default and can be toggled from the camera toolbar. The Units control switches every displayed measurement between adaptive metric and US customary units. Selection properties report the element origin and occupied X/Y/Z extents from generated metadata.

Production verification:

```bash
cd viewer
npm test
npm run prepare-model
npm run test:model
npm run build
npm run preview
```

`prepare-model` requires one generated GLB plus `generated/manifests/build-manifest.json` and `generated/manifests/design-elements.json`. It verifies every artifact referenced by the build manifest, discovers optional STEP, IFC, SVG, DXF, PDF, JSON, and CSV files, and copies only supported artifacts. Override locations for isolated testing with `--source` and `--destination`.

## GitHub Pages

`.github/workflows/pages.yml` runs the Python build, prepares viewer assets, tests and builds the viewer, and deploys `viewer/dist`. In the GitHub repository, choose **Settings → Pages → Build and deployment → Source: GitHub Actions**. The workflow derives Vite's base path from the repository name, so an installed project named `benge_freecad_project` deploys at:

```text
https://brandon-benge.github.io/benge_freecad_project/
```

The service worker caches the application and generated artifacts after the first successful visit. Browsers can then reopen already-cached designs offline. A new deployment replaces the application cache; large model files still require enough browser storage.

## Architecture

- `scripts/prepare-model.mjs` is the build-time, read-only artifact ingestion boundary.
- `src/viewer/` owns artifact parsing, semantic metadata resolution, Babylon scene setup, camera behavior, and selection.
- `src/ui/` renders the model tree, drawings, downloads, build information, and properties without a framework.
- `src/types/` defines generated-artifact contracts.
- `public/model/` contains ignored copied artifacts, never authoritative design data.

Element selection resolves stable IDs from glTF extras first, then joins against `design-elements.json` and quantity records. Mesh names are not used as semantic authority. Helper meshes without stable IDs are not selectable. Generated materials are preserved.
