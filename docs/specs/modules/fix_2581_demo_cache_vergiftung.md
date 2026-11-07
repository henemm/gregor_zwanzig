---
entity_id: fix_2581_demo_cache_vergiftung
type: module
created: 2026-11-06
updated: 2026-11-06
status: draft
version: "1.0"
tags: [cache, demo, vorschau, fixture, single-flight, prognose-archiv, mandantentrennung]
---

# Demo-Vorschau vergiftet den Wetter-Cache und das Prognose-Archiv (Issue #2581)

## Approval

- [ ] Approved

## Purpose

Die Demo-Vorschau nutzt den `FixtureProvider` (statische Beispielwerte aus lokalen Dateien). Dieser meldet sich bewusst als `"openmeteo"`, damit Aufrufer ihn nicht von der echten Wetterquelle unterscheiden müssen. Genau diese Tarnung führt zu zwei Vergiftungswegen, weil der Fixture-Provider und der echte Open-Meteo-Provider für die geteilten Mechanismen dieselbe Kennung tragen:

1. **Cache und Single-Flight.** `SegmentWeatherService._resolve_model_id` nimmt ohne `select_model()` den `provider.name`, beim Fixture-Provider also `"openmeteo"`. Der echte Open-Meteo-Provider liefert im Rückfall (kein Regionalmodell passt) ebenfalls `"openmeteo"`. `_bucket_key` und `flight_key` enthalten keinen Provider, nur Koordinate, Höhe, `model_id` und die Anreicherungs-Schalter. Ergebnis: Ein Demo-Abruf kann den Cache-Eintrag eines echten Abrufs erben (Beispielwerte landen in einem echten Briefing oder Alarm) und umgekehrt (die Demo zeigt echte Werte), und zwei gleichzeitige Abrufe (Demo und live) teilen sich einen Single-Flight-Abruf.
2. **Prognose-Archiv (#2030).** `segment_weather.py` ruft nach jedem Abruf `capture_segment_forecast(provider=self._provider.name, ...)`. Im Demo-Modus werden Fixture-Werte als `provider="openmeteo"` ins Prognose-Archiv geschrieben (der Schalter `GZ_FORECAST_CAPTURE` ist standardmäßig an). Ein reiner Cache-Schlüssel-Fix schließt diesen zweiten Weg nicht.

Beide Wege haben dieselbe Wurzel: der Fixture-Provider tarnt sich als `"openmeteo"`. Dieses Modul führt ein Provider-Merkmal `cache_namespace` ein, trennt damit den Cache und den Single-Flight sauber und lässt das Prognose-Archiv für solche Provider aus. `provider.name` bleibt unverändert `"openmeteo"`.

Erfolgszusage: Ein Demo-Abruf kann nie einen echten Abruf (Cache, Single-Flight, Prognose-Archiv) beeinflussen und umgekehrt, in beiden Reihenfolgen, ohne dass dazwischen der Cache geleert werden muss.

## Source

- **File:** `src/providers/fixture.py` (neues Klassenmerkmal `cache_namespace = "fixture"` an `FixtureProvider`)
- **File:** `src/services/segment_weather.py` (`SegmentWeatherService._resolve_model_id`; Guard um den `capture_segment_forecast`-Aufruf)
- **File:** `src/services/weather_cache.py` (nur Docstring von `_bucket_key`: Begründung des Namensraums im `model_id`-Teil, Muster #1329/#1991; keine Logikänderung)
- **File:** `docs/specs/modules/weather_cache.md` (Verweis auf dieses Modul ergänzen, siehe „Folgepflege")

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/`). Go-API und Frontend bleiben unverändert. `SegmentWeatherService` wird von `trip_alert`, `trip_report_scheduler`, `stage_weather`, `comparison_engine` und `compare_location_weather_source` genutzt; alle profitieren, ohne selbst geändert zu werden. Die Schlüsseländerung ist rein additiv: Nach dem Neustart von `gregor-python` ist der In-Memory-Cache ohnehin leer.

> **Querschnitts-Prüfpunkte:**
> - **Mandantentrennung:** Wetter ist nutzerneutral, der Cache-Schlüssel enthält bewusst keine `user_id` und bekommt auch jetzt keine. Die Trennung verläuft entlang der Datenquelle (Fixture gegen live), nicht entlang des Nutzers. Getestet mit zwei verschiedenen Nutzern (AC-3).
> - **Trip/Ortsvergleich-Teilung:** Die Änderung sitzt im geteilten `SegmentWeatherService`, den beide Pfade nutzen. Es entsteht keine neue Komponente und kein Pendant (Anti-Pattern #1170).
> - **Kanäle:** Die Änderung betrifft nur die Beschaffung der Rohdaten vor dem Rendern. Der Inhalt der vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) bleibt unverändert (AC-5).

## Scope

Im Scope: eigener Cache-Namensraum `fixture:` fuer den FixtureProvider (Cache und Single-Flight) sowie das Aussetzen des Prognose-Archiv-Mitschnitts fuer Provider mit Namensraum. Nicht im Scope: Bereinigung alter Archivzeilen, `radar_cache`, `thunder_window_cache` (siehe "Nicht im Scope").

## Definition of Done

- AC-1 bis AC-6 sind durch Kern-Tests (offline, ohne Mocks) abgedeckt und gruen.
- Ein Demo-Abruf liefert in beiden Reihenfolgen Fixture-Werte, ein Live-Abruf eigene Werte, ohne den Cache zwischendurch zu leeren.
- Demo-Abrufe schreiben nichts ins Prognose-Archiv.
- Mutations-Gegenprobe zeigt, dass jede Zusicherung bewacht ist.

## Estimated Scope

- **LoC:** ca. +25/-3 Produktivcode (Obergrenze ca. 60), ca. +150 Test
- **Files:** 3 Produktiv (`fixture.py`, `segment_weather.py`, `weather_cache.py` nur Docstring) + 1 Spec-Verweis + 1 Test
- **Effort:** low (Risk: LOW, additive Schlüsseländerung, nur der Demo-Pfad ändert sein Verhalten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `FixtureProvider` | upstream | Trägt das neue Merkmal `cache_namespace = "fixture"` |
| `OpenMeteoProvider.select_model` | upstream | Liefert das Regionalmodell; Rückfall ebenfalls `"openmeteo"` (Ursache der Kollision) |
| `WeatherCacheService._bucket_key` / `flight_key` | upstream | Nehmen die `model_id` unverändert in den Schlüssel; keine Logikänderung nötig |
| `forecast_capture.capture_segment_forecast` (#2030) | upstream | Wird für Provider mit Namensraum nicht aufgerufen |
| `preview_service.py` | downstream | Demo-Vorschau nutzt den Fixture-Provider über `scheduler._fetch_weather` und `fetch_night_weather` |
| `fetch_night_weather` | downstream | Reicht den Provider an `SegmentWeatherService` durch; erbt den Namensraum automatisch |

## Implementation Details

Gewählt ist Variante C der Analyse (`docs/context/fix-2581-demo-cache-vergiftung.md`). Verworfen: (A) nur Kennung im `model_id` (lässt die Archiv-Vergiftung offen), (B) eigene private Cache-Instanz für die Demo (größerer Eingriff in `preview_service` und die Durchreichung an `_fetch_weather` und `fetch_night_weather`, schließt die Archiv-Vergiftung ebenfalls nicht).

**1. Provider-Merkmal `cache_namespace`.** `FixtureProvider` bekommt ein Klassenmerkmal `cache_namespace = "fixture"`. Alle anderen Provider (`OpenMeteoProvider`, `GeoSphereProvider`, Test-Fakes) tragen es nicht. Der Zugriff erfolgt ausschließlich per `getattr(provider, "cache_namespace", None)`; der Standard ist `None`. Es gibt keine Änderung am `WeatherProvider`-Protokoll und kein Pflichtfeld für Fakes.

**2. `_resolve_model_id` stellt den Namensraum voran.** Nach der bisherigen Ermittlung (`select_model()`, sonst `provider.name`) gilt: Ist `cache_namespace` gesetzt (nicht `None`, nicht leer), lautet die Rückgabe `f"{namespace}:{model_id}"`, beim Fixture-Provider also `"fixture:openmeteo"`. Ohne Namensraum bleibt die Rückgabe byte-identisch zu heute. Da `_bucket_key` und `flight_key` die `model_id` bereits enthalten (#1329), trennt das Cache-Treffer und Single-Flight ohne weitere Änderung. `_resolve_model_id` ist die einzige Stelle: der Aufruf in `fetch_segment_weather` (Cache-get, Single-Flight, put) und der Aufruf im Capture-Block verwenden dieselbe Methode.

**3. `provider.name` bleibt `"openmeteo"`.** Es wird als Feld `provider` in `SegmentWeatherData` und damit in Daten, Mails und Diagnosen ausgegeben. Eine Änderung hätte unbeabsichtigte Folgen in allen Renderern und Validatoren; die Aufrufer-Transparenz des Fixture-Providers bleibt erhalten.

**4. Prognose-Archiv-Capture für Provider mit Namensraum überspringen.** Im Block um `capture_segment_forecast` (`segment_weather.py`, ca. Zeile 393 bis 409) wird der Aufruf nur ausgeführt, wenn `getattr(self._provider, "cache_namespace", None)` leer ist. Beispielwerte gehören nicht ins Prognose-Archiv, das echte Prognosen für Alarm- und Briefing-Vergleiche aufzeichnet. Das bestehende `try/except` und der Kill-Switch `GZ_FORECAST_CAPTURE` bleiben unverändert.

**5. Docstring-Pflicht (wie bei #1329/#1991).** `_resolve_model_id` und `_bucket_key` bekommen eine Begründung im Docstring: warum der Namensraum im `model_id`-Teil steht (der Schlüssel trägt keinen Provider; `provider.name` ist beim Fixture-Provider bewusst `"openmeteo"` und kollidiert mit dem Open-Meteo-Rückfall), und warum die `user_id` weiterhin nicht im Schlüssel steht. Der Satz im bisherigen `_resolve_model_id`-Docstring, FixtureProvider falle auf den Provider-Namen zurück, wird korrigiert.

**6. Geprüft und nicht betroffen.** `radar_cache` und `thunder_window_cache` haben eigene Schlüssel. Die Demo-Vorschau ruft dort keinen Fixture-Weg auf (sie nutzt ausschließlich `_fetch_weather` und `fetch_night_weather`). Beide sind deshalb nicht Teil dieses Fixes und bleiben unverändert.

**7. Offline-Testmodus.** Mit `GZ_TEST_FIXTURE_DIR` liefert `get_provider` im Produktivpfad ebenfalls den `FixtureProvider`. Dort ändert sich der Cache-Schlüssel auf `fixture:openmeteo`, konsistent innerhalb eines Satzes; ein Verhaltensverlust entsteht nicht. Die Prognose-Archiv-Zeilen entfallen in diesem Modus (gewollt).

## Expected Behavior

- **Input:** Abruf über `SegmentWeatherService.fetch_segment_weather` mit einem Provider, der `cache_namespace` trägt (Demo) oder nicht (live, Fakes).
- **Output:** Demo und live nutzen getrennte Cache-Einträge und getrennte Single-Flight-Abrufe, in beiden Reihenfolgen und ohne Cache-Leeren dazwischen. `SegmentWeatherData.provider` bleibt `"openmeteo"`.
- **Side effects:** Demo-Abrufe schreiben nichts ins Prognose-Archiv. Live-Abrufe schreiben wie bisher. Provider ohne Merkmal verhalten sich unverändert.

## Acceptance Criteria

- **AC-1:** Given zwei Fixture-Verzeichnisse mit unterschiedlichen Temperaturen (Satz 1 mit 2 C, Satz 2 mit 22 C) und ein geteilter Wetter-Cache, der zwischen den Abrufen nicht geleert wird / When zuerst ein Demo-Abruf (Satz 1, Provider mit Namensraum `fixture`) und danach ein Live-Abruf (Satz 2, Provider ohne Namensraum, gleicher Ort, gleiche Höhe, gleiches Fenster) läuft, und in einem zweiten Lauf mit leerem Cache dieselbe Reihenfolge umgekehrt (erst live, dann Demo) / Then liefert jeder Abruf den Wert seiner eigenen Quelle (Demo 2 C, live 22 C), in beiden Reihenfolgen, und der zweite Abruf verbraucht einen eigenen Anbieter-Abruf statt eines Cache-Treffers.
  - Test: Zwei `FixtureProvider`-Instanzen auf Test-Verzeichnissen; die zweite wird in der Testdatei in einer kleinen Unterklasse ohne `cache_namespace` abgeleitet (simuliert den live-Rückfall `"openmeteo"` ohne Netz). Gemeinsamer `WeatherCacheService`; Reihenfolge demo→live und live→demo, ohne `clear()`. Heute rot.

- **AC-2:** Given ein Segment, für das das Prognose-Archiv aktiv ist (`GZ_FORECAST_CAPTURE` an, Archiv-Datei in einem Test-Verzeichnis) / When einmal ein Demo-Abruf (Provider mit Namensraum `fixture`) und einmal ein Live-Abruf (Provider ohne Namensraum, gleicher Ort) über `SegmentWeatherService` läuft / Then enthält das Prognose-Archiv nach dem Demo-Abruf keine neue Zeile, nach dem Live-Abruf genau eine Zeile mit `provider="openmeteo"`.
  - Test: Archiv-Ziel auf `tmp_path` gelegt (echter Writer, kein `patch()`); Zeilenzahl vor und nach jedem Abruf. Heute rot, weil der Demo-Abruf eine Zeile schreibt.

- **AC-3:** Given zwei verschiedene Nutzer (Nutzer A und Nutzer B, jeweils mit eigener `user_id`) rufen denselben Ort ab, A über die Demo-Vorschau (Fixture) und B live / When beide Abrufe nacheinander über den geteilten Cache laufen, und anschließend ein zweiter Live-Abruf von Nutzer A für denselben Ort / Then teilen sich die beiden Live-Abrufe (B, dann A) einen Cache-Eintrag (1 Anbieter-Abruf, der Schlüssel enthält keine `user_id`), während der Demo-Abruf von A einen eigenen, getrennten Eintrag nutzt und der Live-Eintrag nie Beispielwerte enthält.
  - Test: Zwei Nutzer-IDs, Zählender Provider (echte, deterministische `NormalizedTimeseries`, ohne `Mock()`); geprüft werden Abruf-Zähler und die Temperaturwerte der Ergebnisse. Belegt, dass die Trennung entlang der Datenquelle und nicht entlang des Nutzers verläuft.

- **AC-4:** Given eine Demo-Vorschau mit Nachtsegment (Provider `FixtureProvider`, Satz 1 mit 2 C) und ein bereits gefüllter Cache-Eintrag eines Live-Abrufs für den Ankunftspunkt (Satz 2 mit 22 C) / When `fetch_night_weather(last_segment, provider=FixtureProvider(...), user_id=...)` aufgerufen wird, in der Gegenrichtung auch erst Demo und danach live / Then enthält die Nacht-Zeitreihe der Demo ausschließlich Werte des Fixture-Satzes (2 C), der Live-Abruf nie Werte des Fixture-Satzes, und der Cache-Schlüssel des Nachtabrufs trägt den Namensraum `fixture:`.
  - Test: `fetch_night_weather` mit echtem `FixtureProvider` und geteiltem Cache gegen einen zählenden Live-Fake; Werte und Zähler geprüft, kein `patch()`.

- **AC-5:** Given ein Demo-Abruf mit `FixtureProvider` / When das Ergebnis `SegmentWeatherData` und die zugehörige Zeitreihe betrachtet werden / Then ist `SegmentWeatherData.provider` weiterhin `"openmeteo"` und `FixtureProvider().name` weiterhin `"openmeteo"`; nur der interne Cache-Schlüssel (`model_id = "fixture:openmeteo"`) unterscheidet sich.
  - Test: Direkte Prüfung von `provider.name`, `SegmentWeatherData.provider` und `SegmentWeatherService._resolve_model_id(...)` auf `"fixture:openmeteo"`.

- **AC-6:** Given Test-Fakes und Provider ohne Merkmal `cache_namespace` (z. B. ein `CountingFakeProvider` wie in `tests/unit/test_forecast_cache_sharing.py`, `GeoSphereProvider`, ein Provider mit `select_model()`) / When `_resolve_model_id` und `fetch_segment_weather` darauf laufen / Then bleibt die `model_id` unverändert (`provider.name` bzw. das Ergebnis von `select_model()`, ohne Präfix), das Prognose-Archiv wird wie bisher beschrieben, und die bestehenden Cache-Tests laufen unverändert grün.
  - Test: Zusicherung für `_resolve_model_id` bei Fake ohne Merkmal, bei Fake mit `select_model()` und bei Fake mit `cache_namespace = None`; der bestehende Satz `test_forecast_cache_sharing.py` und `test_weather_cache.py` läuft ohne Änderung durch.

## Known Limitations

- **Nur Provider mit Merkmal.** Künftige Demo- oder Offline-Provider müssen `cache_namespace` selbst setzen. Ein Test stellt sicher, dass der Fixture-Provider es trägt (AC-5).
- **Offline-Testmodus.** Mit `GZ_TEST_FIXTURE_DIR` schreibt der Produktivpfad keine Prognose-Archiv-Zeilen mehr (gewollt, siehe Implementation Details 7).
- **Kein Eingriff in vorhandene Daten.** Bereits im Prognose-Archiv stehende Demo-Zeilen (`provider="openmeteo"`, aus der Zeit vor dem Fix) werden von diesem Fix nicht bereinigt.

## Nicht im Scope

- Eigene private Cache-Instanz für die Demo (Variante B).
- Änderung von `provider.name`, des `WeatherProvider`-Protokolls oder der Logik von `WeatherCacheService` (Covers-Regel, TTL, Schlüsselformat).
- `radar_cache` und `thunder_window_cache` (geprüft, nicht betroffen).
- Bereinigung bereits geschriebener Archiv-Zeilen.

## Folgepflege

`docs/specs/modules/weather_cache.md` (Spec zu #1329) wird im Zuge der Umsetzung um einen Verweis ergänzt: Der `model_id`-Teil des Bucket-Schlüssels kann einen Provider-Namensraum (`<namespace>:`) tragen, siehe `fix_2581_demo_cache_vergiftung.md`. Das ist reine Doku-Querverweis-Pflege, keine inhaltliche Änderung der dortigen Spezifikation.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird kein neuer Mechanismus eingeführt. Der bestehende Schlüsselbestandteil `model_id` (#1329) wird um einen optionalen Präfix erweitert, analog zur Erweiterung um die Höhe (#1991). Die bestehende Entscheidung für einen prozessweit geteilten, nutzerneutralen Cache (ADR-0032) bleibt unberührt.

## Test Plan

Kern-Schicht, netzfrei, ohne Mock-Theater (Test-Politik siehe `CLAUDE.md`):

- Neue Testdatei nach Verhalten benannt: `tests/unit/test_demo_cache_vergiftet_live_nicht.py`, Prüfling relativ zur Testdatei aufgelöst.
- Echte `FixtureProvider`-Instanzen auf zwei temporären Fixture-Verzeichnissen (2 C und 22 C), der Live-Gegenpart ist eine Unterklasse ohne `cache_namespace` (gleicher Name `"openmeteo"`, kein Netz). Ein gemeinsamer `WeatherCacheService`; der Shared-Cache-Reset läuft zentral über die autouse-Fixture in `tests/conftest.py`, zwischen den Abrufen eines Tests wird nicht geleert.
- AC-1: beide Reihenfolgen (demo→live, live→demo) mit je eigenem Cache-Zustand. AC-2: Archiv-Ziel auf `tmp_path`, Zeilen zählen. AC-3: zwei Nutzer-IDs, zählender Fake. AC-4: `fetch_night_weather` mit Fixture-Provider. AC-5: `provider.name`, `SegmentWeatherData.provider`, `_resolve_model_id`. AC-6: Fakes ohne Merkmal und bestehende Cache-Tests.
- Reihenfolge: Tests gegen den Ausgangszustand zuerst rot (AC-1, AC-2, AC-4: Beispielwerte erscheinen im Live-Abruf bzw. die Archiv-Zeile entsteht), erst danach Implementierung.
- Mutations-Gegenprobe (Adversary): Präfix in `_resolve_model_id` entfernen muss AC-1/AC-4 brechen; Capture-Guard entfernen muss AC-2 brechen; Präfix auch ohne Namensraum erzwingen muss AC-6 brechen.

## Risiken

- **Niedrig: Kollision der Schlüsselform.** Ein echtes Regionalmodell heißt nie `"fixture:..."`; der Doppelpunkt kommt in keiner `select_model()`-Kennung vor. Mitigation: AC-6 sichert, dass Provider ohne Merkmal keinen Präfix bekommen.
- **Niedrig: Vergessenes Merkmal bei neuen Demo-Providern.** Mitigation: Known Limitation und AC-5; spätere Provider für Demo oder Offline sind über ihre Spec zu prüfen.
- **Niedrig: Archiv-Lücke im Offline-Testmodus.** Gewollt; Tests des Prognose-Archivs verwenden Provider ohne Merkmal.
- **Niedrig: Cache nach Deploy.** Der Schlüssel ändert sich nur für den Fixture-Pfad; der In-Memory-Cache ist nach dem Neustart ohnehin leer.

## Changelog

- 2026-11-06: Initial spec created (Issue #2581, Variante C: Provider-Merkmal `cache_namespace` plus Capture-Guard)
