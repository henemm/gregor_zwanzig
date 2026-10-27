# Context: fix-2302-s3-geosphere-zeitbudget

## Request Summary
Scheibe C von #2302: `src/providers/geosphere.py` bekommt als letzte Wetterquelle ein
Zeitbudget, das **innerhalb** eines Abrufs greift (Versuche + Retry-Wartepausen), mit dem in
Scheibe A gebauten geteilten Baustein `src/providers/http.py`. Grundlage: Entscheid D2 in
`docs/context/fix-2302-provider-zeitbudget.md:692-703`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/providers/geosphere.py` | Einziger Produktiv-Änderungsort. `_request` (:286-327) hat `stop_after_attempt(5)`, kein `before`, kein Frist-Stop, `self._client.get(url)` **ohne** `timeout=` (Client-Default 30 s, :223). Kein `time`-Import, kein Import aus `providers.http`; `ProviderRequestError` ist schon importiert (:40) |
| `src/providers/http.py` | Geteilter Baustein (Scheibe A), **unverändert**: `make_deadline_before_hook(deadline_attr)` (:32, liest/setzt nur kwarg `deadline_at`), `stop_at_deadline` (:59), `capped_timeout_or_raise(*, provider_name, base_timeout, deadline_at, budget_label, budget_seconds)` (:73, wirft `ProviderRequestError` ohne status_code) |
| `src/providers/dwd.py` | Referenzumsetzung Scheibe B: `FETCH_DEADLINE_SECONDS = 180.0` (:74), Accessor `_fetch_deadline_seconds` (:321), `@retry(... stop=stop_after_attempt \| stop_at_deadline, before=make_deadline_before_hook(...))` (:334-365), `fetch_forecast` bildet die Frist einmal (:585) und reicht sie an vier `_fetch_series` durch |
| `src/providers/regional_stubs.py:63-101` | `GeoSphereDirectProvider` (`at_direct`) ruft `fetch_combined(include_cloud_layers=False)`; übersetzt nur httpx-Fehler, `ProviderRequestError` geht durch (mit `provider="geosphere"`) |
| `src/providers/openmeteo.py:1093-1117` | Totalausfall-Weiche → `at_direct` für AT-Koordinaten (`region_routing.py:34`); fängt `ProviderRequestError`, wirft danach den ursprünglichen Open-Meteo-Fehler. **Einziger Weg von GeoSphere in den Alarm-Pfad** |
| `src/providers/openmeteo.py:482` | `_enrich_snow` ruft `GeoSphereProvider().fetch_snowgrid(lat, lon)` ohne Frist, eingeschlossen in `except Exception: pass` → bekommt künftig per Hook ein eigenes 180-s-Fenster |
| `src/services/radar_service.py:736-770` | Nutzt nur `fetch_nowcast` (geht durch `_request`), `except Exception` → nächste Quelle |
| `tests/tdd/test_provider_request_deadline.py` | Wächter aus A/B (1552 Zeilen): `_HangingServer` (:158), `_antwortender_server` (:247), `_zaehlender_server` (:686) — beide Server liefern **Open-Meteo-JSON**, für GeoSphere-NWP ist ein GeoJSON-Rumpf mit `features` nötig (sonst `ValueError` :668). `_dwd_ruesten` (:971) als Rüst-Vorbild inkl. `wait=` |
| `tests/tdd/test_snowgrid_enrichment_health.py:262` | Bewacht #1992 AC-3: SNOWGRID-Fehler lässt `fetch_combined` nie scheitern |
| `tests/tdd/test_issue_1142_geosphere_direct_fallback.py:218` | Patcht `GeoSphereProvider._request.retry.wait` (echter 503-Server, 5 Versuche) — wird vom neuen `stop` berührt |

## Abrufwege in `geosphere.py`
| Methode | durch `_request`? | Fehlerbehandlung heute |
|---|---|---|
| `fetch_nwp_forecast` (:348) | ja | keine — Fehler gehen durch |
| `fetch_snowgrid` (:373) | ja | fängt httpx-Fehler → `(None, None)`; `ProviderRequestError` geht durch |
| `fetch_nowcast` (:499) | ja | `HTTPStatusError` → `ProviderRequestError` |
| `fetch_thunder_signals_named` (:429) | nein | fest 3 s, fail-soft — **unberührt** (D2) |
| `_fetch_openmeteo_clouds` (:546) | nein | fest 10 s, kein Retry, `except Exception` → `{}` |

`fetch_combined` (:588-660): NWP (:618) ungeschützt → SNOWGRID (:622-631) in
`try/except Exception` → `log_enrichment_call("combined:{e}")`, `None` → Wolken (:641).

## Existing Patterns
- **Frist einmal bilden, an mehrere Abrufe durchreichen** — `dwd.py:585` / `openmeteo.py:~1010`
- **Hook bildet Default-Frist nur, wenn kein `deadline_at` übergeben** — daher für Einzelaufrufer (`_enrich_snow`, `fetch_nowcast`, `fetch_nwp_forecast` direkt) automatisch 180 s
- **Wanduhr-Wächter mit großzügigem Abstand** gegen `_HangingServer`, Frist per monkeypatch auf ~0,45 s, `TIMEOUT` bewusst **über** der Frist (sonst misst der Test das Durchreichen von `timeout=` nicht)
- **Pflicht-Wächterklassen aus A/B** (beide Findings der Scheibe B waren „A hat ihn, B nicht"):
  Wartepausen-Deckel (`wait_fixed(1.0)`, Obergrenze 0,9 s) und Serienfrist über mehrere Abrufe

## Dependencies
- Upstream: `providers/http.py`, tenacity, httpx, `providers/base.ProviderRequestError`, `call_log.log_enrichment_call`
- Downstream: `GeoSphereDirectProvider` (at_direct → Alarm-Pfad über Open-Meteo-Weiche), `openmeteo._enrich_snow`, `radar_service` (INCA-Nowcast), `validation/geosphere_validator.py`, CLI-Default-Provider `geosphere`

## Existing Specs
- `docs/specs/modules/fix_2302_s1_provider_zeitbudget_baustein.md` — Baustein, Scheibe A
- `docs/specs/modules/fix_2302_s2_dwd_zeitbudget.md` — Parallelstruktur (AC-1…AC-10)
- `docs/specs/modules/feat_1992_geosphere_health_amendment.md:233-238` — **AC-3: SNOWGRID-Fehler lässt `fetch_combined` nie scheitern**
- `docs/specs/modules/api_retry.md` — Retry-Grundregeln (vom Modul-Docstring referenziert)

## Risks & Considerations
1. **Konflikt D2 ↔ #1992 AC-3.** D2 fordert „bei Überschreiten `ProviderRequestError`, kein
   stilles Leerergebnis". #1992 AC-3 fordert: SNOWGRID-Fehler lassen `fetch_combined` nie
   scheitern — ein Frist-Fehler **in** SNOWGRID würde heute verschluckt. Muss in der Analyse
   schriftlich aufgelöst werden, nicht still. Arbeitshypothese für `/20`: Beide gelten
   zugleich — `_request` wirft bei erschöpfter Frist (Basisvorhersage nie erfunden/leer), der
   SNOWGRID-Zweig bleibt fail-soft mit `log_enrichment_call` (sichtbarer Anreicherungsausfall,
   kein stilles Leerergebnis). Zu prüfen: Wortlaut ADR-0018 + Sichtbarkeit von
   `log_enrichment_call`. Folge: Die Serien-Zusicherung für `fetch_combined` ist eine
   **Wanduhr-Obergrenze**, keine Ausnahme.
2. **D2 ist in sich widersprüchlich beim Wolken-Abruf:** „an alle drei durchreichen" vs.
   „`:546` (fest 10 s) bleibt unberührt". Der Wolken-Abruf ist einzelner Versuch ohne Retry,
   also ohnehin auf 10 s gedeckelt; er ist fail-soft (`{}`).
3. **Grenze, die Scheibe C nicht schließt:** Die at_direct-Weiche erreicht GeoSphere erst nach
   der Open-Meteo-Kandidatenschleife und reicht deren Restfrist nicht durch — GeoSphere bekommt
   ein frisches 180-s-Fenster. Gegen `ALERT_RUN_DEADLINE_SECONDS = 90` schützt ein 180-s-Budget
   ohnehin nicht (gilt genauso für dwd/meteofrance). Als ausdrückliche Grenze in die Spec.
4. **Bestandstest #1142** patcht `retry.wait`; ein neuer `stop`/`before` darf den 5-Versuche-Pfad
   gegen den 503-Server nicht verändern (Frist 180 s ≫ Testdauer) — in der Regression mitlaufen lassen.
5. **Testserver liefern Open-Meteo-JSON** — GeoSphere-Wächter brauchen einen GeoJSON-Rumpf
   (bestehenden Helfer um einen Rumpf-Parameter erweitern, keinen neuen Server bauen). Im
   Serien-Wächter muss der **NWP-Abruf gelingen**, erst SNOWGRID verzögert — sonst misst er
   wieder nur die Retry-Kette. Wartepausen-Wächter mit **explizitem** `wait_fixed(1.0)`
   (F-ADV1-Falle; #1142 patcht `retry.wait` bereits).
6. Scheibe-B-Fallen: Mutierender und messender Agent nie gleichzeitig; Positiv- und
   Mutationsnachweis in getrennte Artefaktdateien; `e2e_scope` zuletzt vor `/70` auf `backend`;
   Commit mit Pathspec; vor `gh pr create` erst `gh pr list`.

## Analysis

### Type
Feature (Härtung, neues Verhalten: GeoSphere-Abrufe können erstmals an einer Frist abbrechen)

### Konflikt D2 ↔ #1992 AC-3 — aufgelöst (Tech-Lead-Entscheid)
Beide gelten zugleich, kein neues ADR nötig:
- **ADR-0018** (`docs/adr/0018-provider-fallback-ohne-kaschieren.md:11,22`) verbietet Ausweichen
  *ohne Sichtbarkeit*, nicht fail-soft an sich. D2s „kein stilles Leerergebnis" meint die
  **zurückgegebene Vorhersage**.
- **NWP-Frist erschöpft** → `ProviderRequestError`/httpx-Fehler geht durch `fetch_combined`,
  `fetch_forecast` und `GeoSphereDirectProvider` (`regional_stubs.py:80-101`) — nie ein leeres
  oder erfundenes Ergebnis.
- **SNOWGRID-Frist erschöpft** → bleibt fail-soft (#1992 AC-3, Wächter
  `test_snowgrid_enrichment_health.py:262` unberührt), aber **sichtbar**:
  `log_enrichment_call(PATH_SNOWGRID, OUTCOME_UNAVAILABLE)` → `diagnostics/enrichment_calls.jsonl`
  → `/api/scheduler/status` `enrichment_health` (`src/providers/enrichment_health.py:1-10`).
  `fetch_combined` loggt das heute schon (`geosphere.py:622-631`).
- **Zusätzlich:** `fetch_snowgrid` fängt künftig auch `ProviderRequestError` und loggt
  `unavailable`. Grund: `openmeteo._enrich_snow` (`:482`) ruft `fetch_snowgrid` direkt mit
  `except Exception: pass` — ein Frist-Abbruch bliebe dort **weiterhin komplett stumm wie jeder
  andere Nicht-httpx-Fehler heute**.
- **Folge für die Tests:** Die Serien-Zusicherung für `fetch_combined` ist eine
  **Wanduhr-Obergrenze** plus Journal-Eintrag, keine Ausnahme.

### D2 in sich widersprüchlich beim Wolken-Abruf — aufgelöst
`_fetch_openmeteo_clouds` (`:546`) bleibt **unberührt**: ein Versuch, kein Retry, fest 10 s,
fail-soft; `at_direct` (einziger Alarm-Pfad-Zugang) ruft `include_cloud_layers=False`
(`regional_stubs.py:88-95`). Eine gemeinsame Frist dort brächte keinen Schutz, nur Code und
Test-LoC. Obergrenze `fetch_combined` damit ≈ Frist + 10 s — als Grenze in die Spec.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/geosphere.py` | MODIFY | `time`-Import + Bausteine aus `providers.http`; `FETCH_DEADLINE_SECONDS = 180.0`; Accessor `_fetch_deadline_seconds`; `_request`: `stop=… \| stop_at_deadline`, `before=make_deadline_before_hook(...)`, kwarg `deadline_at`, Kopf `capped_timeout_or_raise`, `get(url, timeout=…)`; `deadline_at` durch `fetch_nwp_forecast`/`fetch_snowgrid`; `fetch_combined` bildet Frist einmal; `fetch_snowgrid` fängt `ProviderRequestError` |
| `tests/tdd/test_provider_request_deadline.py` | MODIFY | GeoSphere-Wächter (Parallelstruktur zu A/B) + Zwei-Pfad-Testserver (NWP antwortet GeoJSON, SNOWGRID hängt) |
| `src/providers/http.py` | — | unverändert |

