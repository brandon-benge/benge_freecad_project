---
description: Save verified repository changes through the exclusive Save agent
agent: save
subtask: true
---

Load the `save` skill and follow it exactly.

Save the already-verified repository changes by calling the native OpenCode
tool `specrepo-autocommit` exactly once. Use `$ARGUMENTS` as its `summary` when
the value is non-empty; otherwise use `Save verified repository changes`.

Do not inspect or edit files, run tests, call shell commands, invoke Git
directly, or use any fallback. Report the single tool call's completed,
blocked, rejected, or failed result.