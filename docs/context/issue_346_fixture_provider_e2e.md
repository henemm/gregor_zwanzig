# Context: Issue #346 — E2E-/Abnahmetests dürfen nicht die echte Open-Meteo-API treffen

## Request Summary

E2E-/pytest-Tests rendern Briefing-Vorschauen (`render_email_preview` / `render_sms_preview`)
in-process und holen dabei **echte** Open-Meteo-Daten. Da das API-Limit **pro Server-IP**
gilt und mehrere Dev-Sessions parallel laufen, erschöpft diese Test-Last das gemeinsame
Tageslimit (1.160 `vorschau`-Calls in einer Stunde gemessen) → Produktiv-Briefings bekommen
`429` und gehen ohne Wetterdaten raus (#338). Tests müssen verbindlich auf den
Fixture-Provider gezwungen werden.

## Root Cause (belegt durch Zähler #338)

```
Test → PreviewService.render_*_preview → _build_report
     → TripReportSchedulerService._fetch_weather(segments)
     → providers.base.get_provider("openmeteo")
     → OpenMeteoProvider.fetch_forecast  →  ECHTE Open-Meteo-API
```

- **1.160 `vorschau`-Calls 04:00–05:00 Uhr, alle HTTP 200** (Kontingent aktiv verbraucht).
- Weboberfläche zeigte **0** `/api/preview`-HTTP-Calls im selben Zeitraum → die Last lief
  **in-process** (pytest), nicht über echte Nutzer.
- Zeitlich korreliert mit dem Start paralleler Workflows (u.a. `issue_339_verify_timing` 04:42).
- Regulärer Produktivbetrieb liegt gemessen bei ~2.500–3.800 Einheiten/Tag — erklärt die
  Erschöpfung NICHT. Die Test-Last ist der dominante Verbraucher.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/providers/base.py` | **Zentraler Hebel.** `get_provider("openmeteo")` ist die EINZIGE Python-Provider-Factory; `_load_providers()` registriert die Provider lazy. Ein Fixture-Umweg gehört hierher. |
| `src/services/preview_service.py` | `render_email_preview`/`render_sms_preview` → `_build_report` → Scheduler. Quelle der `vorschau`-Last. |
| `src/services/trip_report_scheduler.py:666` | `_fetch_weather()` ruft `get_provider("openmeteo")` auf (auch `_fetch_night_weather:754`, `_enrich_ensemble_for_trip:809`). |
| `src/providers/openmeteo.py:182` | `OpenMeteoProvider` (`__init__:190`, `name:202`, `fetch_forecast:705`) — Interface, das ein Python-Fixture-Provider erfüllen müsste. |
| `src/providers/call_log.py:32-33` | Tagging `render_*_preview → "vorschau"`; Diagnose-Zähler aus #338, der den Erfolg misst (Akzeptanz). |
| `tests/conftest.py` | Globaler conftest (nur sys.path). Möglicher Ort, um `GZ_TEST_FIXTURE_DIR` für alle pytest-Läufe autozusetzen. |
| `tests/tdd/conftest.py` | TDD-conftest (GroundTruthFetcher-Fixture). |
| `tests/tdd/test_bug_338_openmeteo_call_counter.py:197` | `test_ac2_preview_path_sets_source_vorschau` ruft `render_email_preview` mit echtem Trip KHW 403 → **echte API**. |
| `tests/tdd/test_epic_140_preview_endpoints.py` | T2/T3/T5: `/api/preview`-Endpoints + `render_*_preview` direkt → **echte API**. Header: „Wetter-Provider-Calls werden im Test toleriert". |
| `api/routers/preview.py` | Echter Endpoint `/api/preview` (echte Nutzer) — darf NICHT auf Fixtures umgelenkt werden. |

## Bestehender Fixture-Provider (#263) — nur Go-Seite

- `internal/provider/fixture/provider.go` — `FixtureProvider`, aktiviert wenn `cfg.TestFixtureDir != ""`.
- `cmd/server/main.go` — Provider-Selektion: Fixture wenn `GZ_TEST_FIXTURE_DIR` gesetzt, sonst OpenMeteo.
- `internal/config/config.go` — Feld `TestFixtureDir` (`envconfig:"TEST_FIXTURE_DIR"`).
- `fixtures/openmeteo/{innsbruck,stubai,zillertal}.json` — 3×72 Datenpunkte (existieren bereits).
- `.env.e2e` (committed): `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo`.
- Nearest-Location-Lookup + Timestamp-Re-Stamping auf den aktuellen UTC-Tag.

**Lücke:** Der Python-Pfad respektiert `GZ_TEST_FIXTURE_DIR` **gar nicht** — es gibt kein
Python-Äquivalent. Genau dieser Pfad (`vorschau`) ist aber der dominante Verbraucher.

## Existing Patterns

- **Provider-Registry**: `register_provider(name, factory)` + lazy `_load_providers()` in
  `base.py`. Erweiterbar ohne Aufrufer zu ändern.
- **ENV-gesteuerter Test-Schalter**: #263 etabliert `GZ_TEST_FIXTURE_DIR` als Konvention — in
  Prod ungesetzt = echter Provider, in Tests gesetzt = Fixture. Python sollte dieselbe Var nutzen.
- **Fixture ≠ Mock**: Der Fixture-Provider liefert echte (zuvor real abgerufene) Daten von Disk.
  Er verletzt die „KEINE Mocks"-Regel NICHT — #263 hat dieses Muster bereits als legitim etabliert.

## Dependencies

- **Upstream (was wir nutzen)**: `model.NormalizedTimeseries`/`NormalizedForecast`-Format,
  `fixtures/openmeteo/*.json` (Go-Format — Python müsste es lesen können oder eigenes Format),
  Provider-Protocol `WeatherProvider` in `base.py`.
- **Downstream (was uns nutzt)**: `_fetch_weather`, `_fetch_night_weather`,
  `_enrich_ensemble_for_trip`, alle Reports/Alarme/Compare, der `/api/preview`-Endpoint.

## Existing Specs

- `docs/specs/modules/issue_263_openmeteo_fixture_provider.md` — Go-Fixture-Provider (Vorbild).
- `docs/specs/modules/preview_service.md` — PreviewService-Spec (Epic #140).
- `docs/specs/modules/bug_288_ensemble_api_limit.md` — vorheriger API-Last-Fix (Ensemble).

## Lösungsrichtungen (für Phase 2 zu entscheiden)

1. **Python-Fixture-Provider** (analog #263) in `providers/`, in `get_provider()` umgelenkt
   wenn `GZ_TEST_FIXTURE_DIR` gesetzt → deckt ALLE Python-Pfade ab (vorschau, briefing, alarm…).
2. **conftest erzwingt Fixture-Modus**: `tests/conftest.py` setzt `GZ_TEST_FIXTURE_DIR`
   (oder einen dedizierten Test-Provider) automatisch, sodass kein Test je die echte API trifft.
3. **Schutz-Guard in `render_*_preview`**: ohne explizites Live-Flag kein echter Provider
   (defensive Doppel-Sicherung, vom Issue als „optional" genannt).
4. **Go-Seite absichern**: Playwright-E2E muss den Server mit gesetztem `GZ_TEST_FIXTURE_DIR`
   starten, sonst entstehen weiter `go_*`-Calls.

## Risks & Considerations

- **Prod-Pfad unberührt lassen**: `/api/preview` für echte Nutzer MUSS echte Daten liefern.
  Fixture greift NUR bei gesetzter Test-Var (in Prod ungesetzt). Regression hier wäre fatal.
- **Fixture-Abdeckung**: Echte Trips (KHW 403, GR221) liegen nicht bei Innsbruck/Stubai/Zillertal;
  Nearest-Lookup liefert dann irgendeine der 3 Locations. Für Render-Tests genügt das, für
  inhaltliche Plausibilität (Email-Spec-Validator) evtl. nicht — in Phase 2 prüfen.
- **Akzeptanz misst der #338-Zähler selbst**: Nach 24h Dev-Sessions dürfen KEINE
  `vorschau`/`go_*`-Calls aus Test-Kontext mehr in `data/diagnostics/openmeteo_calls*.jsonl` stehen.
- **Scope-Abgrenzung zu #339**: Parallel laufender Workflow `issue_339_verify_timing`
  (Verifikation in Staging-Phase verlagern). #346 = Tests auf Fixtures zwingen; #339 = Verifikation
  zum richtigen Zeitpunkt. Geringe Überschneidung, aber Doppelarbeit vermeiden.
- **Keine Mocks**: Fixture-Provider liest echte Disk-Daten — konform mit Projektregel.

---

## Analyse (Phase 2)

### Korrektur der ursprünglichen Annahme

Die Belege wurden ursprünglich „E2E-/Playwright-Tests" zugeschrieben. **Faktisch starten die
Playwright-E2E-Tests gar keinen Python-Prozess** — `frontend/playwright.config.ts:25` startet
nur das Frontend (`npm run preview`), `/api` wird zum separat laufenden Go-Server (Port 8090)
geproxyt. Die `vorschau`-Last (Tag wird NUR in `call_log.py:32-33` von `render_*_preview`
gesetzt) kann also nur aus **pytest-Läufen** stammen:

- `tests/tdd/test_bug_338_openmeteo_call_counter.py:197` — `render_email_preview` (echter Trip)
- `tests/tdd/test_epic_140_preview_endpoints.py` — `/api/preview`-Endpoints + `render_*_preview`

**`uv run pytest` läuft in DREI Workflow-Phasen** (`.claude/commands/4-tdd-red.md`,
`5-implement.md`, `6-validate.md`). Bei mehreren parallelen Sessions × mehrfachen Läufen
summiert sich das zu den gemessenen 1.160 Calls/Stunde.

### Technische Fakten

| Frage | Befund |
|-------|--------|
| Python-Provider-Interface | `fetch_forecast(location, start, end, enrich_ensemble) → NormalizedTimeseries` (`openmeteo.py:705`) |
| Rückgabe-Typ | `NormalizedTimeseries{meta, data:[ForecastDataPoint]}` (`models.py:133`) |
| HTTP-Client | `httpx`, `self._client.get()` in `_request()` (`openmeteo.py:456`) + UV/Ensemble (`:520`) |
| Go-Fixture-Format | `{timezone, meta, data:[{ts, t2m_c, wind10m_kmh, gust_kmh, precip_1h_mm, cloud_total_pct, wmo_code, thunder_level, visibility_m, cape_jkg, is_day, dni_wm2, uv_index, snow_depth_cm}]}` — **NICHT** identisch mit Python-`ForecastDataPoint` → Mapping nötig |
| Python liest `GZ_TEST_FIXTURE_DIR`? | **NEIN** — nur Go (`config.go:32`) |
| Python-Fixture/Stub-Provider vorhanden? | **NEIN** |
| pytest-Marker | Nur `tdd`, `email`; `addopts = "-q -m 'not email'"`. KEIN Marker schließt echte-API-Tests aus. |
| Tests, die echte API absichtlich treffen | viele (Geosphere-Parsing, Endpoint-Routing, UV, Confidence…) — Mock-Verbot gilt dort |

### Empfehlung (eine klare Richtung)

**Python-Fixture-Provider analog #263 + Default-Offline für pytest mit `live`-Opt-out.**

1. **`src/providers/fixture.py` (NEU, ~100 LoC):** `FixtureProvider` erfüllt das
   `WeatherProvider`-Protocol, liest die **vorhandenen** `fixtures/openmeteo/*.json`, mappt das
   Go-Format → `NormalizedTimeseries`, Nearest-Location-Lookup + Timestamp-Re-Stamping auf den
   aktuellen Tag (1:1-Logik aus Go #263). Echte aufgezeichnete Daten = **kein Mock**.
2. **`src/providers/base.py` (~10 LoC):** `get_provider("openmeteo")` liefert den
   FixtureProvider, wenn `os.environ.get("GZ_TEST_FIXTURE_DIR")` gesetzt ist — exakt das
   #263-Muster, jetzt Python-seitig. **Produktion bleibt unberührt** (Var dort nie gesetzt).
3. **`tests/conftest.py` (~15 LoC):** autouse-Fixture setzt `GZ_TEST_FIXTURE_DIR` für den
   gesamten pytest-Lauf → kein Test trifft je versehentlich die echte API. Tests mit
   `@pytest.mark.live` deaktivieren die Var (= echte-API-Vertragstests, Mock-Verbot).
4. **`pyproject.toml` (~3 LoC):** Marker `live` registrieren; echte-API-Vertragstests
   (`test_geosphere_parsing`, `test_openmeteo_endpoint_routing`, `test_uv_air_quality` u.ä.)
   mit `@pytest.mark.live` markieren. Diese laufen explizit / in der Staging-Acceptance (#339),
   nicht im lokalen TDD/Implement/Validate-Loop.

**Warum so:** Trifft die belegte Ursache zielsicher (Vorschau-Pfad) UND macht den Zwang
*verbindlich* für künftige Tests, ohne die „Keine-Mocks"-Philosophie zu verletzen — die
echten Vertragstests bleiben echt, nur eben opt-in. Brücke zu #339: schwere Verifikation
gehört in die Staging-Phase, nicht in jeden lokalen pytest-Lauf.

### Scope

- **Kerndateien:** 4 (`fixture.py` neu, `base.py`, `conftest.py`, `pyproject.toml`)
- **Plus:** `@pytest.mark.live`-Annotation an den echten-API-Vertragstests (1-Zeilen-Edits,
  Anzahl ergibt sich in TDD-RED, wenn der erste Offline-Lauf zeigt, welche Tests rot werden)
- **Kern-LoC:** ~130–150 (über dem 250-Default? Nein, darunter — aber Test-Markierungen
  zählen separat)

### Risiken

- **Prod-Regression (hoch, falls falsch):** Würde `GZ_TEST_FIXTURE_DIR` je in Prod gesetzt,
  bekämen echte Nutzer Fixture-Daten. Mitigation: get_provider prüft nur die ENV-Var; der
  Prod-Service (`gregor-python.service`) setzt sie nicht. In Spec als AC absichern.
- **Fixture-Abdeckung:** Nur 3 Alpen-Locations; weit entfernte Trips (GR221 Mallorca) bekommen
  via Nearest-Lookup Alpendaten. Für Render-/Struktur-Tests ausreichend; für den
  Email-Spec-Validator ggf. nicht inhaltlich plausibel → in Spec prüfen.
- **Welche Bestands-Tests brechen:** Zeigt sich empirisch beim ersten Offline-Lauf (TDD-RED).
- **Go-Seite (`go_*`):** sekundär — Playwright startet den Go-Server nicht selbst. `go_*`-Last
  entsteht nur bei E2E gegen den echten gregor-api. #263 greift dort bereits via Var;
  Ergänzung höchstens: sicherstellen, dass der E2E-Go-Start die Var setzt (Doku/Script).
