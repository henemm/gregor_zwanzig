---
entity_id: fix_3085_radar_grenzabbruch
type: bugfix
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: fix-3085-radar-grenzabbruch
tags: [radar, alarm, scheduler, adr-0082]
---

# Fix #3085: Radar-Fristablauf in der Parallelphase bricht die Einheit ab

## Approval

- [ ] Approved

## Purpose

Läuft die Radar-Frist (45 s je Nutzeraufruf) mitten in der Parallelphase ab, wird die Einheit heute nicht
abgebrochen, sondern mit Lücken ausgewertet (Alarm möglich, Stempel gesetzt, Status ok). Das widerspricht
ADR-0082 (Grenzabbruch ist keine Entwarnung: keine Auswertung, kein Protokolleintrag, kein Stempel) und
feat_2261 AC-8. Dieser Fix macht jedes im Radar-Pfad übersprungene Teilergebnis zum Grenzabbruch, einheitlich
für Trip und Ortsvergleich.

## Scope

**Im Scope:** Radar-Alarmlauf (Trip und Ortsvergleich) im Python-Core: Jedes in der Parallelphase übersprungene
Teilergebnis (`skipped="deadline"` oder `"timeout"`) wird über den geteilten Baustein `wirf_radar_grenze` zum
Grenzabbruch der Einheit. Dazu die Präzisierung von feat_1539 AC-8, ADR-0082 Punkt 5 und die Umstellung der
betroffenen Bestandstests.

**Nicht im Scope:** `parallel_fetch.fetch_ordered` und alle anderen Aufrufer (Briefing, `compare_alert`,
`compare_official_alert`, übrige `trip_alert`-Pfade); Go-Scheduler, Frontend; Laufzeit-Budget (Frist bleibt 45 s);
die unter *Known Limitations* genannte Restwirkung.

## Definition of Done

- AC-1 bis AC-7 sind durch automatisierte Tests (ohne Mock-Theater) abgedeckt und grün; die Mutations-Gegenproben
  aus dem Test Plan werden jeweils von mindestens einem Test gefangen.
- feat_1539 AC-8 und ADR-0082 Punkt 5 sind präzisiert; die bisherigen AC-8-Tests (Trip-Lücke, Compare-Ausfall bei
  Zeitüberschreitung) prüfen fachlich den Grenzabbruch.
- Alle bestehenden Radar-, Fairness- und Deadline-Tests bleiben grün; alle 6 CI-Checks grün.
- Staging-Lauf des Radar-Schedulers ohne Fehler, Prod-Deploy mit Selftest-Exit 0.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `wirf_radar_grenze` (geteilt von Trip und Ortsvergleich)

Betroffene Schicht: ausschließlich Python-Core (`src/services/`), kein Go, kein Frontend.

**Trip/Ortsvergleich-Teilung:** Die Änderung sitzt im geteilten Baustein `wirf_radar_grenze`; beide Pfade
verhalten sich danach gleich (bisher divergierten sie: Trip wertete `deadline` und `timeout` als Lücke, Compare
warf nur bei `deadline` und wertete `timeout` als Ausfall). Mandantentrennung: unverändert, keine neuen Daten;
die Tests laufen mit zwei verschiedenen Nutzern. Kanäle: bei Grenzabbruch geht auf keinem der vier Kanäle
(E-Mail, Telegram, SMS, Premium-SMS) ein Alarm hinaus, für alle gleich.

## Estimated Scope