### Scope Assessment
- Files: 2 (1 Produktiv, 1 Test)
- Estimated LoC: Produktiv +55–75; Tests **Ziel ≤ ~300** (Strategie-Schätzung 300–420 im
  docstring-schweren Stil — bewusst knapp halten, Wächter nur für tragende Zusicherungen)
- Risk Level: MEDIUM (Alarm-Pfad über at_direct; Muster zweimal live erprobt)

### Technical Approach
1:1 das Scheibe-B-Muster (`dwd.py:321-347`, `:585`). Tragende Wächter:
- **(a)** `_request` gegen `_HangingServer`, Frist 0,45 s, `TIMEOUT` 5,0 (über der Frist!) → Abbruch in `(ProviderRequestError, httpx.HTTPError)`, < 0,9 s
- **(b)** Wartepausen-Deckel: `TIMEOUT` 0,5, **explizit** `wait_fixed(1.0)`, 0,2 ≤ t < 0,9 (F-ADV1-Klasse)
- **(c)** Serienfrist `fetch_combined`: ein `ThreadingHTTPServer`, Handler unterscheidet über
  `self.path` (`ENDPOINTS["nwp"]` vs. `ENDPOINTS["snowgrid"]`, `geosphere.py:69-70`); NWP
  antwortet nach 0,6 s mit minimalem GeoJSON (`timestamps` + `features[0].properties.parameters.t2m.data`),
  SNOWGRID hängt; Frist 1,0 s, `TIMEOUT` 10,0, **Wartepause nicht neutralisieren**. Korrekt
  ≈ 1,0–1,1 s; Mutation „`deadline_at` nicht an SNOWGRID" ≈ 1,6 s; Mutation „`stop_at_deadline`
  entfernen" ≈ 3 s (wait_exponential min 2 s). Schwelle < 1,35 s. Plus: Ergebnis hat NWP-Daten,
  Journal hat `snowgrid`/`unavailable`. Doppelabdeckung im Docstring benennen.
