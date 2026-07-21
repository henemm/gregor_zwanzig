# Mini-Spec: fix-948-e2e-allowed-dir

Issue: #948 — Workflow-Gate erkennt `e2e/` nicht als Test-Verzeichnis, jeder Playwright-TDD-Test deadlockt in phase5.

## Was ändert sich

- In `/home/hem/gregor_zwanzig/openspec.yaml` (Hauptrepo) wird eine `strict_code_gate:`-Sektion mit `always_allowed_dirs:` angelegt.
- Der Wert ist die **komplette** aktuelle Code-Default-Liste aus `edit_gate.py` **plus `e2e/`**:
  `Tests/, UITests/, Test/, test/, __tests__/, tests/, spec/, docs/, .claude/commands/, scripts/, tools/, e2e/`
- Grund für die Vollständigkeit: Die Config **ersetzt** den Code-Default (`_get_config_list`), nicht ergänzt ihn. Nur `e2e/` einzutragen würde alle anderen Test-/Tooling-Verzeichnisse still aus der Whitelist werfen.

## Was darf sich nicht ändern

- Der Anti-Cheating-Schutz bleibt unberührt: Staging-Gate, `e2e_verified.json`, `renderer_mail_gate`, `email_spec_validator`, `external-validator`, Adversary.
- `src/`, `api/`, `internal/`, `frontend/src/` etc. bleiben in Phasen < phase6 weiterhin blockiert — kein Verzeichnis außer den gelisteten Test-/Tooling-Dirs wird durchgelassen.
- Die `edit_gate.py`-Code-Default-Liste (`ALWAYS_ALLOWED_DIRS`) wird **nicht** angefasst (Plugin-weit) — Fix bleibt projektlokal in der Config.

## Manuelle Test-Schritte

1. Aktiver Workflow in `phase5_tdd_red` (dieser Fix ist selbst kein Playwright-Test — Verifikation über direkten Gate-Aufruf).
2. `edit_gate.py` mit einem simulierten Edit auf `frontend/e2e/foo.spec.ts` in phase5 aufrufen → **erlaubt** (Exit 0, kein BLOCKED).
3. Gegenprobe: simulierter Edit auf `src/app/foo.py` in phase5 → **blockiert** (BLOCKED, Phase-Hinweis). Beweist: kein Schutzverlust.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Test ruft die echte Gate-Logik (`edit_gate.py`, geladene `openspec.yaml`) auf und beweist: `frontend/e2e/*.spec.ts` in einer Nicht-Implement-Phase erlaubt, `src/*.py` in derselben Phase blockiert.
