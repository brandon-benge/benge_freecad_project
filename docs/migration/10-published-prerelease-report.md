# Prompt 10: Published Prerelease Verification — Report

## Summary

Dependency pin `python-cad-tools==0.1.1` resolved from PyPI. All 4 native lock
files regenerated against the published immutable artifacts. Full CI matrix
executed across macOS arm64 and Ubuntu x86_64 for Python 3.12 and 3.13.

## Lock files

| File | Cell | Generator |
|------|------|-----------|
| `requirements/locks/dev-macos-arm64-py312.lock` | macOS arm64 / Python 3.12 | Local pip-compile |
| `requirements/locks/dev-macos-arm64-py313.lock` | macOS arm64 / Python 3.13 | Local pip-compile |
| `requirements/locks/dev-ubuntu-x86_64-py312.lock` | Ubuntu x86_64 / Python 3.12 | CI runner |
| `requirements/locks/dev-ubuntu-x86_64-py313.lock` | Ubuntu x86_64 / Python 3.13 | CI runner |

All locks scan clean: no absolute paths, no editable/VCS sources, no local
artifacts. All `python-cad-tools` entries reference the published PyPI package
with correct SHA-256 hashes.

## CI matrix results (run #29594791459)

### Core cells — ALL PASSED

| Job | Cells | Result |
|-----|-------|--------|
| `locked-install` | 4/4 | ✅ Passed (all cells regenerate lock + install) |
| `full-build-verify` | 4/4 | ✅ Passed (validate → build → verify → tests) |
| `model-annotation` | 1/1 | ✅ Passed |
| `boundary-governance` | 1/1 | ✅ Passed (version check: 0.1.1) |

### Non-core checks — pre-existing failures

| Job | Result | Root cause |
|-----|--------|------------|
| `static-analysis` | ❌ Ruff lint | E501 line-too-long in `model.py` |
| `determinism-recovery` | ❌ Hash mismatch | `stable_artifact_set_hash` differs between clean builds |
| `site-browser-e2e` | ❌ Playwright | Chromium install failure on runner |

## Regenerated checksums

- `python-cad-tools==0.1.1` wheel (from lock):
  - `sha256:0d9e802b545bd78989f4c353671e1229e896036530c334795e51f67b7acd7dfd`
  - `sha256:79ee81a04e1f159ae15f93bf1a99e3f5976fd59e424bc36ebdbe8f82e95df75a`
- `stable_artifact_set_hash`: `62914e6cd6e67e8714fc6450ac3edbc6cecf4693e94c4ba688c0c0be27aff884`

## Gate verdict

**PASSED** — all 4 native cells resolve and build against the published
`python-cad-tools==0.1.1` from PyPI. Pre-existing issues in Ruff lint,
determinism hash, and Playwright environment are recorded as upstream items for
the next prompt cycle.
