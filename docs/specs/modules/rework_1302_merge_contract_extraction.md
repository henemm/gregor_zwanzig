---
entity_id: rework_1302_merge_contract_extraction
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [providers, merge, weather-05b, issue-1302, epic-1301]
---

# Rework #1302 (A1) — Merge-Vertrag befreien

## Approval

- [ ] Approved

**ADR-Nr.:** — (keine neue ADR; reine Extraktion ohne Verhaltenswandel. Der WEATHER-05b-Vertrag aus `docs/specs/modules/model_metric_fallback.md` bleibt inhaltlich unverändert, er wird nur aufrufbar gemacht.)

## Purpose

`_merge_fallback` aus `OpenMeteoProvider` zu einer freien Funktion herauslösen, damit der Ortsvergleich (Scheiben A2/A3) dieselbe Nachfüll-Mechanik nutzen kann, statt eine zweite zu bekommen. **Reine Extraktion, kein Verhaltenswandel.**

PO-Vorgabe wörtlich (2026-07-17): *„Bitte immer gemeinsame Wege suchen!!!!"* — Der Merge-Vertrag existiert bereits, ist bereits anbieter-neutral geschrieben und läuft produktiv im Trip-Pfad. Er ist nur an der falschen Stelle eingesperrt.

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `OpenMeteoProvider._merge_fallback` (`:357-378`), Klassen-Konstante `_PARAM_TO_FIELD` (`:312`)

> **Schicht-Hinweis:** Ausschließlich **Python-Core / Provider** (`src/providers/`). Kein Frontend, kein Go, kein Renderer.

## Estimated Scope

- **LoC:** ~+45 (neue Datei `src/providers/merge.py`) / ~-20 (`openmeteo.py` wird Wrapper) → netto ~+25, weit unter 250
- **Files:** 1 NEU, 1 MODIFY, 1 Testdatei MODIFY (Marker), 1 Testdatei NEU
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NormalizedTimeseries`, `ForecastDataPoint` (`app/models.py`) | Datenmodell | Ein-/Ausgabe der Merge-Funktion, unverändert |
| `OpenMeteoProvider.fetch_forecast` (`:970-1010`) | Einziger Aufrufer | ruft künftig den Wrapper, sonst unverändert |
| `tests/unit/test_model_metric_fallback.py:157,169` | Regressionsschutz | ruft `provider._merge_fallback(...)` direkt → Wrapper hält sie grün |

## Implementation Details

### 1. NEU: `src/providers/merge.py`

Eine freie Funktion, Logik **wörtlich** aus `_merge_fallback` (`openmeteo.py:357-378`) übernommen. Einzige Änderung: `self._PARAM_TO_FIELD` wird zum Parameter.

```python
def merge_missing_fields(
    primary: "NormalizedTimeseries",
    fallback: "NormalizedTimeseries",
    missing_params: list[str],
    param_to_field: dict[str, str],
) -> list[str]:
    """Fuellt None-Felder in primary aus fallback -- nur fuer missing_params.

    Ueberschreibt nie einen vorhandenen Wert. Join ueber dp.ts.
    Gibt die tatsaechlich gefuellten Parameter sortiert zurueck.
    """
```

Vertrag (unverändert gegenüber heute): Join per `dp.ts`; nur `None`-Felder werden gefüllt; vorhandene Werte werden **nie** überschrieben; Rückgabe = sortierte Liste der gefüllten Parameter.

### 2. MODIFY: `openmeteo.py` — `_merge_fallback` wird Thin-Wrapper

```python
def _merge_fallback(self, primary, fallback, missing_params) -> List[str]:
    """Thin-Wrapper. Vertrag lebt in providers/merge.py (Issue #1302, Epic #1301)."""
    return merge_missing_fields(primary, fallback, missing_params, self._PARAM_TO_FIELD)
