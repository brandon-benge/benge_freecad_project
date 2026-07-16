# Installed Python CAD Project Instructions

## Hard boundary: managed tooling

Do not edit files under `.tools/`, managed root `build.py` or `start.sh`, managed root `opencode.jsonc`, managed `viewer/`, `.github/workflows/pages.yml`, managed `.agents/`, `.opencode/commands/`, `.opencode/tools/`, or tool-registration links. These files come from the upstream template through `.tools/update_tools.py` and must not contain project-specific changes. This applies to every assistant and any subagent it invokes.

If a requested change appears to require managed tooling, stop and explain that it belongs upstream. Do not patch managed files as a project workaround.

## Project-owned source

Project-specific design and workflow work belongs in:

- `model.py` and optional project component modules;
- `config.py`;
- `README.md`;
- project-specific tests or validation extensions;
- `pyproject.toml` and `.gitignore` when project dependencies or policy change.

Normal managed updates preserve these project-owned files. An explicit `python .tools/update_tools.py --force` restores the template versions of `README.md`, `pyproject.toml`, `.gitignore`, this `AGENTS.md`, `opencode.jsonc`, and `.agents/`. It never replaces `model.py`, `config.py`, project tests, generated outputs, or unknown files.

Python design source is authoritative. Generated files are disposable build products and must never be edited as design inputs.

The Python CAD Architect must not invoke Git directly or indirectly. Only the managed Save agent may persist verified changes, and only through its exclusive `specrepo-autocommit` tool.

## Build and verification

- Keep geometry parametric and use the managed `python_cad_tools` API.
- Preserve stable semantic IDs or document intentional migrations.
- Create geometry and metadata together; assign intentional IFC mappings or exclusions.
- Run `python build.py` after changes and review the regenerated validation reports and manifests.
- The default build must remain FreeCAD-independent.
- Use `python build.py --include-fcstd` only when optional compatibility output is explicitly required and FreeCADCmd is installed.

Managed updates replace only manifest-declared paths and preserve protected project source. Use `python .tools/update_tools.py`; installer and updater entry points exist only under `.tools/`. Use `--force` only to restore the upstream safe project defaults; `--force-guidance` and `--force-project-files` are compatibility aliases.
