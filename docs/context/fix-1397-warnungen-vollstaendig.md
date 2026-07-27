# Kontext: fix-1397-warnungen-vollstaendig

Issue: #1397 — Amtliche Warnungen gehen verloren (MeteoAlarm-Index nur Seite 1 von N) + ZAMG-Zuständigkeit ist ein Radar-Rechteck.
Typ: Bug (Fast-Track). Erstellt 2026-07-27.

## Analyse

### Typ
Bug — nutzersichtbarer Warn-Verlust, sicherheitskritisch.

### Belegte Befunde

**Defekt 1 (kritisch):** `_get_cached_index()` (`src/services/official_alerts/meteoalarm.py:207-234`) ruft den Länder-Index ohne `page`-Parameter und verarbeitet nur die ersten 100 Features. Die API blättert (`metadata: {page, page_size, total_count, total_pages}`, `page=N` → HTTP 200).

Live bewiesen 2026-07-27: Eine ORANGE Gewitterwarnung Stufe 3 („Trentino Alto Adige"), deren exakte Fläche einen Wegpunkt des Trips „KHW 403" enthält, liegt auf Index-Seite 3 von 3 und erreicht den Nutzer nie. Für die österreichischen Vergleichs-Orte (Geisbergalm, Hochkönig) liegen Gewitter- und Hitzewarnung auf Seite 14 bzw. 18.

**Defekt 2 (mittel):** `GeoSphereWarnSource.covers()` (`geosphere_warn.py:142-147`) nutzt die INCA-Radar-Box (`radar_service.py:36-39`) als Zuständigkeitsnachweis. Der ZAMG-Endpunkt beantwortet nur österreichisches Staatsgebiet und liefert außerhalb HTTP 404. `base.py:120-146` wertet das als Ausfall ⇒ falscher Hinweis „Amtliche Warnungen aktuell nicht abrufbar" + >300 sinnlose Abrufe/Tag.

### Messung S1a (echte API, 2026-07-27 ~06:30 UTC, AT)

| Messung | Ergebnis |
|---|---|
| Seite 1, 23-h-Fenster | `total_count 1640`, `total_pages 17` |
| davon überholt (`supersededAt`/`supersededByAlertId` gesetzt) | **98 von 100** (Seite 17: 38 von 40) |
| eindeutige `alertId` je 100 Features | 50 |
| eindeutige `OBJECTID` (= Fläche) je 100 Features | **15** |
| Seite 1, 3-h-Fenster | `total_count 90`, `total_pages 1` |

Deutung: `datetime` filtert die **Publikationszeit**, nicht die Gültigkeit — das 23-Stunden-Fenster (API-Zwang < 24 h) zieht die komplette Aktualisierungshistorie herein. Der Index besteht zu ~95 % aus überholten Fassungen und mehrfach wiederholten Flächen.

Konsequenz: Ein kürzeres Fenster ist **keine** Lösung (eine vor 20 h publizierte, noch gültige Warnung dürfte nicht verschwinden). Der Hebel ist das Überspringen überholter Features und das Deduplizieren vor jedem Nachlade-Abruf.

### Warum vollständiges Blättern allein nicht reicht

`MeteoAlarmSource.fetch()` (`meteoalarm.py:311-336`) lädt für **jedes** Feature sofort die exakte Fläche nach — kein bbox-Vorfilter, obwohl jedes Feature eine bbox-`geometry` mitbringt. Ohne Gegenmaßnahmen würde vollständiges Blättern die Nachlade-Abrufe von ~200 auf ~2000 je Punkt und Land vervielfachen (Kontingent, vgl. 429-Historie #1348).

Zusätzlich: `_geometry_cache`/`_cap_cache` (`meteoalarm.py:66-67`) sind auf die **presigned URLs** (`meteo.fra1.digitaloceanspaces.com`) geschlüsselt, deren Signatur pro Antwort rotiert. Sie greifen deshalb nie über die Index-Erneuerung hinaus und wachsen unbegrenzt — im dauerhaft laufenden FastAPI-Prozess ein Speicherleck, das mit S1 durchschlägt.

Und fachlich: Ohne `supersededAt`-Filter erscheint dieselbe Warnung mit drei leicht verschobenen Zeiträumen dreifach in der Mail — der Dedup in `base.py:170` greift nur bei exakt gleichem `(valid_from, valid_to)`. Der Filter ist damit **Korrektheitsbedingung**, keine Optimierung.

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/official_alerts/meteoalarm.py` | MODIFY | S1: Seitenschleife, eingefrorenes Zeitfenster, `supersededAt`-Filter, Feature-Dedup, bbox-Vorfilter, stabile Cache-Schlüssel |
| `src/services/official_alerts/warn_egress.py` | MODIFY | S2: `absent_statuses` — Status als „nicht zuständig" statt Ausfall |
| `src/services/official_alerts/geosphere_warn.py` | MODIFY | S2: 404 als „nicht zuständig" |
| `tests/tdd/test_meteoalarm_source.py` | MODIFY | Cache-Schlüssel-Zugriffe, neue Paging-Tests |
| `tests/fixtures/meteoalarm/` | CREATE | Mehrseitige Index-Fixtures inkl. Fehlerfall |

### Scope

- S1: ~85-110 Zeilen Quellcode + ~130-180 Zeilen Tests
- S2: ~28 Zeilen Quellcode + ~90-120 Zeilen Tests
- **Getrennte Workflows** — zusammen über dem 250-Zeilen-Limit, und S2 fasst den von allen fünf Warn-Quellen geteilten Egress-Kern an (eigener Adversary-Durchgang).

### Technischer Ansatz S1 (dieser Workflow)

1. **Seitenweise abrufen** über `warn_egress.cached_fetch()` je Seite (Schlüssel `f"{country}:p{n}"`), damit 429-Rückzug und Egress-Zeile je Seite erhalten bleiben. Zeitfenster **einmal** einfrieren und an alle Seiten übergeben (sonst wandern die Seitengrenzen zwischen den Abrufen).
2. **Unvollständiger Index = Ausfall.** Schlägt eine Seite fehl, liefert `_get_cached_index()` `None` — kein Teilergebnis. `warn_egress` setzt den Fehlschlag-Marker bereits, `base.py:144-146` macht daraus `unavailable=True`. Begründung: die belegte ORANGE Warnung lag auf der **letzten** Seite — genau der, die bei Abbruch fehlt.
3. **Überholte Features überspringen** (`supersededAt`/`supersededByAlertId` gesetzt) — vor jedem Nachlade-Abruf.
4. **Feature-Dedup** nach `(alertId, indexArea, indexInfo)`; Flächen-Abruf nach `OBJECTID`, CAP-Abruf nach `alertId` schlüsseln (statt presigned URL) mit langer Erfolgs-TTL — Geometrie und CAP einer Warnung sind unveränderlich, Änderungen kommen als neue `alertId`.
5. **bbox-Vorfilter** aus der mitgelieferten Feature-`geometry`, als **Obermenge**: min/max der Ring-Koordinaten mit Marge (~0,01°), NICHT `_point_in_geometry()` (dessen striktes Ray-Casting schließt Kantenpunkte aus und würde denselben stillen Verlust an der bbox-Kante erzeugen). Fehlende/unparsbare `geometry` → Fläche nachladen (fail-open).
6. Obergrenze für die Seitenschleife (z. B. 50) und Dedup der zusammengeführten Features nach `OBJECTID`, damit während des Blätterns eintreffende Warnungen keine Verschiebung erzeugen.

### Risiken

- Für österreichische Punkte findet MeteoAlarm künftig Warnungen, die es bisher nicht sah. Wo MeteoAlarm ein höheres Level meldet als ZAMG, wechselt durch den Cross-Source-Dedup (`base.py:153-176`) die angezeigte Quelle — sichtbarer Wechsel in Label/Region, kein Defekt.
- `_fetch_geometry_link`/`_fetch_cap` protokollieren `host="api.meteoalarm.org"`, gehen aber gegen DO-Spaces (`meteoalarm.py:246, 257`). Vor der Wirkungsmessung geradeziehen.
- Bekannte Grenze (nicht in S1): die Trigger-Pfade `trip_alert.py:954` und `compare_official_alert.py:162` verwerfen den `unavailable`-Status — dort bleibt ein unvollständiger Index still.
- `_extract_alerts_from_cap()` gibt alle `<info>`-Blöcke eines CAP zurück, unabhängig vom Gebiet. Bei mehrflächigen CAP-Dokumenten kämen fremde Regionen mit. In S1 nur beobachten (Fixture prüfen), nicht ungeprüft mitfixen.

### Offene Punkte

- keine blockierenden
