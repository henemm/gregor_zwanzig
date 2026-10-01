---
entity_id: fix_2464_brightsky_konvektions_sidecar
type: module
created: 2026-09-30
updated: 2026-09-30
status: draft
version: "1.0"
tags: [radar, nowcast, brightsky, radolan, konvektion, gewitter, hagel, cache, adr-0018]
---

# BrightSky-Konvektions-Sidecar fuer den DE-Radar-Nowcast (Issue #2464)

## Approval

- [ ] Approved

## Purpose

Der Radar-Nowcast fuer Orte in Deutschland (Quelle BrightSky/RADOLAN) erkennt heute nie Gewitter oder Hagel: `_fetch_brightsky` liefert nur Niederschlagsmengen, `is_convective`/`hail` bleiben fuer jeden Frame `False`. INCA (Oesterreich) und Korsika haben dafuer einen Konvektions-Sidecar, DE nicht. Folge: Radar-Alarmstufe Gewitter/Hagel (#660), Akut-Override (#1310) und Gewitter-Hebung (#1759) sind in Deutschland strukturell blind. Diese Spec haengt an den DE-Zweig denselben Sidecar wie bei INCA und schliesst dabei eine Cache-Luecke: `convective_checked` wird bisher nicht mitgecacht, ein Cache-Treffer meldet immer "geprueft" (gilt fuer alle Regionen).

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `RadarNowcastService._fetch_brightsky` (ca. Zeile 807-817), `RadarNowcastService.get_nowcast` (Cache-Hit/-Put, ca. Zeile 491-550); Muster-Vorbild `_fetch_geosphere_inca` (Zeile 819-852) und `_fetch_corsica_arome_fr` (Zeile 854-875), wiederverwendet: `_merge_convective` (Zeile 877), `_fetch_openmeteo_15` (Zeile 913, einziger Open-Meteo-Funnel mit `ForecastBudgetGate` und Offline-Fixture)
- **File:** `src/services/radar_cache.py`
- **Identifier:** `RadarCacheEntry`, `RadarNowcastCacheService.put` / `.get`
- **File (Test-Fixture, NEU):** `tests/fixtures/brightsky/radar_de_kurz.json`
- **File (Tests, NEU):** `tests/tdd/test_radar_brightsky_convective_sidecar.py`

> **Schicht-Hinweis:** Python-Core (`src/services/`, Prozess `gregor-python`). Kein Go-Anteil, kein Frontend. Alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) ziehen aus demselben `NowcastResult`; es gibt keine kanalspezifische Aenderung.

## Estimated Scope

- **LoC:** ca. 25-40 produktiv, Tests ca. 120 (Fixture-Datei zaehlt nicht als Code)
- **Files:** 2 produktiv (`radar_service.py`, `radar_cache.py`), 1 Test, 1 Fixture
- **Effort:** low-medium
- **Risk:** MEDIUM (zentrale Nowcast-Kette; Alarmverhalten in DE aendert sich erstmals — Gewitter-/Hagel-Alarme werden moeglich; Open-Meteo-Budget +1 Call je DE-Radarabfrage)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RadarNowcastService._fetch_openmeteo_15` | Funktion | Sidecar-Abruf (best_match = ICON-D2 in DE), Budget-Gate, Offline-Fixture |
| `RadarNowcastService._merge_convective` | Funktion | Naechster Sidecar-Frame (<= 5 min) -> `is_convective`/`hail` |
| `ForecastBudgetGate` | Klasse | Drosselung des Zusatz-Calls (#1329 C2), unveraendert |
| `BrightSkyProvider.fetch_radar` | Provider | Niederschlagsframes (`precipitation_5`), unveraendert |
| `RadarNowcastCacheService` | Klasse | Frame-Cache (TTL 300 s), erhaelt zusaetzlich das Flag `convective_checked` |
| ADR-0018 | ADR | Kein Kaschieren eines gescheiterten Checks als "kein Gewitter" |
| Akut-Override #1310 (`trip_alert.py:2166`), Hebung #1759 (`thunder_enrichment.py:266`), Radar-Stufe #660 | Verbraucher | haengen an `is_convective` der Radar-Frames |

## Implementation Details

### Live-Messung der Sidecar-Quelle (2026-09-30) — Begruendung

Die Sidecar-Quelle wurde nicht angenommen, sondern gemessen:

- Open-Meteo `minutely_15` `weather_code`, 96 Schritte, 4 DE-Punkte (Muenchen, Hamburg, Allgaeu, Ruegen): `weather_code` und `precipitation` nie `None`. `best_match` ist in DE **identisch** mit `icon_d2` (ebenso `icon_seamless`); `icon_eu` weicht ab (groeber) und wird nicht genommen.
- Rueckblick 92 Tage, `icon_d2`: Code 95 kommt vor (Muenchen 20, Frankfurt 36, Berlin 32, Duesseldorf 20, Allgaeu 76 Viertelstunden), Code 96 kommt vor (Muenchen 24), Code 99 nicht. ICON-D2 traegt in DE damit strukturell Gewitter-Codes — anders als AROME-FR an Korsika (#1761), wo der Code strukturell fehlte.
- BrightSky `/radar?format=plain` mit `Accept-Encoding: gzip`: HTTP 200, 8,06 MB roh, 25 Frames, Raster 401x401, `latlon_position` fraktional. Ohne Kuerzung als Fixture unbrauchbar.

Konsequenz: Sidecar = `_fetch_openmeteo_15(lat, lon, elevation_m=...)` **ohne** `models` (best_match), exakt wie bei INCA. Kein eigenes Modell noetig.

### 1. `_fetch_brightsky` (radar_service.py)

Muster wie `_fetch_geosphere_inca`. Signatur erhaelt `elevation_m: Optional[int] = None`; der Aufruf in `_fetch_frames_with_fallback` (Zeile ~775) reicht `elevation_m` durch.

```
def _fetch_brightsky(self, lat, lon, elevation_m=None):
    if _offline_fixture_active():
        return []                       # unveraendert, Sidecar nie erreicht
    try:
        frames = BrightSkyProvider().fetch_radar(lat, lon)
    except Exception:
        return []                       # unveraendert (Fallback-Kette)
    if not frames:
        return []                       # KEIN Sidecar ohne Frames
    sidecar = self._fetch_openmeteo_15(lat, lon, elevation_m=elevation_m)
    if sidecar:
        self._merge_convective(frames, sidecar)
    else:
        self._convective_checked = False    # ADR-0018
    return frames
