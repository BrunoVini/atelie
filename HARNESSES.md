# Harness Capabilities & Degradation Matrix

atelier is authored once as a Claude Code native skill (the repo root: `SKILL.md`
plus `scripts/`, `references/`, `assets/`, `templates/`, `hooks/`, `commands/`, and the
`.claude-plugin/` manifest). `scripts/build_dist.py` transforms that single source
into per-harness distribution trees under `dist/` (gitignored). This file is the
capability + degradation reference that the builder's `HARNESSES` config mirrors;
keep them in sync.

Last verified: 2026-06-12

The target layouts, frontmatter-field support, and native command systems below were
derived from impeccable's `HARNESSES.md` and its generated harness trees, and
re-verified against each harness's current public docs (URLs in the "Sources" section
at the bottom). atelier ships stdlib-only and its `SKILL.md` carries no
`{{placeholder}}` substitution, so the skill transform is mostly structural copy plus
frontmatter shaping; the command transform is per-harness (see below).

## Build it

```
python3 scripts/build_dist.py --harness all --out dist
python3 scripts/build_dist.py --harness codex          # one harness
```

Re-running is idempotent: each per-harness subdir is cleaned and rebuilt. The
builder writes only under `--out` and never modifies the live repo source.

## Capability matrix

| Harness | Skill install layout (under `--out/<harness>/`) | SKILL frontmatter kept | Native commands | Collision hook | Self-QA floor |
|---|---|---|---|:--:|---|
| **Claude Code** | `.claude/skills/atelier/` + `.claude-plugin/plugin.json` + `marketplace.json` | `name`, `description`, `license` | `commands/*.md` inside the skill (slash commands) | **Yes** | `scripts/qa.py --hook` |
| **Codex CLI** | `.agents/skills/atelier/` | `name`, `description` | `.codex/prompts/atelier-*.md` (markdown custom prompts) | No | `scripts/qa.py --hook` |
| **Cursor** | `.cursor/skills/atelier/` | `name`, `description`, `license` | `.cursor/commands/atelier-*.md` (markdown commands) | No | `scripts/qa.py --hook` |
| **Gemini CLI** | `.gemini/skills/atelier/` | `name`, `description` | `.gemini/commands/atelier/*.toml` (TOML commands) | No | `scripts/qa.py --hook` |
| **GitHub Copilot** | `.github/skills/atelier/` | `name`, `description`, `license` | `.github/prompts/atelier-*.prompt.md` (VS Code prompt files) | No | `scripts/qa.py --hook` |
| **OpenCode** | `.opencode/skills/atelier/` | `name`, `description`, `license` | `.opencode/commands/atelier-*.md` (markdown commands) | No (see note) | `scripts/qa.py --hook` |
| **Kiro** | `.kiro/skills/atelier/` | `name`, `description`, `license` | none — natural-language invocation | No | `scripts/qa.py --hook` |
| **Pi** | `.pi/skills/atelier/` | `name`, `description`, `license` | none — natural-language invocation | No | `scripts/qa.py --hook` |
| **Qoder** | `.qoder/skills/atelier/` | `name`, `description`, `license` | none — natural-language invocation | No | `scripts/qa.py --hook` |
| **Trae (Intl)** | `.trae/skills/atelier/` | `name`, `description`, `license` | none — natural-language invocation | No | `scripts/qa.py --hook` |
| **Trae (China)** | `.trae-cn/skills/atelier/` | `name`, `description`, `license` | none — natural-language invocation | No | `scripts/qa.py --hook` |
| **Rovo Dev** | `.rovodev/skills/atelier/` | `name`, `description`, `license` | none — natural-language invocation | No | `scripts/qa.py --hook` |

Always-carried source dirs (every harness): `scripts/`, `references/`, `assets/`,
`templates/`. Only Claude Code carries `hooks/`. The native command files for the
non-Claude harnesses are written **sibling to the skill dir** (in that harness's own
command directory), because that is where each harness reads its commands.

Reads-also fallbacks (so the `.agents/` and `.claude/` skill trees double as installs
for several harnesses): Cursor / Copilot / OpenCode also read `.agents/skills/` and
`.claude/skills/`; Gemini / Pi also read `.agents/skills/`; Qoder / Rovo Dev also read
their user-level `~/.<harness>/skills/`.