- **(d)** NWP-Frist erschöpft → `fetch_forecast` wirft, kein leeres Ergebnis
- **(e)** Normalfall gegen antwortenden GeoJSON-Server → Daten, < 2,0 s (Gegenprobe gegen „bricht alles sofort ab")
- **(f)** Hook-Default: ohne `deadline_at` gilt `FETCH_DEADLINE_SECONDS` zur **Aufrufzeit** (Laufzeit-Patch)
- **(g)** `fetch_snowgrid` direkt mit erschöpfter Frist → `(None, None)` + Journal `unavailable` (Pfad `_enrich_snow`)
- **Regression:** `test_snowgrid_enrichment_health.py`, `test_issue_1142_geosphere_direct_fallback.py`
  (patcht `retry.wait`, 503-Server — mit 180 s faktisch unberührt), `tests/test_geosphere.py`
  (Mock ohne `call_args`-Check), `test_wegpunkt_hoehe_im_request.py`, übrige ungemarkerte
  GeoSphere-Testdateien. Bestandstests geprüft: kein Fake-Client lehnt `timeout=` ab, niemand
  ruft `_request` positionsgebunden mit `start`/`end` außerhalb der Wächterdatei.

### Grenzen (ausdrücklich in die Spec)
- at_direct bekommt nach der Open-Meteo-Kandidatenschleife ein **frisches** 180-s-Fenster; gegen
  `ALERT_RUN_DEADLINE_SECONDS = 90` schützt das nicht (gilt genauso für dwd/meteofrance)
- Wolken-Abruf außerhalb der gemeinsamen Frist (≤ 10 s, siehe oben)
- Tröpfel-Fall (D6) nicht abgedeckt
- `GeoSphereDirectProvider` meldet Frist-Fehler mit `provider="geosphere"` statt `at_direct` (vorbestehend)

### Dependencies
Reihenfolge: `_request`-Mechanik → Durchreichen → `fetch_combined`-Frist → `fetch_snowgrid`-except → Tests (a)(b) → (c) → (d)–(g) → Regression.

### Open Questions
- keine (Konflikte oben per Tech-Lead-Entscheid aufgelöst; nur ACs brauchen PO-Freigabe)
