---
entity_id: fix_2314_restfenster_date_today
type: bugfix
created: 2026-11-01
updated: 2026-11-01
status: approved
version: "1.0"
tags: [tests, ci, zeitzone, issue-2314]
---

# Fix #2314 (Durchgang 3) — Restfälle im Nachtfenster 00:00–02:30 UTC

## Approval

- [x] Approved (PO-Freigabe 2026-11-01, inkl. täglichem Lauf 00:30 UTC)

## Purpose

Nach PR #2329 (Ortstag) und PR #2338 (UTC-Tag, Schalter `GZ_TEST_PROCESS_TZ`) war der CI-Job `test`
im Nachtlauf vom 31.10./1.11. noch mit **1 Fehler** rot (vorher 144 bzw. 60). Eine Vollmessung aller
148 Testdateien mit `date.today()` unter der „Gestern-Zone" (`Pacific/Midway`) findet **genau 2 Tests**,
die dort rot sind und in der Standardzone grün. Beide datieren ihre Fixtures mit dem Prozesstag, das
Produkt rechnet aber mit UTC-Tag bzw. Ortstag. Diese Lieferung stellt die beiden Tests auf den
fachlich richtigen Tag um und führt einen geplanten CI-Lauf im Teilfenster ein, damit das Fenster
nicht erneut 400 Läufe lang ungeprüft bleibt. Produktivcode wird nicht verändert.

Befund zum vermuteten zweiten Mechanismus: Der „22:29-UTC-Lauf" (Run 41248402333) wurde zwar 22:29
angelegt, der Job `test` startete aber erst 00:03 UTC. Er lief im Teilfenster 00:00–02:30 UTC —
derselbe Mechanismus, kein Freezegun-Leck, kein dritter Mechanismus.

## Source

- **Files:** `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` (Z. 271–287),
  `tests/tdd/test_issue_1012_no_data_guard.py` (Z. ~427–429), `.github/workflows/ci.yml` (Trigger)
- **Helfer (vorhanden):** `tests/helpers/ortstag.py::utc_tag()` / `ortstag(lat, lon)`

> **Schicht-Hinweis:** reine Test-/CI-Änderung. `src/`, `api/`, `internal/`, `frontend/` werden nur
> gelesen (Wahrheitsquelle: `trip_selection._vergleich_ist_aktiv` = UTC-Tag von `now_utc`;
> `trip_day.trip_local_today` = Ortstag).
> **Teilung Trip/Vergleich:** nicht berührt (keine UI-/Produktkomponente). **Mandantentrennung,
> Kanäle:** nicht berührt (keine Nutzerdaten, keine Briefing-/Alarm-Inhalte).

## Estimated Scope

