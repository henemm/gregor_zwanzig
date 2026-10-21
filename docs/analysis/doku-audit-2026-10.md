# Doku-Audit 2026-10-21 — Specs, ADRs, Referenz, Workflow

Branch `docs/glattziehen-2026-10`. Mechanisch Belegbares ist behoben; dieses Dokument hält die
**offenen inhaltlichen Punkte** fest, die eine PO-Entscheidung brauchen. Offene Arbeit gehört nach
GitHub Issues — die Punkte hier sind Entscheidungsvorlage, kein Backlog.

## Was behoben wurde

| Bereich | Ergebnis |
|---|---|
| Specs `docs/specs/modules/` + Unterordner (≈ 895 Dateien) | Status-Vokabular auf `draft · approved · implemented · superseded · deprecated` normalisiert (vorher 10 Varianten). `implemented` nur mit Beleg: Issue *completed* geschlossen **und** Code-Commit bzw. referenzierter Code vorhanden. Signal-/Wizard-/CompareEditor-/NiceGUI-/MOSMIX-Specs `deprecated` mit Kopfnotiz; Nachfolger in `superseded_by:`. Fehlendes Frontmatter ergänzt (nur außerhalb des Archivs). ~470 tote Pfade mit eindeutigem Ziel (reine Verschiebungen, ADR-0017-Umzug) repariert. |
| Spec-Archiv `docs/specs/_archive/` (866 Dateien) | Status ebenso normalisiert; 93 Dateien ohne Frontmatter bleiben so (Datum wäre erfunden). |
| ADRs | 27 Rückverweise „Ergänzt durch", Teil-Ablösungen im Index, 0026-Lücke erklärt, ADR-0031 → „Teilweise abgelöst durch 0083", tote Pfade annotiert, `## Folgen` → `## Konsequenzen`. **Keine Entscheidung inhaltlich geändert.** |
| Referenz (`docs/reference/`, `docs/features/`, `docs/README.md`) | Hook-Übersicht aller 16 verdrahteten Hooks + Prüfdaten-Tabelle in `gates_und_ratschen.md`; SMS-Token-Reihenfolge gegen Code; Premium-SMS-Reichweite; `/70-deploy` ohne Freigabe-Halt; `at_direct`-Provider; Radar-Alarm-Validator; `api_contract.md` §25 Orts-/Gruppenmodell; `corridor_threshold.py` als gelöscht. |
| `.claude/agents`, `commands`, `standards` | Modelle = CLAUDE.md; AC-Format `**AC-N:** Given/When/Then`; Plugin-Pfade (`workflow.py`/`qa_gate.py` liegen im Plugin); Verdict `VERIFIED` statt `HOLDS`; benannte Testdateien statt Breitlauf; `--delete-branch`; richtiger Validator je Mail-Pfad. |
| CLAUDE.md | Plugin-Pfad, vollständige Modelltabelle, Herkunft der Befehle, Alarm-Mail-Validatoren, kein Winner seit #1108, `sms_format.md`/`renderer_email_spec.md` in Referenztabelle. |

## Offen — braucht PO-Entscheidung

### 1. Stille Rücknahmen dokumentierter Entscheidungen (Regel: Abweichung ⇒ neues ADR)

