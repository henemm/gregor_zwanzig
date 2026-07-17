# Context: a1-merge-vertrag-befreien

**Issue:** #1302 — A1: Merge-Vertrag befreien (Scheibe A1 von Epic #1301)
**Typ:** Rework / Extraktion
**Erstellt:** 2026-07-17
**Basis:** `origin/main` @ `12f9c623`

## Request Summary

`_merge_fallback` aus `OpenMeteoProvider` zu einer freien Funktion herauslösen, damit der Ortsvergleich (A2/A3) dieselbe Nachfüll-Mechanik nutzen kann statt einer zweiten. **Reine Extraktion, kein Verhaltenswandel.**

PO-Vorgabe wörtlich (2026-07-17): *„Bitte immer gemeinsame Wege suchen!!!!"*

## Was existiert — WEATHER-05b Metric-Gap-Fill

Spec: `docs/specs/modules/model_metric_fallback.md`. Kernregel: *„Der User soll möglichst vollständige Daten sehen. Welche Metriken aus welchem Modell kommen, wird transparent im Footer dokumentiert."*

| Teil | Ort | Rolle in A1 |
|---|---|---|
| `_merge_fallback` | `openmeteo.py:357-378` | **wird extrahiert** |
| `_PARAM_TO_FIELD` | `openmeteo.py:312` | Open-Meteo-spezifisch → wird **Parameter** |
| `_find_fallback_model` | `openmeteo.py:333-355` | bleibt (nutzt `_load_availability_cache` + `REGIONAL_MODELS`) |
| Aufrufblock | `openmeteo.py:970-1010` | bleibt unverändert |
| Meta-Tagging | `:1002-1005` (`fallback_reason="metric_gap"`, `fallback_metrics`) | bleibt |
| Rendering | `html.py:450-451`, `plain.py:288-289` | bleibt |

## Der Befund: der Vertrag ist bereits anbieter-neutral

`_merge_fallback` joint zwei `NormalizedTimeseries` per `dp.ts`, füllt **nur** `None`-Felder, überschreibt **nie**, meldet Gefülltes zurück. Einzige Bindung an die Klasse:

```python
field_name = self._PARAM_TO_FIELD.get(param)   # :370
```

→ Extraktion = `self._PARAM_TO_FIELD` zum Parameter machen. Sonst nichts.

## RISIKO 1 (hoch): Der Regressionsschutz läuft heute NICHT

`tests/unit/test_model_metric_fallback.py` ist der Wächter dieser Mechanik — 11 Tests, u. a. Test 3 „`_merge_fallback` fills None fields without overwriting" (`:144-170`), der `provider._merge_fallback(...)` direkt aufruft.

**Die ganze Datei trägt `pytestmark = pytest.mark.live` (Zeile ~26).** `pyproject.toml` schließt live per Default aus (`addopts = "-q -m 'not email and not live and not staging'"`).

Gemessen:
- Default-Lauf: **11 deselected, 0 selected** — der Wächter läuft nie.
- Mit `-m live`: **11 passed in 0.51s** — **kein Netz**, kein API-Call. Die Markierung ist sachlich falsch.

**Folge:** Die Mechanik, auf der das gesamte Paket A aufbaut, hat einen Wächter, der im Kern-Testlauf nicht mitläuft. Bräche jemand `_merge_fallback`, bliebe der Testlauf grün. Das ist exakt die Fehlerklasse aus #1298 Punkt 1 (Metrik-Wächter mit Hand-Kopie) und #1290 (Scheduler meldet „ok" bei Totalausfall): **ein Wächter, der bei der Regression grün meldet, ist schlimmer als keiner.**

**Konsequenz für A1:** Die Markierung wird mitrepariert — nicht als Scope-Erweiterung, sondern weil der geforderte Nachweis („bestehende WEATHER-05b-Tests bleiben unverändert grün") ohne laufenden Wächter wertlos wäre. Vor der Umstellung ist zu prüfen, ob **einzelne** Tests der Datei doch Netz brauchen (Test 4 „fetch_forecast integrates fallback when cache available" ist der Kandidat); die dürfen `live` behalten, dann per Funktions-Marker statt Datei-`pytestmark`.

## RISIKO 2: Signatur-Bruch der Bestandstests

`tests/unit/test_model_metric_fallback.py:157,169` ruft `provider._merge_fallback(primary, fallback, ["cape", "visibility"])` direkt. Deshalb bleibt `_merge_fallback` als **Thin-Wrapper** erhalten (CLAUDE.md: „Code-Duplikate konsolidieren — eine Quelle, Rest Thin-Wrapper"). Wer diese Tests anpassen muss, hat die Extraktion falsch gemacht.

## Existing Patterns

- **Thin-Wrapper bei Konsolidierung** — CLAUDE.md-Vorgabe, hier direkt anwendbar.
- **Anbieter-neutrale Merge-Richtung existiert bereits als Gegenbeispiel:** `geosphere.py:435-461` (`fetch_combined`) stempelt SNOWGRID-Schnee und Open-Meteo-Wolken auf eine GeoSphere-Basis — aber als **hartcodierter Spezialfall** mit eigenem HTTP-Client, ohne Merge-Vertrag und ohne Herkunfts-Tagging. Das Epic-Dokument `docs/features/epic-1127-cross-provider-fallback.md` nennt diese Konstruktion ausdrücklich einen Fehler („Versteckte Open-Meteo-Abhängigkeit (kritischer Fund)"). A3 wird sie später durch die hier befreite Funktion ersetzen — **nicht Teil von A1.**

## Dependencies

- **Upstream:** `NormalizedTimeseries`, `ForecastDataPoint` (`app/models.py`)
- **Downstream:** ausschließlich `OpenMeteoProvider.fetch_forecast` (`:970-1010`). Kein anderer Aufrufer im Repo (`grep _merge_fallback src/` → nur `openmeteo.py`).

## Nachweis-Anforderung

1. Bestehende WEATHER-05b-Tests **unverändert** grün (kein Testtext angefasst) — und ab jetzt **im Default-Lauf**.
2. **Neuer Test:** die freie Funktion mit einem **fremden, nicht-Open-Meteo** `param_to_field`-Mapping aufrufen. Beweist die Anbieter-Neutralität — heute nicht möglich, weil die Funktion an `self._PARAM_TO_FIELD` klebt. Das ist der eigentliche Zweck der Scheibe.
3. Kein Verhaltenswandel im Trip-Pfad: `fallback_reason`/`fallback_metrics` unverändert.

## Nicht in dieser Scheibe

A2 (Compare auf `get_provider("openmeteo")`), A3 (SNOWGRID als Ergänzung), A4 (Horizont), `_find_fallback_model` verallgemeinern, Docstring-Lüge `trip_report_scheduler.py:1067` (→ #1199).
