# Context: fix-2314-restfenster-date-today

## Request Summary
#2314 (CI-Job `test` nachts rot) ist nach zwei Fixes (PR #2329 Ortstag, PR #2338 UTC-Tag + Schalter
`GZ_TEST_PROCESS_TZ`) offen geblieben bis zum echten Nachtlauf. Der Lauf vom 31.10. 22:29 UTC
(Run 41248402333) war mit **1 Fehler** rot (vorher 144 bzw. 60): `test_archiviert_und_abgelaufen_zaehlen_nicht`.
Die Läufe vom 1.11. (00:36, 02:06, 02:39 UTC) waren grün. Ziel: die Restfälle systematisch finden und beheben.

## Messung (2026-11-01, 07:50 UTC)
Alle 148 Testdateien mit `date.today()` wurden gelaufen: einmal in der Standardzone, einmal mit
`GZ_TEST_PROCESS_TZ=Pacific/Midway` (Prozesstag = gestern, UTC-Tag = heute). Beide Läufe mit
`--disable-socket -m "not live"` (Pflicht wegen Breit-Lauf-Gate); 74 Tests sind in beiden Läufen rot,
weil die Netzsperre sie trifft (kein Zonenthema, ignorieren).

**Nur in der Gestern-Zone rot: 2 Tests**
| Test | Ursache |
|------|---------|
| `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py::TestEntscheidungstabelle::test_archiviert_und_abgelaufen_zaehlen_nicht` (Z. 271-287) | Test datiert `heute`/`gestern` mit `date.today()` (Prozesstag); Produkt `trip_selection._vergleich_ist_aktiv` (Z. 126-140) vergleicht gegen den UTC-Tag von `now_utc` (Docstring: "Referenztag ist der UTC-Kalendertag") |
| `tests/tdd/test_issue_1012_no_data_guard.py::test_trip_reports_endpoint_returns_partial_status` (Z. ~427-429) | `_make_trip(..., date.today(), ...)` datiert zwei Trips auf den Prozesstag; Endpunkt rechnet am Ortstag, findet 0 Trips (`count: 0`, Status `ok` statt `partial`) |

Reproduktion mit `bash <scratchpad>/lauf.sh Pacific/Midway <testdatei>`; Skripte liegen im Scratchpad.
Hinweis: `GZ_TEST_PROCESS_TZ` mit `<`/`>` im Wert (POSIX-Form) lässt den Worktree-Wächter die Bash-Aufrufe
ablehnen; benannte Zone (`Pacific/Midway`) verwenden.

