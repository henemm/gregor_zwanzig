# Context: fix-3503-mail-gate-imac (#3503)

## Request Summary

Das Renderer-Commit-Gate (#811, Compare-Teil #1282) verlangt für Commits an
`compare_html.py` bzw. den geteilten Helfern einen frischen
`*_email_validation.yaml` mit `workflow_id == aktiver Workflow`, `passed: true`.
Auf dem iMac kann ein *echter* Nachweis nicht entstehen (keine Test-Postfach-/
Kern-Zugangsdaten; `ssh henemm-pruefen mail-pruefen` läuft im Server-Checkout und
prüft dort den Staging-Stand, nicht den ungecommitteten Arbeitsstand). Zweitens
füllen Testläufe (`--eml` mit Fixture-Mails, z. B. „Gatehausen Nord“) dasselbe Log
mit der `workflow_id` des aktiven Workflows; dadurch erfüllen Tests das Gate.

## Related Files

| Datei | Rolle |
|---|---|
| `.claude/hooks/renderer_mail_gate.py` | Gate; `_compare_validator_log_ok()` (Z. ~331-375) liest `_log/*_email_validation.yaml` |
| `.claude/hooks/email_spec_validator.py` | Compare-Validator; `_write_validation_log()` (Z. 43-130) schreibt das Log; `main()` schreibt es für IMAP- **und** `--eml`-Läufe (Z. ~2095) |
| `.claude/hooks/_validator_log.py` | kollisionsfreie Log-Ablage (`place_exclusively`) |
| `scripts/send_gate_test_mails.py` | Server-Weg: `build_compare_mail()` rendert mit dem **lokalen** Code synthetische Fixture-Mail, `send_compare_mail()` schickt sie per SMTP ins Test-Postfach; Validator dann per IMAP |
| `src/output/channels/email.py::build_mime_message` | reine MIME-Bau-Funktion (Header X-GZ-*), ohne SMTP |
| `.claude/tools/staging_mail_pruefen.py` | Staging-Mailweg (`mail-pruefen`), prüft den deployten Staging-Stand |
| `tests/tdd/test_issue_811_renderer_gate.py` | bestehende Gate-Tests |
| `tests/tdd/test_feat_3228_windrichtung_validatoren.py` u. a. | Tests, die `email_spec_validator.py --eml` als Subprozess aufrufen und dabei ins echte Log schreiben |
| `docs/reference/gates_und_ratschen.md` (Abschnitt Renderer-Commit-Gate), `docs/reference/mail_validators.md` | Doku |

## Existing Patterns

- Matrix-Nachweis: `renderer_mail_gate.py record-matrix` schreibt sha256 der gestagten
  Mail-Dateien in `state.gates.renderer_mail.matrix`; Gate vergleicht Hash (Anti-Stale).
  → Vorbild für einen hash-gebundenen Nachweis.
- Log-Frische: `validated_at` muss jünger als mtime der gestagten Dateien sein.
- `staging_gate.py --write-verdict` / Git-Note: Abnahme nach Deploy, Server-seitig.

## Beobachtungen

- Server-Weg = lokal rendern (ungecommitteter Code) + SMTP + IMAP + Absender-Vertrauen.
  Der Renderer-Anteil ist ohne Netz reproduzierbar (`build_compare_mail` +
  `build_mime_message` + `validate_message`); nur der Transport fehlt. Der Transport
  wird für iMac-Tickets ohnehin nach dem Deploy über `mail-pruefen` auf Staging geprüft.
- Der heutige `mail-pruefen`-Lauf vor dem Commit prüft den alten Staging-Stand; er
  kann die Änderung nicht belegen (Henne-Ei). Eine „signierte Rückgabe“ davon wäre
  ein Schein-Nachweis.
- Shared-Log `_log` enthält Paare passed true/false mit gleicher Sekunde aus Testläufen
  (z. B. `fix-2221-…`, `feat-3260-…`, `feat-3423-…`): das Loch ist real und wird
  laufend genutzt, meist unbemerkt.
- Dieselbe Lücke (`--eml` schreibt Gate-Log) besteht bei Briefing-, Radar- und
  Official-Validator; Issue nennt nur Compare. Kandidat für Folge-Issue.

## Dependencies / Dependents

- Abhängig: `hook_utils.get_active_workflow_name`, `_e2e_paths.shared_repo_dir`.
- Dependents: jeder Commit an Compare-/Helfer-Renderer (Server- und iMac-Sitzungen),
  laufender Workflow `fix-2923-ort-kopf-en` (blockiert).

## Risks

- Gate-Lockerung darf keine stille Umgehung öffnen (Nachweis muss an gestagten Stand
  gebunden und von Tests nicht erzeugbar sein).
- Server-Sitzungen mit IMAP-Zugang dürfen ihren bisherigen Weg behalten.
- Verschärfung (Log nur noch aus IMAP-Läufen) blockiert iMac sofort komplett, wenn der
  Ersatzweg nicht im selben Schritt kommt.

## Analysis

**Type:** Bug (Gate-Logik + Gate-Loch), Tooling.

**Root Cause (belegt):**
1. `email_spec_validator.py:2095` schreibt das Gate-Log nach beiden Zweigen (`--eml` :2064-2080, IMAP :2081-2093) ohne Herkunftsfeld; `renderer_mail_gate.py:339-380` prüft nur `workflow_id`/`passed`/`validated_at` → Fixture-Läufe erfüllen das Gate.
2. Konkreter Verursacher: `tests/tdd/test_feat_3228_windrichtung_validatoren.py:420-426` startet den Validator als Subprozess mit `cwd=ROOT` und geerbter Workflow-Variable → passed:true/false-Paare im echten `_log`.
3. iMac: keine IMAP-/SMTP-Zugangsdaten → kein IMAP-Log möglich; `mail-pruefen` prüft vor dem Commit nur den alten Staging-Stand (Henne-Ei).
4. Nebenbefund: Gate liest nur das jüngste passende Log und bricht bei `passed: false` ab → ein Fixture-Fehlerlauf verdeckt einen echten Erfolg.

**Varianten:**

| Variante | schließt Loch | iMac möglich | mechanisch | LoC | Dateien |
|---|---|---|---|---|---|
| V0 nur Herkunftsfeld | ja | nein | ja | ~35 | 3 |
| **V1 Herkunftsfeld + lokaler Render-Nachweis** | ja | ja | ja, hash-gebunden | ~240 | 5-6 |
| V2 Aufschub-Marker ohne Rendern | nein | ja | nein | ~100 | 3-4 |
| V3 signierte `mail-pruefen`-Rückgabe | ja | Schein (alter Stand) | formal | ~200+ | 5+ |

**Empfehlung V1:**
- Validator-Log bekommt `quelle: imap|eml`; Gate (Compare) akzeptiert nur `quelle: imap` (Whitelist), überspringt Logs anderer Herkunft (continue statt Abbruch).
- Neuer Recorder `renderer_mail_gate.py record-compare-lokal`: rendert mit dem gestagten Code die Gate-Fixture (`scripts/send_gate_test_mails.build_compare_mail`, lazy import) für de UND en über `build_mime_message` (mail_type=compare, format=full, lang), prüft je Sprache mit `email_spec_validator.validate_message` und schreibt nur bei Erfolg den Eintrag `gates.renderer_mail.compare_lokal = {passed, mail_files_hash, langs, recorded_at}` in den Workflow-Zustand (nicht in `_log` → Tests erzeugen ihn nicht nebenbei).
- Gate: Compare-Nachweis = frisches imap-Log ODER `compare_lokal` mit Hash == gestagter Mail-Stand.
- Transport/Live-Daten bleiben Aufgabe von `/e2e-verify` (`mail-pruefen compare de|en`) nach Deploy; Doku nennt das.
- Restrisiko wie Matrix-Nachweis: Zustand handschreibbar (Absicht, nicht Versehen), dokumentiert.

**Affected Files:**
- MODIFY `.claude/hooks/renderer_mail_gate.py` (~90 LoC)
- MODIFY `.claude/hooks/email_spec_validator.py` (~8 LoC)
- CREATE `tests/tdd/test_compare_mail_gate_nachweis.py` (~110 LoC)
- MODIFY Bestandstests mit Fixture-Logs (`test_issue_811_renderer_gate.py`, `test_renderer_gate_compare_dispatch.py`, ggf. weitere) → `quelle: imap` (~15 LoC)
- MODIFY `docs/reference/gates_und_ratschen.md` (~15 LoC)

**Scope/Risk:** ~240 LoC, Kern 3 Dateien; Risiko hoch (Gate-Code) → Adversary 2 Runden.

**Reihenfolge:** Herkunftsfeld + Whitelist + Recorder in EINEM Commit (sonst iMac sofort ganz blockiert).

**Out of scope → Folge-Issue:** Briefing-/Radar-/Official-Validator haben dieselbe Lücke; dort zentral in `_validator_log.py` lösen.

**Open Questions:** keine an den PO (Gate-Mechanik ist Tech-Lead-Entscheidung; die Spec-Freigabe zeigt die Lockerung transparent).
