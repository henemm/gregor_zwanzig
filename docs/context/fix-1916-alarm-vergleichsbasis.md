# Context: fix-1916-alarm-vergleichsbasis

Issue: [#1916](https://github.com/henemm/gregor_zwanzig/issues/1916) · `bug` · `priority:high` · `session:khw`
Phase 2 (Analyse), erhoben 2026-08-16.

## Request Summary

Der Abweichungsalarm für Trips vergleicht aktuelle Wetterwerte nicht gegen das zuletzt
verschickte Briefing, sondern gegen `WeatherSnapshotService.load_dated(trip.id, heute)`
(`src/services/trip_alert.py:543-664`, `_get_cached_weather`). Diese Datei wird ausschließlich
beim erfolgreichen Briefing-Versand neu geschrieben (`trip_report_scheduler.py:1505-1512`,
`_write_briefing_anchor`). Scheitert ein Briefing (Prozessabbruch, siehe #1897), bleibt die
Vergleichsbasis auf dem Stand des letzten Erfolgs stehen — im Praxisfall am 16.08. verglich ein
Alarm um 18:15 Uhr einen ~24h alten Wert (Vorabend 18:03 Uhr) statt eines frischen.

PO-Anforderung (2026-08-16, verbindlich):
1. **Sichtbarkeit:** Alarmnachricht muss den Referenz-Zeitpunkt (Ortszeit) erkennen lassen.
2. **Rollierende Basis:** Basis soll sich mit jedem erfolgreichen Alarm-Check weiterschieben,
   nicht nur beim Briefing-Erfolg zurückgesetzt werden — ein gescheitertes Briefing darf die
   Erkennung nicht stundenlang einfrieren.

## Type

Bug (nutzersichtbares Fehlverhalten) + Enhancement (zwei bindende PO-Anforderungen, die über
den reinen Bugfix hinausgehen).

## Verifizierter Root Cause

- **Lesepfad:** `trip_alert.py:_get_cached_weather()` (Zeile 543-664) — lädt `load_dated`
  (heutiger Ortstag), Fallback `load` (undatiert), Fallback `load_target_date`. Aufgerufen aus
  `check_all_trips()` Zeile 478-480 mit `tagesgleicher_anker_noetig=True` — das ist die
  Δ-Vergleichsbasis für den Abweichungsalarm. Der Checker **liest nur, schreibt nie selbst**.
- **Schreibpfad:** ausschließlich `trip_report_scheduler.py` (`_write_briefing_anchor`,
  Zeile 1505-1512, aufgerufen über `_anchor_and_reset()` → `write_anchor_and_reset_memory()`,
  `alert_briefing_anchor.py`) und `trip_command_processor.py` (On-Demand-SMS-Fetch, Zeile
  278-308). `on_demand=True` ist dabei ein struktureller No-Op (`alert_briefing_anchor.py:291-292`).
- **Fachliche Kernentscheidung "Alarm ja/nein":** `DeviationAlertEngine.evaluate()`, ausgewertet
  in `check_and_send_alerts()` Zeile 299-311.
- **Zweiter, unabhängiger Snapshot-Verbraucher:** Radar-Alert-Unterdrückung (#818/#1667) liest
  `load_dated(trip.id, segment_date)` bei `trip_alert.py:1068-1070` als eingefrorene
  Briefing-Prognose, um bereits angekündigten Niederschlag nicht doppelt zu meldenden.

## Zentraler Zusatzbefund (Strategie-Agent, geht über den ursprünglichen Bug-Report hinaus)

Ein naives "Anker bei jedem Check-Lauf neu schreiben" (PO-Formulierung wörtlich genommen) würde
das Δ-Vergleichsfenster auf ein Check-Intervall (15 Min) schrumpfen und damit die
**Trend-Erkennung stillschweigend brechen**: ein langsamer, über Stunden kriechender Anstieg,
der pro 15-Min-Schritt unter der Schwelle bleibt, würde nie mehr als Alarm auslösen — heute
funktioniert das nur, weil der Anker stundenlang stabil bleibt und der Rohvergleich sich
akkumuliert. Das ist eine stille Funktionsregression, wenn Slice 2 unvorsichtig umgesetzt wird.

**Empfohlener Hybrid-Schreibzeitpunkt:** Anker wird geschrieben (a) bei jedem tatsächlichen
Alarmversand (verallgemeinert #816 von "nur Briefing" auf "jeder erfolgreiche Alarm") UND
(b) opportunistisch, wenn der aktuelle Anker eine Alterungs-Ceiling (z. B. 3-6h) überschreitet,
auch ohne ausgelösten Alarm. Das kappt das ~24h-Symptom, ohne das Δ-Fenster auf 15 Min zu
verkleinern. Kostenseitig günstig: `_fetch_fresh_weather()` läuft ohnehin bei jedem Check, es
entsteht nur ein zusätzlicher JSON-Write, kein zusätzlicher Wetterabruf.

**Dritter, separater Snapshot-Typ nötig** (kein Umwidmen von `save_dated`/`load_dated`): würde
man dieselbe Datei rollierend überschreiben, bräche das die Radar-Alert-Unterdrückung
(#818/#1667, `trip_alert.py:1071`), da deren Vergleichswert dann nicht mehr die eingefrorene
Briefing-Prognose wäre, sondern sich selbst ständig nachzöge.

## Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/weather_snapshot.py` | MODIFY | neuer, dritter Anker-Typ (undated, eigener Speicherort/Methode, eigene Alterslogik) |
| `src/services/trip_alert.py` | MODIFY | `_get_cached_weather()` um dritte Quelle erweitert; neuer Schreibpfad nach Check-Lauf (Hybrid-Trigger); Referenz-Zeit an `check_and_send_alerts`/`_send_alert` durchreichen |
| `src/services/notification_service.py` | MODIFY | `stand_at` aktuell `datetime.now(...)` (Zeile ~652/723) → muss Referenz-Zeitpunkt statt Abrufzeitpunkt tragen |
| `src/output/renderers/alert/model.py` | MODIFY | neues `AlertMessage`-Feld für Referenz-Zeitpunkt |
| `src/output/renderers/alert/project.py` | MODIFY | Durchreichen in `to_alert_message`/`to_multi_point_alert_message` |
| `src/output/renderers/alert/render.py` | MODIFY | 4 Kanäle (E-Mail/Telegram/SMS/Premium-SMS); hartcodierter Text "verglichen mit dem letzten Briefing" (Zeile ~517/562) ersetzen; SMS-Budget-Logik (≤160 Zeichen) |
| Tests (Kern-Schicht) | CREATE | golden-message-Tests je Kanal, Trend-Regressionstest, #823/#818-Interaktionstests, Anker-Prioritätskette |

## Scope Assessment

- Files: **7-9 Produktionsdateien** (Bug-Report-Schätzung von 3 Dateien war zu eng gefasst)
- Estimated LoC: **~800-1200** über den ganzen Feature-Zweig inkl. Tests (Bug-Report-Schätzung
  150-200 LoC war zu niedrig; TDD-Red-Phase ist verpflichtend, Repo hat ausführliche
  Docstring-Kultur)
- Risk Level: **MEDIUM** — kein neues Konzept, aber mehrere bestehende Architekturentscheidungen
  (#823 Tagesgrenze, #816 Referenz-Reset, #818 Radar-Unterdrückung) müssen sauber koexistieren

## Technical Approach (Empfehlung)

**Zwei unabhängig lieferbare Scheiben statt ein AC-Paar:**

- **Slice 1 — Sichtbarkeit:** nutzt nur bereits vorhandene Daten (`SegmentWeatherData.fetched_at`
  trägt den Referenz-Zeitstempel bereits, kein neues Snapshot-Feld nötig), berührt keine
  Schreiblogik, kein #823/#816/#818-Risiko. Liefert sofort Nutzen — ersetzt die bereits heute
  sachlich unpräzise Formulierung "verglichen mit dem letzten Briefing".
- **Slice 2 — Rollierende Basis:** der risikoreiche Teil (dritter Snapshot-Typ, Hybrid-Schreib-
  Timing, Interaktion mit #823/#816/#818, Trend-Erkennungs-Invariante). Baut auf Slice 1 auf.

**Compare-Pfad explizit außerhalb des Scopes von Slice 2:** `AlertMessage`/`render.py` sind
zwischen Trip- und Compare-Alarmen geteilt (CLAUDE.md: geteilte Kanal-Auflösung für alle
Alarmarten). Compare nutzt aber eine eigene, undatierte Snapshot-Mechanik ohne #823-Tagesgrenze
(`CompareWeatherSnapshotService`). Sichtbarkeit (Slice 1) wirkt automatisch auf Compare mit und
muss dort als Pflicht-Regressionstest (Golden-Mail/SMS) abgesichert werden; die rollierende
Basis (Slice 2) bleibt auf Trip beschränkt.

**Architekturentscheidung:** #816 (B) — "kein Snapshot-Write mehr bei Alarmversand, Referenz
bleibt bis zum nächsten Briefing stabil" — wird durch Slice 2 bewusst revidiert. Gehört im Spec
als "supersedes #816 (B)" benannt, nicht stillschweigend überschrieben (ADR-Pflicht gemäß
CLAUDE.md bei Abweichung von dokumentierten Entscheidungen).

## Risks

- Trend-Erkennung bricht bei naiver Umsetzung (s.o.) — braucht expliziten Regressions-AC.
- Radar-Alert (#818/#1667) bricht ohne strikt getrennten Speicherort für den neuen Anker-Typ.
- #823-Tagesgrenze muss auch für den neuen Anker-Typ gelten (sonst "heute gegen gestern vor
  Mitternacht" in neuer Form).
- `write_anchor_and_reset_memory()` koppelt Anker-Schreiben mit Melde-Gedächtnis-Reset — der
  neue rollierende Schreibpfad braucht einen eigenen, schlankeren Pfad OHNE diesen Reset,
  sonst könnten bereits gemeldete Werte erneut gemeldet werden.
- SMS-Zeichenbudget: neuer Stand-Text konkurriert mit bestehender Token-Kürzlogik — Priorität
  muss spec-seitig festgelegt werden.
- Zu klären vor Spec-Freigabe: tatsächliches Scheduler-Check-Intervall verifizieren (Docstring
  `check_all_trips` nennt 30 Min, PO/Bug-Report nennen 15 Min — bestimmt die Alterungs-Ceiling).

## Dependencies

#1897 (gleiche Konstellation, gescheiterter Briefing-Versand — entschärft Häufigkeit, löst
#1916 aber nicht), #823 (Ursprung Tagesgrenze), #816 (Ursprung Briefing=Referenz-Reset, Teil B
wird durch Slice 2 revidiert), #818/#1667 (Radar-Alert-Unterdrückung, Regressionsrisiko).

## Open Questions

- [ ] Alterungs-Ceiling für den opportunistischen Schreib-Trigger: 3h? 6h? (abhängig vom
      tatsächlichen Check-Intervall, s.o.)
- [ ] Exaktes SMS-Kurzformat für den Referenz-Zeitpunkt (Zeichenbudget-Priorität ggü.
      bestehenden Kürz-Token)
- [ ] Slice 1 und Slice 2 als zwei Issues/PRs oder ein Workflow mit zwei AC-Gruppen?
