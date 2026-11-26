# Domain Docs

How engineering skills should consume this repo's domain documentation when exploring the codebase.

**Layout:** single-context — one `CONTEXT.md` at the repo root, ADRs in `docs/adr/`.
**CONTEXT.md:** present at repo root — read it first for system context.
**ADR format:** `docs/adr/YYYY-MM-DD-short-title.md`
**Consumer rule:** read `CONTEXT.md` before writing code; ADRs explain past decisions.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If these files don't exist, **proceed silently**. Don't flag their absence or suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       └── YYYY-MM-DD-short-title.md
└── src/
```

## Use the glossary's vocabulary

When output names a domain concept (in an issue title, a refactor proposal, a hypothesis, or a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept isn't in the glossary yet, either reconsider invented language or note the gap for `/domain-modeling`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts `docs/adr/YYYY-MM-DD-short-title.md` — but worth reopening because…_