```

Signatur **unverändert**. CLAUDE.md: „Code-Duplikate konsolidieren — eine Quelle, Rest Thin-Wrapper".

### 3. NICHT anfassen

`_find_fallback_model` (`:333-355`), der Aufrufblock (`:970-1010`), `REGIONAL_MODELS`, die Meta-Setzung (`fallback_reason`/`fallback_metrics`, `:1002-1005`), `_PARAM_TO_FIELD` selbst (bleibt Klassen-Konstante — sie **ist** Open-Meteo-spezifisch), das Fußtext-Rendering (`html.py:450-451`, `plain.py:288-289`).

### 4. Den Wächter zum Laufen bringen

`tests/unit/test_model_metric_fallback.py` trägt `pytestmark = pytest.mark.live` für die **ganze Datei**. `pyproject.toml` schließt `live` per Default aus.

Gemessen am 2026-07-17: Default-Lauf **11 deselected, 0 selected**; mit `-m live` **11 passed in 0.51s — kein Netz**. Die Markierung ist sachlich falsch.

**Vorgehen:** Datei-`pytestmark` **ersatzlos entfernen** — alle 11 Tests laufen ab jetzt im Kern.

**Korrektur der Erstfassung dieser Spec (2026-07-17, RED-Phase):** Die Erstfassung nannte Test 4 „fetch_forecast integrates fallback when cache available" als Kandidaten, der `live` behalten müsse. **Dieser Test existiert nicht.** Er steht nur im Docstring am Dateikopf (`:8`) als seinerzeit geplanter Test; tatsächlich enthält die Datei 11 `def test_*` in vier Klassen (`TestForecastMetaFallbackFields`, `TestFindFallbackModel`, `TestMergeFallback`, `TestFooterFallbackInfo`), und **keiner** ruft `fetch_forecast` auf. Die Erstfassung hatte dem Docstring geglaubt statt die Tests zu zählen — genau der Fehler, den dieses Paket bekämpft (vgl. den irreführenden Docstring `trip_report_scheduler.py:1067`).

Einzeln geprüft, alle 11 ohne Netz: `ForecastMeta`-Attribut-Checks (1-3); `_find_fallback_model` liest eine lokale JSON-Datei via `monkeypatch` auf `tmp_path` und iteriert die statische `REGIONAL_MODELS`-Liste (4-5); `_merge_fallback` ist reines In-Memory (6-7); `TripReportFormatter().format_email(...)` ist reines Rendering ohne HTTP (8-11). `OpenMeteoProvider.__init__` legt nur einen `httpx.Client` an, ohne Verbindungsaufbau.

Begründung, warum das zu A1 gehört und keine Scope-Erweiterung ist: Der geforderte Nachweis lautet „bestehende WEATHER-05b-Tests bleiben unverändert grün". Ein Wächter, der im Kern-Testlauf gar nicht mitläuft, kann das nicht leisten — der Nachweis wäre wertlos. Gleiche Fehlerklasse wie #1298 Punkt 1 und #1290.

## Acceptance Criteria

- **AC-1:** Given eine Zeitreihe mit Lücken und eine Ergänzungs-Zeitreihe / When `merge_missing_fields` mit einem **fremden, nicht-Open-Meteo** `param_to_field`-Mapping aufgerufen wird / Then füllt sie die Lücken korrekt und meldet die gefüllten Parameter zurück — der Beweis, dass der Vertrag anbieter-neutral ist. Heute unmöglich, weil die Funktion an `self._PARAM_TO_FIELD` klebt. Das ist der Zweck dieser Scheibe.

- **AC-2:** Given eine Zeitreihe, in der ein Feld bereits einen Wert trägt / When `merge_missing_fields` einen abweichenden Wert für dasselbe Feld anbietet / Then bleibt der **vorhandene Wert unverändert** — die Funktion füllt nur Lücken und überschreibt nie. Kernzusage des WEATHER-05b-Vertrags.

- **AC-3:** Given die bestehenden WEATHER-05b-Tests (`tests/unit/test_model_metric_fallback.py`) / When die Extraktion abgeschlossen ist / Then laufen sie **unverändert** grün — **kein Testtext angepasst**. `provider._merge_fallback(...)` bleibt mit identischer Signatur aufrufbar. Wer diese Tests anfassen muss, hat die Extraktion falsch gemacht.

- **AC-4:** Given ein normaler Testlauf ohne Sondermarker (`uv run pytest tests/unit/test_model_metric_fallback.py`) / When er ausgeführt wird / Then **laufen die Tests tatsächlich** (nicht „deselected") und sind grün. Heute meldet derselbe Befehl „11 deselected, 0 selected" — der Wächter der Mechanik, auf der Paket A aufbaut, läuft nie mit. Tests, die echt Netz brauchen, dürfen `live` behalten, aber als Funktions-Marker.

- **AC-5:** Given der Trip-Briefing-Pfad / When ein Briefing mit Metrik-Lücken gerendert wird / Then sind `fallback_reason` (`"metric_gap"`) und `fallback_metrics` **unverändert** gesetzt und der Fußtext nennt weiterhin die Herkunft der nachgefüllten Werte — kein Verhaltenswandel durch die Extraktion.

## Known Limitations

- **`_find_fallback_model` bleibt Open-Meteo-gebunden.** Es sucht ausschließlich über `REGIONAL_MODELS` (alles `api.open-meteo.com`) und braucht `_load_availability_cache`. Für A3 (GeoSphere als Schnee-Ergänzer) wird **kein** Kandidatensuche gebraucht — die Quelle steht dort fest. Eine Verallgemeinerung ist nicht Teil dieses Pakets.
- **`_PARAM_TO_FIELD` bleibt in `OpenMeteoProvider`.** Es bildet Open-Meteo-Parameternamen ab und ist dort richtig aufgehoben. A3 wird ein eigenes Mapping für GeoSphere-Felder mitbringen — genau dafür ist der Parameter da.
- **Die versteckte Open-Meteo-Abhängigkeit in `geosphere.py:336-404`** (`_fetch_openmeteo_clouds`, eigener HTTP-Client, kein Merge-Vertrag, kein Tagging) bleibt in A1 unangetastet. Sie ist in `docs/features/epic-1127-cross-provider-fallback.md` als „kritischer Fund" dokumentiert und wird in **A3** durch die hier befreite Funktion ersetzt.

## Verification

- **Kern-Tests, deterministisch, ohne Netz.** Keine Mocks, die die eigene Annahme spiegeln; keine Dateiinhalt-Checks als Verhaltensnachweis.
- Bestandssuite `tests/unit/test_model_metric_fallback.py` **unverändert** grün — und ab jetzt im Default-Lauf sichtbar (AC-4).
- Neue Tests für AC-1/AC-2 gegen die freie Funktion, mit echten `NormalizedTimeseries`-Objekten.
- Trip-Regressionsschutz (AC-5): Renderpfad-Test, dass `fallback_metrics` im Fußtext weiterhin erscheint.
- **Kein** Renderer-Commit-Gate (#811) — es sind keine Mail-Inhalts-Dateien betroffen. **Kein** Mail-Validator nötig: Diese Scheibe ändert keine Mail-Inhalte.
