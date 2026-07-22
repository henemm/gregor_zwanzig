---
entity_id: provider_tz_normalization
type: bugfix
created: 2026-07-22
updated: 2026-07-22
status: draft
version: "2.0"
tags: [provider, geosphere, openmeteo, timezone, fallback, issue-1345]
workflow: fix-1345-geosphere-tz-normalisierung
---

# Provider-Zeitstempel-Normalisierung (naive UTC an der Provider-Grenze erzwingen)

## Approval

- [x] Approved (PO-go 2026-07-22, v2.0)

## Purpose

Erzwingt die Hausnorm "naive UTC" für alle `ForecastDataPoint.ts`-Werte an zwei
Stellen. Die RED-Phase von Issue #1345 hat gezeigt, dass die ursprüngliche
Fehlerhypothese (v1.0 dieser Spec) den falschen Pfad adressierte: der
GeoSphere-Fallback crasht heute NICHT, weil `TripSegment.start_time`/`end_time`
per `_validate_segment` (`src/services/segment_weather.py:300-331`) zwingend
aware UTC sein müssen — GeoSphere liefert aware Zeitstempel, die Fensterung
funktioniert. Der echte Prod-Crash sitzt am primären Open-Meteo-Pfad:
`ForecastDataPoint.ts` ist dort naive; Commit `f0310cac` (#1331/#1334) stellte
den Fensterfilter in `_aggregate_for_segment` auf vollen `datetime`-Vergleich um
(`segment_weather.py:246-258`) — naive `dp.ts` gegen aware `start_floor`/
`end_floor` löst `TypeError: can't compare offset-naive and offset-aware
datetimes` aus. Der Code-Kommentar in Zeile 244-245 ("beide UTC-aware") ist
falsch und wird mit diesem Fix korrigiert. Dieser `TypeError` gilt nicht als
transienter Fehler, daher greift kein Retry und das Briefing zeigt
"Wetterdaten nicht verfügbar" — obwohl der primäre Provider technisch
erreichbar war und Daten geliefert hat.

## Source

- **File:** `src/services/segment_weather.py`
- **Identifier:** Methode `_aggregate_for_segment` (Zeile 230-277), Fenster-Berechnung Zeile 246-247

## Estimated Scope

- **LoC:** ~+90/-15
- **Files:** ~5
- **Effort:** medium (zentrale Aggregationsstelle + Guard-Klasse, beide Provider betroffen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ForecastDataPoint (`src/app/models.py`) | module | `__post_init__` (Zeile 144) normalisiert aware → naive UTC bereits seit v1.0; bleibt unverändert Bestandteil des Fixes |
| GeoSphereDirectProvider (`src/providers/geosphere.py`) | module | AT-Cross-Provider-Fallback (#1142); heute grüner Regressionspfad (AC-5), Cloud-Layer-Sommerzeit-Fix (Zeile 397-400) unverändert aus v1.0 |
| Open-Meteo-Provider (`src/providers/openmeteo.py`) | module | primärer Provider; liefert naive `ForecastDataPoint.ts` — dieser Pfad ist der eigentliche Absturzort, nicht GeoSphere |
| segment_weather (`src/services/segment_weather.py`) | module | `_aggregate_for_segment` (Zeile 246-247), Ort des tatsächlichen `TypeError`-Crashs seit Commit `f0310cac` (#1331/#1334); `_validate_segment` (Zeile 300-331) garantiert aware UTC auf `TripSegment` und bleibt unangetastet |
| trip_report_scheduler (`src/services/trip_report_scheduler.py`) | module | Retry-Logik (`_is_transient_fetch_error`, Zeile 66-75) und Fetch-Schleife (Zeile 1150-1181), betroffen vom Regressionstest 503→200 (AC-4, unverändert aus v1.0) |
| #1143 (FR-Direktprovider), #1144 (DE-Direktprovider) | future module | profitieren strukturell von der Normalisierung, sobald implementiert; AC-5 dient als Abnahme-Vorlage |

## Implementation Details

1. **Fenster-Normalisierung in `_aggregate_for_segment`**
   (`src/services/segment_weather.py:246-247`): `start_floor` und `end_floor`
   werden aus `segment.start_time`/`.end_time` berechnet, die laut
   `_validate_segment` garantiert aware UTC sind. Zusätzlich zur bestehenden
   `.replace(minute=0, second=0, microsecond=0)`-Rundung wird `.replace(tzinfo=None)`
   angehängt, sodass `start_floor`/`end_floor` naive UTC-Werte sind — konsistent
   mit `dp.ts`, das seit v1.0 durch `ForecastDataPoint.__post_init__` bereits
   naive UTC ist (egal ob der Provider aware oder naive geliefert hat). Der
   Vergleich in Zeile 252-259 (`dp.ts == start_floor`, `start_floor <= dp.ts <
   end_floor`) vergleicht damit wieder naive gegen naive Werte. Der falsche
   Kommentar in Zeile 244-245 ("beide UTC-aware") wird korrigiert auf: "`dp.ts`
   ist seit `ForecastDataPoint.__post_init__` immer naive UTC;
   `start_floor`/`end_floor` werden hier zusätzlich auf naive UTC gebracht,
   damit der Vergleich funktioniert, unabhängig davon ob der liefernde
   Provider aware oder naive Zeitstempel produziert."

2. **`ForecastDataPoint.__post_init__`** (`src/app/models.py:144`,
   **unverändert aus v1.0**): Normalisiert aware → naive UTC zentral für alle
   Provider. Bleibt Bestandteil des Fixes, weil GeoSphere weiterhin aware
   liefert und diese Normalisierung Voraussetzung für Schritt 1 ist (`dp.ts`
   muss naive sein, damit der Vergleich in Schritt 1 überhaupt greift).

3. **GeoSphere Cloud-Layer-Zeitzone** (`src/providers/geosphere.py:397-400`,
   Methode `_fetch_openmeteo_clouds`, **unverändert aus v1.0**): Der
   Open-Meteo-Request fragt explizit `timezone=Europe/Vienna` ab (Zeile 371),
   die zurückgegebenen naiven Zeiten sind lokale Wiener Zeit. Die
   Hartkodierung `timezone(timedelta(hours=1))` ist im Sommer (CEST = UTC+2)
   eine Stunde falsch. Fix bleibt: naive Zeit mit `ZoneInfo("Europe/Vienna")`
   versehen, danach `.astimezone(timezone.utc)`.

4. **Kein Verhaltenswandel bei Retry-Logik selbst (unverändert aus v1.0):**
   `_is_transient_fetch_error` und `FETCH_RETRY_ATTEMPTS` bleiben unverändert.
   Der Fix beseitigt lediglich die Ursache (`TypeError` durch
   aware/naive-Mismatch im Fensterfilter), wodurch der bestehende Retry-Pfad
   bei echten 503-Fehlern wieder greifen kann.

## Expected Behavior

- **Input:** Open-Meteo liefert naive `ForecastDataPoint.ts`; `TripSegment.start_time`/
  `.end_time` sind aware UTC (per `_validate_segment` erzwungen).
- **Output:** `_aggregate_for_segment` filtert die Zeitreihe fehlerfrei — keine
  `TypeError`, unabhängig davon, ob die Datenpunkte vom (naiven) Open-Meteo-
  oder vom (ursprünglich aware, seit v1.0 normalisierten) GeoSphere-Pfad
  stammen.
- **Side effects:** Segment-Fensterung (`segment_weather.py`) vergleicht
  durchgehend naive gegen naive Zeitstempel. Cloud-Layer-Dictionary-Keys in
  `_fetch_openmeteo_clouds` sind ganzjährig korrekt (nicht nur im Winter). Der
  GeoSphere-Fallback-Pfad (heute bereits grün) bleibt funktional unverändert.

## Acceptance Criteria

- **AC-1:** Given ein `ForecastDataPoint` wird mit einem timezone-aware
  Zeitstempel konstruiert (z.B. `datetime.now(timezone.utc)` oder aware Zeit
  in `+02:00`), When das Objekt erzeugt wird, Then ist `ts.tzinfo is None` und
  der UTC-Zeitwert bleibt erhalten (Guard-Test, beweist echte Konvertierung
  statt bloßem `tzinfo`-Strip).
  - Test: `tests/test_provider_tz_normalization.py::test_ac1_*` — unverändert
    aus v1.0.

- **AC-2 (ersetzt v1.0, echter Bug-Repro):** Given eine erfolgreiche
  Open-Meteo-Antwort mit naiven Datenpunkten (Fixture bzw. HTTP-Stub) und ein
  regulärer `TripSegment` mit aware UTC `start_time`/`end_time`, When
  `fetch_segment_weather` für dieses Segment läuft, Then liefert das Segment
  Wetterdaten und wirft KEINEN `TypeError` ("can't compare offset-naive and
  offset-aware datetimes"). Vor dem Fix: ROT (reproduziert den Prod-Crash aus
  Issue #1345). Nach dem Fix: GRÜN.
  - Test: `tests/test_provider_tz_normalization.py::test_ac2_*` — umgebaut
    gegenüber v1.0 (dort fälschlich auf den GeoSphere-Fallback-Pfad gezielt,
    der nie crashte); zielt jetzt auf den primären Open-Meteo-Pfad und
    `_aggregate_for_segment` direkt.

- **AC-3:** Given eine GeoSphere-Cloud-Layer-Antwort im Sommer (CEST, UTC+2)
  mit lokaler Wiener Zeit "14:00", When die Zeit in UTC normalisiert wird,
  Then ist das Ergebnis "12:00 UTC" (nicht "13:00 UTC", wie es die
  hartkodierte UTC+1-Annahme liefern würde).
  - Test: `tests/test_provider_tz_normalization.py::test_ac3_*` — unverändert
    aus v1.0.

- **AC-4:** Given der GeoSphere-Fetch schlägt zweimal mit einem transienten
  503-Fehler fehl und gelingt beim dritten Versuch, When
  `fetch_segment_weather` mit Retry-Schleife aufgerufen wird, Then werden die
  konfigurierten Versuche (`FETCH_RETRY_ATTEMPTS + 1`) ausgeschöpft, der
  Log-Eintrag enthält "after N attempt(s)" mit N größer 1 nur im endgültigen
  Fehlerfall, und beim 503→200-Wechsel liefert der letzte Versuch erfolgreiche
  Daten.
  - Test: `tests/test_provider_tz_normalization.py::test_ac4_*` — unverändert
    aus v1.0.

- **AC-5 (neu, Regressionsschutz Fallback):** Given ein Open-Meteo-
  Totalausfall (503-Fixture) und eine aufgezeichnete GeoSphere-Antwort
  (`tests/fixtures/geosphere_nwp_innsbruck.json`, existiert bereits), When das
  Segment über den AT-Fallback geholt wird, Then liefert es vollständige
  Wetterdaten. Dieser Pfad ist HEUTE bereits grün (GeoSphere crasht nicht) —
  der Test stellt sicher, dass die Normalisierung aus Schritt 1 diesen
  funktionierenden Pfad nicht bricht. Bleibt Abnahme-Vorlage für #1143/#1144.
  - Test: `tests/test_provider_tz_normalization.py::test_ac5_*` — neu
    hinzugefügt gegenüber v1.0.

## Known Limitations

- Segment 4 des ursprünglichen Vorfalls ("Cannot compute metrics from empty
  timeseries" — GeoSphere lieferte eine leere Reihe) ist ein separates
  Problem und NICHT Teil dieses Fixes (siehe Analyse in
  `docs/context/fix-1345-geosphere-tz-normalisierung.md`).
- Die Normalisierung in `ForecastDataPoint.__post_init__` greift nur für
  Objekte, die über den regulären Konstruktor erzeugt werden; direkte
  Feldmutation nach Konstruktion (`dp.ts = aware_dt`) wird nicht abgefangen
  (kein bekannter Aufrufer tut dies aktuell).
- Die Fenster-Normalisierung in `_aggregate_for_segment` setzt voraus, dass
  `segment.start_time`/`.end_time` bereits UTC sind (durch `_validate_segment`
  erzwungen); ein `.replace(tzinfo=None)` ohne vorherige `_validate_segment`-
  Prüfung wäre für andere Zeitzonen falsch — dieser Fix ändert
  `_validate_segment` selbst nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Architekturmuster, sondern Korrektur einer
  fehlerhaften Kommentierung und Ergänzung einer fehlenden Normalisierung an
  einer bestehenden Vergleichsstelle (`_aggregate_for_segment`), im Rahmen der
  bereits etablierten Hausnorm "naive UTC als Provider-Grenze". Kein
  ADR-würdiger Richtungsentscheid.

## Changelog

- 2026-07-22: Initial spec created (Issue #1345)
- 2026-07-22: v2.0 — RED-Phase-Korrektur: echter Crash-Ort ist der primäre
  Open-Meteo-Pfad in `_aggregate_for_segment` (Commit `f0310cac`, #1331/#1334),
  nicht der GeoSphere-Fallback (der bereits heute grün ist). AC-2 ersetzt
  (echter Bug-Repro statt Fallback-E2E), AC-5 neu (Regressionsschutz für den
  bereits grünen Fallback-Pfad), falscher Code-Kommentar Zeile 244-245 als
  Teil des Fixes vermerkt. Approval zurückgesetzt — Neu-Freigabe erforderlich.
