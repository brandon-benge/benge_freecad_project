---
name: save
description: Persist already-verified repository changes exactly once through specrepo-autocommit after explicit user selection.
compatibility: opencode
metadata:
  repository: benge-property-cad
  role: persistence
---

# Save Skill

## Purpose

Persist already-verified work after the user explicitly selects the `save`
agent.

## Preconditions

- The user explicitly requested persistence.
- Implementation is already complete.
- Required checks and reviews were already performed.
- A concise summary is available.

## Restrictions

- Do not read or inspect repository files.
- Do not edit files.
- Do not run shell commands.
- Do not invoke Git directly.
- Do not implement, review, test, or verify.
- Do not invoke another agent.
- Do not call `specrepo-autocommit` more than once.

## Procedure

1. Use the supplied summary.
2. Invoke `specrepo-autocommit` exactly once.
3. Return the persistence result.
4. Do nothing else.
