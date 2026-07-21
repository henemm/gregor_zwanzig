---
entity_id: issue_1004_startzeit_ssot
type: bugfix
created: 2026-07-03
updated: 2026-07-03
status: draft
version: "1.0"
tags: [briefing, trip-model, scheduling, segments, ssot]
---

<!-- Issue #1004 — SSoT-Fix Segment-Startzeit (Re-Fix von #995 Gruppe A, verworfener Flag-Ansatz) -->

# Issue 1004 — Segment-Startzeit: Eine maßgebliche Quelle (SSoT)

## Approval

- [ ] Approved

## Purpose

Der #995-Fix (Gruppe A, Commit 34929cd3) war wirkungslos: Briefing-Mails und Segmenttabellen
rechnen weiterhin ab der alten GPX-Import-Zeit statt ab der vom Nutzer konfigurierten Etappen-
Startzeit, weil das dort eingeführte Herkunfts-Flag `time_window_origin` nie persistiert wird
(`gpx_processing.py` setzt es nur in-memory, kein Loader/Go-Modell kennt das Feld) und weil
`origin=None` konservativ wie "manuell" behandelt wurde — was ALLE Bestandstrips vom Fix ausnahm.
Beweis in echten Daten: `data/users/henning/trips/74de939c.json`, Etappe "nach Sassenberg" hat
`start_time=14:00`, zeigt aber weiterhin `time_window=07:00`.