## Commands: one source, native per harness

atelier's seven user-invocable commands (`design-md`, `check`, `review`, `refine`,
`preview`, `variants`, `migrate`) are authored once as Claude Code slash commands in
`commands/*.md` — a `description` / `argument-hint` frontmatter plus a one-paragraph
prompt body that uses two Claude-isms: `$ARGUMENTS` and
`${CLAUDE_PLUGIN_ROOT}/scripts/…`. `build_dist.py` ports them into each harness's real
command system:

| Harness | Command system + file | Args token | Path rewrite |
|---|---|---|---|
| Claude Code | `commands/atelier-*.md` shipped verbatim inside the skill | `$ARGUMENTS` | `${CLAUDE_PLUGIN_ROOT}` (native) |
| Codex CLI | `.codex/prompts/atelier-*.md` (`description` + `argument-hint` frontmatter) | `$ARGUMENTS` (native) | rewritten to `.agents/skills/atelier/…` |
| Cursor | `.cursor/commands/atelier-*.md` (body is the prompt; description folded into a lead heading) | prose (Cursor has no arg variable) | rewritten to `.cursor/skills/atelier/…` |
| Gemini CLI | `.gemini/commands/atelier/*.toml` (`description` + `prompt`) | `{{args}}` (native, shell-escaped) | rewritten to `.gemini/skills/atelier/…` |
| GitHub Copilot | `.github/prompts/atelier-*.prompt.md` (`description` + `argument-hint` frontmatter) | `${input:target}` (VS Code input variable) | rewritten to `.github/skills/atelier/…` |
| OpenCode | `.opencode/commands/atelier-*.md` (`description` frontmatter) | `$ARGUMENTS` (native) | rewritten to `.opencode/skills/atelier/…` |
| Kiro / Pi / Qoder / Trae / Rovo Dev | **none** — no documented project-level command system | n/a | n/a |

Because ported command files live outside the skill dir, the `${CLAUDE_PLUGIN_ROOT}`
placeholder is rewritten to the harness's actual skill install path so a bundled
script reference still resolves.

**Harnesses with no command system degrade to natural-language invocation.** The skill
itself is still installed and model-invocable on every harness — the user just says
what they want ("review this page", "make a DESIGN.md for this repo") and the skill's
own routing (the SKILL.md command table) does the work. No command files are invented
for these harnesses.

Codex's custom prompts are officially **deprecated in favor of skills**; we still emit
them because they continue to work and give Codex users an explicit slash surface, but
the skill install (`.agents/skills/atelier/`) is the primary, recommended path.

## Enforcement & degradation by harness

atelier's strongest enforcement mechanism is the **collision gate**, a Claude Code
`Stop` / `SubagentStop` hook (`hooks/atelier-collision-gate.py` + `hooks/hooks.json`).
The harness runs it automatically when an agent tries to stop, so it can **force** a
re-check before work is allowed to finish. Nothing equivalent exists in the other
harnesses' skill mechanisms.

- **Claude Code** — full strength. The collision gate is wired via `hooks.json` and
  the harness enforces it. `scripts/qa.py` (the self-QA loop) runs on top as the
  in-skill discipline.
- **OpenCode** — degraded, despite having a real JS plugin system. OpenCode plugins
  (`.opencode/plugin/*.js`) expose ~25 lifecycle events, and `tool.execute.before`
  can *block a tool* by throwing. But the stop-equivalent event, `session.idle`, is
  **notification-only** — it fires when the agent finishes responding and cannot deny
  the stop. So OpenCode has no event that reproduces Claude's blocking `Stop` gate. We
  do **not** ship a plugin that pretends to gate; that would overstate the
  enforcement. The floor is the `scripts/qa.py --hook` self-QA loop plus the prose
  definition-of-done in `SKILL.md`.
- **Codex / Cursor / Gemini / Copilot / Kiro / Pi / Qoder / Trae / Rovo Dev** —
  degraded. There is no harness hook that can force a re-check the way the Claude
  `Stop` hook does. The floor here is the `scripts/qa.py --hook` self-QA loop plus the
  prose definition-of-done in `SKILL.md` / `references/`. This is genuinely weaker: it
  relies on the agent choosing to run the loop, not on the harness compelling it.

