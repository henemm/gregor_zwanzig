# Context: fix-3348-ensemble-egress

## Request Summary
Auf Staging fehlt die Großwetterlage in jeder Trip-Mail, weil der Egress-Wächter
den Ensemble-Host `ensemble-api.open-meteo.com` blockt (nicht im Inventar).
Ziel: Host mit derselben Isolationsart wie `api.open-meteo.com` (TEST_ACCESS)
deklarieren, in Python- UND Go-Inventar.

## Ursachenkette (belegt)
1. `src/providers/openmeteo.py:68` — `ENSEMBLE_BASE_HOST = "https://ensemble-api.open-meteo.com"`;
   `_fetch_ensemble_spread` (Z. 775 ff.) ruft `{host}/v1/ensemble` über httpx.
2. `src/app/egress_guard.py:32` `INVENTORY` kennt nur `api.` und `air-quality-api.open-meteo.com`.
   `_is_allowed` (Z. ~101) ⇒ undeklarierter Host ⇒ `EgressBlockedError("httpx egress blocked for host: …")`.
3. `openmeteo.py:816/820` fängt den Fehler ab: `Ensemble fetch failed` (Staging-Log 131× in 3 Tagen),
   `confidence_pct` bleibt auf allen DataPoints `None`.
4. `src/services/weather_pattern.py::compute_for_trip` sammelt nur `confidence_pct`-Werte
   ⇒ leere Liste ⇒ `compute_stability` liefert `None` ⇒ `stability_result=None` in
   `src/services/trip_briefing_aufbau.py:103` ⇒ kein Großwetterlage-Block in der Mail.

Nebenwirkung derselben Sperre auf Staging: auch Verlässlichkeits-Hinweis (confidence)
und Ensemble-Gewitter-Mehrheit (#1983) fehlen dort.

## Prod
`install_egress_guard` ist in Prod ein No-Op (`not (is_test_mode or env == "staging")` ⇒ return,
AC-3 der Spec `egress_guard.md`). Prod ist von der Sperre NICHT betroffen.
Prüfung im Prod-Log nach Deploy als Bestätigung.

## Related Files
| File | Relevance |
|------|-----------|
| src/app/egress_guard.py | Python-Inventar — Eintrag ergänzen |
| internal/egress/inventory.go | Go-Zwillingsliste — Eintrag ergänzen (Drift-Test) |
| tests/test_egress_inventory_drift.py | erzwingt Deckungsgleichheit Py↔Go |
| docs/specs/modules/egress_guard.md | Inventar-Tabelle (Z. ~142) — Zeile ergänzen |
| src/providers/openmeteo.py | Aufrufer des Ensemble-Hosts |
| src/services/weather_pattern.py | Großwetterlage aus confidence_pct |

## Existing Patterns
- Jeder neue regulär gerufene, kontingentfreie Wetter-Host wird TEST_ACCESS in beiden Listen
  (Vorbild `opendata.dwd.de`, #1457 S2b, inkl. Go-Nachzug gegen Drift).
- Warn-Hosts sind BLOCKED; Ensemble ist kein Warn-Feed.

## Dependencies
- Upstream: httpx-Transport-Patch des Guards.
- Downstream: Staging-Trip-Briefing (Großwetterlage, Verlässlichkeit, Gewitter-Ensemble).

## Risks & Considerations
- Staging erzeugt danach zusätzliche Ensemble-Abrufe (Open-Meteo frei, gleicher Anbieter wie
  `api.open-meteo.com`, das bereits TEST_ACCESS ist).
- Nachweis aus Nutzersicht: Test, der mit installiertem Guard einen Ensemble-Request zulässt
  (Sentinel-Transport, wie AC-2 der Guard-Spec) — vorher rot.
- Staging-E2E: Trip mit Folge-Etappen und `show_stability=true` ⇒ Mail enthält Großwetterlage;
  `false` ⇒ nicht.

## Analysis

### Type
Bug (Staging-Isolation zu streng: regulär gerufener Wetter-Host fehlt im Inventar).

### Belege (2026-11-26)
- Staging-Log letzte 2 Tage: 145 Zeilen mit `ensemble-api.open-meteo.com` (Egress-Sperre).
- Prod-Log letzte 2 Tage (21 705 Zeilen): 0× `egress blocked`, 0× `Ensemble fetch failed`
  ⇒ Prod nicht betroffen (Guard dort No-Op), wie erwartet.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/egress_guard.py | MODIFY | `"ensemble-api.open-meteo.com": IsolationKind.TEST_ACCESS` |
| internal/egress/inventory.go | MODIFY | `"ensemble-api.open-meteo.com": TestAccess,` (Drift-Test) |
| docs/specs/modules/egress_guard.md | MODIFY | Inventar-Tabelle um Zeile ergänzen |
| tests/tdd/test_egress_ensemble_host_freigabe.py (Testnamen-Gate: Verhaltensname statt Issue-Nummer; Spec nennt noch den Arbeitstitel) | CREATE | Verhaltenstest: Guard installiert (Test-Modus) ⇒ echter `OpenMeteoProvider._fetch_ensemble_spread`-Weg erreicht den Transport (Sentinel), kein `EgressBlockedError`; zusätzlich Gegenprobe: undeklarierter Nachbar-Host bleibt gesperrt |

### Scope Assessment
- Files: 4 · LoC: ~+60 (davon ~55 Test) · Risk Level: LOW (nur Test/Staging wirksam; Prod No-Op)

### Technical Approach
Host als TEST_ACCESS in beiden Zwillingslisten (Muster `opendata.dwd.de`, #1457). Kein Code-Pfad
ändert sich außer der Inventar-Entscheidung. Nachweis auf Staging per `briefing_mail_validator`:
Trip mit Folge-Etappen, `show_stability=true` ⇒ Großwetterlage-Block in Mail; `false` ⇒ kein Block;
Staging-Log nach dem Lauf ohne neue `ensemble-api`-Sperrmeldung.

### Dependencies
Drift-Test `tests/test_egress_inventory_drift.py`, Go-Guard-Tests `internal/egress/guard_test.go`.

### Open Questions
- keine (Produktverhalten unverändert; reine Staging-Isolationskorrektur).
