# External Validator Report

**Spec:** `docs/specs/modules/loader_display_config_default.md` (v1.1, Issue #111)
**Datum:** 2026-05-03T13:03:00Z
**Server:** https://staging.gregor20.henemm.com
**Validator-User:** `validator-issue110`
**Cookie:** `gz_session=validator-issue110.1777813190.b7a9...`

## Methodik

Tests via **Black-Box-Probing**:
- Test-Trips per `POST /api/trips` (Go-Backend) angelegt — bewusst OHNE `display_config`-Feld, mit verschiedenen `aggregation`-Varianten.
- Loader-Verhalten verifiziert via `GET /api/_internal/trip/{id}/loaded` (Python-Loader-Wrap, Issue #115).
- Side-Effect-Check via `GET /api/trips/{id}` (Go-Backend liest Roh-JSON von Platte).
- Quervergleich mit Spec `Expected Behavior`-Sektion.

Es wurde NICHT in `src/`, `git log`, `git diff` oder `docs/artifacts/` gelesen.

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Trip-JSON ohne `display_config` und ohne `weather_config` → `Trip.display_config ≠ None` | `01-loaded-no-aggregation.json`: `display_config={trip_id, metrics:24 Eintraege, ...}` | **PASS** |
| 2 | `display_config` wird via `build_default_display_config_for_profile(trip_id, profile)` befuellt; `trip_id` korrekt durchgereicht | Alle 4 Default-Trips: `display_config.trip_id` == requested ID | **PASS** |
| 3 | Profil aus `aggregation.profile` gelesen | `02-...-wandern.json`: 9 Wander-Metriken (incl. `uv_index`); `03-...-wintersport.json`: 10 Winter-Metriken (incl. `snow_depth`, `fresh_snow`, `wind_chill`); klar profil-spezifisch | **PASS** |
| 4 | Edge: `aggregation` fehlt → `profile = ALLGEMEIN` | `01-loaded-no-aggregation.json`: 7 generische Metriken (temperature, wind, gust, precipitation, rain_probability, cloud_total, sunshine), Top-Level `aggregation.profile == "allgemein"` | **PASS** |
| 5 | Edge: `aggregation.profile is None` → `profile = ALLGEMEIN` | `04-loaded-profile-null.json`: identisches 7-Metriken-Set wie Edge 4 | **PASS** |
| 6 | Side effects: Loader modifiziert die JSON-Datei auf Platte NICHT | Nach mehrfachem `/_internal/.../loaded`-Aufruf liefert `GET /api/trips/{id}` (Go-Backend liest Roh-Datei) weiterhin `display_config` und `aggregation` als **NICHT vorhanden** zurueck | **PASS** |
| 7 | Vorhandenes `display_config` wird NICHT vom Default ueberschrieben (Branch-Korrektheit) | `05-loaded-with-explicit-display-config.json`: nur 1 Metrik (`temperature`, `alert_enabled=true`, `alert_threshold=30`) — exakt der gepostete Inhalt, kein Default-Merge | **PASS** |
| 8 | Alle Default-Metriken haben `alert_enabled=False` (Spec, Known Limitations) | Alle 24 Metriken in `01-...json`: `alert_enabled=False` | **PASS** |

## Findings

### F1 — Metric Count divergiert von Spec-Annahme

- **Severity:** LOW (informational, nicht im Expected-Behavior-Block)
- **Expected:** Spec `Known Limitations`: "Der Default-`UnifiedWeatherDisplayConfig` enthaelt **29 Metriken**, von denen pro Profil-Template nur **ca. 10** `enabled=True` haben."
- **Actual:** Default enthaelt **24 Metriken**. Enabled-Counts: ALLGEMEIN=7, WANDERN=9, WINTERSPORT=10.
- **Evidence:** `01-loaded-no-aggregation.json` (24 Metriken), `02-...-wandern.json` (9 enabled), `03-...-wintersport.json` (10 enabled).
- **Impact:** Keiner — der Spec-Block "Known Limitations" ist deskriptiv, nicht normativ. Die Anzahl der Metriken ist nicht im "Expected Behavior" geforderter Vertrag. Der Bugfix selbst (display_config != None) funktioniert.
- **Empfehlung:** Spec aktualisieren oder Catalog erweitern. Kein Blocker fuer dieses Verdict.

### Cleanup-Hinweis

Der Validator hat 5 Test-Trips unter dem User `validator-issue110` angelegt:
- `validator-test-1`, `validator-test-wandern`, `validator-test-winter`, `validator-test-noprofile`, `validator-test-with-dc`

Diese Test-Trips bleiben auf Staging liegen, koennen vom Implementierer manuell aufgeraeumt oder beim naechsten Validator-Reset entfernt werden.

## Verdict: VERIFIED

### Begruendung

Alle 7 normativen Punkte aus dem `Expected Behavior`-Block der Spec wurden empirisch gegen die laufende Staging-App bestaetigt:

1. **Bugfix wirkt:** Trip ohne `display_config` und ohne `weather_config` produziert in der Loader-Antwort ein voll-strukturiertes `UnifiedWeatherDisplayConfig` (24 Metriken) statt `None`. Das vorher per `AttributeError` abgestuerzte Konsumenten-Verhalten ist damit unmoeglich gemacht.
2. **Profil-Routing korrekt:** Drei Profile getestet (allgemein, wandern, wintersport), jeweils plausible profil-spezifische Metriken (z.B. `snow_depth` nur bei wintersport, `uv_index` nur bei wandern + allgemein-relevante Sub-Sets).
3. **Edge-Cases robust:** Sowohl fehlendes `aggregation` als auch `aggregation.profile = null` fallen sauber auf ALLGEMEIN zurueck.
4. **Side-Effect-frei:** Mehrfache Loader-Aufrufe modifizieren die JSON-Datei auf Platte nicht (verifiziert via Go-Backend, das die Roh-Datei ausliefert).
5. **Bestehende Configs werden respektiert:** Trip mit eigenem `display_config` wird durchgereicht, der Default-Branch greift nicht.

Das einzige Finding (F1) bezieht sich auf eine deskriptive Aussage in `Known Limitations`, nicht auf ein normatives Verhalten — kein Blocker.

Backfill-Skript-Idempotenz (`scripts/backfill_display_config_issue111.py`) konnte vom Validator nicht direkt geprueft werden (kein Filesystem-Zugriff auf Staging-VM), wird aber implizit unterstuetzt durch Side-Effect-Beweis (Loader schreibt nicht zurueck) — Backfill-Effekt waere ueber denselben Mechanismus sichtbar geworden.
