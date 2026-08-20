---
entity_id: wegpunkt_hoehe_provider
type: module
created: 2026-08-20
updated: 2026-08-20
status: draft
version: "1.0"
tags: [provider, openmeteo, hoehe, trip, ortsvergleich, nowcast]
---

# Wegpunkt-Höhe an die Wetter-Provider

## Approval

- [x] Approved (PO Henning, 2026-08-20, "go")

## Purpose

Die Geländehöhe eines Wegpunkts wird bei der Wetterabfrage mitgeschickt, damit die Provider ihre
Vorhersage auf die echte Höhe herunterrechnen statt auf die Höhe ihrer eigenen, geglätteten
Geländekarte. Ohne diese Angabe sind Gipfelwerte zu warm und Hüttenwerte zu kalt — gemessen bis
6,2 °C Abweichung an einem einzigen Punkt.

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** neuer Params-Erbauer `_punkt_params()`, angewandt auf alle Open-Meteo-Abrufe
- **Schicht:** Python-Core (`src/providers/`, `src/services/`) — kein Frontend, kein Go

## Estimated Scope

- **LoC:** ~100 produktiv (Limit 250), ~280 Test (Limit 500)
- **Files:** 9 produktiv + 3 Dokumentation
- **Effort:** medium

## Ausgangsmessung (2026-08-20, echte API)

| Punkt | echte Höhe | Höhe im Modell | Abweichung heute |
|---|---|---|---|
| Dresdner Hütte (Stubai) | 2302 m | 3078 m | **6,2 °C zu kalt** |
| Obstanserseehütte (KHW) | 2304 m | 1794 m | 4,8 °C zu warm |
| Schaufelspitze (Stubai) | 3333 m | 2925 m | 3,5 °C zu warm |
| Bocca di Foggiale (GR20) | 1962 m | 1716 m | 1,6 °C zu warm |

Mitbetroffen (stundenscharf, 48 h): Nullgradgrenze bis 460 m, Niederschlag bis 2,4 mm,
Wettercode in bis zu 11 von 48 Stunden.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `Location` (`src/app/config.py:82`) | Datenklasse | trägt bereits `elevation_m`, kein Umbau nötig |
| `GPXPoint` / `Waypoint` (`src/app/models.py:364/374`) | Datenklasse | Herkunft der Trip-Höhe |
| `SavedLocation` (`src/app/user.py:58`) | Datenklasse | Herkunft der Ortsvergleich-Höhe (Pflichtfeld) |
| `WeatherCacheService` (`src/services/weather_cache.py`) | Service | Cache-Bucket muss nach Höhe trennen |
| `RadarNowcastService` (`src/services/radar_service.py`) | Service | fünfter Open-Meteo-Aufrufer |
| ADR-0018 | Entscheidung | Fallback ohne Kaschieren — trägt die Provider-Asymmetrie |
| ADR-0056 | Entscheidung | Alarm-Anker — betroffen vom einmaligen Wertesprung |

## Implementation Details

### Scheibe S1 — Trip-/Vorhersagepfad

Ein gemeinsamer Erbauer in `src/providers/openmeteo.py`:

```
_punkt_params(location, **rest) -> dict
    latitude, longitude aus location
    elevation NUR wenn location.elevation_m is not None  (int, gerundet)
    rest wird daruebergelegt
```

Angewandt auf: `fetch_forecast` (`:973`), `fb_params` (`:1175`), `_fetch_ensemble_spread` (`:724`),
`_fetch_uv_data` (`:807`, Signatur von `lat, lon` auf `location` heben). Zusätzlich
`geosphere.py:508` (`_fetch_openmeteo_clouds`, hartkodierter URL).

`_request()` ist bewusst **nicht** der Ort: es kennt die `Location` nicht und deckt nur vier von
sechs Baustellen ab. Die Vollständigkeit sichert stattdessen ein **AST-Wächter** nach dem
Hausmuster `tests/test_onset_callsite_timezone_guard.py` — kein Dict-Literal und kein
String-Literal in `src/`/`api/` darf `latitude` an Open-Meteo übergeben, ohne über den Erbauer zu
laufen oder namentlich mit Begründung in der Ausnahmeliste zu stehen.

Bewusste Ausnahmen in der Liste: die Fähigkeits-Probe (`openmeteo.py:354`, feste Sondier-Koordinaten
ohne Ortsbezug) und der Luftqualitäts-Endpunkt (`openmeteo.py:807`, kennt `elevation` nicht).

### Scheibe S2 — Ortsvergleich und Cache

- `compare_location_weather_source.py:150` setzt die Höhe nicht mehr hart auf `None`
- `LocationWeatherSource.fetch` (`src/services/point_weather.py:84`) nimmt die Höhe entgegen
- Aufrufer `compare_alert.py`, `scheduler_dispatch_service.py` reichen `SavedLocation.elevation_m` durch
- `weather_cache.py:226` nimmt die Höhe in den Bucket-Schlüssel auf