The SKILL.md "Definition of done" section is the cross-harness contract: on every
non-Claude harness the agent is instructed to run `python3 scripts/qa.py <artifact>
--hook` and treat its exit code as the gate before declaring an artifact done.

Honest summary of the gap: on Claude Code a forgotten re-check is *blocked*; on every
other harness a forgotten re-check is only *discouraged*. The builder reflects this
by including `hooks/` only in the Claude tree and printing the omission for the
others.

## What runs when you install

Across every harness, installing or cloning atelier executes **nothing**:

- **No install scripts, no postinstall, no telemetry, no network fetch on install.**
  A build/clone copies files; it does not run them.
- **Stdlib-only Python / Node-builtins-only `.mjs`.** Nothing to install to use the
  core skill; the scripts run only when explicitly invoked (by you or by the agent
  during a task), never in the background.
- **Ported command files are inert prompt templates** — markdown or TOML that the
  harness loads into its slash menu; they run a script only when you invoke the
  command and the agent acts on it.
- **The one harness-driven exception is the Claude-Code collision hook**, and it ships
  **only to the Claude build**. `hooks/hooks.json` registers
  `hooks/atelier-collision-gate.py` on `Stop` / `SubagentStop`; the Claude harness
  auto-runs it to gate on rendered layout collisions before an agent finishes. It
  reads files locally and makes **no network calls**. Every other harness omits
  `hooks/` entirely (see the matrix above) and degrades to the `qa.py` self-QA loop —
  so on those harnesses nothing auto-runs at all.

## Frontmatter shaping

- `name` and `description` are emitted on every harness.
- `license` is kept in frontmatter for every harness that accepts the spec `license`
  field (Claude Code, Cursor, Copilot, Kiro, OpenCode, Pi, Qoder, Trae, Rovo Dev).
- `license` is **demoted into the body** as a `_License: …_` note for the two
  harnesses that don't keep it — Codex (validates only name + description) and Gemini
  (parses-but-ignores `license`) — so the licensing is relocated, never lost.
- atelier's `SKILL.md` has no provider extensions (`user-invocable`, `allowed-tools`,
  `hooks:` frontmatter, etc.) and no `{{placeholder}}` substitution, so no other
  skill-body shaping is required.

## Assumptions

- **Codex subagents**: impeccable ships TOML subagents nested under the skill's own
  `agents/` folder for Codex auto-discovery. atelier currently has no subagents, so
  no `agents/` folder is emitted. The layout is documented here so the slot is
  obvious when atelier adds one.
- **`marketplace.json`** is emitted alongside the Claude tree (it is Claude
  Code / plugin-marketplace metadata) and omitted for the other harnesses, which
  have no equivalent.
- **Trae** has no official skills/commands documentation yet; we mirror impeccable's
  `.trae/skills/` and `.trae-cn/skills/` skill layout and give it no command files
  (the safe degradation) until a command system is documented.

## Sources (re-verified 2026-06-12)

- Codex custom prompts (deprecated; markdown, `$ARGUMENTS`, `description` +
  `argument-hint`): <https://developers.openai.com/codex/custom-prompts>
- Gemini CLI custom commands (TOML, `description` + `prompt`, `{{args}}`):
  <https://geminicli.com/docs/cli/custom-commands/>
- Cursor commands (`.cursor/commands/*.md`):
  <https://cursor.com/changelog/1-6>
- GitHub Copilot / VS Code prompt files (`.github/prompts/*.prompt.md`, frontmatter
  `description` + `argument-hint`, `${input:…}` variables):
  <https://code.visualstudio.com/docs/agent-customization/prompt-files>
- OpenCode commands (`.opencode/commands/*.md`, `description` frontmatter,
  `$ARGUMENTS`): <https://opencode.ai/docs/commands/>
- OpenCode plugins (`session.idle` is notification-only; `tool.execute.before` can
  block a tool): <https://opencode.ai/docs/plugins/>

Skill directory layouts (`.qoder/skills/`, `.trae/skills/`, `.trae-cn/skills/`,
`.rovodev/skills/`, and the reads-also fallbacks) are mirrored from impeccable's
`HARNESSES.md` "Skill Directory Structure" table.

See `scripts/build_dist.py` for the authoritative, executable version of this matrix.