| # | ADR sagt | Gelebt wird | Vorschlag |
|---|---|---|---|
| 1a | ADR-0005:21 erlaubt SMS-Token `C+/C~/C?` | gestrichen in 6924df6ec (#2233), CLAUDE.md „gibt es nicht" | neues ADR „Confidence-Token entfällt", 0005 → teilweise abgelöst |
| 1b | ADR-0006:18-19: echte Mail-/API-Calls in allen Tests | CLAUDE.md „Zwei Schichten": Kern ohne Netz, aufgezeichnete Fixtures | neues ADR „Zwei Test-Schichten", 0006 → teilweise abgelöst |
| 1c | ADR-0049:22/105/118 Premium-SMS „einziger Kanal ohne Netz", :115 „kein Alarm-Kanal" | Empfangslage korrigiert 2026-09-05; Alarm-Kanal Trip+Compare (#2275/#1533) | neues ADR „Kanal-Parität" (Epic #2133), löst 0049-Teile und 0046 ab |
| 1d | ADR-0046 Kanal-Schwelle über 3 Kanäle | „Alarme erreichen **alle** Kanäle" (#1701) | in 1c mit klären |
| 1e | ADR-0009:49 „keine absoluten Schwellen" | Radar-/Onset-Alarm ist absolut, ohne ADR | ADR „Radar-Alarm-Typ" |
| 1f | ADR-0013 Schwelle `≥` | Code löst bei `>` aus | Code oder ADR angleichen (Bug-Prüfung) |

### 2. Gelebte Grundsatzentscheidungen ohne ADR

Kanal-Parität (#2133) · Trip/Compare-Code-Teilung (ADR-0026 war dafür reserviert) · PR statt
Direkt-Push + CI-Merge-Regel · autonomer Deploy ohne Freigabe-Halt · Regel-Budget · Read-Modify-Write-Merge
(hängt nur noch an der teilweise abgelösten 0031) · ADR-Nummernvergabe ohne Kollisionsschutz
(wiederholte Umnummerierungen paralleler Sessions).

### 3. Wizard-Abschaffung unvollständig (ADR-0032)

- `frontend/src/lib/components/compare/compareWizardState.svelte.ts` und `compare/steps/` leben weiter;
  `feat_2277_s2c_compare_from_vorlage.md` (30.09.) baut noch darauf auf.
- `feat_1301_f2a_compare_new_trip_pattern.md:351` reserviert „ADR-0029 anlege-shell-je-domaene-eigen"
  (Nummer längst vergeben, Inhalt widerspricht der Code-Teilungs-Regel).
- ADR-0032:29 verwirft einen eigenen Compare-Anlege-Editor, die Entscheidung nennt `CompareNewEditor`.

### 4. Specs, die noch „drei Kanäle" als Soll festschreiben

`feat_1717_s3_premium_sms_ui.md:431` (AC-12) · `fix_1719_s3_aus_ist_ein_zustand.md:406` ·
`feat_1703_s8_compare_kanal_tabs.md:21`. Außerdem `forecast_confidence.md:21,42` (Confidence-Spalte/
SMS-Symbole, widerspricht ADR-0005/#2233) und `warn_unavailable_hint.md:226` (`C+/C~/C?`).

### 5. Gates/Konfiguration (`.claude/settings.json`, nicht Teil dieses PR)

- **`data_schema_backup.py` ist nicht verdrahtet** — CLAUDE.md und Playbook behaupten automatischen
  Pre-Snapshot bei Schema-Edits. Datenverlust-Schutz fehlt faktisch (sofern das Plugin ihn nicht einhängt).
- `nebenbefund_gate.py` ist verdrahtet, die Datei existiert nicht (wirkungslos).
- Abgelaufene Prüfdaten: `test_naming_gate` (selbst abgeschaltet 2026-10-09 → Namensregel nicht mehr
  erzwungen), `tests/test_adr_index_drift.py` und `test_api_contract_drift.py` (2026-10-20).
  `file_claim_gate` läuft am 2026-11-11 ab.

### 6. Kleinere Lücken

- `api_contract.md`: ~25 Go-Felder fehlen (User/SMS-Verifikation, Segment, Forecast); Drift-Test prüft
  nur Trip/ComparePreset mit Teilwort-Treffern; Abschnitt „17)" dreifach vergeben.
- Keine Format-Referenz für Telegram und Premium-SMS.
- Normale SMS hat keinen Befehlseingang — reibt sich mit „jeder Kanal beantwortet jede Frage".
- Scheduler-Zuständigkeit Go vs. Python unterschiedlich beschrieben.
- ~50 Specs ab 2026-05-11 nutzen AC-Schreibweisen (`**AC-1 (Titel):**`, `**AC-A1:**`), die die
  Gate-Regex nicht erkennt; 7 haben keine Given/When/Then-ACs.
- `developer` vs. `developer-agent`: zwei Developer-Definitionen.
- ~1 600 tote Pfade auf bewusst gelöschten Code bleiben als historische Verweise stehen.

Detailberichte mit Datei:Zeile lagen im Session-Scratchpad; die hier genannten Stellen sind die
belastbaren Kernbefunde.
