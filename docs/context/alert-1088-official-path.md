# Context: alert-1088-official-path

## Request Summary
Issue #1088 (Epic #1073 Slice 4): Amtliche Warnungen (FR/AT/IT, Quelle `get_official_alerts_for_location`)
sollen zusätzlich zum bestehenden Alert-Pfad (`trip_alert.py` / `radar_alert_service.py`)
verfügbar werden — additiv zur bestehenden Wetter-Delta-Logik, mit eigenem Ein-/Ausschalter
analog zum Trip-Toggle aus Slice 3 (#1087). Offen ist, ob eine neu aufgetretene amtliche
Warnung selbst einen Alert-Versand auslöst oder nur mitgeschickt wird, wenn ohnehin schon
ein Wetter-Delta-Alert feuert.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py` | `get_official_alerts_for_location(lat, lon)` — reine, fail-soft Funktion, Quelle der amtlichen Warnungen (Registry-Pattern) |
| `src/services/official_alerts/__init__.py` | Registrierte Quellen: Vigilance, MeteoForets, MassifClosure, GeoSphereWarn (FR+AT) |
| `src/services/trip_alert.py` (997 Zeilen) | Zentraler Alert-Trigger: `check_and_send_alerts()` (Wetter-Delta-Pfad), `check_radar_alerts()` (Nowcast/Onset-Pfad), Gate-Kette (QuietHours → Throttle → Tageslimit → Change-Detection → alert_state-Filter → Versand) |
| `src/services/radar_alert_service.py` (101 Zeilen) | Reine Formatierungs-/Versand-Helfer für Radar-Onset-Alerts (`build_onset_alert_message`, `send_radar_alert_email`), keine eigene Trigger-Logik |
| `src/services/alert_preset.py` (247 Zeilen) | Preset-/Metrik-Schwellwert-Expansion (`expand_preset`, `expand_per_metric_levels`) → erzeugt `AlertRule`-Objekte für die Delta-Metriken. Amtliche Warnungen sind KEINE Metrik in `_PRESET_TABLE` — dieser Mechanismus passt nicht direkt für einen simplen Toggle |
| `src/services/alert_state.py` (69 Zeilen) | Melde-Gedächtnis pro Trip: `{"<metric>:<segment_id>": {"last_reported_value", "reported_at"}}`, verhindert Wiederholungs-Spam; Reset bei Briefing-Versand |
| `src/services/trip_report_scheduler.py:660-670` | Slice-3-Vorbild: ruft nach Wetter-Fetch `get_official_alerts_for_location()` pro eindeutigem Segment-Startpunkt ab, Toggle-gated |
| `src/output/renderers/alert/official_alerts.py` | Gemeinsamer Renderer (Slice 3) für Compare UND Trip — `render_official_alerts_html/_plain`, `collect_trip_alert_entries` |
| `src/app/models.py:405-406`, `src/app/loader.py:416,440,1097-1098` | Python-Trip-Modell: `official_alerts_enabled: bool | None` (Pointer-Semantik, RMW im Loader) |
| `internal/model/trip.go:106-109`, `internal/handler/trip.go:154,234-235` | Go-Pendant: `OfficialAlertsEnabled *bool`, Read-Modify-Write im Handler |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Checkbox „Amtliche Warnungen" im Trip-Alerts-Tab (Slice 3) |
| `docs/specs/modules/epic_1073_trip_official_alerts.md` | Spec zu Slice 3 — Vorbild für AC-Struktur |
| `docs/features/epic-1073-alerts-at-it.md` | Epic-Doku mit Slice-Tabelle und Architektur-Leitplanken |

## Existing Patterns
- **Registry-Pattern für Quellen** (`official_alerts/base.py`): `OfficialAlertSource`-Protocol,
  `register_official_alert_source()`, `get_official_alerts_for_location()` iteriert alle
  zuständigen Quellen fail-soft (Exception pro Quelle wird geloggt, nie geworfen). Bereits
  länderneutral — für Slice 4 keine neue Quelle nötig, nur ein neuer *Konsument*.
- **Gemeinsamer Renderer statt Duplikat** (#1073 Punkt 6, in #1087 verankert): Compare und Trip
  nutzen denselben Renderer-Modul-Import. Für Slice 4 heißt das: Alert-Pfad sollte denselben
  `get_official_alerts_for_location`-Call und ggf. denselben Renderer-Baustein nutzen wie
  Compare/Trip-Briefing — kein eigener Fetch-/Format-Code.
  **Nebenbefund:** `radar_alert_service.py` (Onset-Nachrichten) hat aktuell KEINE Anbindung an
  offizielle Warnungen und keinen eigenen Renderer-Reuse — bei Einbindung dort prüfen, ob der
  gemeinsame Renderer wiederverwendbar ist oder ein separater Kurztext (Alert-Format ist knapper
  als Trip-Briefing) nötig ist.
- **Trip-Toggle-Pattern** (Slice 3, #1087): `*bool`-Pointer-Feld `official_alerts_enabled`
  (Default `true`), Go-Handler macht Read-Modify-Write-Merge (`if req.X != nil { existing.X = req.X }`),
  Python-Loader prüft `is not None`. Slice 4 soll „analog Slice-3-Toggle" ein Pendant für den
  Alert-Pfad einführen — vermutlich ein zusätzliches Feld (z. B. am Alert-Preset/Trip-Alert-Config),
  NICHT einfach denselben `official_alerts_enabled` wiederverwenden, da Briefing-Anzeige und
  Alert-Versand konzeptionell getrennte Schalter sind (Trip-Briefing zeigt an, Alert löst aktiv
  Versand aus) — das muss die Analyse-Phase festlegen.
- **Alert-Melde-Gedächtnis** (`alert_state.py`): generischer `<key>: {last_reported_value, reported_at}`-
  Store, aktuell nur für numerische Metrik-Deltas genutzt (Key `<metric>:<segment_id>`). Für
  amtliche Warnungen wäre ein analoger Key denkbar (z. B. `official_alert:<segment_id>:<hazard>`),
  um Wiederholungs-Spam bei unverändert aktiver Warnung zu vermeiden — aber `last_reported_value`
  ist float-typisiert, amtliche Warnungen haben kein numerisches Delta-Maß, sondern einen
  Level/Hazard-Zustand. Das Schema müsste erweitert oder ein Parallel-Store eingeführt werden.
- **Alert = Abweichungs-Wächter** (Produkt-Prinzip, siehe Projekt-Memory): bestehende Alerts
  vergleichen Nowcast/Fresh-Weather gegen das letzte Briefing (Delta), NICHT gegen einen
  absoluten Schwellwert. Amtliche Warnungen sind aber ein absoluter Behörden-Zustand (Issue-Text:
  „additiv zur Delta-Logik"). Diese Spannung ist der Kern der offenen Designfrage unten.

## Dependencies
- **Upstream:** `services.official_alerts` (Slice 1/2 Quellen: FR live, AT/GeoSphere live seit
  #1085, IT/MeteoAlarm noch nicht — #1086 wartet auf MeteoGate-Registrierung). Slice 4 funktioniert
  bereits jetzt für FR+AT, IT kommt automatisch dazu sobald #1086 liefert (kein Code-Change nötig
  dank Registry).
- **Downstream:** Nichts hängt heute vom Alert-Pfad-Ergebnis ab außer dem E-Mail-/Telegram-Versand
  selbst (`_send_alert`) und dem Cockpit-Alarm-Log (`_append_alert_log`, Issue #393).

## Existing Specs
- `docs/specs/modules/epic_1073_trip_official_alerts.md` — Slice-3-Spec (Vorbild für AC-Format,
  RMW-Anforderung, Fail-soft-Anforderung).
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — Registry-Fundament.
- `docs/specs/modules/issue_816_alert_deviation_core.md` — Alert-Melde-Gedächtnis (`alert_state.py`).
- Kein existierender Spec für den Alert-Pfad-Trigger-Mechanismus selbst (`trip_alert.py` ist über
  viele Issues gewachsen: #638, #816, #846, #946, #961, #1070 — keine einzelne SSOT-Spec).

## Risks & Considerations
- **Fail-soft Pflicht (AC-3 im Issue):** `get_official_alerts_for_location` wirft nie, aber der
  NEUE Aufrufer-Code im Alert-Pfad muss selbst auch fail-soft sein (Netzwerk-Timeout einer Quelle
  darf den Alert-Zyklus für alle Trips nicht abbrechen) — Vorbild: try/except-Pattern in
  `trip_report_scheduler.py`.
- **Read-Modify-Write-Pflicht** bei jeder Persistenz-Änderung an Trip-/Alert-Preset-Feldern
  (CLAUDE.md-Regel, Hintergrund BUG-DATALOSS-GR221/#102) — gilt für ein neues Toggle-Feld genauso
  wie für Go- und Python-Seite.
- **Kein Doppel-Alert-Spam:** Wenn ein Wetter-Delta-Alert UND eine neue amtliche Warnung gleichzeitig
  auftreten, darf nicht zweimal versendet werden — Design muss festlegen, ob beides in EINEM Alert
  gebündelt wird (analog Compare/Trip-Briefing: ein Renderer-Block zusätzlich zu den Delta-Changes).
- **Mandantentrennung:** `AlertStateService(user_id=...)` ist bereits pro Nutzer isoliert — ein
  neuer Zustands-Key muss dieses Muster fortführen, nicht `"default"` fallbacken.
- **Testbarkeit:** CLAUDE.md verbietet gemockte API-/E-Mail-Tests — ein TDD-Test für „neue amtliche
  Warnung löst Alert aus" braucht einen echten `get_official_alerts_for_location`-Call (z. B. gegen
  eine Koordinate mit bekannter Massiv-Sperre/GeoSphere-Warnung) oder eine Fake-Quelle über die
  Registry (analog zum in Slice 1/#1085 und beim Onset-Alert-Feature genutzten Fake-Radar-Seam,
  siehe Projekt-Memory `reference_onset_preview_verification`).

## Offene Designfrage für Analyse-Phase
**Löst eine neu aufgetretene amtliche Warnung selbst einen Alert-Versand aus (aktiver Trigger,
Zustandsvergleich gegen ein erweitertes `alert_state.py`), oder wird sie nur additiv an einen
ohnehin schon (durch Wetter-Delta) ausgelösten Alert angehängt?**

Technische Fakten für die Entscheidung:
- Der bestehende Trigger-Mechanismus in `check_and_send_alerts()` basiert vollständig auf
  numerischen Deltas zwischen `cached_weather` und `fresh_weather` (`_detect_all_changes` →
  `_filter_significant_changes` → `_filter_against_alert_state`). Amtliche Warnungen haben
  keinen "cached vs. fresh"-Vergleichspunkt in diesem Sinn — sie sind ein aktueller Zustand
  einer externen Quelle, kein Delta zwischen zwei eigenen Messungen.
- `alert_state.py` ist strukturell erweiterbar (generisches `dict[str, {last_reported_value, reported_at}]`),
  aber `last_reported_value` ist auf `float` ausgelegt; für einen Warnungs-Zustand (z. B.
  Warnstufe 1–4 oder Hazard-Enum) wäre das Schema zumindest semantisch zweckzuentfremden oder zu
  erweitern (z. B. `last_reported_value` = numerischer Level, das funktioniert für GeoSphere/Vigilance
  bereits, da `OfficialAlert.level` numerisch 1–4 ist — ein reiner Trigger „neuer/höherer Level als
  zuletzt gemeldet" wäre technisch mit dem bestehenden Schema OHNE Strukturänderung möglich).
- Eigenständiger Trigger bedeutet: Alert-Zyklus muss `get_official_alerts_for_location()` für jeden
  Trip/jedes Segment ZUSÄTZLICH zum Wetter-Fetch aufrufen, auch wenn keine Wetter-Delta-Änderung
  vorliegt — zusätzliche Netzwerklast pro Check-Intervall (`check_all_trips()` läuft periodisch).
  Rein additiv (nur anhängen, wenn ohnehin schon ein Wetter-Alert feuert) bedeutet: kein
  zusätzlicher Trigger-Call nötig außerhalb des ohnehin laufenden Alert-Zyklus, aber eine neue
  amtliche Warnung an einem ansonsten wetter-stabilen Tag würde NIE gemeldet — das widerspricht
  dem Issue-Wortlaut „Ein Ort mit neu aufgetretener amtlicher Warnung erzeugt/ergänzt einen Alert"
  (AC-1 im Issue nennt ausdrücklich „erzeugt ODER ergänzt" — beide Fälle).
- Radar-Alert-Pfad (`check_radar_alerts()`) läuft mit kürzerem Cooldown (120 Min Default) als der
  Wetter-Delta-Pfad — falls der eigenständige Trigger dort andockt, ist die Versand-Frequenz höher
  als beim Trip-Briefing-Zyklus.

## Analysis

### Type
Feature (Slice 4 von Epic #1073).

### Produktentscheidungen (PO 'go', 2026-07-08)
1. **Eigenständiger Trigger:** Eine neu aufgetretene oder gestiegene amtliche Warnstufe löst
   für sich einen Alert-Versand aus — auch wenn das Wetter selbst stabil ist und sonst kein
   Wetter-Delta-Alert feuern würde. Jeder periodische Alert-Check-Zyklus fragt zusätzlich
   `get_official_alerts_for_location()` ab. Erfüllt AC-1 im Issue wörtlich ("erzeugt ODER
   ergänzt").
2. **Zwei getrennte Checkboxen:** Die bestehende Checkbox „Amtliche Warnungen" im Alerts-Tab
   (`official_alerts_enabled`, Slice 3) bleibt unverändert zuständig für die Briefing-Anzeige.
   Eine NEUE, eigene Checkbox kommt dazu, die ausschließlich den Sofort-Alert-Ausläser steuert.
   Beide leben auf der Alerts-Konfigurationsseite (`AlertsTab.svelte`), architektonisch getrennt
   von der Trip-Content-Konfiguration.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_state.py` | MODIFY | Neuer Key-Namespace für amtliche Warnungen (z. B. `official_alert:<segment_id>:<hazard>`), `last_reported_value` = numerischer Level (passt ins bestehende Float-Schema, keine Strukturänderung nötig) |
| `src/services/trip_alert.py` | MODIFY | Neue Methode (analog `check_radar_alerts`) die pro Trip/Segment `get_official_alerts_for_location()` abfragt, gegen `alert_state` vergleicht (neu/höherer Level als zuletzt gemeldet) und `_send_alert` auslöst; Einbindung in `check_all_trips()`; fail-soft try/except pro Quelle |
| `src/app/models.py` | MODIFY | Neues Feld für den Alert-Ausläser-Toggle (z. B. `official_alert_warnings_enabled: bool \| None`, Pointer-Semantik analog `official_alerts_enabled`) |
| `src/app/loader.py` | MODIFY | Read-Modify-Write-Merge für das neue Feld (analog Zeilen 416/440/1097-1098 für `official_alerts_enabled`) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | MODIFY | Neue, eigene Checkbox für den Alert-Ausläser-Toggle, eigener Auto-Save-Pfad (analog `buildOfficialAlertsSaveFn`) |
| `src/output/renderers/alert/official_alerts.py` | MODIFY (ggf.) | Prüfen ob gemeinsamer Renderer für den kompakten Alert-Text wiederverwendbar ist oder ein separater Kurztext nötig ist |
| Tests (neu) | CREATE | Reproduktion mit echtem `get_official_alerts_for_location`-Call gegen bekannte Warnlage (z. B. GeoSphere-Testkoordinate) oder Fake-Quelle über die Registry |

### Scope Assessment
- Files: ~7 (5 MODIFY im Kern, 1 optional, 1+ neue Testdatei(en))
- Estimated LoC: +80/-10 (Standard-Track-Rahmen, unter dem 250-LoC-Workflow-Limit)
- Risk Level: MEDIUM (Alert-Versand-Pfad, betrifft Nutzer-Benachrichtigungen, aber additiv zu bestehender Logik, kein Breaking Change)

### Technical Approach
Neue Methode in `TripAlertService` (analog `check_radar_alerts`), die pro Trip mit aktivem
Toggle die amtlichen Warnungen für jeden eindeutigen Segment-Startpunkt abruft, den Level pro
`(segment_id, hazard)`-Key gegen `alert_state` vergleicht und bei neu/gestiegen einen Alert
versendet (ggf. gebündelt mit einem zeitgleich laufenden Wetter-Delta-Alert, um Doppel-Spam zu
vermeiden — Bündelungslogik in `_send_alert`/`check_all_trips` verankern). Wiederverwendung des
Registry-Fetches und, wo möglich, des gemeinsamen Renderers aus Slice 3.

### Dependencies
Siehe oben (`services.official_alerts` Registry; FR+AT sofort nutzbar, IT folgt automatisch mit #1086).

### Open Questions
Keine offenen Fragen mehr — beide Design-Entscheidungen sind mit dem PO geklärt (s.o.).
