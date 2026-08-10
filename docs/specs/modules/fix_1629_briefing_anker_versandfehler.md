---
entity_id: fix_1629_briefing_anker_versandfehler
type: bugfix
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [alerts, briefing, dispatch, issue-1629, observability]
---

# Briefing-Anker überlebt Versandfehler (Issue #1629)

## Approval

- [x] Approved — Product Owner, 2026-08-09 („Go"). Freigegeben wurden AC-1 bis AC-10 in der hier
  vorliegenden Fassung, einschließlich der nachträglich ergänzten AC-10 (Absicherung darf nur den
  Versandaufruf umschließen) und der Klarstellung zu den zwei getrennten Gedächtnissen bei AC-4/AC-6.
  Beleg als Kommentar an Issue #1629.

## Purpose

Scheitert der Versand eines Trip-Briefings mit einer Ausnahme (z.B. E-Mail-Allowlist-Fehler),
wird heute der Wetter-Snapshot des Tages NICHT geschrieben — obwohl ein bloß nicht zustellbares
Briefing (Kanal konfiguriert, aber unerreichbar) ihn bereits heute schreibt. Diese Lücke ließ am
08.08.2026 den Abweichungs-Alarm eines laufenden Trips einen ganzen Tag ausfallen, unsichtbar bis
auf eine in Dauerrauschen untergehende Logzeile. Diese Spec stellt Gleichbehandlung zwischen
"Kanal unerreichbar" und "Versand wirft eine Ausnahme" her und macht einen anhaltenden
Versandfehler am Status-Endpunkt sichtbar.

Vollständige Herleitung und Messungen:
`docs/context/fix-1629-briefing-anker-ueberlebt-versandfehler.md`. Diese Spec wiederholt nichts
davon, sondern zieht den Scope daraus.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportSchedulerService._send_trip_report_outcome` (Zeile 958 Versandaufruf,
  Zeile 1046 `write_anchor_and_reset_memory(...)`)
- Nebendateien: `src/services/scheduler_dispatch_service.py` (Ortsvergleich, Zeile 401 vor 423),
  `internal/scheduler/briefing_health.go` (Sichtbarkeit)

> **Schicht-Hinweis:** Betroffene Schicht: **Python-Core** (`src/services/`) für den Anker-Fix
> und den Diagnose-Schreiber, **Go-API** (`internal/scheduler/`) für die Aggregation am
> Status-Endpunkt. Kein Frontend-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alert_briefing_anchor.write_anchor_and_reset_memory` | function | geteilter Baustein, den beide Aufrufer bereits nutzen — wird unverändert weiterverwendet, nicht angepasst (#1467 S2 AG5) |
| `dispatch_orchestrator.TripDispatchStrategy.dispatch_one` / `CompareDispatchStrategy` | module | fängt die Ausnahme bereits heute EINE Ebene höher; Zählung/Log dort bleibt Referenzverhalten |
| `record_corrupt_trip_observability` (#1262) | function | Vorbild für den fail-soft Diagnose-Schreiber (Dedup-/Journal-Muster) |
| `internal/scheduler/briefing_health.go` `analyzeBriefingProviderErrors` | function | Vorbild für die Streak-Berechnung (Namensanalogie `provider_error_streak_since`) |
| ADR-0018 | decision | "Provider-Fallback ohne Kaschieren" — verlangt ein mit der Ausfalldauer wachsendes Signal, trägt diese Scheibe |
| `rework_1467_s2_aenderungsalarm` (AG5) | module | Regel "Anker und Melde-Reset an EINER Bedingung" — bleibt unverändert gültig |
| `fix_1628_nowcast_datenluecke` | module | nächstverwandte Spec: "Ausfall ≠ nichts zu melden", gleiche Fehlerklasse |

## Estimated Scope

- **LoC:** ~90 Produktivcode (Limit 250).
- **Files:** 4 Produktivdateien (`trip_report_scheduler.py`, `scheduler_dispatch_service.py`, ein
  neuer/erweiterter Diagnose-Schreiber, `briefing_health.go`), 3 Testdateien.
- **Effort:** medium — geteilter Baustein, beidseitige Wirkung (Trip + Ortsvergleich), aber die
  Änderung stellt bereits bestehende Semantik wieder her statt neue einzuführen.

## Nicht in dieser Scheibe

- **Härtung der Leseseite (#1661):** Altersschutz für den undatierten Rückfall in
  `trip_alert.py:509` (analog zu `compare_alert.py` `_MAX_ANCHOR_AGE`), sowie fehlender
  `load_dated`-Schutz auf der Compare-Seite (`compare_alert.py:359`). Unabhängig testbar, eigene
  ACs, eigenes Issue.
- **Nachlieferung gescheiterter Versände (#1662):** Der bestehende Nachhol-Mechanismus (#1012,
  `pending_briefings.json`) erfasst nur Wetterdaten-Fehler, keinen Versandfehler. Ein
  Versandfehler bleibt für den Nutzer unbemerkt ohne Nachlieferung — eigenes, nutzersichtbares
  Problem, eigenes Issue.
- **Rauschen der Warnzeile "No fresh weather data"** (~1350 Treffer in der Journal-Historie):
  gebucht als Sammel-Eintrag in **#1199**.
- **Fehlender `CLAUDE_MQ_SECRET`** (Totalausfall-Melder #1346 schweigt schweigend): gemeldet an
  die Infrastruktur (`internal/notify/mq.go:39`), kein Python-Defekt, nicht Teil dieser Scheibe.

## Implementation Details

### Kernänderung — Versandaufruf fängt die Ausnahme, Anker läuft trotzdem

`trip_report_scheduler.py`, Zeile 958:

```
result = self._notification_service.send_trip_report(request)
```

wird in ein `try/except` gefasst. Im `except`-Zweig läuft **derselbe** Anker-Aufruf wie im
Erfolgsfall (`write_anchor_and_reset_memory` mit demselben `_write_briefing_anchor`-Closure,
`entity_ids=[trip.id]`, `on_demand=on_demand`, `reset_memory=self._reset_alert_state_after_briefing`,
`briefing_entity_id=trip.id`, `briefing_entity_type="trip"` — identisch zu Zeile 1046-1056), dazu
fail-soft der neue Diagnose-Eintrag (s. unten). Danach `raise`, damit die Ausnahme unverändert bis
`dispatch_orchestrator.py:76-78` durchreicht — Zählung (`self._failed += 1`) und Fehlerprotokoll
(`logger.error("Failed %s report for %s: %s", ...)`) bleiben dadurch **identisch** zum heutigen
Verhalten.

`record_official_alerts_reported` (Zeile 1036-1044, `if result.sent and not on_demand`) bleibt
unverändert — im `except`-Zweig existiert `result` gar nicht, dieser Block wird dort nie erreicht,
genau wie heute bei jedem anderen Frühausstieg vor Zeile 986.

Symmetrisch für den Ortsvergleich in `scheduler_dispatch_service.py`: der Versandaufruf über
`NotificationService(...).send_compare_report(...)` (Zeile 401-415) bekommt dasselbe `try/except`,
im `except`-Zweig läuft derselbe `write_anchor_and_reset_memory`-Aufruf wie Zeile 423-435
(`entity_ids=[f"{preset_id}:{loc.id}" for loc in locations]`, `write_anchor=lambda: ...`,
`briefing_entity_id=preset_id`, `briefing_entity_type="compare"`), danach `raise`.

### Diagnose-Schreiber (fail-soft, Muster `record_corrupt_trip_observability`)

Neue oder erweiterte Funktion (z.B. `record_briefing_dispatch_failure(user_id, kind, entity_id,
error)` in `alert_briefing_anchor.py` oder einem neuen kleinen Modul) hängt eine Zeile an
`users/<uid>/diagnostics/briefing_dispatch_failures.jsonl` an (`{"ts": ..., "kind": "route"|
"vergleich", "entity_id": ..., "error": str(exc)}`), analog zu `openmeteo_calls.jsonl`. Schreiben
ist in ein eigenes `try/except (OSError, ...)` mit `logger.warning` gekapselt — ein defekter
Diagnose-Schreiber darf den `raise` der eigentlichen Versandausnahme nie verhindern oder
überdecken (AC-7).

### Sichtbarkeit (ADR-0018) — `briefing_health.go`

Neue Go-Funktion `analyzeBriefingDispatchErrors(dataDir string, now time.Time) (string, int)`,
strukturell identisch zu `analyzeBriefingProviderErrors` (Datei einlesen, Zeitstempel sortieren,
`recentCount` = Treffer der letzten 24h, `streakSince` = Rückwärtslauf ab dem jüngsten Fehler,
solange Lücken unter der bestehenden Gap-Schwelle bleiben; ein erfolgreicher Versand schreibt
keine neue Zeile in diese Datei — die Streak-Berechnung selbst erkennt das Ende einer Serie über
die bestehende Zeit-Lücken-Logik, kein zusätzlicher "Erfolg"-Eintrag nötig). Liest über alle
Nutzer per `filepath.Glob(.../diagnostics/briefing_dispatch_failures.jsonl)`, privacy-safe
aggregiert (kein `user_id`/`trip_id` im Ergebnis, Muster wie `aggregateCorruptTrips`).

`BriefingHealth()` (Zeile 139-148) bekommt zwei zusätzliche Feldpaar-Einträge:
`briefing_dispatch_error_streak_since` und `briefing_dispatch_errors_recent_count` — Namensanalogie
zu `provider_error_streak_since`/`provider_errors_recent_count`, damit dieselbe externe
BetterStack-Eskalationsformel (`now - streak_since`) ohne Anpassung greift. Kein neues Journal
außer der einen `.jsonl`-Datei, kein neuer Endpunkt — Erweiterung des bestehenden
`/api/scheduler/status`.

### Verworfene Alternativen

- **Anker schreiben, Melde-Reset auslassen.** Verworfen: `write_anchor_and_reset_memory` bündelt
  beide Schritte bewusst an EINER Bedingung (#1467 S2 AG5). Der Docstring von
  `alert_briefing_anchor.py:7-14` benennt genau diese Trennung als die gefährlichste Kombination —
  ein frischer Anker gegen ein altes Melde-Gedächtnis kann eine echte Abweichung dauerhaft und ohne
  jede Logzeile verschlucken. Ein sichtbarer Ein-Tages-Ausfall würde gegen einen unsichtbaren
  Dauerausfall getauscht — schlechterer Handel.

## Expected Behavior

- **Input:** ein Trip- bzw. Ortsvergleich-Versandlauf, dessen `NotificationService`-Aufruf eine
  Ausnahme wirft (z.B. `OutputConfigError` durch die Resend-Allowlist).
- **Output:** die Ausnahme wird nach oben durchgereicht wie bisher (Lauf zählt als `failed`); der
  Wetter-Snapshot des Tages (datiert und undatiert) wird trotzdem geschrieben, das Melde-Gedächtnis
  wird trotzdem zurückgesetzt, ein fail-soft Diagnose-Eintrag entsteht.
- **Side effects:** ein neuer, kleiner JSONL-Diagnose-Eintrag je Nutzer; zwei neue Felder am
  bestehenden `/api/scheduler/status`. Kein neuer HTTP-Aufruf, kein neuer Endpunkt.

## Acceptance Criteria

- **AC-1:** Given der Versand eines Trip-Briefings scheitert mit einer Ausnahme (z.B. E-Mail-Allowlist-Fehler), When der Versandlauf abgeschlossen ist, Then wurde für diesen Trip trotzdem ein Wetter-Snapshot des Tages gespeichert — sowohl der datierte als auch der undatierte.
  - Test: `_send_trip_report_outcome()` mit einem garantiert scheiternden E-Mail-Kanal (z.B.
    Resend-Allowlist-Fehler simuliert wie im gemessenen Fall) aufrufen, Ausnahme abfangen, danach
    `WeatherSnapshotService(user_id).load(trip.id)` UND `.load_dated(trip.id, target_date)`
    prüfen — beide liefern den erwarteten Snapshot, nicht `None`.

- **AC-2:** Given derselbe Versandfehler tritt beim Ortsvergleich auf, When der Versandlauf abgeschlossen ist, Then wurde für alle Orte des betroffenen Presets trotzdem ein Vergleichs-Snapshot geschrieben — dieselbe Zusicherung wie AC-1, nur für den Ortsvergleich.
  - Test: `send_one_compare_preset()`-Pfad mit garantiert scheiterndem Kanal aufrufen, Ausnahme
    abfangen, `CompareWeatherSnapshotService` für jeden Ort des Presets prüfen — Snapshot vorhanden.

- **AC-3:** Given ein Versandfehler wie in AC-1, When der Aufrufer (`dispatch_orchestrator`) den Lauf verarbeitet, Then wird der Lauf weiterhin als fehlgeschlagen gezählt und die bisherige Fehlerzeile im Protokoll bleibt unverändert — die Ausnahme wird tatsächlich weitergereicht, nicht verschluckt.
  - Test: `TripDispatchStrategy.dispatch_one()` mit demselben scheiternden Versand aufrufen und
    prüfen, dass `self._failed` um 1 steigt und die Fehler-Logzeile weiterhin geschrieben wird —
    identisch zum Verhalten vor dieser Änderung (Regressionstest gegen den Bestand).

- **AC-4:** Given ein Versandfehler wie in AC-1, When der Anker geschrieben wird, Then wird das Melde-Gedächtnis genauso zurückgesetzt wie im heutigen Fall "Kanal konfiguriert, aber unerreichbar" (`result.sent == False`) — kein Sonderweg für den Ausnahmefall.
  - Test: Melde-Gedächtnis (`AlertStateService`) vor dem Lauf mit einem alten Eintrag vorbelegen,
    Versandfehler auslösen, danach prüfen, dass der Eintrag zurückgesetzt wurde — gleicher Zustand
    wie bei einem parallel durchgeführten `result.sent == False`-Lauf (Vergleichsmessung).

- **AC-5:** Given ein Ad-hoc-Abruf (`on_demand=True`), bei dem der Versand mit einer Ausnahme scheitert, When der Aufruf abgeschlossen ist, Then bleiben Anker und Melde-Gedächtnis unverändert — ein Ad-hoc-Abruf bleibt auch im Fehlerfall wirkungslos gegenüber beiden Zuständen.
  - Test: `_send_trip_report_outcome(trip, report_type, on_demand=True)` mit demselben
    Versandfehler aufrufen, Snapshot-Zeitstempel und Melde-Gedächtnis vor/nach vergleichen —
    identisch, keine Änderung.

- **AC-6:** Given ein Trip-Briefing mit amtlicher Warnung, dessen Versand mit einer Ausnahme scheitert, When der Lauf abgeschlossen ist, Then wird die Warnung NICHT als "im Briefing bereits gemeldet" vermerkt — dieser Vermerk bleibt an die tatsächliche Zustellung gebunden, damit eine nie zugestellte Warnung den unabhängigen Alarm-Checker nicht stummschaltet.
  - Test: bestehender Test `tests/tdd/test_alert_state_briefing_reset.py::test_fehlgeschlagener_versand_schreibt_das_melde_gedaechtnis_nicht` (Zeile 846) bleibt unverändert grün; ergänzend ein neuer Fall mit Ausnahme statt `result.sent=False` prüft dieselbe Nicht-Vermerkung.
  - ⚠️ **Nicht mit AC-4 verwechseln — es geht um ZWEI verschiedene Gedächtnisse.** AC-4 betrifft das
    **Abweichungs-Melde-Gedächtnis** (`AlertStateService`, „welchen Wert habe ich zuletzt gemeldet"),
    das beim Briefing bewusst zurückgesetzt wird. AC-6 betrifft den **Vermerk über amtliche
    Warnungen** (`record_official_alerts_reported`, #1614), der eine bereits zugestellte Warnung vor
    doppelter Meldung schützt. Der irreführende Name des bestehenden Tests („Melde-Gedaechtnis")
    meint das zweite, nicht das erste. Ersteres wird im Fehlerfall zurückgesetzt, letzteres nicht —
    das ist kein Widerspruch, sondern zwei getrennte Zusicherungen.

- **AC-7:** Given der neue Diagnose-Schreiber selbst scheitert (z.B. Dateisystemfehler beim Schreiben der JSONL-Zeile), When ein Versandfehler gleichzeitig auftritt, Then bricht der Briefing-Lauf dadurch nicht zusätzlich — die ursprüngliche Versandausnahme wird trotzdem weitergereicht, der Diagnose-Fehler wird nur geloggt.
  - Test: den Diagnose-Schreiber mit einem simulierten Schreibfehler (z.B. nicht beschreibbares
    Zielverzeichnis) versehen, Versandfehler zusätzlich auslösen, prüfen dass exakt die
    ursprüngliche Versand-Ausnahme (nicht der Diagnose-Fehler) beim Aufrufer ankommt.

- **AC-8:** Given mehrere aufeinanderfolgende Versandfehlschläge desselben Nutzers, When der Status-Endpunkt abgefragt wird, Then wächst das Ausfall-Signal mit der Dauer — der Startzeitpunkt der Fehlerserie (`briefing_dispatch_error_streak_since`) verschiebt sich durch weitere Fehlschläge NICHT nach vorne, und ein danach erfolgreicher Versand lässt die Serie enden.
  - Test: `analyzeBriefingDispatchErrors()` mit einer JSONL-Fixture aus mehreren
    Fehler-Zeitstempeln in Folge aufrufen — `streak_since` bleibt der erste Zeitstempel der
    ununterbrochenen Serie; mit einem zusätzlichen, weit zurückliegenden Fehler nach einer großen
    Lücke bleibt `streak_since` auf dem jüngeren Serienbeginn (Lücken-Logik wie
    `analyzeBriefingProviderErrors`).

- **AC-9 (Wirkungs-AC, zwingend):** Given ein Morgen-Briefing, dessen Versand mit einer Ausnahme scheitert, When am selben Tag der Abweichungs-Alarm-Lauf für denselben Trip ausgeführt wird, Then findet dieser Lauf einen gültigen, heute datierten Wetter-Snapshot und führt die normale Abweichungsprüfung durch — er endet NICHT in der Warnung "No fresh weather data".
  - Test: End-to-End innerhalb der Kern-Suite (kein echtes Netz): Morgen-Briefing mit
    garantiertem Versandfehler laufen lassen, danach `TripAlertService.check_and_send_alerts()`
    (bzw. den internen `_fetch_fresh_weather`/`_get_cached_weather`-Pfad) für denselben Trip und
    Tag aufrufen — Ergebnis zeigt, dass Segmente gefunden wurden (kein `[]`, kein
    `logger.warning("No fresh weather data ...")`), sondern eine reguläre Abweichungsprüfung
    stattfindet. Dieser Test prüft die WIRKUNG am Alarm-Pfad, nicht nur die Existenz einer
    Snapshot-Datei.

- **AC-10:** Given der Fehler entsteht **vor** dem Versand — etwa weil der Wetterabruf scheitert und gar keine vollständigen Segmentdaten vorliegen —, When der Lauf mit einer Ausnahme endet, Then wird KEIN Wetter-Snapshot geschrieben und das Melde-Gedächtnis bleibt unangetastet; der Anker entsteht ausschließlich dann, wenn die Wetterdaten des Tages vollständig ermittelt wurden.
  - Begründung: Diese Zusicherung grenzt die Änderung ein. Der Absicherungs-Block darf **nur** den
    Versandaufruf (`trip_report_scheduler.py:958` bzw. `scheduler_dispatch_service.py:401`)
    umschließen, nicht den davorliegenden Wetterabruf. Andernfalls entstünde ein Anker aus
    unvollständigen oder leeren Daten — der Alarm vergliche dann gegen eine Referenz, die nie ein
    Briefing war. Das wäre eine schlimmere Fehlerklasse als der behobene Defekt.
  - Test: Wetterabruf so verfälschen, dass er vor Erreichen des Versands wirft; danach prüfen, dass
    weder datierter noch undatierter Snapshot existiert und `AlertStateService` unverändert ist.
  - Mutations-Gegenprobe (Pflicht): Wird der Absicherungs-Block versuchsweise über die **gesamte**
    Methode gezogen, MUSS dieser Test rot werden. Bleibt er grün, bewacht er nichts.

## Hinweis für die TDD-RED-Phase (Go-Test aus AC-8)

Der Go-Test zu AC-8 liegt bauartbedingt neben dem Produktivcode (`internal/scheduler/*_test.go`).
In Phase 5 blockt `edit_gate.py` jedes Schreiben einer `.go`-Datei außerhalb eines Verzeichnisses
namens `test`/`tests`, während Phase 6 einen RED-Beleg verlangt — ohne Umweg entsteht daraus eine
Zwickmühle. Bewährter Weg (kein Gate-Eingriff, verifiziert in #1396): Testdatei außerhalb des
Repos ablegen und per `go test -overlay=<overlay.json>` virtuell ins Paket einblenden, Ausgabe als
RED-Artefakt registrieren, danach wandert die Datei an ihren regulären Platz. `go` liegt unter
`/usr/local/go/bin` und ist nicht im `PATH`.

## Known Limitations

- **Bei einer Fehlerserie wird das Melde-Gedächtnis je Versuch neu geleert**, was
  Wiederholungsmeldungen begünstigen kann. Dieses Muster existiert bereits im heutigen
  `result.sent == False`-Pfad unverändert — diese Scheibe führt es nicht neu ein, sie stellt nur
  Gleichbehandlung her.
- **Geteilter Baustein wirkt auf beide Seiten:** jede Änderung an `write_anchor_and_reset_memory`
  oder an ihrer Aufrufstelle betrifft Trip UND Ortsvergleich gleichermaßen (gewollt, #1467 S2 AG5) —
  aber auch ein unentdeckter Fehler in dieser Scheibe hätte doppelte Reichweite.
- **Die "Quelle:"-Diagnose enthält keine Aussage über die Ursache des Versandfehlers** außer der
  gefangenen Exception-Nachricht als Freitext — keine strukturierte Fehlerklassifizierung. Reicht
  für ein wachsendes Ausfallsignal, nicht für eine Root-Cause-Anzeige.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — löst eine bestehende Zusage aus ADR-0018 ein (Punkt 3,
  "Nicht-Kaschieren-Invariante": ein persistenter Ausfall muss ein mit der Ausfalldauer
  wachsendes Signal erzeugen).
- **Rationale:** Der Versandfehler-Pfad hatte bislang weder eine Datenmarkierung noch ein
  Health-Signal — ein Totalausfall des Briefings blieb sowohl beim Nutzer (fehlender Alarm) als
  auch beim Betrieb (Dauerrauschen statt Ausnahmesignal) unsichtbar. Diese Scheibe wendet dasselbe
  Muster an, das für `provider_error_streak_since` bereits etabliert ist (Streak-Berechnung über
  Zeitstempel-Lücken, kein neues Journal-Format), auf einen bisher unerfassten Ausfallpfad.

## Changelog

- 2026-08-10 (Adversary F003): **Abweichung von der Spec-Formulierung, dem PO vorgelegt und
  freigegeben.** Der Abschnitt „Sichtbarkeit" oben sagt „solange Lücken unter der **bestehenden**
  Gap-Schwelle bleiben" und meint damit `providerErrorStreakGapThreshold = 2h`. Die Umsetzung führt
  stattdessen einen eigenen Wert `dispatchErrorStreakGapThreshold = 26h` ein
  (`internal/scheduler/briefing_health.go:181`). **Begründung:** Anbieter-Abrufe passieren viele
  Male pro Lauf, Briefing-Versände nur zwei Mal täglich, bei manchen Nutzern einmal. Mit 2 h wäre
  jeder Fehlschlag eine Serie der Länge 1, und die Vorwärtsprüfung gegen „jetzt" hätte das Signal
  **zwei Stunden nach dem Ausfall gelöscht** — genau das Kaschieren, das ADR-0018 Punkt 3 verbietet.
  Die Formel und beide Feldnamen bleiben unverändert, die externe Eskalation rechnet weiter
  `now - streak_since`. Dem PO am 2026-08-10 als „Auffälligkeit 1" der GREEN-Ergebnisse vorgelegt
  und mit „go" freigegeben. Der Adversary hat die Abweichung unabhängig gefunden und fachlich als
  nachvollziehbar bewertet; sie war nur nicht schriftlich festgehalten — das holt dieser Eintrag nach.
- 2026-08-09: Initiale Spec. Scope auf den Anker-Fix (Trip + Ortsvergleich, symmetrisch) und die
  Go-Sichtbarkeitserweiterung begrenzt. Leseseite (#1661) und Nachlieferung (#1662) ausdrücklich
  ausgeschlossen, eigene Folge-Issues.
