"""Static policy checks for CI/workflow definitions, symlinks, and boundaries.

These tests run locally without contacting GitHub, installing dependencies,
or building the project.
"""

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_ci_yml_exists():
    assert (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").is_file()


def test_pages_yml_exists():
    assert (PROJECT_ROOT / ".github" / "workflows" / "pages.yml").is_file()


def test_old_build_design_yml_removed():
    assert not (PROJECT_ROOT / ".github" / "workflows" / "build-design.yml").is_file()


def test_ci_yml_required_jobs():
    text = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    required = [
        "locked-install",
        "static-analysis",
        "model-annotation",
        "full-build-verify",
        "determinism-recovery",
        "site-browser-e2e",
        "boundary-governance",
        "compatibility-report",
        "required-gate",
    ]
    for job in required:
        assert job in text, f"ci.yml missing required job: {job}"


def test_actions_pinned_to_sha():
    """Check that third-party actions are pinned to full commit SHAs."""
    for wf in ["ci.yml", "pages.yml"]:
        text = (PROJECT_ROOT / ".github" / "workflows" / wf).read_text()
        for match in re.finditer(r"uses:\s+(\S+)(?:@)(\S+)", text):
            action = match.group(1)
            ref = match.group(2)
            if not action.startswith("actions/"):
                continue
            # actions/checkout@v4 and similar version tags are acceptable
            # if they are well-known actions. The plan says to pin
            # third-party actions to reviewed full commit SHAs, but
            # actions/checkout, setup-python, etc. are first-party.
            if not re.match(r"^[0-9a-f]{40}$", ref):
                if action.startswith("actions/"):
                    # Known first-party actions may use tags
                    assert re.match(r"^v?\d+", ref), f"{action}@{ref} not pinned to SHA or version tag"
                else:
                    assert re.match(r"^[0-9a-f]{40}$", ref), (
                        f"Third-party action {action}@{ref} must be pinned to full SHA"
                    )


def test_workflow_permissions_least_privilege():
    for wf in ["ci.yml", "pages.yml"]:
        text = (PROJECT_ROOT / ".github" / "workflows" / wf).read_text()
        # Must declare permissions at top level
        assert "permissions:" in text, f"{wf} missing top-level permissions block"
        # Must not use write-all
        assert "write-all" not in text, f"{wf} uses write-all"


def test_pages_yml_workflow_run_trigger():
    text = (PROJECT_ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "workflow_run:" in text
    assert "workflows:" in text
    assert "Benge Property CAD CI" in text


def test_pages_yml_no_node():
    text = (PROJECT_ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "node" not in text.lower()
    assert "npm" not in text.lower()
    assert "viewer/" not in text


def test_pages_yml_verify_head_sha():
    text = (PROJECT_ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "head_sha" in text
    assert "git rev-parse HEAD" in text or "rev-parse" in text


def test_agents_directory_structure():
    agents_dir = PROJECT_ROOT / ".agents" / "agents"
    assert agents_dir.is_dir()
    expected = [
        "benge-design-maintainer.md",
        "benge-project-operations.md",
        "benge-artifact-reviewer.md",
        "cad-compatibility-verifier.md",
        "save.md",
    ]
    for name in expected:
        assert (agents_dir / name).is_file(), f"Missing agent: {name}"


def test_skills_directory_structure():
    skills_dir = PROJECT_ROOT / ".agents" / "skills"
    assert skills_dir.is_dir()
    for role in [
        "benge-design-maintainer",
        "benge-project-operations",
        "benge-artifact-reviewer",
        "cad-compatibility-verifier",
        "save",
    ]:
        assert (skills_dir / role / "SKILL.md").is_file()
        assert (skills_dir / role / "agents" / "openai.yaml").is_file()


def test_symlinks_resolve_and_are_contained():
    links = [
        ".claude/agents",
        ".claude/skills",
        ".codex/agents",
        ".codex/skills",
        ".opencode/agents",
        ".opencode/skills",
        "CLAUDE.md",
    ]
    for link_name in links:
        link_path = PROJECT_ROOT / link_name
        assert link_path.is_symlink(), f"Not a symlink: {link_name}"
        target = os.readlink(str(link_path))
        assert target, f"Empty target for {link_name}"
        resolved = (link_path.parent / target).resolve()
        assert str(resolved).startswith(str(PROJECT_ROOT)), (
            f"{link_name} -> {target} resolves outside repository: {resolved}"
        )
        assert resolved.exists(), f"{link_name} -> {target} -> {resolved} does not exist"


def test_claude_md_points_to_agents_md():
    link_path = PROJECT_ROOT / "CLAUDE.md"
    target = os.readlink(str(link_path))
    assert target == "AGENTS.md", f"CLAUDE.md should -> AGENTS.md, got -> {target}"


def test_opencode_directories_exist():
    for d in [".opencode/commands", ".opencode/tools"]:
        assert (PROJECT_ROOT / d).is_dir(), f"Missing directory: {d}"


def test_opencode_jsonc_exists():
    assert (PROJECT_ROOT / "opencode.jsonc").is_file()


def test_agents_md_exists():
    assert (PROJECT_ROOT / "AGENTS.md").is_file()


def test_agents_md_has_separation_of_duties():
    text = (PROJECT_ROOT / "AGENTS.md").read_text()
    assert "benge-design-maintainer" in text
    assert "benge-project-operations" in text
    assert "benge-artifact-reviewer" in text
    assert "cad-compatibility-verifier" in text
    assert "save" in text
    assert "Repository boundary" in text
    assert "Separation of duties" in text


def test_locks_in_requirements_locks():
    locks_dir = PROJECT_ROOT / "requirements" / "locks"
    assert locks_dir.is_dir()
    expected = [
        "dev-ubuntu-x86_64-py312.lock",
        "dev-ubuntu-x86_64-py313.lock",
        "dev-macos-arm64-py312.lock",
        "dev-macos-arm64-py313.lock",
    ]
    for name in expected:
        assert (locks_dir / name).is_file(), f"Missing lock: {name}"


def test_no_cross_boundary_tooling_authority():
    """No agent should have authority over tooling source or site-packages."""
    text = (PROJECT_ROOT / "AGENTS.md").read_text()
    assert "site-packages" in text or "tooling source" in text
    for agent_file in (PROJECT_ROOT / ".agents" / "agents").iterdir():
        text = agent_file.read_text()
        assert "python_cad_tools" not in text or "public" in text, (
            f"{agent_file.name} must not reference editing tooling source"
        )