```

Der Sidecar-Fehler darf den BrightSky-Erfolg nicht kippen: Frames bleiben erhalten, nur `_convective_checked` wird `False` (Niederschlagsmenge und Beginn bleiben nutzbar). Budget-Drosselung und Offline-Fixture kommen automatisch ueber `_fetch_openmeteo_15`; die dort gesetzten Flags (`_budget_throttled_this_call`, `_openmeteo_unavailable_this_call`) duerfen das Niederschlagsergebnis nicht als "Daten nicht verfuegbar" markieren, solange BrightSky-Frames vorliegen (im Test abzusichern, siehe AC-2).

### 2. `radar_cache.py` — `convective_checked` mitfuehren

- `RadarCacheEntry` erhaelt `convective_checked: bool = True`.
- `put(..., convective_checked: bool = True)` speichert es.
- `get_nowcast`: beim Put wird `self._convective_checked` uebergeben; beim Cache-Hit wird `self._convective_checked = cached.convective_checked` gesetzt, **bevor** `_derive_result` laeuft (heute ist es dort zwangslaeufig `True`, weil es am Aufrufanfang auf `True` zurueckgesetzt wird).
- Cache-Schluessel (Koordinate + Region-Bucket + Hoehe) bleibt unveraendert. Negativ-Ergebnisse (leere Frames) werden weiterhin nie gecacht.

Das schliesst die Luecke fuer alle Regionen: ein nach Sidecar-Ausfall gecachter Eintrag wird 5 Minuten lang nicht faelschlich als "Gewitter geprueft, keines" weiterbedient. Bekannte Abweichung, im selben Ticket behoben (nicht vertagt).

### 3. Fixture

`tests/fixtures/brightsky/radar_de_kurz.json`: aufgezeichnete BrightSky-`/radar`-Antwort (Live-Original 8,06 MB, 401x401), auf ein kleines Fenster um eine Zielzelle gekuerzt. Gleiche JSON-Struktur wie das Original (`radar`-Frames mit `timestamp`, `precipitation_5`, Metadaten inkl. `latlon_position` — dort auf das gekuerzte Fenster angepasst). Versioniert, keine Laufzeit-Erzeugung.

## Expected Behavior

- **Input:** Radar-Nowcast-Abfrage fuer einen Ort im RADOLAN-Gebiet (DE), BrightSky liefert Frames.
- **Output:** `NowcastResult` mit Niederschlagsdaten aus BrightSky; `is_convective` und `hail` je Viertelstunden-Frame aus dem Open-Meteo-Sidecar (95 -> Gewitter; 96/99 -> Gewitter + Hagel, gemaess `_is_convective_weathercode`/`_is_hail_weathercode`); `convective_checked=True` bei erfolgreichem Sidecar, sonst `False`.
- **Side effects:** +1 Open-Meteo-Call je DE-Radarabfrage bei Cache-Miss (Cache 5 min, `ForecastBudgetGate` greift). Cache-Eintrag traegt `convective_checked` mit. Ausgabetexte enthalten nur Daten, keine Handlungsempfehlungen.

## Acceptance Criteria

- **AC-1:** Given ein Ort in Deutschland, fuer den BrightSky Radar-Frames liefert und der Open-Meteo-Sidecar (best_match = ICON-D2) in einem Viertelstundenfenster Wettercode 95, 96 oder 99 meldet, When der Radar-Nowcast berechnet wird, Then ist der zugehoerige Radar-Frame `is_convective` (bei 96/99 zusaetzlich `hail`), die Radar-Alarmstufe Gewitter bzw. Hagel ist erreichbar und der Akut-Override (#1310) greift fuer diesen Ort.
  - Test: Frames aus der Fixture `radar_de_kurz.json`, Sidecar liefert Codes 95/96/99 fuer ein Fenster; Assertion auf `is_convective`/`hail` des passenden Frames, auf die abgeleitete Radar-Stufe und auf die Entscheidung des Akut-Override-Pfads. Frames ausserhalb des Sidecar-Fensters bleiben `False`.

- **AC-2:** Given ein DE-Ort mit BrightSky-Frames, When der Sidecar leer ist, vom `ForecastBudgetGate` gedrosselt wird oder einen Fehler wirft, Then meldet der Nowcast `convective_checked=False` (nie als "kein Gewitter" kaschiert, ADR-0018), die Ausgabe enthaelt "Storm check not available." und Niederschlagsmenge und Beginn bleiben unveraendert erhalten und werden nicht als "Daten nicht verfuegbar" markiert.
  - Test: drei Varianten (leerer Sidecar, Gate verweigert `allow`, Exception); jeweils `convective_checked is False`, Text enthaelt den Marker, `data_unavailable` bleibt `False`, `precip`/Onset gleich wie im Erfolgsfall.

- **AC-3:** Given ein DE-Ort, When BrightSky keine Frames liefert (leer oder Fehler) oder der Offline-Fixture-Modus aktiv ist, Then wird kein Sidecar-Abruf ausgeloest, und im Offline-Modus bleibt der Pfad netzfrei (`_fetch_brightsky` liefert `[]`).
  - Test: `_fetch_openmeteo_15` als Zaehler beobachtet (Aufrufzahl 0) bei leerer BrightSky-Antwort, bei Provider-Fehler und bei aktivem Offline-Schalter; keine Netzwerkzugriffe (`--disable-socket` bleibt gruen).

- **AC-4:** Given ein Radar-Ergebnis wurde bei ausgefallenem Sidecar (`convective_checked=False`) in den Radar-Cache geschrieben, When innerhalb der 5 Minuten TTL derselbe Ort erneut abgefragt wird (Cache-Treffer), Then meldet auch der Treffer `convective_checked=False` (nicht faelschlich `True`) — und dasselbe gilt fuer alle Regionen (DE, INCA, Korsika). Ein erfolgreich geprueftes Ergebnis wird als `True` bedient.
  - Test: zweimaliger `get_nowcast`-Aufruf je Region (DE mit BrightSky, INCA, Korsika) mit ausgefallenem Sidecar, zweiter Aufruf ohne neuen Provider-Call (Cache-Hit belegt); `convective_checked is False`. Gegenprobe mit erfolgreichem Sidecar: `True`. Direkttest `put`/`get` auf das Flag.

- **AC-5:** Given ein Nowcast-Ergebnis mit erkanntem Gewitter bzw. mit `convective_checked=False`, When Alarm und Briefing gerendert werden, Then stammen beide Aussagen aus demselben `NowcastResult`, der Alarm-Pfad meldet Gewitter/Hagel und die Renderer-Stelle mit dem `convective_checked`-Marker gibt bei `False` "Storm check not available." aus; es gibt keine kanalspezifische Sonderlogik, alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) sind gleichrangig.
  - Test: ein `NowcastResult` aus dem DE-Pfad wird durch den Alarm-Pfad und durch mindestens eine Renderer-Stelle (`convective_checked`-Marker) geschickt; Assertion auf Gewitter-Aussage bzw. Marker-Text; Inhalt ist rein Daten (keine Handlungsempfehlung).

- **AC-6:** Given zwei Nutzer mit Orten in unterschiedlichen DE-Zellen, When beide den Radar-Nowcast abrufen, Then leakt kein Nowcast-/Cache-Ergebnis zwischen Orten oder Nutzern: der Cache-Schluessel (Koordinate + Region-Bucket + Hoehe) bleibt unveraendert und der Ort mit Gewitter-Sidecar-Code beeinflusst den Ort ohne Code nicht.
  - Test: zwei Orte mit unterschiedlichem Sidecar-Ergebnis, nacheinander im selben Prozess mit geteiltem Cache abgefragt; Ort A `is_convective`, Ort B nicht und `convective_checked` je Ort korrekt; zusaetzlich zwei `user_id`-Werte am `ForecastBudgetGate`, ohne Vermischung.

- **AC-7:** Given die versionierte, gekuerzte, aufgezeichnete BrightSky-Antwort `tests/fixtures/brightsky/radar_de_kurz.json` (Struktur wie Original, `latlon_position` auf das gekuerzte Fenster angepasst), When der BrightSky-Parser sie verarbeitet, Then entstehen daraus `RadarFrame`-Objekte mit korrekt umgerechnetem `precip_mm_h` (aus `precipitation_5`) und Zeitstempeln — netzfrei im Kern-Testlauf, ohne `@pytest.mark.live`.
  - Test: Parser laeuft auf der Fixture (Frame-Anzahl, Zeitstempel, `precip_mm_h` gegen von Hand nachgerechnete Werte einer bekannten Zelle); die Fixture-Datei ist kleiner als 1 MB.

## Known Limitations

- Der Sidecar liefert das Gewitter-Signal aus dem Modell (ICON-D2), nicht aus dem Radar selbst: das Radarbild bleibt Niederschlags-, nicht Blitzquelle. Die Aussage "Gewitter erkannt" ist dieselbe wie bei INCA und Korsika.
- Code 99 trat im 92-Tage-Rueckblick nicht auf; der Pfad ist ueber die Fixture-/Sidecar-Tests abgesichert, nicht ueber Live-Daten.
- Zusaetzlicher Open-Meteo-Verbrauch: +1 Call je DE-Radarabfrage bei Cache-Miss (TTL 5 min mildert). Das Gate greift; ein gedrosselter Sidecar wird als `convective_checked=False` gemeldet. Kein Sonderweg vorgesehen.
- `_within_radolan`/`_within_inca` ueberlappen an der AT-Grenze: RADOLAN/BrightSky wird zuerst versucht, nur bei leerer BrightSky-Antwort folgt INCA — Verhalten unveraendert.
- Der Gewitterfall in DE ist im Kern nur ueber Sidecar-Doubles an der Grenze zum Provider belegbar; die echte Kette wird zusaetzlich im Live-E2E (Staging) gemessen.

## Test-Politik

- **Kern (netzfrei, deterministisch):** `tests/tdd/test_radar_brightsky_convective_sidecar.py`, benannt nach Verhalten. Echte, aufgezeichnete Fixture statt Mock-Theater; nur die Aussengrenzen (BrightSky-Antwort, Open-Meteo-Sidecar-Antwort) werden aus Fixtures bzw. schmalen Doubles gespeist, der Kern (Merge, Flag-Uebernahme, Cache, Ableitung, Renderer) laeuft real.
- **Live-Schicht:** nur `/e2e-verify` gegen Staging; DE-Ort abfragen, Sidecar-Aufruf und `convective_checked` in Log/Antwort pruefen.
- **Mutations-Gegenprobe (Pflicht, per String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`):**
  1. Sidecar-Aufruf in `_fetch_brightsky` entfernen -> AC-1 muss rot werden.
  2. Zuweisung `self._convective_checked = False` im Sidecar-Fehlerzweig entfernen -> AC-2 muss rot werden.
  3. Cache-Flag ignorieren (Hit setzt `_convective_checked` nicht aus dem Eintrag) -> AC-4 muss rot werden (in allen drei Regionen).
  4. Sidecar auch ohne Frames rufen -> AC-3 muss rot werden.
  5. Region-Bucket aus dem Cache-Schluessel nehmen -> AC-6 muss rot werden.
  Es zaehlt, WELCHER Test rot wird; eine Mutation ohne roten Test ist ein Finding.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0018 (Provider-Fallback ohne Kaschieren) — keine neue Entscheidung
- **Rationale:** Der Sidecar folgt dem bestehenden Muster von INCA und Korsika. Ein gescheiterter Konvektions-Check wird nie als "kein Gewitter" gemeldet, sondern als `convective_checked=False`. Es aendert sich weder Kanalmodell noch Provider-Wahl, daher kein neues ADR.

## Changelog

- 2026-09-30: Initial spec created (Issue #2464)