- **LoC:** Produkt +15/-25, Tests +80/-30
- **Files:** 3 Produktcode, 2 Tests, 2 Doku
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/parallel_fetch.py` (`fetch_ordered`) | module | liefert `skipped` (deadline/timeout); bleibt unverändert |
| `src/services/radar_service.py` (`hole_nowcasts`, `RadarDeadlineExceeded`) | module | Parallelphase, Grenz-Ausnahme |
| `src/services/trip_alert.py` (`_radar_folgepunkte`, `_abort_radar_unit`) | module | Trip-Pfad, bestehender Abbruchweg |
| `src/services/compare_radar_alert.py` | module | Ortsvergleich-Pfad, bestehender `except RadarDeadlineExceeded` |
| `AlertCheckStateStore` (Fairness-Stempel) | module | abgebrochene Einheit bleibt vorn |
| `api/routers/scheduler.py` (`_radar_run_response`) | module | Status `partial` bei `hit_deadline` |
| ADR-0082, feat_1539_s4_radar_parallel, feat_2261_a2s2_radar_takt | docs | fachliche Grundlage |

## Implementation Details

Gewählt ist Option 1 aus der Analyse (`docs/context/fix-3085-radar-grenzabbruch.md`).

- `radar_service.wirf_radar_grenze(outcomes)`: wirft zusätzlich zum Worker-`RadarDeadlineExceeded` bei
  **jedem** `skipped` (Grund `deadline` oder `timeout`) `RadarDeadlineExceeded`. Begründung: `skipped` entsteht im
  Radar-Pfad ausschließlich durch Fristablauf. Vor dem Werfen steht für jeden übersprungenen Punkt bzw. Ort eine
  Log-Zeile mit Grund.
- `trip_alert._radar_folgepunkte`: der Zweig `out.skipped` (Lücke, „der Alarm laeuft weiter") wird unerreichbar
  und entfernt; der Abbruch läuft über das bestehende `except RadarDeadlineExceeded` und `_abort_radar_unit`.
- `compare_radar_alert`: `_wirf_bei_nie_gestarteten` und der `skipped`-Ausfallzweig entfallen; Ausfall-Protokolleintrag
  bei Zeitüberschreitung gibt es nicht mehr.
- `parallel_fetch.fetch_ordered` bleibt unverändert; Aufrufer Briefing, `compare_alert`, `compare_official_alert`
  und `trip_alert` (Nicht-Radar) behalten ihr Verhalten.

### Spec-Änderung an feat_1539 AC-8 (ausdrücklich)

feat_1539 AC-8 (übersprungener Punkt zählt als gescheitert, fehlt im Ergebnis, Auswertung läuft weiter) wird
fachlich geändert: im Radar-Pfad gilt ein übersprungener Punkt/Ort als **Grenzabbruch** der Einheit, die Log-Zeile
je Punkt bleibt. `docs/specs/modules/feat_1539_s4_radar_parallel.md` AC-8 wird entsprechend neu formuliert. Die
bestehenden Tests `tests/tdd/test_radar_parallel_fetch.py` (Trip, ca. Z.1016; Compare-timeout, ca. Z.990)
erwarten heute Lücke bzw. Ausfall und werden **fachlich auf Grenzabbruch umgestellt** — kein stilles Umbiegen,
sondern durch diese Spec und ADR-0082 gedeckt.

## Expected Behavior

- **Input:** Radar-Lauf einer Einheit (Trip oder Ortsvergleich), Frist `deadline_at` läuft während oder vor der
  Parallelphase ab.
- **Output:** `RadarDeadlineExceeded` im Hauptfaden, Einheit abgebrochen, `hit_deadline=True`, Scheduler-Antwort
  `partial` mit `reason="deadline"`.
- **Side effects:** kein Stempel, kein Alarmprotokoll-Eintrag, keine Sperrzeit-/Tageslimit-Buchung, kein Versand.

## Test Plan

### Automated Tests (TDD RED)

Ohne Mock-Theater: steuerbare Uhr `_Uhr`, echte Threads, echter Slot-Mechanismus (Muster aus
`tests/tdd/test_radar_parallel_fetch.py`).

- [ ] Trip: Worker läuft beim Fristablauf noch (echter Thread, `_Uhr` springt über die Frist) ⇒ keine Auswertung,
  kein Alarm, kein Protokolleintrag, kein Stempel, `hit_deadline=True`, Status partial.
- [ ] Compare: gleiche Lage ⇒ gleiche Wirkung, zusätzlich kein Ausfall-Protokolleintrag.
- [ ] Trip und Compare: nie gestartete Punkte (`skipped="deadline"`) ⇒ Grenzabbruch.
- [ ] Log-Zeile je übersprungenem Punkt/Ort vorhanden (caplog).
- [ ] Fairness: abgebrochene Einheit kommt im Folgelauf zuerst (`test_radar_alarmlauf_fairness.py`).
- [ ] Negativ: Frist abgelaufen, aber keine Worker laufend, vollständige Ergebnisse ⇒ normale Auswertung.
- [ ] Negativ: Quellenfehler ohne Frist ⇒ Lücke/Ausfall wie bisher.
- [ ] Unverändert: `fetch_ordered`-Aufrufer Briefing, `compare_alert`, `compare_official_alert` (bestehende Tests grün).
- [ ] Umgestellt: AC-8-Tests Trip und Compare-timeout erwarten Grenzabbruch.
- [ ] Zwei verschiedene Nutzer: Abbruch bei Nutzer A stempelt/protokolliert nichts bei Nutzer B.

**Mutations-Gegenprobe (Pflicht für den Adversary; nur per String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`; zu klären ist, welcher Test rot wird):**