Diese Spec ersetzt den Gruppe-A-Ansatz aus `issue_995_mail_bugs_bundle.md` vollständig durch
eine PO-verbindliche Regel (Issue #1004): Es gibt genau EINE maßgebliche Startzeit pro Etappe —
`stage.start_time`. `Waypoint.time_window` ist erwiesenermaßen ein reiner GPX-Import-Artefakt
ohne jeden manuellen Schreibpfad im Produkt und verliert deshalb komplett seine Autorität in der
Prioritätskette — kein Flag, keine Migration, gilt sofort für alle Trips inkl. Bestand.

## Source

- **File:** `src/services/trip_segments.py` — `convert_trip_to_segments()` (Zeilen 86-130,
  Prioritätskette für `wp1_start`/`wp2_start`) — **Kernänderung**
- **File:** `src/services/gpx_processing.py` — setzt `time_window` + totes
  `time_window_origin` beim Import (Zeilen 143-163); `gpx_to_stage_data()` (Zeilen 230-241)
  reicht das Flag über den echten Wizard-Upload-Endpunkt ohnehin nie durch
- **File:** `src/app/trip.py` — `Waypoint.time_window_origin` (Zeile 83), totes Feld, wird
  entfernt
- **File:** `frontend/src/routes/_home/cockpitHelpers.ts` — `stageWindow()` (Zeilen 31-37),
  aufruferlose TS-Kopie derselben falschen Kette (`time_window` vor `arrival_calculated`);
  laut `issue_568_home_redesign.md` für spätere Anbindung vorgesehen — wird auf die neue
  Regel umgestellt (NICHT gelöscht), sonst reproduziert die Anbindung später exakt #1004
- **File:** `docs/reference/api_contract.md` — Zeilen 669-672 (Erklärungsabschnitt zum nie
  wirksamen Flag; wird durch die neue Kette ersetzt) UND Zeilen 2384-2388 (Changelog-Eintrag
  zu #995; bleibt stehen, wird um einen #1004-Eintrag zur Entfernung ergänzt)
- **File:** `src/app/loader.py` — `save_trip()` (Zeilen 1197-1201) ruft bei JEDEM Speichern
  `compute_stage_arrivals()` für jede Stage auf — Python-seitiges Äquivalent zu Go
  `store.SaveTrip`/`ComputeStageArrivals`; zusätzlicher Beleg, dass `arrival_calculated`
  sowohl im Go-API-Pfad als auch im Python-Scheduler-Pfad immer frisch ist
- **File:** `tests/tdd/test_issue_995_segment_start_time.py` — kodiert `origin=None ≈
  manuell` als Soll (AC-2); wird an die neue Regel angepasst
- **Identifier:** `convert_trip_to_segments`, `Waypoint`, `stageWindow`, `save_trip`

> **Schicht-Hinweis:** Die fachliche Kernänderung liegt ausschließlich im Python-Backend
> (`src/services/`, `src/app/`). Zusätzlich betroffen: eine ungenutzte, aber laut
> `issue_568_home_redesign.md` für eine spätere Anbindung vorgesehene TypeScript-Funktion im
> Frontend-Cockpit (Anpassung der Prioritätslogik, KEINE Löschung, keine neue UI-Logik) und
> ein Doku-File. Kein Go-Code (`internal/`, `api/`) wird geändert — `internal/model/naismith.go`
> und `internal/store/store.go` sind bereits die Quelle der stets frisch berechneten
> `arrival_calculated`-Werte und bleiben unangetastet.

## Estimated Scope

- **LoC:** ~80 Produktionscode (Kettenlogik + totes Feld/Funktion entfernen), +150 Tests
- **Files:** ~7 (Code 4, Doku 1, Tests 2)
- **Effort:** medium — **Risk Level:** MEDIUM (zentrale Zeitkette mit 4 Produkt-Aufrufern)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `convert_trip_to_segments()` (`trip_segments.py`) | function | SSoT für Segment-Zeitpriorität — 4 Aufrufer (`trip_report_scheduler.py`, `preview_service.py`, `trip_command_processor.py`, `trip_alert.py`) müssen konsistent denselben, korrigierten Wert sehen |
| `Waypoint.arrival_override` (Issue #303) | field | Einziger legitimer manueller Zeit-Mechanismus — bleibt an oberster Stelle der Kette erhalten |
| `ComputeStageArrivals` (`internal/model/naismith.go:104-122`) | Go-Funktion | Läuft bei JEDEM `store.SaveTrip` (`internal/store/store.go:179-187`) und kaskadiert `arrival_calculated` immer frisch ab `stage.StartTime` — Garant dafür, dass das Fallback-Glied der Kette nie veraltet |
| `save_trip()` (`src/app/loader.py:1197-1201`) | function | Python-seitiges Spiegelbild von `store.SaveTrip`: ruft `compute_stage_arrivals()` bei JEDEM Speichern auf — `arrival_calculated` ist also auch auf dem Python-Persistenz-Pfad garantiert frisch, nicht nur über Go |
| `_format_hhmm()` (`src/core/naismith.py:66-72`) | function | Clamp auf `23:59` (Zeile 71) — Ursache der Mitternachts-Klemme, die nach diesem Fix erstmals erreichbar wird |
| Self-Heal-Bedingung (`src/services/trip_segments.py:66-69`) | guard | Greift NUR wenn ALLE `arrival_calculated` einer Stage `None` sind — bei teilweise gefülltem Zustand (manche Wegpunkte haben einen Wert, andere nicht) greift kein Self-Heal, Kette muss auch dafür robust sein (AC-7) |
| `data/users/henning/trips/74de939c.json` | Fixture/Referenz | Echter Bestandstrip als Abnahme-Referenz (start_time 14:00 vs. veraltete time_window 07:00) |
| `docs/specs/modules/issue_995_mail_bugs_bundle.md` | spec | Gruppe A wird durch diese Spec vollständig ersetzt (Flag-Ansatz verworfen) |
| `docs/specs/modules/issue_783_776_778_briefing_fixes.md` | spec | Dokumentiert die jetzt obsolete alte Kette `time_window > arrival_override > stage.start_time > arrival_calculated` |

## Implementation Details

**Neue Prioritätskette** in `convert_trip_to_segments()` — `time_window` fliegt komplett aus
der Kette, kein Flag-Check mehr nötig:

```
wp1_override = arrival_override, falls gesetzt          # Issue #303, weiterhin oberste Stelle
wp1_calculated = arrival_calculated (Naismith)

if wp1_override is not None:
    start = wp1_override
elif i == 0 and stage.start_time:
    start = stage.start_time              # einzige Quelle für Segment 1 einer Etappe
elif wp1_calculated is not None:
    start = wp1_calculated                # Naismith-Kaskade, immer frisch ab start_time
elif i == 0:
    start = default_start                 # 08:00
else:
    start = cumulative_time               # Fallback wie bisher
```

`wp1.time_window` / `wp2.time_window` werden in beiden Zweigen (Zeilen 88-92 und 116-121 in
der aktuellen Fassung) ersatzlos aus dem Vergleich entfernt — das Feld selbst bleibt am
`Waypoint`-Objekt für Persistenz/Anzeige (Read-Modify-Write, BUG-DATALOSS-GR221-Regel), wird
aber nirgends mehr als Startzeit-Quelle *gelesen*.

Begleitend:
- `src/app/trip.py:83` — `time_window_origin: Optional[str] = None` entfernen (nie
  persistiert, nach der Kettenänderung ohnehin funktionslos)
- `src/services/gpx_processing.py:143-163,230-241` — alle `time_window_origin`-Zuweisungen
  entfernen; `time_window`-Zuweisung selbst bleibt unverändert (Roundtrip/Anzeige-Artefakt)
- `frontend/src/routes/_home/cockpitHelpers.ts:31-37` — `stageWindow()` auf die neue
  Prioritätsregel umstellen (`stage.start_time` bzw. `arrival_calculated` des ersten
  Wegpunkts; `time_window` ignorieren) + Kommentar, dass `time_window` nie autoritativ ist —
  die Funktion ist laut `issue_568_home_redesign.md` für spätere Anbindung vorgesehen
- `docs/reference/api_contract.md:669-672` — Flag-Absatz durch Beschreibung der neuen Kette
  ersetzen; Changelog (Z.2384-2388) um #1004-Eintrag ergänzen (Feld entfernt)
- **Mitternachts-Klemme (Challenger-Fund, Testfall statt Redesign):** Der bestehende
  `end_dt <= start_dt`-Guard (`trip_segments.py:144-148`) bleibt unverändert — er verwirft
  einzelne kollabierte Folgesegmente bereits heute defensiv. Es wird lediglich testgesichert,
  dass das ERSTE Segment und alle nicht geklemmten Folgesegmente auch bei sehr später
  `stage.start_time` erhalten bleiben (kein stiller Totalausfall der kompletten Etappe).

## Expected Behavior

- **Input:** Ein beliebiger Trip (neu importiert ODER vor diesem Fix bereits gespeicherter
  Bestand) mit einer konfigurierten `stage.start_time`, unabhängig davon, was `time_window`
  an den Wegpunkten historisch enthält
- **Output:** Segment 1 jeder Etappe beginnt exakt bei `stage.start_time` (sofern kein
  `arrival_override` gesetzt ist); alle Folgesegmente folgen der Naismith-Kaskade
  (`arrival_calculated`), konsistent über alle 4 Produkt-Pfade (Scheduler-Briefing,
  Trip-Detail, Telegram, Alerts)
- **Side effects:** Änderung an `src/app/trip.py` löst den Pre-Snapshot-Hook
  `data_schema_backup.py` aus. Sichtbare Zwischenzeiten können sich bei Bestandstrips ändern,
  deren `time_window` bisher zufällig von `stage.start_time`/`arrival_calculated` abwich —
  das ist die beabsichtigte Konsequenz einer einzigen konsistenten Kaskade.

## Acceptance Criteria

- **AC-1 (Bestandstrip):** Given ein VOR diesem Fix angelegter, bereits gespeicherter Trip,
  dessen Etappe eine konfigurierte Startzeit hat (Referenzfall: `data/users/henning/trips/74de939c.json`,
  Etappe "nach Sassenberg" mit `start_time=14:00`, alte Import-Zeiten 07:00/09:00/11:00 an
  den Wegpunkten) / When die Briefing-Mail bzw. die Trip-Detail-Stundentabelle für diesen
  Trip real gerendert wird — OHNE Neu-Import, OHNE Migration / Then beginnt Segment 1 um
  14:00 und die Folgesegmente folgen der Naismith-Kaskade (14:21, 14:46) — nirgends erscheint
  mehr 07:00.
  - Test: Den echten Bestandstrip laden (keine neu erstellte Fixture), den vollen
    Rendering-Pfad (bzw. `convert_trip_to_segments()` gegen genau diese Datei) real
    aufrufen und den tatsächlich erzeugten Zeit-String prüfen — kein Dateiinhalt-Check.

- **AC-2 (Persistenz-Roundtrip):** Given ein frisch per GPX importierter Trip, der gespeichert
  und danach neu aus der Datei geladen wird / When die Etappen-Startzeit anschließend über die
  echte API geändert wird und danach die Stundentabelle real abgerufen wird / Then zeigt sie
  die neue Startzeit — der #995-Fehlermodus "wirkt nur im Speicher, überlebt keinen Reload"
  ist damit nachweislich ausgeschlossen.
  - Test: Echter GPX-Import → Speichern → Reload aus der Datei → API-Aufruf zum Ändern von
    `start_time` → erneuter Reload → Rendering-Aufruf → Vergleich des gerenderten Zeit-Strings.
    Kein In-Memory-Only-Ersatztest.

- **AC-3 (alle 4 Produkt-Pfade):** Given derselbe Trip-Zustand mit einer geänderten
  Etappen-Startzeit / When Scheduler-Briefing (`trip_report_scheduler.py`), Trip-Detail
  (`preview_service.py`), Telegram-Segmentabruf (`trip_command_processor.py`) und
  Alert-Segmentfenster (`trip_alert.py`) unabhängig voneinander die Segmentzeiten abfragen /
  Then liefern alle vier denselben, aktuellen Startzeitpunkt — keiner zeigt noch die alte
  Importzeit.
  - Test: 4 echte Aufrufe der jeweils öffentlichen Funktion/des jeweiligen Endpoints gegen
    denselben Trip-Zustand, Vergleich der zurückgegebenen Zeitwerte auf Übereinstimmung.

- **AC-4 (arrival_override bleibt maßgeblich):** Given ein Wegpunkt mit einem manuell über
  die Nutzeroberfläche gesetzten `arrival_override` (Issue #303) / When Segmente für die
  betroffene Etappe gebaut werden, unabhängig vom Stand von `stage.start_time` oder
  `time_window` / Then bleibt der `arrival_override`-Wert für diesen Wegpunkt maßgeblich —
  kein Regressionsverhalten für den einzigen tatsächlich existierenden manuellen
  Zeit-Mechanismus im Produkt.
  - Test: Echten Trip mit einem über die API gesetzten `arrival_override` anlegen,
    Segmentzeiten real abrufen und den Override-Wert im tatsächlich gerenderten Ergebnis
    nachweisen.

- **AC-5 (Mitternachts-Klemme):** Given eine Etappe mit später Startzeit (z.B. 22:00) und
  mehreren Wegpunkten, deren berechnete Ankunftszeiten von der Naismith-Kaskade auf 23:59
  geklemmt werden / When die Segmente für diese Etappe gebaut werden / Then bleiben das erste
  Segment und alle nicht geklemmten Folgesegmente erhalten — kein stiller Totalausfall der
  ganzen Etappe; geklemmte Folgesegmente dürfen kollabieren (bestehender `end_dt<=start_dt`-
  Guard greift dort weiterhin), das Verhalten wird nachvollziehbar geloggt statt die
  komplette Etappe verschwinden zu lassen.
  - Test: Echten Trip mit `start_time=22:00` und ausreichend langer Etappen-Distanz anlegen,
    `convert_trip_to_segments()` real aufrufen, prüfen dass die Segmentliste nicht leer ist
    und Segment 0 die korrekte Startzeit trägt, sowie dass für geklemmte Folgesegmente eine
    Warnung geloggt statt eine leere Liste zurückgegeben wird.

- **AC-6 (Zwei-Nutzer-Isolation):** Given zwei verschiedene Nutzer (`user_id` A und B) mit je
  einem eigenen Trip, bei dem Nutzer A eine geänderte Etappen-Startzeit hat und Nutzer B nicht
  / When beide Trips über denselben SSoT-Aufrufer (z.B. `preview_service.py`) unabhängig
  voneinander abgefragt werden / Then sieht Nutzer A ausschließlich die neue Startzeit seines
  eigenen Trips und Nutzer B ausschließlich die unveränderte Startzeit seines Trips — keine
  Cross-User-Vermischung der Segmentdaten.
  - Test: Echte Persistenz unter `data/users/<user_id>/trips/` für zwei Test-User anlegen,
    beide über die echte API/Funktion mit dem jeweils korrekten `user_id`-Kontext abfragen,
    Ergebnisse getrennt und auf Isolation prüfen.

- **AC-7 (teilweise gefülltes arrival_calculated):** Given eine Etappe, bei der nur EIN Teil
  der Wegpunkte bereits ein berechnetes `arrival_calculated` trägt (z.B. weil ein Import- oder
  Migrations-Zustand nicht alle Wegpunkte erfasst hat) — der Self-Heal-Mechanismus
  (`trip_segments.py:66-69`) greift NICHT, da er nur bei komplett leerem Zustand (alle `None`)
  auslöst / When die Segmente für diese Etappe gebaut werden / Then fällt für Wegpunkte ohne
  `arrival_calculated` (bei `i>0`) höchstens auf das bestehende `cumulative_time`-Fallback
  zurück — kein Segment wird dadurch still verworfen oder übersprungen.
  - Test: Echten Trip mit einer Etappe aus mindestens 3 Wegpunkten anlegen, bei der handgesetzt
    nur der mittlere Wegpunkt `arrival_calculated=None` hat (die übrigen einen Wert tragen),
    `convert_trip_to_segments()` real aufrufen und prüfen, dass alle Segmente der Etappe in der
    zurückgegebenen Liste erscheinen (keine stille Lücke).

## Known Limitations

- **Legacy-CLI-Pfad bleibt außen vor (out of scope, Folge-Issue):**
  `src/services/trip_forecast.py:145-155` liest `waypoint.time_window` weiterhin direkt fürs
  Wetter-Abfragefenster. Einziger Aufrufer ist der Legacy-CLI-Pfad (`src/app/cli.py:228-229`,
  `--trip`), NICHT der Produkt-Scheduler/Mail/Telegram/Alert-Pfad. Dieser Fix ändert daran
  nichts — wird im PO-Freigabetext ausdrücklich genannt, plus Folge-Issue für eine spätere
  Bereinigung.
- **Mitternachts-Klemme bleibt Grenzverhalten (nur abgesichert, nicht neu designt):** Der
  Naismith-Clamp auf 23:59 (`src/core/naismith.py:71`) und der `end_dt<=start_dt`-Guard
  (`trip_segments.py:144-148`) bleiben inhaltlich unverändert. Dieser Fix stellt nur sicher,
  dass eine sehr späte `stage.start_time` nicht mehr die komplette Etappe stumm zum
  Verschwinden bringt (AC-5) — ein grundsätzliches Redesign der Klemm-Logik ist NICHT Teil
  dieses Fixes und wird im PO-Freigabetext ausdrücklich genannt.
- **Schema-Restrisiko `PUT /api/trips/{id}` (akzeptiert, folgenlos):** Der Endpoint kann
  weiterhin unvalidierte `time_window`-Werte im Request-Body schreiben (Roundtrip-Feld). Kein
  aktiver Client tut das aktuell; nach diesem Fix ist es ohnehin folgenlos, da `time_window`
  nie mehr autoritativ gelesen wird. Wird im PO-Freigabetext ausdrücklich genannt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird kein neues Datenschema, keine neue Kanal-/Provider-Entscheidung und
  kein neuer Gate-/Guard-Hook eingeführt — im Gegenteil, ein zuvor eingeführtes Flag
  (`time_window_origin`) wird als gescheiterter Ansatz wieder entfernt und durch eine
  Vereinfachung der bestehenden Prioritätskette ersetzt. Fällt damit unter keine der
  ADR-Guard-Kategorien aus `docs/adr/README.md`. Sollte `adr_guard.py` beim Commit dennoch
  anschlagen (z.B. weil `trip.py` als Datenschema-Datei erkannt wird), ist `[no-adr]` in der
  Commit-Message mit Verweis auf diese Sektion zulässig.

## Test Coverage

- `tests/tdd/test_issue_995_segment_start_time.py` (ANGEPASST) — die bisherigen AC-1/AC-2/AC-3
  aus #995 kodierten `origin=None ≈ manuell` als Soll; werden durch die neue Regel ersetzt
  (kein Herkunfts-Flag mehr, `time_window` grundsätzlich nicht mehr autoritativ)
- `tests/tdd/test_issue_1004_startzeit_ssot.py` (NEU) — AC-1 (Bestandstrip-Fixture-Nachweis
  gegen `74de939c.json`), AC-2 (Persistenz-Roundtrip), AC-4 (`arrival_override`-Vorrang),
  AC-5 (Mitternachts-Klemme), AC-6 (Zwei-Nutzer-Isolation), AC-7 (teilweise gefülltes
  `arrival_calculated` — Self-Heal `trip_segments.py:66-69` greift nur bei komplett None)
- `tests/tdd/test_issue_1004_ssot_callers.py` (NEU) — AC-3: 4 SSoT-Aufrufer liefern
  konsistente Startzeit für denselben Trip-Zustand

## Changelog

- 2026-07-03: Initial spec erstellt — Issue #1004, ersetzt den gescheiterten Flag-Ansatz aus
  `issue_995_mail_bugs_bundle.md` Gruppe A durch die PO-verbindliche Ein-Quelle-Regel
  (`stage.start_time` statt `time_window`), aufbauend auf
  `docs/context/fix-1004-startzeit-ssot.md` inkl. Challenger-Funden (Mitternachts-Klemme,
  Legacy-CLI-Pfad, tote `stageWindow()`-Kopie).
- 2026-07-03: Ergänzt nach zweitem Challenger-Durchlauf: (1) zweite `time_window_origin`-
  Fundstelle in `api_contract.md:2384-2388` (Changelog-Eintrag, wird ergänzt statt gelöscht)
  aufgenommen; (2) `stageWindow()` (`cockpitHelpers.ts:31-37`) wird NICHT mehr gelöscht,
  sondern auf die neue Kette umgestellt (laut `issue_568_home_redesign.md` für spätere
  Anbindung vorgesehen — sonst würde eine künftige Anbindung Bug #1004 exakt reproduzieren);
  (3) neues AC-7 für den Randfall "teilweise gefülltes `arrival_calculated`" (Self-Heal greift
  nur bei komplett leerem Zustand); (4) `save_trip()` (`loader.py:1197-1201`) als Python-
  seitiges Äquivalent zu Go `ComputeStageArrivals` als zusätzlicher Beleg ergänzt.
