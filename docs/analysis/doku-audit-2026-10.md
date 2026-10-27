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

| # | ADR sagt | Gelebt wird | Stand |
|---|---|---|---|
| 1a | ADR-0005:21 erlaubt SMS-Token `C+/C~/C?` | gestrichen in 6924df6ec (#2233), CLAUDE.md „gibt es nicht" | **erledigt 2026-10-21:** [ADR-0093](../adr/0093-confidence-token-in-sms-entfaellt.md), 0005 → teilweise abgelöst |
| 1b | ADR-0006:18-19: echte Mail-/API-Calls in allen Tests | CLAUDE.md „Zwei Schichten": Kern ohne Netz, aufgezeichnete Fixtures | **erledigt 2026-10-21:** [ADR-0094](../adr/0094-zwei-test-schichten-kern-und-live-e2e.md), 0006 → teilweise abgelöst |
| 1c | ADR-0049:22/105/118 Premium-SMS „einziger Kanal ohne Netz", :115 „kein Alarm-Kanal" | Empfangslage korrigiert 2026-09-05; Alarm-Kanal Trip+Compare (#2275/#1533) | **erledigt 2026-10-21:** [ADR-0095](../adr/0095-kanal-paritaet-jeder-kanal-jede-frage.md), 0049 + 0046 → teilweise abgelöst |
| 1d | ADR-0046 Kanal-Schwelle über 3 Kanäle | „Alarme erreichen **alle** Kanäle" (#1701) | **erledigt 2026-10-21** in ADR-0095: Schwelle bleibt, gilt für alle vier Kanäle (`AlertChannelThresholdsConfig.PremiumSms` seit #1701 S2b, `split_by_threshold()` an allen sechs Nahtstellen); „alle Kanäle" = alle vom Nutzer gewählten |
| 1e | ADR-0009:49 „keine absoluten Schwellen" | Radar-/Onset-Alarm ist absolut, ohne ADR | **erledigt 2026-10-21:** [ADR-0096](../adr/0096-radar-onset-alarm-absolute-schwelle.md), 0009 → teilweise abgelöst (Ausnahme) |
| 1f | ADR-0013 Schwelle `≥` | Auslösung strikt `>` | **geprüft 2026-10-21, kein Bug** — s. Befund unten |

**Befund 1f (ADR-0013 `≥` vs. Code `>`):** Zwei verschiedene Vergleiche, kein Widerspruch im
Verhalten. ADR-0013 definiert nur die **Renderer-Einstufung** „über Schwelle":
`over_thr()` = `abs(value_to − value_from) >= threshold` (`src/output/renderers/alert/model.py:298`)
— deckt sich mit dem ADR. Die **Auslösung** liegt in der Erkennung:
`triggered = abs(delta) > threshold` (`src/services/weather_change_detection.py:865`, stetige
Größen; Gewitter läuft über Niveaus, `:862-863`). Daneben `≥`: Beginn-Verschiebung
(`weather_change_detection.py:939`, `< threshold` ⇒ kein Alarm) und Melde-Gedächtnis
(`src/services/deviation_alert_engine.py:246`). Nutzersichtbar ist nur der Grenzfall „Änderung
genau gleich der Schwelle" bei stetigen Größen (z. B. Böen Δ = 20,0 km/h bei „standard"): kein
Alarm. Dem Renderer kann so ein Ereignis aus der Erkennung nie erreichen, die Mail-Einstufung ist
also nie falsch. Das strikte `>` ist PO-freigegebene Spec: `rework_1460_t1_relevanzfilter.md`
AC-18 („striktes `>` — bei genau 20 km/h KEIN Alarm"), bewacht von
`tests/tdd/test_alert_sensitivity_levels.py:333` (+ `:356` Δ = 20,01 löst aus) und
`tests/integration/test_friendly_format_email_and_alerts.py:699/:751`. **Empfehlung: kein Bug,
Code nicht ändern;** ADR-0013 bei nächster Berührung per Nachtrag präzisieren (Einstufung `≥`,
Auslösung `>` laut AC-18).

### 2. Gelebte Grundsatzentscheidungen ohne ADR

**Erledigt 2026-10-21:** ADR-0094/0095 sowie 0097 Code-Teilung (0026 aufgegangen), 0098 Liefer-Workflow, 0099 autonomer Deploy, 0100 Regel-Budget, 0101 Read-Modify-Write-Merge. Offen: ADR-Nummernvergabe ohne Kollisionsschutz.

### 3. Wizard-Abschaffung unvollständig (ADR-0032)

Code-Rest gebucht in #1199; ADR-0032-Nachtrag klärt `CompareNewEditor` (dünne Shell über geteilte Bausteine, s. ADR-0097). Kopfkommentar von `CompareNewEditor.svelte` verweist fälschlich auf „ADR-0029" (gemeint 0097) — Code, bei nächster Berührung korrigieren.

- `frontend/src/lib/components/compare/compareWizardState.svelte.ts` und `compare/steps/` leben weiter;
  `feat_2277_s2c_compare_from_vorlage.md` (30.09.) baut noch darauf auf.
- `feat_1301_f2a_compare_new_trip_pattern.md:351` reserviert „ADR-0029 anlege-shell-je-domaene-eigen"
  (Nummer längst vergeben, Inhalt widerspricht der Code-Teilungs-Regel).
- ADR-0032:29 verwirft einen eigenen Compare-Anlege-Editor, die Entscheidung nennt `CompareNewEditor`.

### 4. Specs, die noch „drei Kanäle" als Soll festschreiben

`feat_1717_s3_premium_sms_ui.md:431` (AC-12) · `fix_1719_s3_aus_ist_ein_zustand.md:406` ·
`feat_1703_s8_compare_kanal_tabs.md:21`. Außerdem `forecast_confidence.md:21,42` (Confidence-Spalte/
SMS-Symbole, widerspricht ADR-0005/#2233) und `warn_unavailable_hint.md:226` (`C+/C~/C?`).

### 5. Gates/Konfiguration

**Erledigt 2026-10-21 (#2592):** `data_schema_backup.py` verdrahtet, toter `nebenbefund_gate`-Eintrag entfernt, Prüfdaten auf 2027-01-19 verlängert (gebucht in #1197). Offen: `file_claim_gate` läuft am 2026-11-11 ab (#1197).

### 6. Kleinere Lücken

- ~~`api_contract.md`: ~25 Go-Felder fehlen (User/SMS-Verifikation, Segment, Forecast); Drift-Test prüft
  nur Trip/ComparePreset mit Teilwort-Treffern; Abschnitt „17)" dreifach vergeben.~~ **Erledigt** (Felder ergänzt, 17/17.1/17.2; Drift-Test-Schwäche bleibt).
- ~~Keine Format-Referenz für Telegram und Premium-SMS.~~ **Erledigt:** `telegram_format.md`, `premium_sms_format.md`.
- Normale SMS hat keinen Befehlseingang — reibt sich mit „jeder Kanal beantwortet jede Frage". Ist-Stand in `sms_format.md` §1a; Produktfrage in #1199.
- ~~Scheduler-Zuständigkeit Go vs. Python unterschiedlich beschrieben.~~ **Erledigt:** Go-Cron taktet, Python entscheidet/versendet (architecture.md, CLAUDE.md).
- ~50 Specs ab 2026-05-11 nutzen AC-Schreibweisen (`**AC-1 (Titel):**`, `**AC-A1:**`), die die
  Gate-Regex nicht erkennt; 7 haben keine Given/When/Then-ACs.
- `developer` vs. `developer-agent`: zwei Developer-Definitionen (gebucht in #1197).
- ~1 600 tote Pfade auf bewusst gelöschten Code bleiben als historische Verweise stehen.

Detailberichte mit Datei:Zeile lagen im Session-Scratchpad; die hier genannten Stellen sind die
belastbaren Kernbefunde.
