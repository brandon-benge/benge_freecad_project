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
| `python-cad-tools-upgrader` | Upgrade the published dependency and apply version-aware testing | `pyproject.toml`, dependency locks |

## Collaboration

The working agents may call one another when the receiving agent owns the
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
5. Any agent may invoke `save`, but only after the user explicitly asks to
   commit the changes to Git.

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
- never invokes Git directly and uses `save` only after an explicit user
  request to commit the changes to Git

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
- invoke `save` without an explicit user request to commit the changes to Git

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
- invoke Git directly or invoke `save` without an explicit user request to
  commit the changes to Git

It may read public remote package documentation or repository content only when
needed to diagnose a package-level blocker. If access, documentation, parent
repository state, credentials, or source changes are required, it must report
the exact blocker, evidence, and user input or access needed.

## Verification expectations

Use the smallest verification tier that provides evidence proportional to the
change. Do not run integration, viewer, or E2E tests by default for a localized
design-source change.

### Focused tier

Use for localized changes to parameters, geometry, annotations, metadata, or
focused tests. Run:

```text
ruff check config.py model.py drawing_annotations.py tests/
ruff format --check config.py model.py drawing_annotations.py tests/
mypy config.py model.py drawing_annotations.py tests/
python -m pytest -q <affected test files or node IDs>
python-cad validate --project-root .
```

Select affected tests narrowly. Do not substitute the complete test suite when
a test file or node ID directly covers the change.

### Export-sensitive tier

Use when a change affects solid construction, semantic identity, materials,
relationships, quantities, drawings, or exported formats. Run the focused tier
first, then the applicable integration and artifact checks:

```text
python -m pytest -q -m integration
python-cad build --project-root .
python-cad verify --project-root .
```

Run only the applicable commands when the current environment or installed
toolchain cannot support an output. Report every skipped or failed command and
its reason.

### Full and E2E tier

Run the complete suite, site preparation, HTTP, viewer, or browser checks only
for broad cross-project changes, UI or site changes, minor or major dependency
upgrades, explicit full/E2E requests, or failures that require those checks for
diagnosis:

```text
python -m pytest -q
python -m pytest -q -m "e2e or viewer"
python-cad prepare-site --project-root . --destination site --base-path /file-template-cad/
```

The `integration` marker identifies artifact/export integration tests. The
`viewer` marker identifies viewer and local HTTP behavior. The `e2e` marker
identifies end-to-end tests that may require services, sockets, or browsers.

Classify `python-cad-tools` upgrades with semantic versioning. A change only to
the patch component (for example, `0.1.4` to `0.1.5`) uses basic tests and must
not run E2E tests. A minor or major change, or a user request for a full
upgrade, requires E2E testing. E2E testing is also available on demand through
the manually dispatched `File Template CAD End-to-End` GitHub Actions workflow.

The `python-cad-tools-upgrader` owns dependency upgrades. It must use its skill,
install only the published package, regenerate applicable locks, and run the
documented upgrade smoke sequence. It must not run E2E tests for patch-only
upgrades unless the user explicitly requests them.

Do not invent unsupported commands or silently bypass failed checks. Report
environment-specific skipped checks and the reason.

## Save and persistence

`save` is a skill available to every working agent; there is no separate save
agent. An agent may load it and invoke `specrepo-autocommit` only after the user
explicitly asks to commit or save the changes to Git. Never infer this intent
from task completion, approval, a request to continue, or a generic request to
save a file. The tool requires an explicit confirmation argument and persists
already-verified changes exactly once using the supplied summary.

The user decides when work is ready to be committed. Agents must not assume it.
