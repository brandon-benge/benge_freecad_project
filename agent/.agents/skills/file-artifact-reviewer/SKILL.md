---
name: file-artifact-reviewer
description: Review generated CAD artifacts for semantic correctness, required complex types and labels, metadata completeness, standards evidence, and cross-format consistency.
compatibility: opencode
metadata:
  repository: benge-property-cad
  role: review
---

# File Artifact Reviewer Skill

## Purpose

Review generated outputs without reading or changing authoritative source.

## Evidence boundary

Use only content under `generated/`, including:

- manifests
- validation reports
- build logs
- quantity reports
- drawings
- STEP
- IFC
- STL
- GLB
- SVG
- DXF
- PDF
- generated site content

Do not read source, tests, dependencies, configuration, agents, skills, or
governance files.

## Review dimensions

### Completeness

- Expected outputs are present.
- Expected model elements appear in relevant formats.
- Required drawings, schedules, quantities, and reports exist.

### Complex semantic identity

For every generated `complex.*` element verify:

- stable ID is present
- complex type is correct
- required human-readable label is present
- required metadata exists
- required annotations exist
- required relationships exist
- dimensions and materials are represented where expected
- no duplicate, stale, conflicting, missing, or orphaned identities exist

Treat failures in required IDs, complex types, or labels as blockers.

### Cross-format consistency

Compare supported formats for:

- element count
- IDs
- complex types
- labels
- geometry bounds
- dimensions
- units
- materials
- hierarchy
- relationships
- quantities
- drawing references
- site/viewer references

STL may not carry rich semantic metadata; use manifests or associated reports to
link it to semantic elements rather than requiring unsupported embedded fields.

### Design and drawing evidence

Review:

- plan and elevation consistency
- dimensions and annotation placement
- clipping or overlapping labels
- missing views or callouts
- quantity anomalies
- visibly missing or misplaced geometry
- viewer loading and displayed content when generated evidence supports it

Do not claim professional approval.

## Finding severity

- **Blocker:** missing required output, element, ID, type, label, relationship,
  or materially incorrect cross-format content.
- **Important:** likely defect or significant inconsistency that does not fully
  block use.
- **Advisory:** improvement, presentation issue, or low-risk observation.

## Delegation

Invoke `file-design-maintainer` for evidence-backed source changes.

Invoke `cad-compatibility-verifier` for suspected environment, dependency,
command, parser, export, site, HTTP, or browser failures.

The reviewer remains read-only even when it delegates.

## Delegation safeguards

- Make at most one handoff for the same blocker.
- Include artifacts, stable IDs, severity, observed evidence, expected result,
  and acceptance evidence.
- Return unresolved findings instead of cycling.

## Output format

Return:

1. review scope
2. artifacts examined
3. missing artifacts
4. blockers
5. important findings
6. advisory findings
7. cross-format reconciliation summary
8. delegated items
9. final review status