## Related Files
| File | Relevance |
|------|-----------|
| `conftest.py` (Root) | fixiert Prozess-TZ `America/St_Johns` (#1402); Schalter `GZ_TEST_PROCESS_TZ` bricht ab, wenn Zone zur Laufzeit nicht "gestern" ist |
| `tests/helpers/ortstag.py` | `ortstag(lat, lon)` und `utc_tag()` — vorhandene Helfer für Fixtures |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | Ratsche gegen Wanduhr-Fixtures (#2314); hat die zwei Restfälle nicht gefangen |
| `tests/tdd/test_prozesszonen_schalter.py` | Test des Zonen-Schalters |
| `src/services/trip_selection.py` | Produkt-Seite von Fall 1 (UTC-Tag) |
| `docs/specs/modules/fix_2314_ci_zeitzonen_riss.md`, `fix_2314_nachtfenster_utc_tag.md` | Vorgänger-Specs, Messreferenz-Tabelle |

## Offene Frage für die Analyse
Die Ratsche `test_fixture_wallclock_ratchet.py` ließ beide Fälle durch. Prüfen, warum (Allowlist? nur bestimmte
Dateien/Familien erfasst?) — sonst entstehen Restfälle immer wieder. Außerdem: der 22:29-UTC-Fehler tritt auf, obwohl
Prozesstag == UTC-Tag war (St. John's noch Sommerzeit) — möglicher zweiter Mechanismus (Lauf >00:00 UTC? freezegun-Leck?)
klären, bevor die Spec "2 Tests" als vollständig behauptet.

## Dependencies / Dependents
- Upstream: Produkt-Tageslogik (`trip_day.trip_local_today`, `trip_selection`), ADR-0044 (Ortstag)
- Downstream: nur CI-Job `test`; keine Laufzeitwirkung auf Staging/Prod

## Risks & Considerations
- Nur `tests/` ändern, kein Produktivcode.
- Ein Fix, der nur diese 2 Tests korrigiert, behandelt das Symptom; ohne Verschärfung der Ratsche kehrt die Klasse zurück.
- AC-9 aus #2314 (echter Nachtlauf grün) ist erst nach Merge im Fenster 22:00–02:30 UTC prüfbar.

## Analysis

### Type
Bug (Test-Fixtures datieren mit dem Prozesstag; kein Produktfehler)

### Befunde zu den offenen Fragen
1. **Zweiter Mechanismus beim 22:29-UTC-Lauf? Nein.** Run 41248402333 wurde 22:29 UTC angelegt, der Job `test`
   startete aber erst **00:03 UTC** (Runner-Wartezeit) und endete 00:33 UTC. Er lief also im Teilfenster
   00:00-02:30 UTC (Prozesstag = gestern, UTC-Tag = heute) = derselbe Mechanismus wie die gemessenen 2 Tests.
   Kein Freezegun-Leck, kein dritter Mechanismus. Hinweis: Die "Created"-Zeit eines Laufs ist NICHT die Laufzeit des Jobs.
2. **Warum fing die Ratsche beide nicht?** `test_fixture_wallclock_ratchet.py` meldet nur die KOMBINATION
   Wanduhr-Etappendatum + ungeklemmte `strftime("%H:%M")`-Ankunftszeit innerhalb einer Funktion (Klasse #1667:
   Mitternachts-Rollover der Wegpunktzeiten). Beide Restfälle haben keine Ankunftszeit-Arithmetik
   (Test 1: nur `end_date` eines Vergleichs; Test 2: Trips mit festen Wegpunkten) -> Merkmal 2 fehlt, kein Fund.
   Die Ratsche ist also nicht lückenhaft, sie bewacht schlicht eine andere Fehlerklasse. Eine Klasse
   "`date.today()` als Soll-Tag gegen Produkt-Tageslogik" ist syntaktisch nicht von harmlosem `date.today()`
   unterscheidbar (148 Dateien nutzen es, nur 2 sind rot) -> Ratsche wäre Falsch-Positiv-Flut.
   Der belastbare Detektor ist die **Messung unter der Gestern-Zone** (`GZ_TEST_PROCESS_TZ`), nicht eine Syntax-Regel.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| tests/tdd/test_eingangsauswahl_trip_und_vergleich.py (Z. 271-287) | MODIFY | `heute`/`gestern` per `utc_tag()` statt `date.today()` (Produkt: UTC-Tag von `now_utc`) |
| tests/tdd/test_issue_1012_no_data_guard.py (Z. ~427-429) | MODIFY | beide `_make_trip(..., date.today(), ...)` per `ortstag(lat, lon)` der Trip-Koordinaten (_STUBAI / _INNSBRUCK) |
| .github/workflows/ (neu, optional) | CREATE | Zeitgesteuerter Lauf im Fenster 00:00-02:30 UTC (siehe Entscheidung) |
| tests/tdd/test_prozesszonen_schalter.py | evtl. MODIFY | nur falls Guard-Test für den Zeitplan nötig |

### Scope Assessment
- Files: 2 (Pflicht) + 1 optional · LoC: ca. +6/-6 (Pflicht), +25 (Workflow, optional)
- Risk: LOW (nur `tests/`, kein Produktivcode, keine Laufzeitwirkung auf Staging/Prod)

### Technical Approach
- Die zwei Tests auf die vorhandenen Helfer `utc_tag()` bzw. `ortstag(lat, lon)` umstellen (bewährtes Muster aus PR #2329/#2338).
- Vorher RED nachweisen: beide Tests unter `GZ_TEST_PROCESS_TZ=Pacific/Midway` rot, danach grün; zusätzlich in Standardzone grün.
- Abschluss-Messung: erneuter Gesamtlauf aller `date.today()`-Dateien in beiden Zonen (wie oben) -> 0 Unterschiede.
- Dauerhafter Schutz statt neuer Syntax-Ratsche: ein zeitgesteuerter CI-Lauf (cron ca. 00:30 UTC) macht das Teilfenster
  00:00-02:30 UTC regelmäßig real prüfbar; heute gibt es in `.github/workflows/` keinen Zeitplan, daher blieb das Fenster
  400 Läufe lang ungeprüft. Das schließt zugleich AC-9 aus #2314 (echter Nachtlauf grün). Alternative: nur manueller Lauf.

### Dependencies
`tests/helpers/ortstag.py` (vorhanden), `services.trip_selection._vergleich_ist_aktiv`, `trip_day.trip_local_today`.

### Open Questions
- [ ] Zeitgesteuerten CI-Lauf (cron) einführen oder nur einmaliger manueller `workflow_dispatch`? (Empfehlung: cron, 1x täglich ca. 00:30 UTC, Kosten ~15 Min Runner; Entscheidung in der Spec treffen)
- [ ] Nachtjob 22:00-24:00 UTC ebenfalls real belegen (derselbe Zeitplan könnte ein zweites Zeitfenster 22:30 UTC abdecken)
