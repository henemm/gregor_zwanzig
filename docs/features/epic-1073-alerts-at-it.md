# Epic 1073: Amtliche Warnungen für Österreich & Italien + querschnittliche Nutzung

**Status:** Geplant (2026-07-07). Baut direkt auf Epic #1033 (amtliche Alerts Frankreich) auf.
**Priorität:** hoch.

## Ausgangslage

Epic #1033 hat ein **steckbares, länderneutrales Warnquellen-System** geschaffen:
`OfficialAlertSource`-Protocol + Registry (`src/services/official_alerts/`), Datentyp `OfficialAlert`
(source/hazard/level/label/region_label), `get_official_alerts_for_location(lat, lon)` mit
Fail-soft pro Quelle. Frankreich ist über drei Quellen abgedeckt (Vigilance, Météo des forêts,
Massiv-Sperren). Damit ist die **Architektur-Anforderung von #1073 Punkt 6 bereits erfüllt** — neue
Länder = neue Quellen im selben Registry, kein Fundament-Umbau.

**Aktueller Konsum:** Warnungen fließen bisher nur in den **Orts-Vergleich** (`comparison_engine`,
Compare-Renderer) und den Scheduler-Versand. **Trip-Briefings und der Alert-Pfad konsumieren sie
noch nicht** — das ist die zentrale Neuarbeit von #1073 (Verkabelung, nicht Fundament).

## API-Landschaft (verifiziert 2026-07-07)

| Quelle | Land | Zugang | Modell | Fit |
|---|---|---|---|---|
| **GeoSphere Warn API** | AT | auth-frei, CC-BY | REST/JSON, koordinatenbasiert (`getWarningsForCoords?lat=&lon=`) | ⭐ ideal für `fetch(lat,lon)`, keine Registrierung |
| **MeteoAlarm (MeteoGate/OGC-EDR)** | EU (AT+IT) | kostenlos, **Registrierung nötig** | REST/GeoJSON (kein MQTT nötig) | deckt IT + EU-weit in einer Quelle |
| Radar-DPC | IT | frei | WebSocket/Nowcast | → Punkt 5 (Nowcast), NICHT Warnungen |
| ARPA Veneto | IT (Veneto) | frei | regional | optional/später |

**Architektur-Leitentscheidung:** **Kein MQTT/WebSocket.** Gregor ist ein geplanter, pull-basierter
Report-Generator — Warnungen werden bei Report-Generierung abgeholt (wie die #1033-Quellen), keine
Dauerverbindungen. MeteoAlarm/DPC bieten Realtime via MQTT/WS, aber die REST-Pfade genügen und
vermeiden Betriebskomplexität.

## Slice-Schnitt

| Slice | Issue | Inhalt | #1073-Punkte | Abhängigkeit |
|---|---|---|---|---|
| 1 | #1085 | **GeoSphere-Warn-Quelle (AT)** — neue `OfficialAlertSource`, auth-frei, koordinatenbasiert; erscheint sofort im Orts-Vergleich | 1, 4 (AT) | #1033 |
| 2 | #1086 | **MeteoAlarm-Quelle (AT+IT)** — REST/GeoJSON via MeteoGate, deckt Italien + EU | 1, 4 (IT) | #1033 + MeteoGate-Reg. |
| 3 | #1087 | **Warnungen in Trip-Briefings + Trip-Ein-/Ausschalter** (analog #1040 ComparePreset→Trip) — querschnittliche Nutzung | 2, 6 | Slice 1/2 |
| 4 | #1088 | **Warnungen im Alert-Pfad** (trip_alert / radar_alert) | 3 | Slice 3 |
| 5 | #1089 | **Region-optimale Nowcasts** (AT=GeoSphere INCA, IT=Radar-DPC) für Gefahren/Regen/Gewitter | 5 | eigenes Subsystem |

**Reihenfolge-Empfehlung:** Slice 1 zuerst (auth-frei, schneller AT-Nutzen, beweist Länder-
Erweiterung end-to-end), parallel MeteoGate-Registrierung für Slice 2. Slice 5 (Nowcast) ist ein
anderes Subsystem (`radar_service`/Provider-Auswahl) — als eigenständiges Thema führen, ggf.
eigenes Folge-Epic.

## Betreiber-Voraussetzung (kein Code)

MeteoGate/MeteoAlarm-Account registrieren (für Slice 2) — analog zum Météo-France-Portal-Account
(#1043). Zeitnah anstoßen.

## Offene Punkte für die Slice-Analyse

- Warn-Level-Semantik von GeoSphere Warn + MeteoAlarm auf die `OfficialAlert.level`-Skala (1=grün…4=rot) mappen — je Quelle eigene Legende verifizieren (wie bei #1035 Vigilance und #1037 Massiv).
- GeoSphere-Warn-Antwort ist GeoJSON mit `properties` (Warn-Typ/Level) + Zonen-Geometrie — Struktur gegen Live-Antwort erschließen.
- Italien-Granularität: MeteoAlarm national vs. regional (ARPA) — für MVP national genügt.
- Trip-Toggle: eigenes Feld analog `ComparePreset.OfficialAlertsEnabled` (#1040) am Trip-/Briefing-Modell; Read-Modify-Write-Merge (Datenverlust-Regel).

## Changelog

| Datum | Änderung |
|---|---|
| 2026-07-07 | Epic geplant, API-Landschaft verifiziert (GeoSphere Warn auth-frei/koordinatenbasiert; MeteoAlarm REST via MeteoGate), 5 Slices geschnitten, Kein-MQTT-Leitentscheidung, Nowcast (Punkt 5) als eigenständiges Subsystem abgegrenzt. |
