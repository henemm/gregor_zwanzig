# Decision Matrix — Wetterdaten-Provider (Ist-Stand)

> Stand: 2026-08-02. Ersetzt das MET/MOSMIX-Auswahlmodell der MVP-Ära
> (historisch: ADR-0002, superseded). Quelle der Wahrheit für Details ist der
> Code — dieses Dokument beschreibt nur die Auswahllogik und wo sie liegt.

## Standard-Provider: Open-Meteo

Alle Produktionspfade (Briefings, Orts-Vergleich, Alerts, Vorschau) holen
Wetterdaten über `get_provider("openmeteo")` — Registry in
`src/providers/base.py` (`_load_providers()`).

## Fallback-Kette (in dieser Reihenfolge)

| Stufe | Was | Wo im Code | Referenz |
|---|---|---|---|
| 1 | **Intra-Modell-Fallback** innerhalb Open-Meteo: regionale Modelle → gröbere Modelle, ohne den Ausfall zu kaschieren | `src/providers/openmeteo.py` (`REGIONAL_MODELS`) | ADR-0018, #1115 |
| 2 | **Cross-Provider-Fallback** bei Open-Meteo-Totalausfall: Koordinate → regionale Direktanbindung (AT → `at_direct`/GeoSphere, DE → `de_direct`/ICON-D2-Open-Data-Direktprovider (DWD), FR → `fr_direct`/AROME-WCS-Direktprovider (Météo-France); Prüfreihenfolge AT→DE→FR, Alpenraum fällt bewusst an AT) | `src/providers/region_routing.py` | Epic #1127, #1141, #1143, #1144 |

## Weitere registrierte Provider

