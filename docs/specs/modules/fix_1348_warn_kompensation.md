---
entity_id: fix_1348_warn_kompensation
type: module
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [official-alerts, safety, issue-1348]
---

# Fix: Amtliche-Warnungen-Hinweis nur bei echter Lücke (Kompensation zählt)

## Approval

- [ ] Approved

## Purpose

Der Briefing-Hinweis "amtliche Warnungen aktuell nicht abrufbar" wird heute
schon dann gesetzt, wenn EINE von mehreren für einen Ort zuständigen
Warn-Quellen ausfällt — auch wenn eine andere zuständige Quelle erfolgreich
geantwortet hat. Das erzeugt Fehlalarme (belegt: Trip "KHW 403", 30.07.,
GeoSphere lieferte durchgehend erfolgreich, nur MeteoAlarm war gesperrt,
Hinweis erschien trotzdem). Ein Sicherheitshinweis, der auch ohne echte
Lücke erscheint, wird überlesen. Dieses Modul stellt die PO-Korrektur vom
2026-07-30 her: der Hinweis erscheint nur noch, wenn KEINE für den Ort
zuständige Quelle erfolgreich geantwortet hat.

## Source

- **File:** `src/services/official_alerts/base.py`
- **Identifier:** `def get_official_alerts_with_status`, Formelzeile (aktuell `unavailable = covering > 0 and failed >= 1`)

Python-Core / Domain-Backend (`src/services/`) — keine andere Schicht betroffen.

## Estimated Scope

- **LoC:** ~60-80
- **Files:** 3 (1 Produktivdatei, 1 Testdatei, 1 bestehende Spec-Korrektur)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.base.OfficialAlertSource` | Protocol | Quellen-Interface (`covers`, `fetch`, `name`) |
| `services.official_alerts.base._REGISTERED_SOURCES` | module-state | Registry aller amtlichen Quellen, wird iteriert |
| `services.official_alerts.warn_egress.observe_fetch_failure` | context manager | erkennt fail-soft-Ausfälle ohne Exception (Real-Pfad) |
| `services.official_alerts.__init__` | registry | heute registriert: `VigilanceSource, MeteoForetsSource, MassifClosureSource, GeoSphereWarnSource, MeteoAlarmFeedSource("IT"), MeteoAlarmFeedSource("AT"), DpcSource` |
| `services.trip_report_scheduler.TripReportScheduler` | service | Konsument, keine Codeänderung |
| `services.comparison_engine` | service | Konsument, keine Codeänderung |
| ADR-0018 | decision | "Provider-Fallback ohne Kaschieren" — dieselbe Leitidee: Ausweichen erlaubt, solange keine echte Lücke entsteht |

## Implementation Details

Formel in `get_official_alerts_with_status()` ändern:

```
# Vorher (PO-Entscheid 2026-07-23, STRENG — abgelöst):
unavailable = covering > 0 and failed >= 1

