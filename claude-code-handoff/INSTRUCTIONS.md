# Claude Code Handoff — Gregor Zwanzig Design + Spec Alignment

This folder contains **15 issues** for `henemm/gregor_zwanzig`. Most of them are
**already on GitHub** from earlier handoffs — only one is new this round (see
status per issue in `issues.json`, `"status": "new"` vs `"existing-or-update"`).

**Each issue body starts with a stable-ID marker** that survives across
handoffs:

```
<!-- gregor-zwanzig-handoff: stable_id=<slug> -->
```

Use the marker to dedupe (Step 3 below).

## Quick start (paste this prompt into Claude Code)

> Read `claude-code-handoff/INSTRUCTIONS.md` and execute it. **Do not blindly
> create 15 issues** — first dedupe against existing GitHub issues by
> stable-ID marker, then only create what is missing and edit bodies of
> what already exists. Ask before pushing if anything is ambiguous.
>
> Issue mit `"status": "new"` in `issues.json` ist garantiert noch nicht
> auf GitHub. Issue #14 (Output-Layout-System) ist eine Backend-/Frontend-
> Architektur-Story — nur Issue erstellen, Implementierung erfolgt später
> separat.

## What's in here

```
claude-code-handoff/
├── INSTRUCTIONS.md           ← THIS file (full plan + commands)
├── PROMPT-FÜR-CLAUDE-CODE.txt ← One-line prompt to paste into Claude Code
├── create-issues.sh          ← Optional CLI fallback if you want to run it yourself
├── issues.json               ← Machine-readable index: 15 issues with titles, labels, body_file paths
├── issue-bodies/
│   ├── body-00.md            ← Body for each issue in order
│   ├── … (14 "body-NN.md" files for the design-compliance issues)
│   ├── body-13.md
│   └── body-14-output-layout-system.md  ← NEW: Spalten/Detail/Aus + Kanal-Constraints
└── screenshots/
    ├── 01-…-11-*.png         ← Ist-Screenshots (current implementation)
    └── soll-*.png            ← Soll-Mockups (target designs from Soll-Mockups.html)
```

Each issue body references screenshots by URL pointing at
`https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/<slug>.png`.
**So the screenshots must be committed and pushed to `main` before the issues are created**, otherwise the images won't render. Order matters — see step 2 below.

## Plan for Claude Code to follow

### 1. Verify environment

```bash
cd /path/to/gregor_zwanzig
git status                                      # clean working tree expected
gh auth status                                   # gh CLI must be authenticated
git rev-parse --abbrev-ref HEAD                  # confirm we're on main (or branch off)
```

If `gh` is not authenticated, stop and ask the user to run `gh auth login`.

### 2. Commit screenshots first

Copy `screenshots/*.png` from this handoff folder into the repo at
`.github/issue-assets/`, then commit and push:

```bash
mkdir -p .github/issue-assets
cp /path/to/claude-code-handoff/screenshots/*.png .github/issue-assets/
git add .github/issue-assets/
git commit -m "chore(design): add design-compliance issue screenshots"
git push origin main
```

After push, verify one URL resolves with curl:

```bash
curl -fsI "https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1A-home-kacheln.png" | head -1
# expect: HTTP/2 200
```

If it 404s, GitHub may take ~30 seconds to propagate. Retry.

### 3. Dedupe against existing GitHub issues

For each entry in `issues.json`, check if a GitHub issue with that
`stable_id` already exists:

```bash
stable_id="foundation-css-tokens"
gh issue list --repo henemm/gregor_zwanzig --state all --search \
  "in:body gregor-zwanzig-handoff: stable_id=$stable_id" --json number,title,state
```

- **Match found, state=closed** → issue is done. Skip silently. Do NOT reopen.
- **Match found, state=open** → issue exists. Update body if changed
  (`gh issue edit <num> --body-file ...`). Update labels if `issues.json`
  lists labels not yet on the issue. Do NOT change the title.
- **No match** → create the issue (next step). This is the only case where
  the entry with `status: "new"` should land; for `status: "existing-or-update"`
  entries without a match, ask the user before creating — may have been
  deleted intentionally.

Report at the end: how many issues were created, updated, skipped (closed),
or flagged for user-decision.

### 4. Create only the truly new issues

