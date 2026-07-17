# Prompt 04: Model Imports and Neutral Annotations Report

## Starting Git State

- **Date**: 2026-07-16
- **Branch**: `main`
- **HEAD**: `a82127e feat(migration): set canonical identity, dependency boundary, and platform locks (Prompt 03)`
- **Working tree**: dirty (deleted `.agents/`, `AGENTS.md`, `.opencode/`; untracked backup files and migration plans)

### Recent commits (ancestors of HEAD)

```
a82127e feat(migration): set canonical identity, dependency boundary, and platform locks (Prompt 03)
6e296e0 chore(migration): verify python-cad-tools==0.1.0rc1 candidate intake
9e6609a chore(migration): preserve Benge baseline
df58179 docs: add staged Benge migration prompts
21f828d test(benge_project): update test expectations for added hot tub platform model element
```

## Pre-migration Artifact State

- **236** `complex.*` elements
- **28** `material.complex.*` materials
- All element/material IDs preserved exactly from Prompt 03

## Current Architecture (Pre-migration)

### `config.py`
- Simple typed constants using `FOOT`, `INCH` from `python_cad_tools.units`
- No annotation-related constants
- Door width defined (`DOOR_WIDTH = 6 * FOOT`) but door height is a literal (`7 * cfg.FOOT`) in `model.py`

### `model.py`
- Imports `drawing_annotations` as a side-effect import (`noqa: F401 — registers atexit handler`)
- Uses `7 * cfg.FOOT` literal for door height
- Imported symbols: `BuildContext`, `DesignElement`, `DesignModel`, `Dimensions`, `IfcMapping`, `MaterialSpec`, `Placement`, geometry helpers, units

### `drawing_annotations.py`
- Legacy module (652 lines) with:
  - `atexit` handler registration for post-build mutation
  - Direct SVG XML editing via `xml.etree.ElementTree`
  - Direct DXF editing via `ezdxf`
  - Subprocess support (`drawing_annotations.py --rebuild`)
  - CLI entry point (`main()`, `rebuild_and_annotate()`)
  - Global `PROJECT_DIR`, `GENERATED_DIR`, `SECTION_CUT_X`
  - Filename-based sheet detection
  - Silent skips on missing files/parse errors
  - Duplicated literal values (section cut position, elevation points, schedule content)
  - No PDF annotation support
  - Output written after build manifest is hashed (annotation bytes not in manifest)

### `pyproject.toml` `[tool.python-cad]`
- No `drawing-annotations` entry
- `source-inputs` includes `drawing_annotations.py`

## Installed Package API

- `python-cad-tools==0.1.0rc1` installed in `.venv/lib/python3.13/site-packages/python_cad_tools/`
- Public drawing contract at `python_cad_tools.drawings`: `DrawingAnnotationSet`, `SheetAnnotations`, `SectionCallout`, `ElevationMarker`, `Table`, `TableRow`, `Line`, `Polyline`, `Text`
- `DrawingContext` has `project_root`, `config`, `model`, `sheets`, `length_unit`
- `_project_loader.py` imports `drawing_annotations:build_annotations` when `drawing-annotations` is configured in `pyproject.toml` and validates return via `validate_annotation_set`
- `DrawingExporter.export()` receives annotations separately from model, calls `project_model()` with per-sheet annotations

## Changes to Make

1. Add annotation facts to `config.py` (section cut X, elevation markers, door height)
2. Remove `import drawing_annotations` from `model.py`; use `cfg.DOOR_HEIGHT`
3. Rewrite `drawing_annotations.py` as pure `build_annotations(context: DrawingContext) -> DrawingAnnotationSet`
4. Configure `drawing-annotations` in `pyproject.toml`
5. Add annotation tests
