# Context: Issue #521 — Staging Validator Agent

## Request Summary

Ein intelligenter Staging Validator Agent soll die bestehende `/e2e-verify`-Checkliste ersetzen: Er loggt sich in Staging ein, navigiert zu den betroffenen UI-Features und verifiziert jedes UI-AC aus der Spec — analog zum Adversary, aber gegen die laufende App statt gegen den Code. Das Ergebnis ist ein VERIFIED/BROKEN/AMBIGUOUS-Verdict, das `deploy-gregor-prod.sh` als Hard Gate nutzt.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `.claude/agents/implementation-validator.md` | Vorbild: Adversary-Agent-Struktur, Findings-Format, Verdict-Schema |
| `.claude/agents/external-validator.md` | Vorbild: Playwright-Login via Cookie, `gz_session`, Isolation |
| `.claude/hooks/e2e_browser_test.py` | Bestehendes Browser-Skript — loggt sich NICHT ein (Problem des Issues) |
| `.claude/hooks/e2e_commit_gate.py` | `detect_scope()` — klassifiziert Änderungen als frontend/backend/docs-only |
| `.claude/hooks/qa_gate.py` | Muster: Verdict in Workflow-State schreiben |
| `.claude/e2e_verified.json` | Artefakt — fehlt `verified_commit`-Feld; wird durch neues Format ersetzt |
| `.claude/validator.env` | Staging-Credentials: `GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`, `GZ_VALIDATION_URL` |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | Deploy-Script — bekommt die Hard-Gate-Logik |
| `.claude/hooks/workflow_state_multi.py` | Workflow-State lesen (aktiver Workflow → Spec-Pfad) |

## Existing Patterns

- **Adversary-Agent:** Wird als Claude-Agent (Sonnet, kontext-isoliert) gespawnt. Output enthält VERIFIED/BROKEN/AMBIGUOUS-Block. `qa_gate.py` liest Test-Output und setzt `adversary_verdict` im Workflow-State.
- **External Validator:** Agent mit Playwright-Zugriff; Login via Cookie (`gz_session`). Cookie wird vom Launcher-Script übergeben, nicht vom Agenten selbst ermittelt.
- **Validator-Credentials:** `validator.env` enthält `GZ_VALIDATOR_USER` + `GZ_VALIDATOR_PASS` + `GZ_VALIDATION_URL` für `staging.gregor20.henemm.com`. Analoges Schema für den neuen Agenten.
- **Gate-Mechanismus Adversary:** `pre_commit_gate.py` liest `adversary_verdict` aus Workflow-State und blockt Commit bei fehlendem/BROKEN-Verdict.
- **detect_scope():** Bereits in `e2e_commit_gate.py` — klassifiziert in `frontend-only`, `full-stack`, `backend`, `docs-only`.

## Neue Artefakte (neu zu erstellen)

| Datei | Inhalt |
|-------|--------|
| `.claude/agents/staging-validator.md` | Neuer Agent (analog `implementation-validator.md`) |
| `.claude/hooks/staging_gate.py` | Gate-Logik: prüft `verified_commit == HEAD` + `staging_verdict == VERIFIED` |

## Zu ändernde Dateien

| Datei | Änderung |
|-------|----------|
| `.claude/e2e_verified.json` | Format-Erweiterung: `verified_commit`, `staging_verdict`, `findings[]` |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | Hard-Gate-Block vor dem eigentlichen Deploy einfügen |

## Dependencies

- **Upstream:** `detect_scope()` aus `e2e_commit_gate.py` — bestehende Funktion, kein Code-Änderung nötig
- **Upstream:** Playwright installiert (verifiziert: ✅)
- **Upstream:** Staging-Login über `GZ_VALIDATOR_USER/PASS` (verifiziert: ✅ `validator.env` vorhanden)
- **Downstream:** Deployment-Gate in `deploy-gregor-prod.sh` — liegt in `henemm-infra`, Änderung dort nötig

## Risks & Considerations

1. **henemm-infra ist ein anderes Repo** — Änderungen an `deploy-gregor-prod.sh` müssen dorthin committed und deployed werden (MQ-Nachricht an `infra` sinnvoll)
2. **Playwright-Login** — Login-Flow kann sich ändern (Passkey, Magic-Link, Passwort). Agent muss Passwort-Login via `email`-Input explizit ansteuern, nicht Passkey.
3. **Multi-Step-Flows** — Agent muss Wizard-Steps navigieren können; einzelne Steps sind ohne vorherige Steps nicht direkt erreichbar.
4. **AC-Extraktion** — Agent liest ACs aus Spec-Datei des aktiven Workflows; Workflows ohne UI-ACs sollten kein Staging-Validator-Gate auslösen.
5. **GZ_SKIP_E2E_GATE=1** — Override-Pfad muss Deploy-Log-Eintrag schreiben (kein stiller Bypass), nicht einfach ignorieren.
6. **Worktree-Kompatibilität** — `e2e_verified.json` liegt unter `.claude/` → bei Worktree-Sessions wird das Artefakt im Worktree gespeichert, nicht im Hauptrepo. Deploy liest immer aus Hauptrepo. Lösung: Agent schreibt nach `$REPO_DIR/.claude/e2e_verified.json` (absoluter Pfad).
