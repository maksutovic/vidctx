# Codex support

The skill is agent-neutral: one `SKILL.md` (in `src/vidctx/skill/`) serves Claude Code and Codex.
Both read the same format (YAML frontmatter with `name` and `description`, then instructions).

## Where skills live

| | User level (all projects) | Repo level |
|---|---|---|
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | `<repo>/.claude/skills/<name>/SKILL.md` |
| Codex | `~/.agents/skills/<name>/SKILL.md` | `.agents/skills/` in the cwd, its parents, or the repo root |

Codex also reads `/etc/codex/skills` (admin) and its bundled system skills. Source:
[Codex docs, Build skills](https://learn.chatgpt.com/docs/build-skills) (formerly
developers.openai.com/codex/skills), checked 2026-09-25.

`vidctx install-skill` detects agents by `~/.claude` and `~/.codex` and installs for each one found;
`--claude` / `--codex` pick one explicitly.

## Differences the skill has to handle

- **Viewing images.** Claude Code opens a still with `Read`; Codex has `view_image`. The skill
  names both and keeps the rule: one image per tool call, in time order.
- **Sandbox.** Codex's default `workspace-write` sandbox on macOS (Seatbelt) allows writes only in
  the workspace and temp folders, and network access is off unless
  `sandbox_workspace_write.network_access = true`
  ([permissions](https://developers.openai.com/codex/permissions),
  [sandboxing](https://developers.openai.com/codex/concepts/sandboxing)). vidctx needs network for
  YouTube and the first model download, writes to `~/.cache`, and uses the Apple GPU through MLX, which
  hasn't been tested under Seatbelt. The skill therefore tells Codex to request escalated permissions
  for `vidctx` up front.
- **Cache fallback.** If `~/.cache/vidctx` isn't writable, vidctx uses the system temp folder
  (`$TMPDIR/vidctx`); `VIDCTX_CACHE` overrides both. Tested: with `~/.cache` unwritable and
  `HF_HUB_OFFLINE=1`, a cached-model run still completes (85 stills on the walkthrough).
- **No session scratchpad.** Claude Code gives each session a scratch folder; Codex doesn't, so the
  skill says to omit `--out` there and use the default cache location.

## Not yet verified

Running the skill end to end inside Codex (desktop app or CLI) hasn't been tested: in particular,
whether `view_image` is available in the app, and whether transcription on the GPU works inside the
sandbox if a user declines escalation.
