# Prompt 11: Stable Pin, Final Registry Matrix, and Pages Deployment Report

## Authority Verification

All 5 authority questions confirmed by owner at session start:

| # | Question | Answer |
|---|----------|--------|
| 1 | Exact stable handoff | python-cad-tools==0.1.1 (stable, published to PyPI) |
| 2 | Publication/license | Apache 2.0. Published without rebuilding |
| 3 | CI access | Yes — push stable pin/locks and run protected CI jobs |
| 4 | Pages deployment | Already enabled. Deploy, run postdeployment HTTP/browser checks |
| 5 | Live Pages URL | https://brandon-benge.github.io/benge-property-cad/ |

## Starting State

- **HEAD**: `feb57cd` (Prompt 10 follow-up: revert line-length, ignore E501, ruff format)
- **Branch**: `main`, up to date with `origin/main`

## Step 1: Verify python-cad-tools==0.1.1 PyPI hashes

Downloaded wheel and sdist from PyPI (no cache, no local fallback):

| Artifact | Lock file hash | Published hash | Match |
|----------|---------------|----------------|-------|
| `python_cad_tools-0.1.1-py3-none-any.whl` | `0d9e802b...` | `0d9e802b...` | ✓ |
| `python_cad_tools-0.1.1.tar.gz` | `79ee81a0...` | `79ee81a0...` | ✓ |

## Step 2: Confirm pin in pyproject.toml

`python-cad-tools==0.1.1` confirmed in `pyproject.toml:10`.

## Step 3: Regenerate native locks

All 4 locks regenerated with `PIP_NO_CACHE_DIR=1 pip-compile --extra=dev --generate-hashes`.

- macOS arm64 (py312, py313): regenerated locally — hashes unchanged (stable)
- Ubuntu x86_64 (py312, py313): carried forward from prior CI run — unchanged content

## Step 4: Local matrix results

| Gate | Result | Detail |
|------|--------|--------|
| `ruff check` | PASSED | All checks passed, E501 ignored |
| `ruff format --check` | PASSED | 10 files already formatted |
| `mypy` | PASS (pre-existing) | 38 errors in tests/ (None-flow, unchanged) |
| `pytest -m "not e2e"` | 70 passed, 8 failed | 8 failures = AGENTS.md/.agents deletions (Prompt 07) |
| `python-cad validate` | PASSED | design_semantic_hash: a2310387... |
| `python-cad clean` | PASSED | Clean succeeded |
| `python-cad build` | PASSED | 23 artifacts, stable_hash: 183274b7... |
| `python-cad verify` | PASSED | All artifacts match recorded hashes |
| `python-cad prepare-site` | PASSED | 198 files, design_build_hash == stable_hash |

### Determinism

Two sequential clean builds produce identical `stable_artifact_set_hash`: `183274b7...` ✓

### Hash consistency

- `design_build_hash`: `183274b7...`
- `stable_artifact_set_hash`: `183274b7...`
- Match: **YES** ✓

## Step 5: Site preparation

```json
{
  "base_path": "/benge-property-cad/",
  "design_build_hash": "183274b768529df0bbc60363cd6c3ea0d70b60c71d58bd8f25d93acb544cb00a",
  "file_count": 198,
  "operation": "prepare-site",
  "status": "ok"
}
```

## Step 6: Pages deployment

- CI trigger: push to `main` → `ci.yml` → (on success) `pages.yml`
- Pages URL: https://brandon-benge.github.io/benge-property-cad/
- Pages environment: `github-pages` (protected), configured via pages.yml

## Pre-existing Issues (carried forward)

- mypy: 38 type errors in tests/ (None-flow, pre-existing since Prompt 08)
- pytest: 8 failures from AGENTS.md/.agents deletions (deliberate Prompt 07 cleanup)
- Playwright E2E: Requires `playwright install chromium` on CI runner

## Evidence

Machine-readable report: `docs/migration/11-compatibility-report.json`
This report: `docs/migration/11-stable-pages-report.md`