1. In `wirf_radar_grenze` den `skipped`-Zweig entfernen ⇒ Trip- und Compare-Grenztest rot (AC-1, AC-2).
2. Nur `skipped="deadline"` werfen, `"timeout"` ausnehmen ⇒ AC-1/AC-2 rot (Worker läuft noch).
3. Nur `"timeout"` werfen, `"deadline"` ausnehmen ⇒ AC-3 rot.
4. Log-Zeile je übersprungenem Punkt entfernen ⇒ AC-4 rot.
5. Im Compare-Pfad Ausfall-Protokolleintrag bei `skipped` wieder schreiben ⇒ AC-2 rot.
6. `_abort_radar_unit` nicht aufrufen (Stempel bleibt) ⇒ AC-1, AC-5 rot.
7. Grenzabbruch auch ohne `skipped` werfen (zu breit) ⇒ AC-6 rot.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen Radar-Frist abläuft, während ein Zonenpunkt-Worker noch läuft / When der
  Radar-Lauf endet / Then wird die Einheit abgebrochen: keine Auswertung, kein Alarm, kein Alarmprotokoll-Eintrag,
  kein Stempel, `hit_deadline=True` und der Scheduler meldet Status `partial`.
  - Test: echter Thread hält einen Punkt über die Frist (`_Uhr`); der Trip löst nichts aus, trägt keinen Stempel
    und der Lauf meldet `partial`.

- **AC-2:** Given ein Ortsvergleich, dessen Radar-Frist abläuft, während ein Orts-Worker noch läuft / When der
  Radar-Lauf endet / Then wird die Einheit abgebrochen wie beim Trip, und es entsteht bei der Zeitüberschreitung
  kein Ausfall-Protokolleintrag mehr.
  - Test: Compare-Lauf mit hängendem Orts-Worker; weder Alarm noch Ausfall-Eintrag noch Stempel, `partial`.

- **AC-3:** Given Punkte bzw. Orte, die wegen abgelaufener Frist nie gestartet wurden (`skipped="deadline"`) /
  When der Radar-Lauf endet / Then ist das in Trip und Ortsvergleich gleichermaßen ein Grenzabbruch ohne
  Auswertung.
  - Test: mehr Punkte/Orte als freie Slots bei abgelaufener Frist; beide Pfade brechen ab, keine Lücken-Auswertung.

- **AC-4:** Given übersprungene Punkte bzw. Orte bei Fristablauf / When die Einheit abgebrochen wird / Then steht
  für jeden übersprungenen Punkt/Ort eine Log-Zeile mit Grund, nichts wird still weggelassen.
  - Test: Log-Prüfung (caplog) je übersprungenem Punkt/Ort in beiden Pfaden.

- **AC-5:** Given eine im Lauf zuvor wegen Fristablauf abgebrochene Einheit / When der nächste Radar-Lauf
  startet / Then kommt diese Einheit fair zuerst dran (Stempel nicht gesetzt, sie steht vorn).
  - Test: Fairness-Test mit zwei Einheiten; nach Abbruch von A ist A im Folgelauf zuerst.

- **AC-6:** Given Fristablauf ohne noch laufende Worker, vollständige Ergebnisse, oder ein echter Quellenausfall
  (Fehler ohne Frist) / When der Radar-Lauf endet / Then verhält sich alles unverändert: normale Auswertung
  bzw. Lücke und Ausfall-Protokolleintrag wie bisher, kein Grenzabbruch.
  - Test: Läufe ohne Fristablauf und mit Quellenfehler; Ergebnis und Protokoll wie vor dem Fix.

- **AC-7:** Given die anderen Aufrufer von `fetch_ordered` (Briefing, `compare_alert`, `compare_official_alert`) /
  When sie Ergebnisse mit `skipped` erhalten / Then verhalten sie sich unverändert, `parallel_fetch.fetch_ordered`
  ist nicht geändert.
  - Test: bestehende Tests dieser Aufrufer bleiben grün; Verhalten bei `skipped` dort unverändert.

## Known Limitations

Außerhalb des Scopes (bekannte Restwirkung, besteht im ADR-0082-Design genauso):

- **Kopf der Schlange:** Ein dauerhaft langsamer Trip bleibt per Fairness vorn und bricht jeden Lauf ab;
  beobachtbar über `skipped_ids`/`hit_deadline`.
- **Verwaiste Worker:** Nach dem Abbruch laufen Worker bis zur nächsten Quellengrenze weiter (ein laufender
  HTTP-Aufruf ist nicht unterbrechbar), wie heute.
- Keine Verlängerung des Wartens bis Frist + Einzelschritt-Toleranz (Option 2 verworfen: Laufzeit bis 233 s,
  Folgenutzer rutschen in `not_reached`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue Entscheidung; ADR-0082 (Punkt 5, Grenzabbruch ist keine Entwarnung) wird präzisiert
  (Hinweis, dass auch übersprungene Teilergebnisse als Grenzabbruch gelten).
- **Rationale:** Der Code wird ADR-konform gemacht, die Entscheidung selbst ändert sich nicht. Die Umstellung von
  feat_1539 AC-8 ist als Spec-Änderung oben ausgewiesen.

## Changelog

- 2026-11-17: Initial spec created
