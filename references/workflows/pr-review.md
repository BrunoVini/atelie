# Workflow: PR Design Review

Put contract enforcement where decisions are made — the pull request. Scope the
checks to the diff and post a structured design-review comment, so atelier acts
like a design teammate, not a one-shot generator.

## Steps

1. **Scope to the diff** — get changed files:
   - GitHub: `gh pr diff --name-only`
   - Azure DevOps: `repo_get_pull_request_changes` (MCP) for the PR.
2. **Lint the changes** against the contract:
   ```bash
   python3 scripts/lint_design.py . --contract design/design-tokens.json --json
   ```
   Filter findings to the changed files.
3. **Contrast** — if the PR touched tokens, run `audit_contrast.py` on the new palette.
4. **Regression (opt)** — for changed routes, `diff_screens.mjs <route>` (baseline
   must exist) and attach the before/after.
5. **Compose the comment** — drift introduced (file:line → fix), any contrast
   regression, the visual diff verdict, and a one-line overall judgement.
6. **Post it:**
   - GitHub: `gh pr comment <n> --body-file review.md`
   - Azure DevOps: `repo_create_pull_request_thread` (MCP) — post as a thread,
     optionally anchored to the file/line of each finding.

## Tone

Comment on the design, not the author. Lead with what's good, then findings by
severity (⚠️/⚡/💡), then the one thing to fix before merge. If the gate
(`check.py`) fails, say so explicitly — that's the blocking signal.