- **LoC:** ca. +6/−6 in Tests, +4 in `ci.yml`
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/ortstag.py` | vorhanden | `utc_tag()`, `ortstag(lat, lon)` als Datumsquelle |
| `services.trip_selection._vergleich_ist_aktiv` | Wahrheitsquelle UTC-Tag | Produkt-Referenz Fall 1 |
| `trip_day.trip_local_today` (ADR-0044) | Wahrheitsquelle Ortstag | Produkt-Referenz Fall 2 |
| Root-`conftest.py` `GZ_TEST_PROCESS_TZ` | Messwerkzeug | stellt „Prozesstag = gestern" lokal her |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | unverändert | bewacht Klasse #1667 (Ankunftszeit-Rollover), nicht diese Klasse |

## Implementation Details

**Fall 1** (`test_archiviert_und_abgelaufen_zaehlen_nicht`): `heute` und `gestern` aus
`utc_tag()` statt `date.today()` ableiten (Produkt vergleicht gegen den UTC-Tag von `now_utc`).

**Fall 2** (`test_trip_reports_endpoint_returns_partial_status`): beide `_make_trip(..., date.today(), ...)`
datieren per `ortstag(lat, lon)` der jeweiligen Trip-Koordinaten (`_STUBAI`, `_INNSBRUCK`), weil der
Endpunkt am Ortstag rechnet.

**Keine neue Syntax-Ratsche:** 148 Dateien nutzen `date.today()`, nur 2 sind rot — eine Syntaxregel
wäre eine Falsch-Positiv-Flut. Belastbarer Detektor ist die Messung unter der Gestern-Zone. Diesen
Detektor macht der geplante Lauf dauerhaft.

**Geplanter Lauf:** `ci.yml` bekommt `schedule: - cron: "30 0 * * *"` (täglich 00:30 UTC, mitten im
Teilfenster 00:00–02:30 UTC). Fehlschläge melden GitHub-Standard-Benachrichtigungen an den Besitzer.
Entscheidung: **cron, nicht nur manuell** — nur so wird das Fenster regelmäßig real geprüft und
AC-9 aus #2314 belegbar. Kosten: ein CI-Lauf pro Tag. Das Fenster 22:00–24:00 UTC bleibt vorerst
ungeplant (Durchgang 1 hat es per Messung geschlossen; ein zweiter Zeitplan nur bei erneutem Befund).

## Expected Behavior

- **Input:** dieselben zwei Tests, gleicher Inhalt; nur die Datumsquelle ändert sich.
- **Output:** beide Tests grün in der Standardzone **und** unter `GZ_TEST_PROCESS_TZ=Pacific/Midway`;
  Vollmessung aller `date.today()`-Dateien in beiden Zonen zeigt 0 Unterschiede.
- **Side effects:** täglicher CI-Lauf 00:30 UTC.

## Acceptance Criteria

**AC-1:** Given der Test `test_archiviert_und_abgelaufen_zaehlen_nicht` und Prozesstag = gestern
(`GZ_TEST_PROCESS_TZ=Pacific/Midway`), When er läuft, Then ist er grün (vorher rot), und in der
Standardzone bleibt er grün.

**AC-2:** Given der Test `test_trip_reports_endpoint_returns_partial_status` und Prozesstag = gestern,
When er läuft, Then liefert der Endpunkt Status `partial` mit zwei gefundenen Trips (vorher `ok` mit
`count: 0`), und in der Standardzone bleibt er grün.

**AC-3:** Given beide Tests vor der Änderung, When sie unter der Gestern-Zone laufen, Then sind sie
nachweislich rot (RED-Artefakt), bevor die Datumsquelle umgestellt wird.

**AC-4:** Given alle Testdateien mit `date.today()`, When sie einmal in der Standardzone und einmal
unter `Pacific/Midway` mit `--disable-socket -m "not live"` laufen, Then ist die Menge der nur in der
Gestern-Zone roten Tests leer.

**AC-5:** Given `.github/workflows/ci.yml`, When das Repository auf `main` steht, Then enthält der
Trigger-Block einen `schedule`-Eintrag mit Cron `30 0 * * *`, und alle bisherigen Trigger
(`push`, `pull_request`, `workflow_dispatch`) bleiben unverändert.

**AC-6:** Given der geplante Lauf nach dem Merge, When er im Fenster 00:00–02:30 UTC erstmals läuft,
Then ist der Job `test` grün (Nachweis für AC-9 aus #2314; erst nach Merge prüfbar, Issue-Close
erst danach).

**AC-7:** Given die Änderung, When der Diff geprüft wird, Then liegen Änderungen ausschließlich unter
`tests/` und `.github/workflows/`, kein Produktivcode.

## Known Limitations

- AC-6 ist erst am Morgen nach dem Merge prüfbar; bis dahin bleibt #2314 offen.
- 74 Tests sind in beiden Zonen wegen der Netzsperre rot (kein Zonenthema, außerhalb des Umfangs).
- Der Zeitplan läuft nur, wenn `ci.yml` auf dem Standardbranch liegt (GitHub-Eigenschaft).