### Scheibe S3 — Kurzfrist-Nowcast

`radar_service.get_nowcast` und die interne Abrufkette führen die Höhe mit; der Open-Meteo-Abruf
(`:458`) trägt sie; `radar_cache.py:72` trennt danach.

## Expected Behavior

- **Input:** Wegpunkt oder Ort mit Höhe in Metern; oder ohne Höhe (`None`)
- **Output:** Wetterwerte, die auf die angegebene Höhe heruntergerechnet sind
- **Side effects:** Beim ersten Lauf nach der Umstellung springen die Werte einmalig; dadurch können
  Abweichungsalarme auslösen (bewusst hingenommen, siehe Known Limitations)

## Acceptance Criteria

- **AC-1:** Given ein Trip-Wegpunkt mit hinterlegter Höhe von 3333 m / When das System für diesen
  Wegpunkt eine Vorhersage abruft / Then trägt die abgesetzte HTTP-Anfrage an Open-Meteo den
  Parameter `elevation=3333` in der Adresszeile.
  - Test: Kern-Schicht mit `httpx.MockTransport` — der Prüfling setzt einen echten Request ab, der
    Test liest dessen fertig kodierte Query. Kein Objekt-Double des Providers.

- **AC-2:** Given ein Wegpunkt ohne Höhenangabe (`elevation_m is None`) / When das System die
  Vorhersage abruft / Then enthält die Anfrage **überhaupt keinen** `elevation`-Parameter — weder
  leer noch mit Platzhalter — und der Abruf liefert wie bisher ein Ergebnis.
  - Test: Abwesenheits-Prüfung (`"elevation" not in params`), nicht Gleichheit mit Leerstring; ein
    versehentliches `params["elevation"] = None` würde sonst als `elevation=` durchrutschen.

- **AC-3:** Given ein Wegpunkt mit Höhe und eingeschalteter Ensemble-Anreicherung / When der Lauf
  sowohl die Hauptvorhersage als auch den Ensemble-Abruf und den Wolken-Abruf über GeoSphere
  auslöst / Then tragen **alle** diese Open-Meteo-Anfragen die Höhe, nicht nur die erste.
  - Test: Alle im Testlauf beobachteten Anfragen an Open-Meteo werden gesammelt und einzeln geprüft.

- **AC-4:** Given jemand ergänzt später eine neue Stelle im Code, die Open-Meteo direkt mit
  Koordinaten anspricht, ohne den gemeinsamen Erbauer zu benutzen / When der Testlauf läuft /
  Then schlägt ein Wächter fehl und benennt Datei und Zeile der neuen Stelle.
  - Test: Statische Analyse über `src/` und `api/` mit namentlicher Ausnahmeliste; Gegenprobe durch
    Einfügen einer neuen Aufrufstelle muss den Wächter rot machen.

- **AC-5:** Given eine Vorhersage wurde mit Höhenangabe abgerufen / When das Ergebnis vorliegt /
  Then ist die von der Wetterquelle tatsächlich verwendete Höhe im Ergebnis festgehalten und
  weicht bei erfolgreicher Korrektur nicht mehr von der angeforderten Höhe ab.
  - Test: Antwort liefert `elevation: 3333.0`, `meta.model_elevation_m` trägt diesen Wert.

- **AC-6:** Given ein Ort im Ortsvergleich mit hinterlegter Höhe / When für diesen Ort Wetterdaten
  geholt werden (Vorschau, Versand oder Alarmlauf) / Then trägt die Anfrage dessen Höhe — der
  Ortsvergleich verliert die Höhe nicht mehr auf dem Weg zum Provider.
  - Test: Wie AC-1, aber über den Ortsvergleichs-Einstieg; zwei verschiedene Nutzer, damit die
    Mandantentrennung mitgeprüft wird.

- **AC-7:** Given ein Trip-Wegpunkt und ein Ortsvergleichs-Ort liegen auf derselben Koordinate,
  haben aber unterschiedliche Höhen / When beide nacheinander im selben Prozess abgefragt werden /
  Then bekommt jeder die Werte seiner eigenen Höhe, statt dass der zweite die Zwischenspeicherung
  des ersten erbt.
  - Test: Zwei Abrufe hintereinander, beide Antworten unterscheiden sich; ohne die Trennung wäre die
    zweite Antwort mit der ersten identisch.

- **AC-8:** Given ein Wegpunkt auf 3333 m mit aktivem Kurzfrist-Nowcast / When der Nowcast Regen
  oder Schnee abruft / Then trägt auch diese Anfrage die Höhe.
  - Test: Wie AC-1, über den Nowcast-Einstieg.