Iterate over `issues.json` and run for each entry:

```bash
gh issue create \
  --repo henemm/gregor_zwanzig \
  --title "<title from json>" \
  --label "<label1>" --label "<label2>" --label … \
  --body-file "claude-code-handoff/<body_file from json>"
```

**Labels:** Some labels in `issues.json` may not exist yet in the repo. Create them first if needed:

```bash
gh label list --repo henemm/gregor_zwanzig
# create missing ones (idempotent — failures are OK if exists):
for spec in \
  "design-compliance:c45a2a:Design system compliance issue" \
  "foundation:8c3e1a:Foundational change — do first" \
  "feature:2a6cb3:New feature" \
  "backend-coordination:6b675c:Requires backend changes" \
  "breaking-change:a83232:Breaking change to existing UX" \
  "ux:c08a1a:UX improvement" \
  "bug:a83232:Bug fix" \
  "priority:high:a83232:" \
  "priority:medium:c08a1a:" \
  "area:tokens:9a958a:" \
  "area:home:9a958a:" \
  "area:trips:9a958a:" \
  "area:editor:9a958a:" \
  "area:alerts:9a958a:" \
  "area:reports:9a958a:" \
  "area:compare:9a958a:" \
  "area:sidebar:9a958a:" \
  "area:weather:9a958a:" \
  "area:output:9a958a:Briefing-Output · Spalten/Detail/Aus-Layout" \
  "area:components:9a958a:"; do
  name="${spec%%:*}"; rest="${spec#*:}"; color="${rest%%:*}"; desc="${rest#*:}"
  if [ -n "$desc" ]; then
    gh label create "$name" --color "$color" --description "$desc" --repo henemm/gregor_zwanzig 2>/dev/null || true
  else
    gh label create "$name" --color "$color" --repo henemm/gregor_zwanzig 2>/dev/null || true
  fi
done
```

Or use the included `create-issues.sh` which handles this.

### 5. Report back

Print a per-issue summary (created / updated / skipped-closed / asked-user)
with URLs where applicable. Example:

```
Dedupe summary (15 entries in issues.json):
  CREATED  #58  Output-Layout-System            https://github.com/henemm/gregor_zwanzig/issues/58
  UPDATED  #44  Replace native checkboxes       https://github.com/henemm/gregor_zwanzig/issues/44
  SKIPPED  #42  Fix dangling CSS variables      (closed, already merged)
  ASKED    —    Sidebar logo                    (no match, status=existing-or-update)
```

### 6. No "start with X" recommendation

Unlike earlier handoffs, the user's repo state is now mixed (several issues
done, others in flight). Do not recommend a starting point. Only the new
issue (`status: "new"`) is a fresh work item; everything else is
user-prioritized.

## Manifest · packet integrity

Before starting, verify the handoff packet arrived intact. Expected file
count in `claude-code-handoff/` matches `MANIFEST.txt`:

```bash
bash claude-code-handoff/check-manifest.sh   # or eyeball the count
wc -l claude-code-handoff/MANIFEST.txt
```

If counts don't match, the upload was truncated — ask the user for a fresh
zip and stop.

## Edge cases & notes

- **Issue 00 / body-00.md** is the highest-impact foundation fix. Do it first.
- **Issue 01 / body-01.md** depends on no other issues but provides `<Checkbox>` and
  `<Select>` components that issues 07, 08, 09, 10 reference. If you implement
  the issues sequentially, do 00 → 01 first.
- The bodies contain code blocks with `var(--g-*)` references that map to
  tokens defined in `frontend/src/app.css` (`@layer base { :root { ... } }`).
- Tests: every issue's acceptance criteria notes the relevant `data-testid` /
  Playwright selectors that must be preserved.

## If something fails

- **`gh issue create` fails with HTTP 422 on labels:** the label doesn't exist; create it (step 3).
- **Screenshots show as broken images in GitHub:** Confirm step 2 push succeeded and the URL is reachable with curl. Sometimes raw.githubusercontent.com takes 1-2 min to propagate.
- **Title is too long:** GitHub caps at 256 chars. None of these should hit that, but if they do, truncate to 250 + "…".
- **User wants to skip a screen:** Ask the user before creating. They may have a specific subset in mind.
