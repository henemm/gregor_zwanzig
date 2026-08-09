# Context: fix-1614-briefing-warnfenster

## Request Summary
**KORRIGIERT nach Forensik am echten Vorfall (siehe unten) — die ursprüngliche
Issue-Prämisse ("Warnung fehlte im Briefing wegen zu engem Zeitfenster") ist
widerlegt.** Der tatsächliche Umfang, PO-bestätigt 2026-08-08, vier Teile:

1. **Doppelversand:** Eine amtliche Warnung, die bereits korrekt im Briefing
   erscheint, wird bis zu 15 Minuten später vom unabhängigen Alarm-Checker
   NOCHMAL als eigene, redundante Nachricht verschickt — weil der
   Briefing-Pfad das Melde-Gedächtnis nie beschreibt.
2. **GELB-Kontrast in der E-Mail:** Die Warnfarbe für Stufe 2 (`G_ALERT_L2`)
   hat nachweislich 4,11:1 Kontrast — unter der von CLAUDE.md geforderten
   WCAG-AA-Grenze (4,5:1). Deshalb wird die Warnung leicht übersehen.
3. **Fehlende Verdrahtung (#1461 S3b-2a):** Der Briefing-Versand ruft die
   bereits gebaute Kanal-Schwellen-Funktion (`min_official_level_for_threshold`)
   nie auf — GELB-Warnungen erreichen SMS/Telegram im Briefing deshalb nie,
   obwohl genau das am 2026-08-05 als PO-Entscheidung bereits beschlossen und
   für den separaten Alarm-Weg bereits umgesetzt wurde. Gilt für Trip UND
   Ortsvergleich (dort als offener Teilschritt S3b-2b bereits bekannt).
4. **"!"-Kennzeichnung:** Neue, bisher nicht existierende Kennzeichnung für
   amtliche Warnungen, die den SMS-Kanal erreichen.

## 🔴 Forensik-Befund (2026-08-08, entscheidend für den Zuschnitt)

Die ursprüngliche Issue-Behauptung ("Warnung fehlte in SMS/E-Mail des
16:01-Uhr-Briefings") wurde direkt an der **tatsächlich verschickten Mail**
geprüft (Resend-Read-API, `RESEND_READ_API_KEY` aus
`/home/hem/henemm-infra/.env`, `GET https://api.resend.com/emails/<id>`,
User-Agent-Header nötig sonst Cloudflare-403). Ergebnis: Mail-ID `86918bc7`
(2026-08-08 16:01:33 UTC, Betreff „[KHW 403] Etappe 2 … — Abend") enthielt
die Warnung korrekt:
```
━━ Amtliche Warnungen ━━
  ⚠️ Amtliche Warnung: Yellow Thunderstorm Warning (So 09.08. · 14:00 – Mo 10.08. 01:59)
```
Die 14 Minuten später verschickte Mail-ID `7d0bbfd6` (16:15:01, Betreff
„[KHW 403] Segment 4 · GELB Gewitter (So)") ist **dieselbe** Warnung
(Region „Trentino Alto Adige", identischer Zeitraum, Stufe GELB) — als
eigene, redundante Alarm-Mail. Auch die reine Zeitfenster-Rechnung mit den
echten historischen Werten (Snapshot `weather_snapshots/5f534011_2026-08-09.json`,
Segment „Ziel" 46.706056/12.406271, Fenster 06:00–18:00 UTC alt vs. Warnung
12:00–23:59 UTC) bestätigt das: die Warnung überschneidet sich mit dem ALTEN
Fenster bereits — `filter_alerts_to_window()` direkt mit den echten Werten
aufgerufen liefert 1 Treffer. **Die Fenster-Theorie war falsch, das Symptom
war ein Doppelversand, keine fehlende Warnung.**

## Related Files

### Teil 1 — Doppelversand
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:1061-1151` (`check_official_alert_triggers`) | Unabhängiger 15-Min-Checker, deckt die GESAMTE Restroute ab (#1460 P4) — findet Warnungen, die das Briefing bereits gezeigt hat, erneut und meldet sie separat, weil er nicht weiß, dass sie schon gezeigt wurden. |
| `src/services/trip_alert.py:1153-1167` (`_record_official_alert_state`) | Schreibt NACH erfolgreichem Alarm-Versand den Melde-Stand (`official_alert:`-Namensraum, `AlertStateService`). Der Briefing-Pfad ruft das nirgends auf — genau diese Lücke erzeugt den Doppelversand. |
| `src/services/trip_report_scheduler.py` (nahe `:1028`, vor `write_anchor_and_reset_memory`, `_send_trip_report_outcome`) | Hier fehlt der Aufruf, der die im Briefing gezeigten `sw.official_alerts` als „gemeldet" vermerkt. |
| `src/services/trip_report_scheduler.py:1180-1187` (`_reset_alert_state_after_briefing`) | Löscht nur den Änderungs-Raum; der `official_alert:`-Raum bleibt bewusst erhalten (#1460 P2) — passt zur Lösung, muss nicht geändert werden. |
| `src/services/alert_briefing_anchor.py` | Geteilter Baustein (#1467 S2 AG5) für Anker+Reset zwischen Trip und Ortsvergleich — Vorbild/Zielort für die neue geteilte "als gemeldet vermerken"-Funktion (PO-Linie: "zwingend derselbe Code"). |
| `src/output/renderers/alert/official_alerts.py:407` (`official_alert_state_key`) | Kanonische Schlüsselbildung, MUSS von der neuen Record-Funktion verwendet werden (Präfix-Kopplungstest existiert bereits, `test_official_alert_state_key_praefix_stimmt_mit_dem_reset_filter_ueberein`). |

### Teil 2 — GELB-Kontrast
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/design_tokens.py:32` | `G_ALERT_L2 = '#9a6f00'` — Kommentar im Code selbst: „4,11:1 auf G_PAPER" — unter der CLAUDE.md-Mindestgrenze 4,5:1 (WCAG-AA). |
| `src/output/renderers/alert/official_alerts.py:1330,1335,1408,207,1222` | Alle Stellen, die `G_ALERT_L2/L3/L4` als `level_colors`-Mapping verwenden (Warn-Block, Standalone-HTML, Compact-Badges) — Farbwert wird zentral aus `design_tokens.py` bezogen, EINE Änderung wirkt überall. |
| `src/output/renderers/email/compare_html.py:107` | Compare-Pendant nutzt denselben Token `G_ALERT_L2` (mit eigenem Hintergrund-Ton `#f2e4b0`) — Kontrast dort separat zu prüfen, da Text/Hintergrund-Kombination abweicht. |

### Teil 3 — Fehlende Kanal-Schwellen-Verdrahtung (#1461 S3b-2a/S3b-2b)
| File | Relevance |
|------|-----------|
| `src/services/alert_urgency.py:71-80` (`min_official_level_for_threshold`) | Fertige Funktion: Kanal-Schwelle ('LOW'/'MODERATE'/'HIGH') → niedrigste amtliche Stufe, die den Kanal erreichen darf. Bereits gebaut, PO-Entscheidung 2026-08-05 bereits getroffen — **wird vom Trip-Briefing nie aufgerufen** (verifiziert: `grep` auf `trip_report_scheduler.py` findet keinen Treffer). |
| `src/output/tokens/hazard_symbols.py:32-37` | `MIN_SMS_LEVEL = 3` (alte, feste Grenze) — bleibt als Fallback-Default bestehen, wird aber pro Aufruf durch `sms_alert_min_level` überschrieben, WENN der Aufrufer ihn setzt. |
| `src/output/renderers/sms_trip.py:143-178,381,413-458` (`_official_alert_entries`, `sms_alert_min_level`-Parameter) | Die Parameter-Durchreichung existiert bereits bis zum Renderer — nur der EINE Aufruf-Ort im Scheduler übergibt nie einen aus `trip.alert_channel_thresholds` abgeleiteten Wert. |
| `src/services/trip_report_scheduler.py` | Baustelle: hier muss `alert_urgency.min_official_level_for_threshold(trip.alert_channel_thresholds.get('sms', 'LOW'))` (und analog fürs Telegram-Pendant) berechnet und durchgereicht werden. |
| `src/services/comparison_engine.py:704,869` (laut `project_1461_s3b2a_kanal_schwelle`-Memory) | Compare-Pendant derselben Lücke (S3b-2b, bereits als offen dokumentiert) — Teilungsregel verlangt denselben Fix hier. |
| `frontend/.../shared/alarme-tab/alertChannelState.ts` | Der Bedienort, den der PO meint: Reiter „Alarme", `AlertChannelThresholdState` (LOW/MODERATE/HIGH je Kanal, Default LOW). Muss NICHT geändert werden — ist bereits der richtige, geteilte Bedienweg; nur das Backend liest ihn im Briefing-Pfad nicht aus. |

### Teil 4 — „!"-Kennzeichnung
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/official_alerts.py:368-404` (`official_alerts_to_sms_entries`) | Erzeugt die `(Kürzel, Stufenbuchstabe, Stunde)`-Tripel, die in die SMS-Kurzform einfließen — hier oder an der Stelle, die diese Tripel zu Text zusammensetzt, muss die „!"-Kennzeichnung ergänzt werden. Existiert heute nirgends im Code (verifiziert per grep). |

## Existing Patterns
- **#1460 P2** (`AlertStateService.reset()`, `services/alert_state.py`) trennt
  bereits zwei Namensräume: Änderungs-Raum (wird beim Briefing zurückgesetzt)
  vs. `official_alert:`-Raum (überlebt den Reset). Die fehlende Schreibung in
  diesen Raum aus dem Briefing-Pfad ist die Lücke, die Teil 1 schließt.
- **#1467 S2 AG5** hat "beide Pfade müssen sich gleich verhalten" bereits für
  Anker+Reset als EINEN geteilten Baustein etabliert — Vorlage für die neue
  geteilte "record"-Funktion statt einer Zweitfassung von
  `_record_official_alert_state`.
- **#1461 S3a/S3b-2a** hat die komplette Dringlichkeits-/Kanal-Schwellen-
  Architektur bereits gebaut und für den Alarm-Pfad verdrahtet (`alert_urgency.py`,
  `alert_channel_threshold.py`, Frontend-Reiter „Alarme"). Teil 3 ist reines
  Nachziehen der bereits getroffenen PO-Entscheidung ("Bericht zeigt künftig
  mehr, auch gelb", 2026-08-05) für den Briefing-Pfad — keine neue Entscheidung,
  keine neue Architektur.
- **Design-Tokens zentral** (`design_tokens.py`) — EIN Ort für alle
  Warnstufen-Farben, von mehreren Renderern konsumiert (Teil 2 ändert nur
  den Token-Wert, keine Konsumenten-Logik).

## Dependencies
- **Upstream:** `services.official_alerts.get_official_alerts_with_status` /
  `.base.filter_alerts_to_window` (Zeitfenster-Filterung); `AlertStateService`
  (Melde-Gedächtnis, Datei je Nutzer/Trip).
- **Downstream:** E-Mail-/SMS-/Telegram-Renderer, die `sw.official_alerts`
  konsumieren (Format unverändert); `trip_alert.py`s 15-Min-Checker, der
  `AlertStateService` liest.

## Existing Specs
- `docs/specs/modules/rework_1460_t1_relevanzfilter.md` — P2 Gedächtnis, P4
  Ort+Zeit-Kopplung (AC-20..AC-33). Direkte fachliche Nachbarschaft.
- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — AG5 geteilter
  Baustein Anker+Reset.
- `docs/specs/modules/feat_1461_s3b1_briefing_sichtbarkeit.md` —
  Sichtbarkeits-Regeln im Briefing.

## Vorhandene Tests als Vorbild
- `tests/tdd/test_official_alert_time_window.py` — P4-Fenster-Semantik des
  Alarm-Checkers (Pro-Segment-Fenster, Dedup-Schlüssel).
- `tests/tdd/test_alert_state_briefing_reset.py` — AC-20..23, inkl. echtem
  `_reset_alert_state_after_briefing()`-Aufrufpfad über eine echte
  `TripReportSchedulerService`-Instanz. AC-22/22b sind exakt das Muster
  "Briefing hat stattgefunden → Checker meldet danach nicht erneut / meldet
  bei echter Verschärfung doch" — das Gegenstück zu dem, was #1614 fürs
  Briefing selbst braucht.
- `tests/tdd/test_official_alert_dedup_timespan.py`,
  `test_issue_1088_official_alert_triggers.py` — weitere Nachbarn.

## Risks & Considerations
- **Doppelversand-Gefahr bleibt bei reiner Fenster-Erweiterung:** Wird nur das
  Abfragefenster geweitet, ohne das Melde-Gedächtnis aus dem Briefing-Pfad zu
  beschreiben, verschiebt sich der Bug nur — die Warnung erscheint dann im
  Briefing UND weiterhin separat ~15 Min später, weil der Checker sie
  weiterhin für "neu" hält. Die Spec muss beide Teile explizit als AC fassen.
- **Fachliche Entscheidung Fensterdefinition:** "ab jetzt bis Ende Zieletappe"
  (im Issue vorgeschlagen) vs. Alternativen — für PO-Freigabe in der Spec
  explizit machen.
- **Test-Politik:** `AlertStateService`/`get_official_alerts_with_status` sind
  reine Dateizugriffe ohne Netz/Live-Dienst → Kern-Schicht (deterministisch),
  passend zu den bestehenden Nachbartests, kein Live-E2E nötig für den
  Kern-Nachweis.
- **Mandantentrennung:** `AlertStateService(user_id=...)` durchgängig; mit
  zwei Nutzern testen (CLAUDE.md-Pflicht).
- **Kein Compare-Pendant nötig:** siehe `comparison_engine.py` oben — dort
  existiert das enge Fenster gar nicht, also keine Teilungs-Verletzung durch
  diesen Fix. Pendant-Gate (#1481 B) greift ohnehin nur bei `frontend/`- und
  `compare_*`/`trip_*`-präfigierten Renderer-Neuanlagen, nicht bei
  `services/`-Änderungen.
- **Laufende Parallel-Arbeit:** Worktree `intake-1555` (#1467 S3, Workflow
  `rework-1467-s3-nowcast`, Phase Validation, kein Live-Lock) ändert
  `trip_alert.py` im Bereich ~658-970 (Nowcast-Tagesobergrenze). Die für
  #1614 relevanten Zeilen (~1061-1225) sind davon nicht direkt berührt;
  spätere Rebase-Reibung beim Merge ist möglich, aber kein Blocker.

## Offene Frage für /20-analyse
Soll die neue "als im Briefing gemeldet vermerken"-Logik als eigenständige
Funktion neben `_record_official_alert_state` in `trip_alert.py` liegen, per
Extraktion in `alert_briefing_anchor.py` geteilt werden, oder direkt
`TripAlertService._record_official_alert_state` aus dem Scheduler heraus
aufrufen? Analyse-Phase soll entscheiden, welcher Weg der etablierten
Teilungs-Konvention (#1467 S2 AG5) am ehesten entspricht.

→ **Beantwortet, siehe Analysis-Sektion unten.**

## Analysis

### Type
Bug (Teil 1, 3) + kleine Design-Korrektur (Teil 2) + neues, kleines Feature
(Teil 4). Zuschnitt PO-bestätigt 2026-08-08, nach Forensik-Korrektur (s.o.)
und mehreren Rückfragen im Chat. **Kein Fenster-/Zeitproblem mehr Teil des
Zuschnitts** — die ursprüngliche Issue-Hypothese ist widerlegt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/alert_briefing_anchor.py` | MODIFY (neue Funktion) | `record_official_alerts_reported(*, user_id, entity_id, alerts)` — State-Schreib-Body aus `trip_alert.py:1153-1167` übernommen. |
| `src/services/trip_alert.py:1153-1167` | MODIFY (Refactor) | `_record_official_alert_state` wird dünner Wrapper um die neue geteilte Funktion. |
| `src/services/trip_report_scheduler.py` (nahe `:1028`) | MODIFY | Nach erfolgreichem, nicht-Ad-hoc-Versand: gezeigte `sw.official_alerts` als „gemeldet" vermerken (Teil 1). |
| `src/services/trip_report_scheduler.py` (SMS/Telegram-Request-Aufbau) | MODIFY | `sms_alert_min_level` aus `trip.alert_channel_thresholds` ableiten und durchreichen; analoge Telegram-Schwelle (Teil 3). |
| `src/services/comparison_engine.py:704,869`-Umfeld | MODIFY | Dieselbe Verdrahtung für Ortsvergleich (Teil 3, S3b-2b). |
| `src/output/renderers/email/design_tokens.py:32` | MODIFY | `G_ALERT_L2` auf einen Wert mit ≥4,5:1 Kontrast anheben (Teil 2). |
| `src/output/renderers/alert/official_alerts.py:368-404` (`official_alerts_to_sms_entries`) bzw. Konsument in `sms_trip.py` | MODIFY | „!"-Präfix für amtliche Warnungen, die den SMS-Kanal erreichen (Teil 4). |
| Tests | MODIFY/CREATE | `test_alert_state_briefing_reset.py` (Teil 1), neuer/erweiterter Test für Kanal-Schwelle im Briefing-Pfad (Teil 3), Kontrast-Wächter oder Snapshot-Vergleich (Teil 2), SMS-Format-Test (Teil 4). |

### Scope Assessment
- Files: ~8 Produktivdateien (davon 1 neue Funktion, 2 Wiring-Ergänzungen, 1 Refactor, 1 Konstante, 1 Renderer-Ergänzung), mehrere Testdateien erweitert.
- Estimated LoC: +70–100 Produktivcode, +200–300 Tests (deutlich größer als der ursprüngliche Zuschnitt, weil drei zusätzliche, PO-bestätigte Teilthemen dazukamen).
- Risk Level: **MEDIUM–HIGH** (sicherheitsrelevanter Warnpfad, vier unabhängige Änderungsflächen, Renderer-Commit-Gate #811 greift wegen `official_alerts.py`/`sms_trip.py`/`design_tokens.py`-Änderungen — `briefing_mail_validator.py` UND `email_spec_validator.py` können beide betroffen sein).

### Technical Approach

**Teil 1 — Doppelversand-Schutz** (unverändert gegenüber der ersten Analyse,
nur ohne die Fenster-Änderung): neue geteilte Funktion
`record_official_alerts_reported()` in `alert_briefing_anchor.py`, aufgerufen
im Scheduler nach erfolgreichem, nicht-Ad-hoc-Versand, VOR
`write_anchor_and_reset_memory`. `_record_official_alert_state` in
`trip_alert.py` wird Wrapper darauf.

**Teil 2 — GELB-Kontrast:** `G_ALERT_L2` in `design_tokens.py` auf einen
dunkleren Ocker-/Gelbton anheben, der ≥4,5:1 gegen `G_PAPER` UND gegen
`G_CARD` (weiß) erreicht — beide Hintergründe kommen je nach Einbettung vor
(Trip-Warn-Block sitzt auf der Seite, Compare-Badges evtl. auf Karte).
Reiner Token-Wert-Wechsel, keine Konsumenten-Logik ändert sich.

**Teil 3 — Kanal-Schwelle verdrahten:** Im Scheduler (Trip) und in
`comparison_engine.py` (Compare) den bereits fertigen
`alert_urgency.min_official_level_for_threshold(threshold)` aufrufen, mit
`trip.alert_channel_thresholds.get("sms", "LOW")` bzw. dem Telegram-Pendant,
und das Ergebnis als `sms_alert_min_level` (SMS) sowie an der äquivalenten
Telegram-Stelle durchreichen. Kein neuer Mechanismus — nur der fehlende aus
#1461 S3b-2a nachgezogene Aufruf. Compare-Pendant folgt der Teilungsregel
(dieselbe Funktion, keine Zweitfassung).

**Teil 4 — „!"-Kennzeichnung:** Amtliche Warnungen, die den SMS-Kanal
erreichen (nach Teil-3-Schwelle), bekommen ein „!"-Präfix in der SMS-Kurzform.
Exakte Platzierung (vor dem Kürzel? vor dem ganzen Block?) und ob Telegram
dieselbe Kennzeichnung bekommt, ist eine offene Frage für die Spec-ACs.

### Dependencies
- `services/alert_state.py` (`AlertStateService`, `OFFICIAL_ALERT_KEY_PREFIX`) — Teil 1, unverändert wiederverwendet.
- `output/renderers/alert/official_alerts.py:407` (`official_alert_state_key`) — Teil 1, MUSS verwendet werden.
- `services/alert_urgency.py` (`min_official_level_for_threshold`, bereits vorhanden) — Teil 3, MUSS verwendet werden, keine zweite Schwellen-Logik.
- `output/renderers/email/design_tokens.py` — Teil 2, zentraler Farb-Token.
- Renderer-Commit-Gate #811 (`renderer_mail_gate.py`) — betrifft Teil 1 (trip_report_scheduler.py-Umfeld zählt nicht direkt, aber `official_alerts.py`/`sms_trip.py` sind explizit gelistet) UND Teil 3/4. Vor Commit: `tests/tdd/test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` grün.

### Risiken (gegengeprüft)
- **Teil 1:** Kaltstart unkritisch (`state.get(key)` liefert `None`); Reset (`_reset_alert_state_after_briefing`) schont den `official_alert:`-Namensraum bereits strukturell; echte Eskalation meldet weiterhin korrekt (State vergleicht `level`).
- **Teil 2:** Kontrast-Fix darf die zweite Verwendung (`compare_html.py:107`, eigener Hintergrund `#f2e4b0`) nicht verschlechtern — dort separat nachrechnen, nicht blind denselben Hex übernehmen falls der Hintergrund abweicht.
- **Teil 3:** Mehr SMS-Traffic als bisher (GELB erreicht jetzt SMS, sofern Nutzer die Schwelle nicht selbst hochgesetzt hat) — das ist die **bereits getroffene** PO-Entscheidung von #1461 S3b-2a, kein neues Risiko, aber sollte in der Spec explizit als bewusste Verhaltensänderung stehen, nicht als Nebeneffekt.
- **Teil 4:** SMS-Zeichenbudget (160 Zeichen) — ein zusätzliches „!" pro Warnung ist minimal, aber bei mehreren gleichzeitigen Warnungen in Summe zu prüfen.
- **Test-Politik:** Teile 1/3 sind reine Dateizugriffe/Funktionsaufrufe (Kern-Schicht). Teil 2 (Kontrast) und Teil 4 (SMS-Text) sind Renderer-Änderungen — Pflicht-Validatoren (`briefing_mail_validator.py`) laufen vor „E2E bestanden".

### Open Questions
- [ ] Teil 4: „!" nur bei SMS, oder auch bei Telegram? (Telegram hat bereits Emoji-Kennzeichnung `⚠️`/`🔴` — evtl. redundant.)
- [ ] Teil 3: exakter GELB-Grenzfall — reicht `LOW` als Default wirklich bis Stufe 2 runter, oder soll die Spec das als eigenes AC mit Beispiel-Level fixieren (Mehrdeutigkeit vermeiden)?
- [ ] Teil 2: konkreter neuer Hex-Wert für `G_ALERT_L2` — muss vor Implementierung berechnet/geprüft werden (Kontrast-Rechner gegen G_PAPER `#f6f4ee` UND G_CARD `#ffffff`).