# Nachher (PO-Entscheid 2026-07-30 — Kompensation zählt):
unavailable = covering > 0 and failed >= covering
```

`covering` und `failed` werden unverändert gezählt (kein Änderungsbedarf an
der Zähl-Logik selbst, nur an der Ableitung des Booleans daraus). Bei genau
einer zuständigen Quelle ist `failed >= covering` äquivalent zu `failed >= 1`
— das strenge Verhalten für Orte mit nur einer zuständigen Quelle bleibt
unverändert. Erst ab zwei oder mehr zuständigen Quellen wirkt Kompensation:
eine erfolgreiche zuständige Quelle genügt, um `unavailable=False` zu halten.

Docstring der Funktion (aktuell Zeile 98-116) wird auf die neue Regel
umgeschrieben; ebenso der Moduldocstring von
`tests/tdd/test_official_alerts_unavailable_hint.py` (referenziert aktuell
wörtlich "PO-Entscheid 2026-07-23, STRENG").

## Expected Behavior

- **Input:** Koordinaten eines Orts; Zustand der registrierten amtlichen
  Warn-Quellen (deckt ab ja/nein, Fetch erfolgreich/ausgefallen)
- **Output:** `(alerts: list[OfficialAlert], unavailable: bool)` — Signatur
  unverändert
- **Side effects:** keine (reine Berechnung, kein neuer Zustand)

## Acceptance Criteria

- **AC-1:** Given zwei für einen Ort zuständige Quellen, eine fällt beim
  Fetch aus (wirft), die andere liefert erfolgreich (auch leer) / When
  `get_official_alerts_with_status()` aufgerufen wird / Then
  `unavailable=False` (Kompensation greift — Kern der PO-Korrektur).
  - Test: bestehenden Test `test_mischfall_streng_one_fail_one_empty_is_unavailable`
    umbenennen (`test_mischfall_kompensiert_one_fail_one_success_is_available`)
    und Assertion auf `unavailable is False` umdrehen.

- **AC-2:** Given zwei für einen Ort zuständige Quellen, BEIDE fallen beim
  Fetch aus / When der Status berechnet wird / Then `unavailable=True`
  (keine Kompensation möglich, wenn nichts übrig bleibt, das kompensieren
  könnte).
  - Test: neuer Test mit zwei `_AllCoveringFailSource`-artigen Quellen (oder
    einer zweiten Fail-Quelle zusätzlich zur bestehenden), erwartet
    `unavailable is True`.

- **AC-3:** Given genau EINE für einen Ort zuständige Quelle, diese fällt
  aus / When der Status berechnet wird / Then `unavailable=True`
  (Regressionswächter: bei nur einer Quelle bleibt das Verhalten so streng
  wie zuvor — keine Kompensation ohne Kompensationspartner).
  - Test: bestehender Test `test_all_covering_fail_is_unavailable` bleibt
    unverändert grün (dient als Regressionsnachweis für diesen Fall).

- **AC-4:** Given keine für den Ort zuständige Quelle / When der Status
  berechnet wird / Then `unavailable=False` (unverändert, kein
  Fehlalarm ohne Zuständigkeit).
  - Test: bestehender Test `test_non_covering_is_available` bleibt
    unverändert grün.

- **AC-5 (Realpfad AT, PO-Vorfall):** Given die heute registrierten
  AT-Quellen `GeoSphereWarnSource` (liefert erfolgreich, echter Objekt-Pfad)
  und `MeteoAlarmFeedSource("AT")` (Egress-Block simuliert real-blockiert,
  fail-soft `[]` ohne Exception) für einen österreichischen Punkt / When der
  Status berechnet wird / Then `unavailable=False` — genau der am 30.07.
  gemeldete Fehlalarm-Fall ist jetzt korrekt.
  - Test: neuer Realpfad-Test mit den ECHTEN, heute registrierten Klassen
    (kein Double), analog zum bestehenden Muster mit
    `GeoSphereWarnSource`/Egress-Guard.

- **AC-6 (Realpfad IT/Südtirol, reale heutige Quellenlage):** Given die
  heute registrierten IT-Quellen `MeteoAlarmFeedSource("IT")`
  (real-blockiert, fail-soft `[]`) und `DpcSource` (liefert erfolgreich,
  auch leer) für einen Südtirol-Punkt / When der Status berechnet wird /
  Then `unavailable=False` — reflektiert die REALE heutige Zwei-Quellen-Lage
  für Südtirol (nicht das am 2026-07-30 noch gültige, seit `DpcSource`
  (2026-07-31) überholte Einzelquellen-Beispiel aus dem PO-Kommentar).
  - Test: neuer Realpfad-Test, echte Klassen, PO-Entscheid 2026-08-09
    (reale Lage statt Alt-Beispiel).

- **AC-7 (Regression, unverändert bestehender Realpfad-Test):** Given eine
  einzelne, im Egress-Wächter blockierte Quelle (`GeoSphereWarnSource`,
  isolierte Registry mit nur dieser einen Quelle) / When der Status
  berechnet wird / Then `unavailable=True` — bleibt der bestehende
  Regressionswächter `test_real_failsoft_empty_from_blocked_source_is_unavailable`
  unverändert grün.

## Known Limitations

- Der Warn-Lücken-Hinweis existiert weiterhin nur im E-Mail-Trip-Briefing
  (full+compact); SMS/Telegram/Compare-Mail sind laut #1348-Kommentar
  bewusste Folge-Scheiben, kein Blocker dieser Korrektur.
- `DpcSource` hat eigene bekannte Grenzen (Zonen-Drift, #1434) — diese
  Korrektur ändert nichts an der Zuverlässigkeit einzelner Quellen, nur an
  der Ableitung von `unavailable` aus dem kombinierten Quellenstatus.
- Coverage-Grenzen einzelner Quellen (z.B. INCA-Bbox reicht über
  Österreich hinaus, #1397) bleiben wie dokumentiert unverändert bestehen —
  außerhalb des Scopes dieser Korrektur.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue)
- **Rationale:** Setzt ADR-0018 ("Provider-Fallback ohne Kaschieren") konsequent
  um — Ausweichen auf eine kompensierende Quelle ist erlaubt, solange keine
  echte Lücke entsteht; fällt die letzte zuständige Quelle auch aus, wird das
  weiterhin laut gemeldet, nicht kaschiert. Kein neuer Architektur-Entscheid
  nötig, nur eine Formel-Korrektur innerhalb der bestehenden Entscheidung.

## Changelog

- 2026-08-09: Initial spec created (Korrektur der PO-Entscheidung 2026-07-30 zu #1348)
