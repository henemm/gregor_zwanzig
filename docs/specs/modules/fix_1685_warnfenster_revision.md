---
entity_id: fix_1685_warnfenster_revision
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
workflow: fix-1685-warnfenster-revision
---

# Fix #1685: Amtliche Warnung wird bei reiner Fenster-Revision nicht erneut gemeldet

## Approval

- [ ] Approved

## Purpose

Eine amtliche Warnung, deren Behörde nur das Gültigkeitsfenster nachträglich korrigiert
(gleiche Region/Gefahr/Stufe, überlappender Zeitraum), löst heute einen zweiten,
redundanten Alarm aus — weil `official_alert_state_key()` den Zeitraum als Teil der
Identität behandelt und jede Fenster-Änderung dadurch wie eine neue Warnung wirkt. Am
Live-System zweifach belegt (GeoSphere Kartitsch 10.08., MeteoAlarm Trentino 09.08.,
`docs/context/fix-1685-warnfenster-revision.md` Abschnitt 2). Diese Spec ergänzt die
Melde-Entscheidung um eine Überlappungs-Prüfung: eine Revision desselben
Identität+Gefahr-Eintrags bleibt still, außer die Stufe ist gestiegen oder der Beginn
liegt ≥2h früher — PO-Entscheidung 2026-08-10 (Kontext-Doc Abschnitt 6).

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` (neue geteilte Entscheidungsfunktion, neben `official_alert_state_key`)
- **Identifier:** `official_alert_state_key` (Zeile 407-423, unverändert) — daneben neu: `official_alert_revision_verdict` (Entscheidung) und `official_alert_state_entry` (Schema-Builder für Melde-Gedächtnis-Einträge)
- **Weitere Lesepfad-Dateien:** `src/services/trip_alert.py:1378-1384`, `src/services/compare_official_alert.py:224-234` (Methode `_detect`)
- **Weitere Schreibpfad-Dateien:** `src/services/alert_briefing_anchor.py:305-333` (`record_official_alerts_reported`), `src/services/compare_official_alert.py:264-273` (`_record_state`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.official_alerts.official_alert_state_key` | function | Kanonische Schlüsselbildung (Identität+Hazard+Zeitraum), unverändert — die neue Funktion baut darauf auf, ersetzt sie nicht |
| `output.renderers.alert.official_alerts.dedupe_official_alerts` | function | Anzeige-Ebene, bewusst NICHT verändert — arbeitet weiter mit dem exakten `(ident, hazard, valid_from, valid_to)`-Tupel (Zeile 339), zeigt zwei Perioden also unverändert getrennt |
| `services.alert_state.AlertStateService` | class | Melde-Gedächtnis, Datei je Nutzer/Entität; `load()`/`save()` werden vom neuen Fortschreibungs-Zweig direkt im Lesepfad aufgerufen (Vertragsänderung, s. „Implementation Details") |
| `services.alert_state.OFFICIAL_ALERT_KEY_PREFIX` | constant | `"official_alert:"` — Fortschreibungs-Einträge bleiben in diesem Namensraum, überleben Briefing-Resets (#1460 P2) unverändert |
| `services.trip_alert.TripAlertService.check_official_alert_triggers` | method | Trip-Lesepfad, Zeile 1283-1385; nutzt ab dieser Spec die geteilte Entscheidungsfunktion statt des rohen `state.get(key)`-Vergleichs |
| `services.compare_official_alert.CompareOfficialAlertService._detect` | method | Ortsvergleich-Lesepfad, Zeile 182-235; identische Umstellung, pro Ort eigenes `AlertStateService` |
| `services.alert_briefing_anchor.record_official_alerts_reported` | function | Trip-Schreibpfad (Briefing + Standalone-Alarm); erweitert um `valid_from`/`valid_to` im Eintrag |
| `services.compare_official_alert.CompareOfficialAlertService._record_state` | method | Compare-Schreibpfad; identisch erweitert (eigene, bisher unabhängige Inline-Kopie) |
| #1245 (PO 2026-07-15) | decision | Ursprung der Zeitraum-in-Identität-Regel; diese Spec präzisiert AC-4, hebt sie nicht auf |
| ADR-0040 | decision | „Eine gerissene Grenze wird einmal gemeldet, erneut erst bei Verschärfung" — bestätigt die Richtung dieser Spec |
| #1614 | spec | Direkter Vorgänger, identische Codestellen (Doppelversand zwischen Briefing und 15-Min-Checker); dort ungelöst blieb die Revision-INNERHALB des Checkers selbst — das ist genau diese Spec |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Neue Funktionen `official_alert_revision_verdict(alert, state)` und `official_alert_state_entry(alert, reported_at_iso)` direkt unterhalb von `official_alert_state_key` (Zeile ~424) |
| `src/services/trip_alert.py` (Lesepfad `check_official_alert_triggers`, ~1378-1384) | MODIFY | Ersetzt den rohen Schlüssel-Vergleich durch `official_alert_revision_verdict`; führt bei stiller Revision die Fortschreibung inkl. `state_svc.save()` sofort aus |
| `src/services/compare_official_alert.py` (Lesepfad `_detect`, ~224-234) | MODIFY | Identische Umstellung, pro `loc_id` eigenes `AlertStateService` |
| `src/services/compare_official_alert.py` (Schreibpfad `_record_state`, ~264-273) | MODIFY | Nutzt `official_alert_state_entry` statt eigenem Inline-Dict — Read-Modify-Write-Merge, `valid_from`/`valid_to` künftig persistiert |
| `src/services/alert_briefing_anchor.py` (`record_official_alerts_reported`, ~305-333) | MODIFY | Nutzt `official_alert_state_entry` statt eigenem Inline-Dict — identische Erweiterung für den Trip-Schreibpfad |
| `tests/tdd/test_official_alert_revision_dedup.py` | CREATE | Neue, nach Verhalten benannte Testdatei (Namensregel #1196) — alle 14 Tests dieser Spec |

**Nicht angefasst (bewusst):** `src/services/trip_report_scheduler.py:1219-1227` — delegiert bereits an
`record_official_alerts_reported()` und erbt die Erweiterung automatisch, keine eigene Änderung nötig.

### Estimated Changes

- Files: 5 Produktivdateien, 1 neue Testdatei
- LoC: +90/-20 Produktivcode (neue Entscheidungs- und Entry-Builder-Funktion, zwei Lesepfad-Umstellungen, zwei Schreibpfad-Umstellungen); +200/-0 Tests

## Implementation Details

### Identität+Hazard-Präfix statt Zeitstempel-Parsing

`official_alert_state_key()` bleibt unverändert. Neu: ein Präfix ohne Zeitraum, gebildet
mit derselben Präzedenz (`dedup_id` > `region_label` > `label`):

```python
def _identity_hazard_prefix(alert: "OfficialAlert") -> str:
    if alert.dedup_id:       ident = f"id:{alert.dedup_id}"
    elif alert.region_label: ident = f"region:{alert.region_label}"
    else:                    ident = f"label:{alert.label}"
    return f"official_alert:{ident}:{alert.hazard}:"
```

Damit lassen sich alle Bestandsschlüssel derselben Identität+Gefahr per `str.startswith`
finden — **ohne** die ISO-Zeitstempel aus dem Schlüssel-String zu parsen (der Grund, warum
das heute fragil wäre, s. Kontext-Doc Abschnitt „Technische Vorgaben"). Der Zeitraum wird
stattdessen aus dem **Eintrags-Wert** gelesen (neue Felder, s.u.), nicht aus dem Schlüssel.

### Neue Entscheidungsfunktion `official_alert_revision_verdict`

```python
def official_alert_revision_verdict(alert, state: dict):
    """Liefert (should_report: bool, stale_key: str|None, merged_entry: dict|None).
    should_report=True: melden (Kern-Vergleich `state.get(key)`, wie bisher,
    ODER Eskalation/Vorverlegung >=2h innerhalb einer echten Überlappung).
    should_report=False + merged_entry gesetzt: stille Revision -- Aufrufer
    MUSS stale_key entfernen, merged_entry unter dem NEUEN Schluessel
    speichern und sofort persistieren (state_svc.save)."""
```

Ablauf: (1) `key = official_alert_state_key(alert)`, `prev = state.get(key)`. Fehlt
`alert.valid_from`/`valid_to`, entscheidet ausschließlich dieser exakte Treffer — wie
heute (fail-soft, kein Rateverhalten bei zeitlosen Warnungen). (2) Sonst: alle
Bestandsschlüssel mit `_identity_hazard_prefix(alert)` sammeln, deren **Eintrag** eigene
`valid_from`/`valid_to`-Felder trägt (fehlen sie — Alt-Eintrag vor diesem Fix —, wird der
Schlüssel bei diesem Schritt ignoriert, verhält sich weiter wie heute über den exakten
Treffer aus Schritt 1). (3) Unter den verbleibenden Kandidaten den mit **echter**
Überlappung wählen (`alert.valid_from < kandidat.valid_to and kandidat.valid_from <
alert.valid_to`; bei mehreren Treffern: höchster `last_reported_value`, bei Gleichstand
spätester `reported_at`). (4) Kein überlappender Kandidat → zurück zu Schritt 1
(unverändertes Ist-Verhalten, deckt #1245 AC-4 und die Hitzewarnungs-Gegenprobe ab).
(5) Überlappender Kandidat gefunden: `melden`, wenn `alert.level > kandidat.level` ODER
`kandidat.valid_from - alert.valid_from >= 2h`; sonst `still` mit
`merged_entry = {"last_reported_value": max(kandidat.level, alert.level), "reported_at":
kandidat.reported_at (UNVERÄNDERT), "valid_from": alert.valid_from, "valid_to":
alert.valid_to}` und `stale_key = kandidat-Schlüssel`.

### Vertragsänderung: Lesepfad wird zum Schreibpfad (nur im Still-Zweig)

`check_official_alert_triggers()` dokumentiert heute explizit „Schreibt KEINEN
alert_state" (Zeile 1294-1295). Diese Spec ändert das für genau den Still-Zweig: ohne
sofortige Fortschreibung würde der DRITTE Fall einer Revisionskette gegen das veraltete,
erste Fenster verglichen und fälschlich erneut gemeldet (Kontext-Doc Abschnitt
„Fortschreibung statt Wachstum", Beispiel 14–22 → 18–03 → 22–06). Der Melden-Zweig bleibt
unverändert reiner Lesepfad — die eigentliche Schreibung nach erfolgreichem Versand läuft
weiterhin über `record_official_alerts_reported`/`_record_state` (unverändertes Gate:
`result.sent`, #1614 AC-4). Beide Aufrufer (`trip_alert.py`, `compare_official_alert.py`)
rufen bei `should_report=False and merged_entry is not None` sofort `del
state[stale_key]`, `state[key] = merged_entry`, `state_svc.save(entity_id, state)` — mit
demselben `AlertStateService`/`entity_id`, das sie für den Lesezugriff schon geladen haben.

### Schema-Erweiterung im Melde-Gedächtnis (Read-Modify-Write mit Merge)

Neue Funktion `official_alert_state_entry(alert, reported_at_iso) -> dict`:

```python
def official_alert_state_entry(alert, reported_at_iso: str) -> dict:
    return {
        "last_reported_value": float(alert.level),
        "reported_at": reported_at_iso,
        "valid_from": alert.valid_from.isoformat() if alert.valid_from else None,
        "valid_to": alert.valid_to.isoformat() if alert.valid_to else None,
    }
```

Ersetzt die bisher **zwei unabhängig duplizierten** Inline-Dicts in
`record_official_alerts_reported` und `_record_state` (Compare). Bestandseinträge ohne
`valid_from`/`valid_to` werden beim nächsten Laden unverändert übernommen (kein Migrations-
Lauf nötig) — sie bekommen die Felder automatisch, sobald für ihre Identität+Gefahr
erneut geschrieben wird; bis dahin bleiben sie über den exakten Schlüsseltreffer gültig
(Read-Modify-Write mit Merge, CLAUDE.md „Daten-Schema-Reworks").

## Test Plan

### Test-Schicht

Kern-Schicht (deterministisch): `AlertStateService` ist reiner Dateizugriff (kein Netz),
die neue Entscheidungsfunktion ist eine reine Funktion über `dict`/`OfficialAlert`. Kein
Mock-Theater. Testdatei nach Verhalten benannt (`test_naming_gate.py`).

### Automated Tests (TDD RED)

- [ ] **Test 1** (später, überlappt): GIVEN im Melde-Gedächtnis steht Warnung X (Kartitsch, Gewitter, GELB, 14:00–22:00 UTC lokal), WHEN dieselbe Identität+Gefahr mit Fenster 18:00–03:00 GELB geprüft wird, THEN meldet der Checker sie NICHT (still, echte Überlappung 18:00–22:00).

- [ ] **Test 2** (nur verlängert): GIVEN dieselbe Vorlage wie Test 1, WHEN das neue Fenster 14:00–02:00 GELB liefert (gleicher Start, verlängertes Ende), THEN bleibt der Checker still.

- [ ] **Test 3** (2h früher, exakte Grenze): GIVEN dieselbe Vorlage wie Test 1, WHEN das neue Fenster exakt 2 Stunden früher beginnt (12:00–20:00 GELB), THEN meldet der Checker die Warnung erneut.

- [ ] **Test 4** (4h früher): GIVEN dieselbe Vorlage wie Test 1, WHEN das neue Fenster 10:00–18:00 GELB liefert, THEN meldet der Checker die Warnung erneut.

- [ ] **Test 5** (Stufe gestiegen): GIVEN dieselbe Vorlage wie Test 1, WHEN das neue Fenster 18:00–03:00 ORANGE liefert (später, aber höhere Stufe), THEN meldet der Checker die Warnung trotz späterem Beginn erneut.

- [ ] **Test 6** (kein Zeit-Überlapp): GIVEN dieselbe Vorlage wie Test 1, WHEN am Folgetag dasselbe Fenster 14:00–22:00 GELB erneut auftritt, THEN meldet der Checker sie als eigenständige, neue Warnung.

- [ ] **Test 7** (Ortsvergleich identisch): GIVEN dieselbe Ausgangslage wie Test 1 und Test 3, aber im Ortsvergleichs-Melde-Gedächtnis eines Orts (`CompareOfficialAlertService._detect`), WHEN dieselben zwei Revisionen geprüft werden, THEN verhält sich der Ortsvergleichs-Pfad identisch zum Trip-Pfad (still bei Test-1-Fenster, melden bei Test-3-Fenster).

- [ ] **Test 8** (keine Zeitangabe, unverändert): GIVEN eine Warnung ohne `valid_from`/`valid_to` steht mit Level 2 im Melde-Gedächtnis, WHEN dieselbe zeitlose Warnung mit unverändertem Level erneut geprüft wird, THEN bleibt der Checker still — wie vor dieser Spec, ohne jede Überlappungsprüfung.

- [ ] **Test 9** (Alt-Eintrag ohne neue Felder bleibt lesbar): GIVEN im Melde-Gedächtnis liegt ein Eintrag im alten Schema (nur `last_reported_value`/`reported_at`, ohne `valid_from`/`valid_to` — Bestandsdaten vor diesem Fix), WHEN eine Warnung mit geändertem, überlappendem Fenster geprüft wird, THEN stürzt der Checker nicht ab und behandelt sie wie heute (exakter Schlüsseltreffer entscheidet, kein Interval-Vergleich gegen den Alt-Eintrag).

- [ ] **Test 10** (Kette aus drei Revisionen): GIVEN Warnung X wird mit Fenster 14:00–22:00 GELB gemeldet, WHEN sie danach zu 18:00–03:00 GELB (still, Fortschreibung) und anschließend zu 22:00–06:00 GELB revidiert wird, THEN meldet der Checker nur beim ersten Fenster, beide Folgefenster bleiben still (Fortschreibung verhindert das Falsch-Melden am dritten Glied).

- [ ] **Test 11** (aneinandergrenzende Fenster bleiben getrennt): GIVEN Warnung A endet 22:00 GELB, WHEN Warnung B (gleiche Identität+Gefahr, gleiche Stufe) exakt um 22:00 beginnt, THEN meldet der Checker B als eigenständige, neue Warnung (keine echte Überlappung, Gegenprobe zu #1245 AC-4).

- [ ] **Test 12** (Anzeige unverändert): GIVEN dieselben zwei aneinandergrenzenden oder überlappenden Perioden wie Test 1/Test 11, WHEN `dedupe_official_alerts` für die Anzeige aufgerufen wird, THEN liefert sie weiterhin zwei getrennte Einträge — die neue Regel wirkt ausschließlich im Melde-Gedächtnis.

- [ ] **Test 13** (Mandantentrennung): GIVEN zwei Nutzer mit je einem Trip und je derselben Warnungs-Revision (Fenster wie Test 1), WHEN für Nutzer A die Fortschreibung greift, THEN bleibt das Melde-Gedächtnis von Nutzer B unverändert.

- [ ] **Test 14** (Compare-Orts-Isolation): GIVEN ein Ortsvergleichs-Preset mit zwei Orten, an Ort A liegt bereits Warnung X mit Fenster 14:00–22:00 GELB im Melde-Gedächtnis, WHEN an Ort B dieselbe Warnungs-Identität mit unverändertem Fenster zum ersten Mal auftritt, THEN wird sie für Ort B als neu gemeldet (kein Cross-Talk über die location-id-basierte Trennung, F005/F006).

## Acceptance Criteria

- **AC-1:** Given eine amtliche Warnung mit Fenster 14:00–22:00 GELB steht im Melde-Gedächtnis, When dieselbe Identität+Gefahr mit Fenster 18:00–03:00 GELB (später, echte Überlappung) geprüft wird, Then meldet der Checker sie NICHT erneut.
  - Test: Test 1.

- **AC-2:** Given dieselbe Ausgangslage wie AC-1, When das neue Fenster 14:00–02:00 GELB liefert (gleicher Start, nur verlängertes Ende), Then bleibt der Checker still.
  - Test: Test 2.

- **AC-3:** Given dieselbe Ausgangslage wie AC-1, When das neue Fenster exakt 2 Stunden früher beginnt (12:00–20:00 GELB), Then meldet der Checker die Warnung erneut als Alarm.
  - Test: Test 3.

- **AC-4:** Given dieselbe Ausgangslage wie AC-1, When das neue Fenster 10:00–18:00 GELB liefert (4 Stunden früher), Then meldet der Checker die Warnung erneut als Alarm.
  - Test: Test 4.

- **AC-5:** Given dieselbe Ausgangslage wie AC-1, When das neue Fenster 18:00–03:00 ORANGE liefert (Stufe gestiegen, trotz späterem Beginn), Then meldet der Checker die Warnung erneut als Alarm.
  - Test: Test 5.

- **AC-6:** Given dieselbe Ausgangslage wie AC-1, When am Folgetag dasselbe Fenster 14:00–22:00 GELB erneut auftritt (kein Zeit-Überlapp mit dem Vortag), Then meldet der Checker sie als eigenständige, neue Warnung.
  - Test: Test 6.

- **AC-7:** Given dieselben Revisions-Fälle wie AC-1 und AC-3, im Melde-Gedächtnis eines Ortsvergleichs-Orts statt eines Trips, When der Ortsvergleichs-Checker (`_detect`) sie prüft, Then verhält er sich identisch zum Trip-Pfad — still bei AC-1, melden bei AC-3.
  - Test: Test 7.

- **AC-8:** Given eine Warnung ohne `valid_from`/`valid_to` steht mit unverändertem Level im Melde-Gedächtnis, When dieselbe zeitlose Warnung erneut geprüft wird, Then entscheidet ausschließlich der exakte Schlüsseltreffer wie vor dieser Spec — keine Überlappungsprüfung greift.
  - Test: Test 8.

- **AC-9:** Given ein Bestandseintrag im Melde-Gedächtnis ohne die neuen Felder `valid_from`/`valid_to` (Datenstand vor diesem Fix), When eine Warnung mit geändertem, überlappendem Fenster gegen diesen Eintrag geprüft wird, Then bleibt der Eintrag gültig und lesbar, kein Absturz, Verhalten entspricht dem heutigen exakten Schlüsseltreffer.
  - Test: Test 9.

- **AC-10:** Given eine Warnungs-Revisionskette über drei Glieder (14:00–22:00 → 18:00–03:00 → 22:00–06:00, jedes Glied überlappt sein Vorgänger-Fenster, gleiche Stufe), When alle drei Glieder nacheinander geprüft werden, Then meldet der Checker nur beim ersten Glied, die beiden Folgeglieder bleiben still.
  - Test: Test 10.

- **AC-11:** Given zwei aneinandergrenzende, NICHT überlappende Fenster derselben Identität+Gefahr+Stufe (A endet 22:00, B beginnt exakt 22:00), When B geprüft wird, Then meldet der Checker B als eigenständige, neue Warnung — Präzisierung von #1245 AC-4 zu „T2 überlappt T1 nicht".
  - Test: Test 11.

- **AC-12:** Given zwei getrennt gemeldete Perioden derselben Identität+Gefahr (überlappend oder aneinandergrenzend), When die Anzeige-Funktion `dedupe_official_alerts` läuft, Then zeigt sie weiterhin beide Perioden getrennt — die neue Regel wirkt ausschließlich im Melde-Gedächtnis, nicht in der Anzeige.
  - Test: Test 12.

## Non-Regression

Diese Änderung darf keine der folgenden bestehenden Zusicherungen brechen
(Kontext-Doc Abschnitt 5, Live-Nachmessung 2026-08-10):

| Quelle | Zusicherung | Auswirkung dieser Spec |
|---|---|---|
| #1245 AC-1 | Zwei Perioden gleicher Region+Gefahr bleiben in `dedupe_official_alerts` **zwei Einträge** | Unverändert — AC-12 sichert das explizit ab, die Anzeige-Funktion wird nicht angefasst |
| #1245 Known Limitation | Kein Interval-Merging: überlappende Perioden werden NICHT zu einem Gesamtzeitraum verschmolzen | Unverändert — die Fortschreibung ersetzt nur den State-EINTRAG (Melde-Gedächtnis), sie verschmilzt keine angezeigten Zeiträume |
| **#1245 AC-4 — PRÄZISIERT** | Bisher: „Neue Periode T2 ≠ T1 erzeugt eigenen Zustands-Key ohne A zu überschreiben." Neu: „T2 **überlappt T1 nicht**" — nur dann bleiben beide State-Keys unabhängig; überlappt T2 T1 (ohne Eskalation/≥2h-Vorverlegung), wird T1 durch die Fortschreibung ersetzt. Der bewachende Test `tests/tdd/test_official_alert_dedup_timespan.py:271` (`TestAC4TriggerNewPeriodFiresIndependently`) nutzt Perioden, die exakt aneinandergrenzen (Periode B beginnt exakt dort, wo Periode A endet — `period_b_from = period_a_to`) und bleibt damit ohne Änderung grün, weil aneinandergrenzende Fenster nach dieser Spec (AC-11) weiterhin KEINE echte Überlappung sind. |
| #1245 AC-2/AC-3 | Eskalation am selben Zeitraum bzw. Massiv-Sperren kollabieren auf Maximum | Unverändert — betrifft `dedupe_official_alerts`, nicht die neue Melde-Entscheidung |
| #1460 AC-20/AC-22 | `official_alert:`-Einträge überleben den Briefing-Reset | Unverändert — Fortschreibungs-Einträge tragen weiterhin denselben Präfix, `AlertStateService.reset()` behandelt sie identisch |
| #1614 AC-1/AC-2 | Im Briefing gemeldete Warnung feuert im Alarm-Checker nicht erneut; Eskalation feuert weiterhin | Erweitert, nicht ersetzt — #1614 deckte den Doppelversand zwischen Briefing-Schreibpfad und Checker-Lesepfad ab, diese Spec deckt die Revision-Erkennung INNERHALB des Checkers selbst ab |
| #1086 / F001 | Cross-Source-Kollaps minütlich abweichender Zeiträume | Unverändert — Anzeige-Ebene, nicht berührt |
| ADR-0040 | „Eine gerissene Grenze wird einmal gemeldet, erneut erst bei Verschärfung" | Bestätigt — diese Spec setzt das für Fenster-Revisionen explizit um |

## Nicht in dieser Scheibe

- **Ortsvergleich-Briefing vermerkt gezeigte amtliche Warnungen nicht** (Kontext-Doc
  Abschnitt 8): `scheduler_dispatch_service.py:453-464` hat kein Gegenstück zu
  `trip_report_scheduler.py:1219-1227`. Der Compare-Checker (`*/15`) kennt im
  Vergleichs-Briefing gezeigte Warnungen daher nicht als „gemeldet" und würde sie über
  den in dieser Spec beschriebenen Mechanismus erst ab dem eigenen 15-Minuten-Lauf
  verfolgen, nicht ab dem Briefing-Zeitpunkt. Nutzersichtbares Fehlverhalten
  (Triage-Kriterium a) → **eigenes Issue**, nicht Teil dieser Scheibe.
- Drei kleinere Befunde aus derselben Live-Analyse (Kontext-Doc Abschnitt 8, Ende) →
  Sammel-Issue #1199, keine eigenen Issues:
  - `trip_alert.py:434` liest im Vorfilter nur `official_alert_triggers_enabled`, nicht
    `official_warnings.enabled` (der eigentliche Prüfer liest beide).
  - Trip-Prüfer wertet `official_warnings.sources` nicht aus (Compare-Prüfer schon).
  - Briefing und Prüfer holen mit verschiedenen Zeitfenstern, können dadurch je Lauf
    eine andere „beste Quelle" wählen und einen anderen Schlüssel erzeugen.

## Known Limitations

- **`max(alt, neu)` bei der Stufe ist bewusst asymmetrisch gegen Deeskalation.** Ein
  Zurückpendeln GELB→ORANGE→GELB→ORANGE meldet nach dieser Spec nur den ersten
  Stufenanstieg, nicht jeden Wechsel — sonst würde ein Flackern der Quelle wiederholt
  Alarme auslösen. Trade-off, PO-seitig mit der „ohne dass es zu komplex wird"-Vorgabe
  akzeptiert, keine Deeskalations-Meldung vorgesehen.
- **Verwaiste State-Einträge nach Eskalation/Vorverlegung.** Wird eine Revision GEMELDET
  (Eskalation oder ≥2h früherer Beginn), bleibt der ALTE Schlüssel unverändert im
  Melde-Gedächtnis stehen (nur der Still-Zweig entfernt `stale_key`). Das ist bewusst
  konsistent mit #1245 (getrennte Perioden behalten getrennte Keys) und harmlos: ein
  späteres drittes Glied vergleicht gegen ALLE Kandidaten mit echter Überlappung und
  wählt den mit dem höchsten `last_reported_value` (bei Gleichstand: spätestem
  `reported_at`) — der frisch gemeldete Eintrag gewinnt diese Auswahl im Regelfall.
- **Mehrere gleichzeitig überlappende Kandidaten sind ein Theoretischer Randfall.** Die
  deterministische Tie-Break-Regel (höchste Stufe, dann spätester `reported_at`) ist nicht
  über den Kern-Testplan hinaus exhaustiv geprüft — kann bei ungewöhnlicher
  Bestandsanhäufung (mehrere Alt-Einträge derselben Identität vor diesem Fix) auftreten.
- **Lesepfad wird für den Still-Zweig zum Schreibpfad.** `check_official_alert_triggers()`
  und `CompareOfficialAlertService._detect()` waren bisher rein lesend (das dokumentierte
  #1614-Prinzip „Schreiben erst nach erfolgreichem Versand" gilt weiter für den
  Melden-Zweig). Für den Still-Zweig ist eine sofortige Fortschreibung technisch
  notwendig (s. „Implementation Details" — sonst Kettenbug am dritten Glied); das ist eine
  bewusste, hier dokumentierte Abweichung vom bisherigen Vertrag, kein Seiteneffekt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Chirurgische Ergänzung der bestehenden #1245-Architektur (Zeitraum als
  Teil der State-Identität) um eine Überlappungs-Prüfung an der Melde-Entscheidung.
  ADR-0040 deckt die Grundrichtung („eine gerissene Grenze wird einmal gemeldet") bereits
  ab; diese Spec präzisiert eine Detailregel (#1245 AC-4), erzeugt aber keine neue
  Grundsatzentscheidung zu Kanälen, Provider, Datenmodell, Auth oder Editor-Paradigma.

## Changelog

- 2026-08-11: Initial spec created (Issue #1685, PO-Entscheidung 2026-08-10 aus dem Dialog übernommen).