| Name | Zweck |
|---|---|
| `geosphere` | GeoSphere Austria (Direktanbindung, AT-Fallback-Basis) |
| `fr_direct` | Météo-France AROME-WCS (Direktanbindung, FR-Fallback, #1143) — liefert seit #1457 S2a zusätzlich zu Temperatur/Wind/Niederschlag die erwartete Blitzdichte (`lightning_density_per_km2_3h`, nur Frankreich/Korsika; eigenes Feld, nicht mit dem DWD-Blitzpotenzial vermischt); Gewitter-Zuständigkeit läuft über eine eigene Tabelle, s. u. |
| `de_direct` | DWD ICON-D2 Open Data (GRIB2-Direktanbindung, DE-Fallback, #1144) |
| `brightsky` | DWD-Daten via BrightSky — genutzt im Radar-Pfad (`src/services/radar_service.py`) |
| `radar_dpc` | Radar-Nowcast Italien (DPC) — Wetter-Provider, kein Warndienst; nicht zu verwechseln mit der amtlichen DPC-Warnquelle `DpcSource` (`src/services/official_alerts/dpc.py`, Issue #1427), die nicht in dieser Tabelle geführt wird (s.u.) |
| `fixture` | Offline-Testmodus: aktiv wenn `GZ_TEST_FIXTURE_DIR` gesetzt (#346) — bedient `openmeteo`-Anfragen aus versionierten Fixtures |

Amtliche Warnquellen (`official_alerts`-Registry: GeoSphere, MeteoAlarm, DPC, Vigilance,
Météo des forêts, Massiv-Sperren) sind **nicht** Teil dieser Tabelle — sie sind kein
Wetter-Provider im Sinne von `get_provider()`, sondern ein eigenständiges,
länderneutrales Warnungs-System. Details: `docs/features/epic-1073-alerts-at-it.md`.

## Gewitter-Zuständigkeit: eigene Tabelle, getrennt von der Grundvorhersage (#1457 S2a)

Seit #1457 S2a gibt es **zwei** Zuständigkeitstabellen, und das ist Absicht:

| Tabelle | Zweck | Datei |
|---|---|---|
| `region_routing.direct_provider_for` | Zuständigkeit für die **Grundvorhersage** (Temperatur/Wind/Schnee) im Cross-Provider-Fallback | `src/providers/region_routing.py` |
| `thunder_routing.thunder_provider_for` | Zuständigkeit für **Gewittersignale** (`lightning_density_per_km2_3h`) | `src/providers/thunder_routing.py` |

Grund für die Trennung: Die Zuständigkeit ist **größenabhängig** — ein Dienst
kann für Temperatur/Wind/Schnee die beste Quelle sein und trotzdem kein
Gewittersignal führen. Konkreter Zielfall (S2b): Österreich bekommt Schnee/
Temperatur von GeoSphere (`at_direct`), Gewitter aber vom DWD, weil GeoSphere
kein Blitzsignal liefert — beide Tabellen zeigen für denselben Ort dann auf
**verschiedene** Quellen. Verwandtes Muster: ADR-0041 (Zuständigkeit einer
Warn-Quelle wird nach Endpunkt-Art bestimmt).

Der Anschluss ans Datenmodell (`providers/thunder_enrichment.py::enrich_thunder`)
liegt im **regulären** Rückgabeweg von `OpenMeteoProvider.fetch_forecast`
(nicht nur im Totalausfall-Fall) und kennt keinen Providernamen — er schlägt
nur in `thunder_routing.py` nach und ruft das optionale Protokoll
`ThunderSignalProvider` (`src/providers/base.py`). Ein neuer Dienst wird
wirksam, indem er das Protokoll erfüllt und eine Zeile in `thunder_routing.py`
bekommt; die Anreicherungsstelle wird dabei nie angefasst. Heute trägt die
Tabelle nur `fr_direct` (Frankreich/Korsika) ein; S2b (DWD) und S2c
(Lückenfüller) ergänzen weitere Zeilen. Fehlt ein Wert, bleibt das Feld
`None` — „keine Aussage" ist nicht „keine Gefahr".

## Kontingent-Regeln (Open-Meteo)

Der Radar-Pfad dominiert den API-Verbrauch (#1329): geteilter Forecast-Cache +
Budget-/Prioritätssteuerung sind aktiv. Bei Änderungen an Abruf-Pfaden immer
den Kontingent-Effekt mitdenken; Verbrauchslog: `openmeteo_calls.jsonl`
(erfasst den Radar-Pfad NICHT).

## Kontingent-Regeln (Météo-France)

Rate-Limit **100 Anfragen/Minute pro API und pro Benutzerkonto** (seit Januar
2026, vorher 50/min; bei Überschreitung HTTP 429) — vom PO 2026-08-02 aus dem
Météo-France-Portal bestätigt. Wir haben genau **ein** Konto, das sich alle
Trips und Ortsvergleiche aller Nutzer teilen.

Für Gewittersignale (#1457 S2a) mildert ein geteilter Zwischenspeicher
`providers/thunder_window_cache.py` (Prozess-Singleton, Kachelgitter, TTL
600s, Deckel 48 Einträge/32 MiB) das Problem: Ein Abruf lädt ein Rechteck,
jeder weitere Ort darin wird daraus bedient — ein 8-Orte-Vergleich sinkt von
192 auf 24 Abrufe. Das hilft aber nur bei **Überlappung** innerhalb desselben
Gebiets; verstreute Nutzer (Korsika, Pyrenäen, Alpen gleichzeitig) addieren
sich weiterhin gebietsweise.

**Zwei bekannte Lücken, noch nicht gebaut (Folge-Scheibe):**
- Der Zwischenspeicher bündelt **gleichzeitige** Abrufe nicht — zwei Threads,
  die dieselbe Kachel anfordern, laden beide. Heute folgenlos, weil alle
  Aufrufer (Trip wie Ortsvergleich) sequentiell laufen; wird relevant, sobald
  der Alarm-Lauf parallelisiert wird.
- Es fehlt eine **aktive Drosselung**, die Abrufe je Minute zählt und wartet
  (Muster: `telegram.py` Sende-Drossel), statt auf Einhaltung zu hoffen —
  sonst erscheinen HTTP-429-Abweisungen im Betrieb als „keine Gewitterdaten
  verfügbar".

## Historie

- MET Norway / MOSMIX (MVP-Auswahlmodell mit Distanz-/Höhen-Gate): entfernt,
  siehe ADR-0002 (superseded) und Git-Historie dieses Dokuments.
- Metrik-Mapping der Provider: steht im jeweiligen Provider-Modul
  (`src/providers/*.py`), nicht mehr in separater Prosa-Referenz.
