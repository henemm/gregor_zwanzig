# Claude Code Handoff — Gregor Zwanzig Design + Spec Alignment

This folder contains **14 ready-to-create GitHub issues** for `henemm/gregor_zwanzig`,
plus the screenshots they reference (Ist + Soll). **You (Claude Code) should create these
issues on GitHub on the user's behalf.**

## Quick start (paste this prompt into Claude Code)

> Read `claude-code-handoff/INSTRUCTIONS.md` and execute it. Create all 14
> GitHub issues, with screenshots committed first so the embedded image URLs
> resolve. Ask me before pushing if anything is ambiguous.

## What's in here

```
claude-code-handoff/
├── INSTRUCTIONS.md           ← THIS file (full plan + commands)
├── PROMPT-FÜR-CLAUDE-CODE.txt ← One-line prompt to paste into Claude Code
├── create-issues.sh          ← Optional CLI fallback if you want to run it yourself
├── issues.json               ← Machine-readable index: 14 issues with titles, labels, body_file paths
├── issue-bodies/
│   ├── body-00.md            ← Body for each issue in order
│   ├── … (14 files total)
│   └── body-13.md
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

### 3. Create the 14 issues in order

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

### 4. Report back

Print the URLs of all 14 created issues to the user, in order. Example:

```
Created 11 issues:
  #42  Fix dangling CSS variable fallbacks               https://github.com/henemm/gregor_zwanzig/issues/42
  #43  Replace native checkboxes & selects               https://github.com/henemm/gregor_zwanzig/issues/43
  …
```

### 5. Suggested next step

Tell the user: "Start with issues #42 (CSS tokens) and #43 (form controls).
Those two reparieren ~60% des Design-Drift in einem Rutsch. Danach kannst du
03–10 parallel angehen."

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