- **AC-9:** Given zwei Punkte gleicher Koordinate mit unterschiedlicher Höhe / When der Nowcast für
  beide läuft / Then liefert der Zwischenspeicher nicht das Ergebnis des einen für den anderen aus.
  - Test: Wie AC-7, über den Nowcast-Zwischenspeicher.

- **AC-10:** Given die Quellen-Governance verlangt, dass jeder an Open-Meteo gesendete Parameter
  freigegeben ist / When `elevation` produktiv gesendet wird / Then führt `docs/specs/data_sources.md`
  ihn als genehmigten Parameter.
  - Test: `# doc-compliance-test` nach Vorbild `tests/tdd/test_starkregen_kurzfristhinweis.py:639`.

- **AC-11:** Given das Höhen-Soll war bisher nirgends festgelegt / When die Umstellung erfolgt /
  Then hält ein ADR fest, dass die Höhe an die Provider-Schnittstelle durchgereicht wird, dass keine
  eigene Höhenphysik gerechnet wird, und welche Provider die Angabe nicht annehmen können.
  - Test: Der bestehende Index-Abgleich `tests/test_adr_index_drift.py` muss den neuen Eintrag tragen.

- **AC-12:** Given zwei Abrufe für dieselbe Koordinate, einmal mit und einmal ohne Höhenangabe /
  When beide gegen die echte Wetterquelle laufen / Then unterscheiden sich die gelieferten
  Temperaturen messbar, und der Wert mit Höhenangabe passt zur echten Höhe des Punktes.
  - Test: Live-Schicht (Marker `live`), an mindestens zwei Referenzpunkten aus `examples/` —
    ein Gipfel und eine Hütte, damit beide Fehlerrichtungen belegt sind.

- **AC-13:** Given der Luftqualitäts-Abruf kennt keinen Höhenparameter / When ein Wegpunkt mit Höhe
  verarbeitet wird / Then läuft dieser Abruf unverändert und ohne Fehler weiter.
  - Test: Beobachteter Abruf an den Luftqualitäts-Endpunkt trägt keinen `elevation`-Parameter und
    liefert weiterhin ein Ergebnis.

- **AC-14:** Given der deterministische Testlauf schützt bestehendes Verhalten / When die Umstellung
  vollständig ist / Then bleibt er grün, ohne dass eine aufgezeichnete Antwortdatei angepasst werden
  musste.
  - Test: Vollständiger Kern-Testlauf grün; `git diff --stat fixtures/` bleibt leer.

## Known Limitations

- **Provider-Asymmetrie (bewusst).** DWD-GRIB2, DWD-EU, GeoSphere-Zeitreihen und der
  MeteoFrance-WCS nehmen keine Geländehöhe an. Im Regelbetrieb liefern diese Quellen keine
  Temperatur, sondern Gewitter- und Schneesignale; die Asymmetrie greift praktisch nur beim
  Totalausfall aller Open-Meteo-Kandidaten, wo ADR-0018 bereits einen ausgewiesenen Fallback-Grund
  vorsieht. Keine eigene Höhenphysik (PO-Entscheid).

- **Einmaliger Wertesprung beim Umschalten (bewusst hingenommen).** Der Abweichungsvergleich kann
  nicht zwischen „das Wetter hat sich geändert" und „wir fragen seit heute anders" unterscheiden.
  Die Anker werden **nicht** gelöscht: ohne Anker gäbe es gar keinen Abweichungsalarm mehr, bei
  laufender Tour bis zu zwölf Stunden lang. Ein einmaliger Fehlalarm — vom Melde-Gedächtnis auf
  einmal je Metrik und Etappe begrenzt — ist das kleinere Übel als eine blinde Wache.

- **Höhe nur so gut wie ihre Quelle.** Trip-Höhen stammen aus der GPX-Datei, Ort-Höhen aus einem
  externen Höhendienst. Fehlerhafte Eingangsdaten werden jetzt wirksam, wo sie vorher folgenlos
  blieben.

- **Nicht Teil dieser Arbeit:** Der Governance-Rückstand bei acht weiteren bereits produktiv
  gesendeten Parametern (`apparent_temperature`, `cape`, `visibility`, `uv_index`,
  `freezing_level_height`, `is_day`, `precipitation_probability`, `direct_normal_irradiance`) —
  gehört als Sammel-Eintrag nach #1199.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0058 (neu anzulegen)
- **Rationale:** Das Höhen-Soll war nie festgelegt — weder „Modellhöhe akzeptieren" noch
  „korrigieren". Der PO hat am 20.08.2026 entschieden: Höhe an die Schnittstelle durchreichen,
  Korrektur der Quelle überlassen, kein Hinweis im Briefing. Das ist eine Entscheidungsfläche
  (Provider-Vertrag) und braucht daher einen festgehaltenen Beschluss, samt der Provider, die
  nicht mitziehen können.

## Changelog

- 2026-08-20: Initial spec created (Issue #1991, Audit-Befund B-01)
