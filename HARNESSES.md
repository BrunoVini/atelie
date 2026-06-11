# Harness Capabilities & Degradation Matrix

atelier is authored once as a Claude Code native skill (the repo root: `SKILL.md`
plus `scripts/`, `references/`, `assets/`, `templates/`, `hooks/`, and the
`.claude-plugin/` manifest). `scripts/build_dist.py` transforms that single source
into per-harness distribution trees under `dist/` (gitignored). This file is the
capability + degradation reference that the builder's `HARNESSES` config mirrors;
keep them in sync.

Last verified: 2026-06-11

The target layouts and frontmatter-field support below were derived from
impeccable's `HARNESSES.md` and its generated `.claude/`, `.agents/`, and `.cursor/`
trees as of 2026-06-11. atelier ships stdlib-only and its `SKILL.md` carries no
`{{placeholder}}` substitution, so the transform is mostly structural copy plus
frontmatter shaping.

## Build it

```
python3 scripts/build_dist.py --harness all --out dist
python3 scripts/build_dist.py --harness codex          # one harness
```

Re-running is idempotent: each per-harness subdir is cleaned and rebuilt. The
builder writes only under `--out` and never modifies the live repo source.

## Capability matrix

| Harness | Install layout (under `--out/<harness>/`) | SKILL frontmatter kept | Collision hook | Self-QA fallback | Subagents | Notes |
|---|---|---|:--:|---|---|---|
| **Claude Code** | `.claude/skills/atelier/` + `.claude-plugin/plugin.json` + `marketplace.json` | `name`, `description`, `license` | **Yes** | `scripts/qa.py` | `.claude/agents/` (plugin) | Canonical source. Carries `hooks/` (Stop/SubagentStop collision gate). |
| **Codex CLI** | `.agents/skills/atelier/` | `name`, `description` | No | `scripts/qa.py` | nested `<skill>/agents/*.toml` (auto-discovered) | Codex validates only name+description; `license` demoted into the body. atelier ships no subagents today. |
| **Cursor** | `.cursor/skills/atelier/` | `name`, `description`, `license` | No | `scripts/qa.py` | none in skill format | Cursor also reads `.agents/skills/` and `.claude/skills/` as fallbacks. |

Always-carried source dirs (every harness): `scripts/`, `references/`, `assets/`,
`templates/`. Only Claude Code carries `hooks/`.

### Not yet built (impeccable supports; atelier could add later)

Adding any of these is one entry in the `HARNESSES` dict in `build_dist.py` (its
install dir, accepted frontmatter, source dirs, `plugin` flag). Per impeccable's
matrix: Gemini CLI (`.gemini/skills/`, validates name+description only), GitHub
Copilot (`.github/skills/`), Kiro (`.kiro/skills/`), OpenCode (`.opencode/skills/`),
Pi (`.pi/skills/`), Qoder (`.qoder/skills/`), Trae (`.trae/`, `.trae-cn/`),
Rovo Dev (`.rovodev/skills/`).

## Degradation by harness

atelier's strongest enforcement mechanism is the **collision gate**, a Claude Code
`Stop` / `SubagentStop` hook (`hooks/atelier-collision-gate.py` + `hooks/hooks.json`).
The harness runs it automatically when an agent tries to stop, so it can **force**
a re-check before work is allowed to finish. Nothing equivalent exists in the other
harnesses' skill mechanisms.

- **Claude Code** — full strength. The collision gate is wired via `hooks.json` and
  the harness enforces it. `scripts/qa.py` (the self-QA loop) runs on top as the
  in-skill discipline.
- **Codex CLI / Cursor** — degraded. There is no harness hook that can force a
  re-check the way the Claude `Stop` hook does. The floor here is the
  `scripts/qa.py` self-QA loop plus the prose definition-of-done in `SKILL.md` /
  `references/`. This is genuinely weaker: it relies on the agent choosing to run
  the loop, not on the harness compelling it. Treat the prose contract as the
  enforcement ceiling on these harnesses, and run `qa.py` explicitly.

Honest summary of the gap: on Claude Code a forgotten re-check is *blocked*; on
Codex/Cursor a forgotten re-check is only *discouraged*. The builder reflects this
by including `hooks/` only in the Claude tree and printing the omission for the
others.

## Frontmatter shaping

- `name` and `description` are emitted on every harness.
- `license` is kept in frontmatter for Claude Code and Cursor (both accept the spec
  `license` field); for Codex it is **demoted into the body** as a `_License: ..._`
  note so the licensing is relocated, never lost.
- atelier's `SKILL.md` has no provider extensions (`user-invocable`, `allowed-tools`,
  `hooks:` frontmatter, etc.) and no `{{placeholder}}` substitution, so no other
  shaping is required.

## Assumptions

- **Codex subagents**: impeccable ships TOML subagents nested under the skill's own
  `agents/` folder for Codex auto-discovery. atelier currently has no subagents, so
  no `agents/` folder is emitted. The layout is documented here so the slot is
  obvious when atelier adds one.
- **`marketplace.json`** is emitted alongside the Claude tree (it is Claude
  Code / plugin-marketplace metadata) and omitted for the other harnesses, which
  have no equivalent.

See `scripts/build_dist.py` for the authoritative, executable version of this matrix.
