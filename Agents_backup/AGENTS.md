# File Template CAD — Agent Governance

## Repository boundary

This repository is `file-template-cad`. It owns the template-specific design,
including:

- design parameters and dimensions
- geometry composition
- materials and annotations
- project tests
- dependency pins and locks
- CI and GitHub Pages deployment
- repository documentation and agent governance

The repository consumes `python-cad-tools` as an installed PyPI package.

Never copy, vendor, unpack, patch, or modify `python-cad-tools` source or
`site-packages`. Never install it from a local checkout or as an editable
package. When the public package lacks required behavior, report an upstream
requirement instead of creating a local tooling fork or workaround.

## Authoritative design source

The authoritative editable design files are:

- `config.py`
- `model.py`
- `drawing_annotations.py`
- `tests/`

Generated files under `generated/` are disposable evidence and must never be
edited directly.

Keep geometry parametric. Use only documented public `python_cad_tools` APIs.
Preserve stable semantic IDs, including existing `complex.*` IDs, unless an
intentional migration is part of the request. Create or update geometry and its
metadata together.

## Agents and responsibilities

| Agent | Responsibility | May modify |
|---|---|---|
| `file-design-maintainer` | Implement and test template-design changes | `config.py`, `model.py`, `drawing_annotations.py`, `tests/` |
| `file-artifact-reviewer` | Review generated outputs and report design-quality findings | Nothing |
| `cad-compatibility-verifier` | Verify the installed PyPI package, environment, commands, and compatibility | Nothing |
| `save` | Persist already-verified changes through `specrepo-autocommit` | Only through its dedicated tool |

## Collaboration

The three working agents may call one another when the receiving agent owns the
next required responsibility:

- `file-design-maintainer` may call `file-artifact-reviewer` to evaluate
  regenerated outputs.
- `file-design-maintainer` may call `cad-compatibility-verifier` to validate the
  installed package, environment, or declared project checks.
- `file-artifact-reviewer` may call `file-design-maintainer` when its evidence
  requires source changes.
- `file-artifact-reviewer` may call `cad-compatibility-verifier` when an
  artifact problem appears environmental or toolchain-related.
- `cad-compatibility-verifier` may call `file-design-maintainer` when a verified
  blocker belongs to the parent project's editable design source.
- `cad-compatibility-verifier` may call `file-artifact-reviewer` when generated
  output requires specialist review.

Delegation must be bounded:

1. Make at most one handoff for the same distinct blocker.
2. Include the observed evidence, affected artifacts or files, expected result,
   and acceptance evidence.
3. Do not invoke the agent that called you again unless new source changes,
   regenerated outputs, or new verification evidence justify one final review.
4. Return unresolved blockers to the caller rather than repeating a delegation
   cycle.
5. No working agent may invoke `save`.

`permission.task` in `opencode.jsonc` is the enforcement layer for model-driven
delegation. This file describes expected behavior but is not an authorization
boundary.

## File Design Maintainer

The design maintainer:

- edits only the authoritative design source and tests
- uses only public installed `python_cad_tools` APIs
- does not inspect or patch package source or `site-packages`
- preserves stable semantic IDs
- runs applicable tests, build, validation, and verification after changes
- delegates artifact or compatibility review when needed
- never invokes Git, `specrepo-autocommit`, or `save`

When required functionality is unavailable from the installed public package,
return an upstream `python-cad-tools` requirement with evidence.

## File Artifact Reviewer

The artifact reviewer is read-only and may inspect only content under
`generated/`, including artifacts, manifests, drawings, reports, logs, and site
content.

It must not:

- read Python source, tests, dependency files, agent files, or governance files
- edit files
- run shell commands
- infer implementation details that are not evidenced by generated output
- invoke `save`

Classify findings as blocker, important, or advisory. For each finding, report
the affected artifact and stable IDs, the observed issue, expected result,
recommended responsibility owner, and acceptance evidence.

## CAD Compatibility Verifier

The compatibility verifier is read-only. It operates against the current
project and installed environment.

It must:

- use the pinned `python-cad-tools` package from PyPI
- use the dependency lock matching the active platform and Python version
- inspect the current environment before changing it
- create a temporary Python environment only when isolation is required by the
  declared verification workflow
- verify the installed distribution version and resolved module path
- run the project-declared static, test, build, validation, verification, site,
  HTTP, and browser checks as applicable
- produce a machine-readable compatibility report

It must not:

- clone, archive, copy, vendor, unpack, or duplicate either repository
- install `python-cad-tools` from a source checkout or in editable mode
- edit source, tests, configuration, locks, workflows, generated output, agents,
  or governance
- fix failures during the verification run
- invoke Git, `specrepo-autocommit`, or `save`

It may read public remote package documentation or repository content only when
needed to diagnose a package-level blocker. If access, documentation, parent
repository state, credentials, or source changes are required, it must report
the exact blocker, evidence, and user input or access needed.

## Verification expectations

Run the checks that apply to the change and current environment. The declared
project workflow may include:

```text
ruff check config.py model.py drawing_annotations.py tests/
ruff format --check config.py model.py drawing_annotations.py tests/
mypy config.py model.py drawing_annotations.py tests/
python -m pytest -q
python-cad validate --project-root .
python-cad build --project-root .
python-cad verify --project-root .
python-cad clean --project-root .
python-cad prepare-site --project-root . --destination site --base-path /file-template-cad/
```

Do not invent unsupported commands or silently bypass failed checks. Report
environment-specific skipped checks and the reason.

## Save and persistence

`save` is a separate primary agent selected explicitly by the user.

No other agent may call it.

Only `save` may invoke `specrepo-autocommit`. It persists already-verified
changes exactly once using the supplied summary. It must not inspect, implement,
review, test, verify, or delegate work.

The user decides when work is ready to be persisted.
