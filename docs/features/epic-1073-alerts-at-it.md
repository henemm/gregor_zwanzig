# Epic 1073: Amtliche Warnungen für Österreich & Italien + querschnittliche Nutzung

**Status:** Geplant (2026-07-07); Slice 1 (#1085), Slice 3 (#1087) und Slice 4 (#1088)
implementiert; Slice 5 (#1089) über die Kind-Issues #1161 (AT) und #1162 (IT) inhaltlich
umgesetzt, Epic-Issue #1089 selbst zum Zeitpunkt dieser Doku noch offen (siehe Slice-Tabelle).
Baut direkt auf Epic #1033 (amtliche Alerts Frankreich) auf.
**Priorität:** hoch.

## Ausgangslage

Epic #1033 hat ein **steckbares, länderneutrales Warnquellen-System** geschaffen:
`OfficialAlertSource`-Protocol + Registry (`src/services/official_alerts/`), Datentyp `OfficialAlert`
(source/hazard/level/label/region_label), `get_official_alerts_for_location(lat, lon)` mit
Fail-soft pro Quelle. Frankreich ist über drei Quellen abgedeckt (Vigilance, Météo des forêts,
Massiv-Sperren). Damit ist die **Architektur-Anforderung von #1073 Punkt 6 bereits erfüllt** — neue
Länder = neue Quellen im selben Registry, kein Fundament-Umbau.

**Aktueller Konsum (im Code verifiziert 2026-07-07):** Das Datenfundament ist konsum-neutral
(`get_official_alerts_for_location(lat, lon)` = reine Funktion Koordinaten→Warnliste, ohne
Aufrufer-Wissen). **Der tatsächliche Konsum + die Darstellung sind aber Compare-gekoppelt:** das
Feld `official_alerts` hängt nur am Compare-DTO `LocationResult`, die Badge-Darstellung lebt nur in
den Compare-Renderern (`compare_html.py`/`comparison.py`), der Trip-Briefing-Pfad ruft die
Warnungen gar nicht ab. **Folge:** die bestehenden Météo-France-Quellen sind de facto nur im
Orts-Vergleich verfügbar, nicht in Trips.

**Architektur-Leitplanke für Slice 3 (#1087, #1073 Punkt 6 — kein Duplikat):** Die Trip-Verkabelung
muss (a) das Alerts-Datenfeld auf eine allgemeinere Orts-/Etappen-Abstraktion heben und (b) eine
**gemeinsame Warn-Render-Komponente** herauslösen, die Compare UND Trip-Briefing nutzen — nicht die
Compare-Darstellung in den Trip-Renderer kopieren. Damit landen die bestehenden FR-Quellen
automatisch auch in Trips (als verbindliches AC in #1087 verankert).

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
| 1 | #1085 | **GeoSphere-Warn-Quelle (AT)** — neue `OfficialAlertSource`, auth-frei, koordinatenbasiert; erscheint sofort im Orts-Vergleich — **implementiert 2026-07-08** | 1, 4 (AT) | #1033 |
| 2 | #1086 | **MeteoAlarm-Quelle (AT+IT)** — REST/GeoJSON via MeteoGate, deckt Italien + EU | 1, 4 (IT) | #1033 + MeteoGate-Reg. |
| 3 | #1087 | **Warnungen in Trip-Briefings + Trip-Ein-/Ausschalter** (analog #1040 ComparePreset→Trip) — querschnittliche Nutzung — **implementiert 2026-07-07** | 2, 6 | Slice 1/2 |
| 4 | #1088 | **Warnungen im Alert-Pfad** (trip_alert; radar_alert bewusst ausgeklammert, s. Known Limitations) — **implementiert 2026-07-08** | 3 | Slice 3 |
| 5 | #1089 | **Region-optimale Nowcasts** (AT=GeoSphere INCA, IT=Radar-DPC) für Gefahren/Regen/Gewitter — AT-Teil via #1161 implementiert 2026-07-08, IT-Teil via #1162 implementiert 2026-07-09 | 5 | eigenes Subsystem |

**Reihenfolge-Empfehlung:** Slice 1 zuerst (auth-frei, schneller AT-Nutzen, beweist Länder-
Erweiterung end-to-end), parallel MeteoGate-Registrierung für Slice 2. Slice 5 (Nowcast) ist ein
anderes Subsystem (`radar_service`/Provider-Auswahl) — als eigenständiges Thema führen, ggf.
eigenes Folge-Epic.

### Slice 1: GeoSphere-Warn-Quelle für Österreich (Issue #1085) — implementiert 2026-07-08

Erste Nicht-Frankreich-Quelle im Registry-Muster von Epic #1033: `GeoSphereWarnSource`
(`src/services/official_alerts/geosphere_warn.py`, registriert in
`src/services/official_alerts/__init__.py`). Ruft die GeoSphere-`wsapp`-API
`getWarningsForCoords` **auth-frei und koordinatenbasiert** ab (kein Département-/Zonen-Mapping
wie bei den FR-Quellen nötig). Mappt `warnstufeid` (1–3) auf die gemeinsame `OfficialAlert.level`-
Skala (2–4) und deckt 7 Warn-Typen ab. Cache pro Koordinate (300s Normalfall / 60s bei aktiver
Warnung), fail-soft wie alle Quellen des Registries. Spec:
`docs/specs/modules/issue_1085_geosphere_warn_source.md`.

### Slice 3: Warnungen in Trip-Briefings (Issue #1087) — implementiert 2026-07-07

Amtliche Warnungen (bisher nur im Orts-Vergleich, Epic #1033) sind jetzt querschnittlich auch in
Trip-Briefing-Mails verfügbar:

- **Gemeinsamer Renderer:** `src/output/renderers/alert/official_alerts.py`
  (`render_official_alerts_html()`, `render_official_alerts_plain()`,
  `collect_trip_alert_entries()`) — von Compare (`compare_html.py`/`comparison.py`) UND Trip
  (`email/html.py`, `email/plain.py`, `email/compact.py`) genutzt, kein Duplikat-Code (#1073
  Punkt 6, Architektur-Leitplanke).
- **Datenanbindung:** `src/services/trip_report_scheduler.py` ruft nach dem Wetter-Fetch pro
  eindeutiger Etappen-Koordinate `get_official_alerts_for_location()` (#1033) ab und befüllt
  `SegmentWeatherData.official_alerts`.
- **Trip-Toggle:** `official_alerts_enabled` (Default `true`, Pointer-Muster analog
  `ComparePreset.OfficialAlertsEnabled` aus #1040) — Checkbox „Amtliche Warnungen" im
  Trip-Alerts-Tab (`AlertsTab.svelte`) und im Tab „Inhalt" (`WeatherMetricsTab.svelte`, Issue #1117); bei `false` findet strukturell kein Fetch statt.
- **Format-Parität:** `full` (HTML + Plain) und `compact` zeigen die Warnungen; `sms_trip.py`
  bewusst ohne Warn-Block (160-Zeichen-Limit).
- Spec: `docs/specs/modules/epic_1073_trip_official_alerts.md`.

### Slice 4: Amtliche Warnungen als eigenständiger Alert-Trigger (Issue #1088) — implementiert 2026-07-08

Amtliche Warnungen (Slice 3, #1087) lösen jetzt zusätzlich einen eigenständigen Sofort-Alert
aus — unabhängig davon, ob das Wetter selbst stabil ist bzw. ob überhaupt aktive
Wetter-Delta-Alert-Regeln konfiguriert sind:

- **Detektion:** `TripAlertService.check_official_alert_triggers()`
  (`src/services/trip_alert.py`) vergleicht die aktuellen Warnungen pro Trip gegen den
  zuletzt gemeldeten Stand in `alert_state.py` (Key `official_alert:<region_label>:<hazard>`,
  `level`-Vergleich) — neu oder gestiegen = Trigger, fail-soft pro Quelle.
- **Eigener Toggle:** `Trip.official_alert_triggers_enabled` — strukturell getrennt von der
  Slice-3-Briefing-Anzeige-Checkbox `official_alerts_enabled`. Zwei unabhängige Checkboxen im
  Alerts-Tab (`AlertsTab.svelte`).
- **Bündelung:** Feuert im selben Zyklus zusätzlich ein Wetter-Delta-Alert, wird die amtliche
  Warnung in derselben Nachricht angehängt (kein Doppel-Versand); ohne Wetter-Delta erfolgt ein
  eigenständiger Versand über `NotificationService.send_official_alert()`.
- **Kanal-Parität:** E-Mail und Telegram erhalten den Zusatztext, SMS bewusst nicht
  (Zeichenlimit, analog Slice-3-AC-6-Präzedenzfall).
- **Full-Stack-Toggle:** Go-Pendant `internal/model/trip.go::OfficialAlertTriggersEnabled` +
  RMW-Merge in `internal/handler/trip.go`, analog `OfficialAlertsEnabled` (#1087).
- Spec: `docs/specs/modules/issue_1088_alert_official_warnings.md`.

### Slice 5: Region-optimale Nowcasts (Issue #1089) — AT-Teil (#1161) implementiert 2026-07-08, IT-Teil (#1162) implementiert 2026-07-09

Eigenständiges Subsystem (Nowcast-/Radar-Provider-Auswahl, kein Bezug zum
`official_alerts`-Warnquellen-System der Slices 1–4). Beide Kind-Issues von #1089 sind
umgesetzt; das Epic-Issue #1089 selbst war zum Zeitpunkt dieser Doku noch offen:

- **AT (Issue #1161):** österreichische Orte nutzen für die Gewitter-/Hagel-Erkennung den
  GeoSphere-**INCA**-Nowcast statt der generischen Provider-Kette, inkl. Open-Meteo-Sidecar für
  das Konvektionsfeld (`convective_checked`-Flag, ADR-0018-konform bei Sidecar-Ausfall).
  Spec: `docs/specs/modules/issue_1161_inca_convective.md`.
- **IT (Issue #1162):** italienische Orte (inkl. Korsika, PO-Entscheidung — siehe unten) nutzen
  **Radar-DPC** (Protezione Civile) als reale Radarbeobachtung statt Modell-Downscaling
  (AROME-FR) bzw. globalem `minutely_15`-Fallback, ebenfalls mit Open-Meteo-Sidecar für die
  Konvektionserkennung. **PO-Entscheidung 2026-07-09:** Korsika wechselt von AROME-FR auf DPC,
  da die beiden BBoxen sich überlappen und geografisch nicht per Rechteck von Sardinien getrennt
  werden können — reale Radarbeobachtung hat Vorrang. Spec:
  `docs/specs/modules/issue_1162_radar_dpc.md`.

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
| 2026-07-07 | Slice 3 (#1087) implementiert: gemeinsame Warn-Render-Komponente `src/output/renderers/alert/official_alerts.py` (Compare + Trip), Trip-Fetch in `trip_report_scheduler.py`, Toggle `official_alerts_enabled` (Pointer-Muster, Default `true`). |
| 2026-07-08 | Slice 1 (#1085) implementiert: `GeoSphereWarnSource` (AT) — erste Nicht-FR-Quelle im Registry, auth-frei, koordinatenbasiert, `warnstufeid`→`level`-Mapping, Cache pro Koordinate. |
| 2026-07-08 | Dokumentation aktualisiert: Trip-Toggle „Amtliche Warnungen" ist zusätzlich im Tab „Inhalt" konfigurierbar (Issue #1117), nicht nur im Alerts-Tab. |
| 2026-07-08 | Slice 4 (#1088) implementiert: amtliche Warnungen als eigenständiger Alert-Trigger, additiv zur Wetter-Delta-Logik, eigener Toggle `official_alert_triggers_enabled`, Bündelung bei gleichzeitigem Wetter-Delta-Alert; radar_alert-Anbindung bewusst zurückgestellt. |
| 2026-07-08 | Slice 5 (#1089) AT-Teil implementiert: Issue #1161 (GeoSphere-INCA-Nowcast für Gewitter/Hagel in Österreich). |
| 2026-07-09 | Slice 5 (#1089) IT-Teil implementiert: Issue #1162 (Radar-DPC für Italien inkl. Korsika, PO-Entscheidung Korsika-Umstellung von AROME-FR). |
