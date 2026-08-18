---
entity_id: alarm_eingangsprotokoll
type: feature
created: 2026-08-17
updated: 2026-08-17
status: draft
workflow: feat-1948-eingangsprotokoll
version: "1.0"
tags: [alarm, observability, debug]
---

# Alarm-Eingangsprotokoll (Scheibe S1, Issue #1948)

## Approval

- [ ] Approved

## Purpose

Rollierendes Protokoll des ROHEN Eingangszustands jeder verarbeiteten Alarm-Meldung, für alle
drei Alarm-Zweige (a = Δ-Alarm, b = amtliche Warnung, c = Radar-Nowcast). Heute protokolliert
`alert_log.py` (#1459) nur die ENTSCHEIDUNG/den Versand — der Eingang, aus dem diese Entscheidung
entstand, wird nirgends festgehalten (PO-Befund: "der Eingangskanal wird schlicht nirgends
geloggt"). Diese Scheibe schließt genau diese Lücke als Begleit-Log und liefert damit erstens die
Beweisgrundlage, um künftige Format-Beschwerden nachzuvollziehen (Antwort auf Epic #1458 E6/B3),
und zweitens die Rohdaten-Quelle für Scheibe S2 (Testmeldungs-Einspeisung über `alert-preview`).

## Source

- **File:** `src/services/alert_input_capture.py` (NEU)
- **Identifier:** `def capture_user_scoped(...)`, `def capture_system(...)`, `def latest_capture_id(...)`

> Schicht: Python-Core (`src/services/`) — kein Go-/Frontend-Anteil in dieser Scheibe.

## Estimated Scope

- **LoC:** ~200-235 (produktiv; eng am 250-LoC-Ziel der Scheibe, Tests separat)
- **Files:** 5 Code-Dateien (1 neu, 4 geändert) + 6-8 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_log.py` (#1459) | module | Bekommt einen additiven, optionalen `capture_id`-Parameter in `append_entry`/`append_suppressed_entry` — Korrelations-Anker vom Entscheidungs-Eintrag zum Eingangs-Datensatz |
| `src/services/weather_snapshot.py::WeatherSnapshotService._prune_dated_snapshots` | module | Retention-Vorlage: Datei-je-Ereignis, `glob`-Muster, sortiert nach `st_mtime`, älteste zuerst gelöscht |
| `src/services/trip_alert.py` | module | Mount-Punkt Zweig a; Korrelations-Lookup für Zweig b/c an den bestehenden `alert_log`-Aufrufstellen |
| `src/services/official_alerts/warn_egress.py::cached_fetch` | module | Mount-Punkt Zweig b — geteilter HTTP-Layer aller amtlichen Warnquellen |
| `src/services/radar_service.py::RadarService.get_nowcast` | module | Mount-Punkt Zweig c |
| `app.loader.get_data_dir`/`VALID_USER_ID_RE` | module | Nutzerskopierte Ablage für Zweig a, gleiche `user_id`-Validierung wie bei `weather_snapshots` |

## Implementation Details

### Drei Mount-Punkte (verifiziert am Code, Stand 2026-08-17)

| Zweig | Mount-Punkt | Fundstelle | Skopiert? |
|---|---|---|---|
| **a — Δ-Alarm** | nach Aufbau der Änderungsliste `to_report` (nicht leer), vor `self._send_alert(...)` | `src/services/trip_alert.py`, ~Z. 333-352 | trip-/nutzerskopiert (`self._user_id`, `trip.id` liegen bereits vor) |
| **b — amtliche Warnung** | innerhalb `cached_fetch()`, an der bestehenden Ausführungsstelle des optionalen `on_response`-Hooks (nach dem echten, nicht gecachten HTTP-Response, vor `parse_fn`) | `src/services/official_alerts/warn_egress.py`, ~Z. 296-360 | **nicht** skopiert — `cached_fetch` ist ein geteilter, koordinaten-scoped Cache über 8 Provider (GeoSphere, MeteoAlarm, DPC, …), kein `user_id`/`trip_id` im Kontext |
| **c — Nowcast** | vor beiden Aufrufen von `self._derive_result(...)` in `get_nowcast()` (Cache-Hit-Zweig UND Cache-Miss-Zweig) | `src/services/radar_service.py`, Z. 199 und Z. 212 | **nicht** skopiert — `RadarService` cached nach `(lat, lon, region)`, kein `user_id`/`trip_id` im Kontext |

**Abweichung von der ursprünglichen Datei-Angabe (bewusst, mit Team-Lead abgestimmt):** Der Auftrag
nannte `geosphere_warn.py:99` als Mount-Punkt b. Die tatsächliche Naht liegt eine Ebene tiefer, in
`warn_egress.cached_fetch()` selbst — dort laufen GeoSphere, MeteoAlarm UND DPC bereits durch
dieselbe Funktion zusammen (`service`/`host`-Parameter je Aufrufer). Eine Mount-Stelle in
`cached_fetch()` deckt alle drei Quellen mit EINER Code-Änderung ab; eine Mount-Stelle in
`geosphere_warn.py` würde nur GeoSphere erfassen und müsste in `meteoalarm.py`/`dpc.py`/weiteren
Providern dupliziert werden — das widerspricht der "deckt GeoSphere+MeteoAlarm+DPC"-Vorgabe aus
dem Konzept (§8, S1-Zeile) und würde den Datei-/LoC-Rahmen sprengen. `official_alerts.py:1896-2104`
(#1929-Sperrzone) wird durch diese Wahl nicht berührt — die neue Stelle liegt strukturell VOR
diesem Code, im HTTP-Layer.

### Speicherorte (Nutzer- vs. System-Ablage)

- **Zweig a (nutzerskopiert):** `data/users/<user_id>/alert_input/forecast_change_<entity_type>_<entity_id>_<timestamp>.json`
  — `user_id` kommt IMMER aus `self._user_id` des aufrufenden `TripAlertService`, nie ein
  Default-Fallback (gleiche `VALID_USER_ID_RE`-Prüfung wie `get_data_dir`).
- **Zweig b/c (System-Ablage, außerhalb `data/users/`):** `data/debug/alert_input/official_alert/…json`
  bzw. `data/debug/alert_input/nowcast/…json`. **Begründung, warum das KEIN Verstoß gegen die
  Mandantentrennungs-Regel ist:** (1) der PO will explizit den API-Eingang selbst protokolliert
  haben — das ist die HTTP-/Cache-Naht, und die ist strukturell koordinaten-, nicht
  nutzerskopiert; (2) die Rohdaten an dieser Stelle (amtlicher Warndienst-Response, Radar-Rohframes)
  sind zu diesem Zeitpunkt KEINE Nutzerdaten — noch keinem Trip/User zugeordnet, keine
  Empfängerinformation, keine Trip-Namen enthalten; (3) ein Verschieben des Mount-Punkts auf die
  nutzerskopierte Ebene (z. B. erst nach der Trip-Zuordnung) würde genau den rohen Eingangszustand
  verlieren, den die Scheibe einfangen soll — die Cache-Wiederverwendung über mehrere Trips hinweg
  ginge dabei verloren oder würde dupliziert protokolliert.

### Korrelierbarkeit (Pflicht-AC-2, Tech-Lead-Entscheid)

- `alert_input_capture.py` generiert bei jedem Schreibvorgang eine `capture_id` (`uuid.uuid4().hex`,
  gleiches Muster wie `alert_preset.py`) und schreibt sie in den Datensatz.
- `alert_log.append_entry()`/`append_suppressed_entry()` bekommen einen neuen, additiven,
  optionalen Parameter `capture_id: Optional[str] = None` (Bestandsschutz: alte Aufrufer und alte
  Einträge bleiben unverändert, gleiche Additiv-Konvention wie `blocked_reason_codes`).
- **Zweig a:** direktes Durchreichen — `capture_id` entsteht und wird verbraucht in derselben
  Methode (`check_weather_alerts` in `trip_alert.py`), keine Zwischenschicht.
- **Zweig b/c:** kein Durchreichen durch mehrere Funktionsebenen (würde `official_alerts.py`
  und die Nowcast-Kette invasiv anfassen, teils in der #1929-Sperrzone). Stattdessen liefert
  `alert_input_capture.py` eine Lesefunktion `latest_capture_id(branch, source_key, *, max_age)`,
  die an der bestehenden `alert_log`-Aufrufstelle (Zweig b: `_send_official_alert_only`,
  `trip_alert.py` ~Z. 1735; Zweig c: analoge Nowcast-Aufrufstelle mit `reason=REASON_NOWCAST`)
  aus den dort bereits vorliegenden Koordinaten den passenden, jüngsten Eingangs-Datensatz
  nachschlägt (Zeitfenster = Cache-TTL des jeweiligen Zweigs). Bei Cache-Wiederverwendung durch
  mehrere Trips gleichzeitig können mehrere `alert_log`-Einträge korrekt auf dieselbe `capture_id`
  verweisen — das ist beabsichtigt, kein Fehler.

### Retention

Vorlage `WeatherSnapshotService._prune_dated_snapshots` (`weather_snapshot.py:165`): pro
Ablage-Verzeichnis (je Nutzer bei Zweig a, je Branch bei Zweig b/c) werden nach jedem Schreiben
alle `*.json`-Dateien nach `st_mtime` sortiert; alles über die neuesten **50** hinaus wird gelöscht.
50 statt der 7 aus der Vorlage, weil dieser Mitschnitt zweigübergreifend über mehrere Tage hinweg
zur Fehleranalyse dienen soll (PO-Vorgabe "schon mal Daten sammeln"), nicht wie der Wetter-Snapshot
nur den letzten Tagesvergleich sichert. Die Zahl ist eine begründete Anfangsschätzung, kein
PO-fixierter Wert.

### Fail-open

Jeder Mount-Punkt umschließt den Schreibaufruf mit `try/except Exception`, loggt einen
`logger.warning(...)` bei Fehlschlag und lässt den umgebenden Alarm-Fluss unverändert weiterlaufen
— gleiches Muster wie `alert_log._append()` (kaputte Datei killt keinen Alarm) und
`weather_snapshot.save_dated()` (Exception wird gefangen, Funktion kehrt früh zurück).

### Keine Secrets

Der Capture-Schreiber für Zweig b nimmt AUSSCHLIESSLICH den geparsten Response-Body plus
`service`/`host`/Status entgegen — Request-Objekt, Header und Auth-Parameter werden an der
Schreibstelle strukturell gar nicht erst übergeben (kein nachträglicher Filter nötig). Die
amtlichen Warndienste (GeoSphere/MeteoAlarm/DPC) übertragen laut bestehendem Code ohnehin keine
Zugangsdaten im Response-Body — die Ausschluss-Grenze liegt trotzdem an der Schnittstelle, nicht
als Vertrauen in die Quelle.

## Expected Behavior

- **Input:** interne Aufrufe aus den drei bestehenden Alarm-Zweigen (kein neuer externer Endpoint).
- **Output:** JSON-Dateien unter `data/users/<user_id>/alert_input/` (Zweig a) bzw.
  `data/debug/alert_input/<branch>/` (Zweig b/c); optionales `capture_id`-Feld in neuen
  `alert_log`-Einträgen.
- **Side effects:** Dateisystem-Schreibzugriffe (fail-open), Log-Zeilen bei Erfolg (`debug`) und
  Fehlschlag (`warning`). Kein Versandverhalten ändert sich — reines Beobachtungs-Feature.

## Test Plan

Deterministischer Kern, keine Mock-Theater (echte Fixture-Läufe, `tmp_path`, bestehende
Test-Seams wie `_frame_source`/`request_fn`-Injection statt `Mock()`/`patch()`). Testdateien nach
Verhalten benannt, nicht nach Issue-Nummer.

### Automated Tests (TDD RED)

- [ ] `tests/unit/test_trip_alert_forecast_change_capture.py` — Zweig-a-Mount schreibt vor
  `_send_alert` einen Eingangs-Datensatz mit den rohen Change-Werten. → AC-1
- [ ] `tests/unit/test_warn_egress_capture.py` — `cached_fetch` schreibt bei echter (nicht
  gecachter) Antwort einen System-Level-Datensatz mit rohem Body + Service/Host/Cache-Key. → AC-2
- [ ] `tests/unit/test_radar_service_capture.py` — `get_nowcast` schreibt vor `_derive_result`
  (Cache-Hit UND Cache-Miss) einen Datensatz mit den rohen Frames. → AC-3
- [ ] `tests/unit/test_alert_log_capture_correlation.py` — `alert_log.append_entry`/
  `append_suppressed_entry` mit `capture_id` schreiben das Feld; Alt-Einträge ohne das Feld
  bleiben unverändert lesbar (Bestandsschutz). → AC-4
- [ ] `tests/unit/test_alert_input_capture_retention.py` — bei >50 Dateien in einem
  Ablage-Verzeichnis werden die ältesten bis auf 50 gelöscht (sortiert nach `st_mtime`). → AC-5
- [ ] `tests/unit/test_alert_input_capture_tenancy.py` — zwei verschiedene `user_id`-Werte
  erzeugen getrennte Verzeichnisse; kein `"default"`-Fallback in der Signatur möglich. → AC-6
- [ ] `tests/unit/test_warn_egress_capture_no_secrets.py` — Header/Auth-Parameter werden der
  Capture-Funktion strukturell nicht übergeben, landen daher nie in der Datei. → AC-7
- [ ] `tests/unit/test_alert_input_capture_failopen.py` — ein fehlschlagender Schreibvorgang
  (z. B. unschreibbares `tmp_path`-Verzeichnis) verhindert den Alarmversand NICHT, erzeugt nur
  eine Log-Warnung, keine Exception nach oben. → AC-8
- [ ] `tests/unit/test_alert_input_capture_payload_schema.py` — Feldnamen/-typen des
  Zweig-a-Datensatzes gegen `ChangePayload`/`SegmentTimePayload` (`api/routers/validator.py`)
  abgeglichen (Schema-/Attributvergleich, kein Dateiinhalt-Stringcheck). → AC-9

## Acceptance Criteria

- **AC-1:** Given ein Trip löst einen Δ-Alarm mit mindestens einer berichtenswerten Änderung aus, When `check_weather_alerts` die Änderungsliste gebildet hat und bevor `_send_alert` aufgerufen wird, Then liegt unter `data/users/<user_id>/alert_input/` ein Eingangs-Datensatz mit den rohen Änderungswerten (Metrik, alter/neuer Wert, Delta, Schwelle je Änderung).
  - Test: echter Trip-Fixture-Lauf mit injiziertem `DeviationAlertEngine`-Ergebnis, Prüfung des tatsächlich geschriebenen Datei-Inhalts (kein Mock der Schreibfunktion selbst).

- **AC-2:** Given ein amtlicher Warndienst wird über `warn_egress.cached_fetch` mit einer echten, nicht gecachten Antwort abgefragt, When die Antwort erfolgreich geparst wird, Then liegt ein System-Level-Eingangs-Datensatz mit dem rohen Response-Body sowie Service/Host/Cache-Key unter `data/debug/alert_input/official_alert/` — unabhängig davon, ob daraus später eine Warnung für irgendeinen Trip entsteht.
  - Test: `cached_fetch` mit injiziertem `request_fn` (bestehendes Test-Seam) gegen eine reale Fixture-Antwort aufrufen, Datei-Inhalt gegen die Fixture prüfen.

- **AC-3:** Given `RadarService.get_nowcast` liefert Frames aus einem Cache-Hit oder einem frischen Abruf, When die Methode `_derive_result` aufruft, Then existiert vorher ein System-Level-Eingangs-Datensatz mit denselben rohen Frames und der Quelle unter `data/debug/alert_input/nowcast/`.
  - Test: `get_nowcast` mit injizierter `_frame_source` (bestehendes DI-Seam) für Cache-Hit UND Cache-Miss aufrufen, je einen Datensatz nachweisen.

- **AC-4:** Given ein Eingangs-Datensatz wurde für eine später tatsächlich verschickte Alarm-Meldung erzeugt, When der zugehörige `alert_log`-Eintrag geschrieben wird, Then trägt dieser Eintrag ein `capture_id`-Feld, das auf genau diesen Eingangs-Datensatz verweist (Zweig a: direkt durchgereicht; Zweig b/c: über `latest_capture_id`-Lookup nach Branch, Quell-Schlüssel und Zeitfenster).
  - Test: End-to-End innerhalb eines Zweigs (kein Cross-Branch) — geschriebener `alert_log`-Eintrag und der zuvor erzeugte Eingangs-Datensatz teilen dieselbe `capture_id`.

- **AC-5:** Given mehr als 50 Eingangs-Datensätze liegen bereits in einem Ablage-Verzeichnis, When ein weiterer Datensatz in diesem Verzeichnis geschrieben wird, Then werden die ältesten Datensätze über die Grenze von 50 hinaus gelöscht (sortiert nach Änderungszeit, gleiche Mechanik wie `_prune_dated_snapshots`).
  - Test: 55 reale Dateien in einem `tmp_path`-Verzeichnis vorbereiten, einen Schreibvorgang auslösen, genau 50 verbleibende, jüngste Dateien nachweisen.

- **AC-6:** Given zwei verschiedene Nutzer A und B lösen unabhängig voneinander je einen Δ-Alarm für ihren eigenen Trip aus, When beide Eingangs-Datensätze geschrieben werden, Then liegt der Datensatz von A ausschließlich unter `data/users/<user_id_A>/alert_input/` und der von B ausschließlich unter `data/users/<user_id_B>/alert_input/`, und an keiner Aufrufstelle wird `"default"` als `user_id` verwendet.
  - Test: zwei vollständig unterschiedliche `user_id`-Werte durch denselben Code-Pfad schicken, Verzeichnistrennung UND Signatur (Pflichtparameter ohne Default) nachweisen.

- **AC-7:** Given ein Eingangs-Datensatz für Zweig b wird geschrieben, When der Datensatz anschließend gelesen wird, Then enthält er ausschließlich den geparsten Response-Body sowie Service/Host/Status — keine Request-Header, keine Auth-Parameter, kein API-Schlüssel, weil diese der Schreibfunktion strukturell gar nicht übergeben werden.
  - Test: Signatur-/Verhaltenstest — Aufruf der Capture-Funktion mit einem Response-Objekt, das (testweise) einen Header trägt; Nachweis, dass der Header nicht in der geschriebenen Datei landet, weil die Funktion ihn nicht entgegennimmt.

- **AC-8:** Given das Schreiben eines Eingangs-Datensatzes schlägt fehl (z. B. nicht beschreibbares Zielverzeichnis), When der jeweilige Alarm-Zweig weiterläuft, Then wird der Alarm trotzdem wie gewohnt verarbeitet und verschickt, und der Fehlschlag wird ausschließlich als Warnung geloggt, nie als Exception nach oben gereicht.
  - Test: Zielverzeichnis für den Schreibvorgang absichtlich unschreibbar machen (`tmp_path`-Verzeichnis mit entzogenen Schreibrechten oder injizierter Fehlerquelle), Alarmversand-Erfolg UND Log-Warnung gemeinsam nachweisen.

- **AC-9:** Given ein Eingangs-Datensatz für Zweig a, When seine Felder mit `ChangePayload`/`SegmentTimePayload` (`api/routers/validator.py`) verglichen werden, Then decken sie deren Pflichtfelder verlustfrei ab, sodass Scheibe S2 ihn ohne Transformation in `alert-preview` einspeisen kann; für Zweig c liegt am Mount-Punkt vor `_derive_result` nur der rohe Frame-Zustand vor (Feldabdeckung gegen `OnsetPayload` ist dokumentierte Limitation für S2, kein direktes 1:1-Mapping).
  - Test: Feldnamen/-typen des Zweig-a-Datensatzes gegen die Pydantic-Modelldefinition abgleichen (kein Dateiinhalt-Stringcheck, sondern Schema-/Attributvergleich).

## Known Limitations

- Zweig b und Zweig c sind an ihrem vorgegebenen Mount-Punkt strukturell NICHT trip-/
  nutzerskopiert (globaler Koordinaten-Cache) — Ablage bewusst außerhalb `data/users/`
  (Tech-Lead-Entscheid, Begründung siehe Implementation Details). AC-6 gilt daher nur für Zweig a.
- Korrelation für Zweig b/c ist ein Zeitfenster-/Schlüssel-Lookup, kein durch alle Zwischenschichten
  durchgereichtes Argument — bei gleichzeitiger Cache-Nutzung durch mehrere Trips können mehrere
  `alert_log`-Einträge korrekt auf dieselbe `capture_id` verweisen.
- **Zweig-b-Korrelation ist in S1 zurückgestellt (PO-gebilligt, GREEN-Freigabe 2026-08-18):** Der
  Mitschnitt für Zweig b funktioniert vollständig, aber der `alert_log`-Eintrag amtlicher Warnungen
  trägt KEINE `capture_id` — an der Aufrufstelle `_send_official_alert_only` liegt keiner der fünf
  provider-spezifischen Cache-Schlüssel vor (`OfficialAlert`-Objekte tragen weder Rohkoordinaten
  noch `cache_key`), eine rekonstruierte Zuordnung würde meist ins Leere zeigen oder falsch
  verlinken. AC-4 gilt daher für Zweig a (direkt) und Zweig c (Lookup); Zweig b folgt als
  Folge-Ticket (z. B. `service`-Name als zweiter Lookup-Schlüssel in `capture_system`).
- Ortsvergleich (Compare) wird in dieser Scheibe NICHT eigens mitgeschnitten — nur was über
  dieselben geteilten Dienste (`warn_egress`, `RadarService`) ohnehin mitfällt. Ein
  Compare-eigener Δ-Alarm-Mount-Punkt (analog Zweig a) ist NICHT Teil dieser Scheibe — bewusster
  PO-Entscheid (Konzept, durchgehend zurückgestellt), kein Pendant-Verstoß und kein Versehen.
- Retention-Grenze (50 Dateien) ist eine begründete Anfangsschätzung, kein PO-fixierter Wert.
- `official_alerts.py:1896-2104` (#1929-Sperrzone) bleibt unangetastet.
- Diese Scheibe ändert KEIN sichtbares Alarm-Format (SMS/E-Mail/Telegram bleiben bit-identisch) —
  reines Beobachtungs-Feature für S1; die Format-Konsolidierung folgt in S3+.
- **Seit Scheibe S2 (#1948, `alarm_testeinspeisung.md`):** der Zweig-c-Mitschnitt trägt je Frame
  zusätzlich `is_convective` — Voraussetzung für den `nowcast_frames`-Replay über `alert-preview`
  (dort AC-8).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweitert zwei bereits etablierte, dokumentierte Muster additiv (JSON-Read-Modify-
  Write wie `alert_log.py`, Datei-Retention wie `weather_snapshot.py`) — keine neue
  Persistenztechnologie, keine neue externe Abhängigkeit, keine Rücknahme einer bestehenden
  Architekturentscheidung. Kein ADR-würdiger Grundsatzentscheid.

## Changelog

- 2026-08-17: Initial spec created (Scheibe S1 aus #1948, PO-Entscheidung Runde 4: "Debug zuerst").
