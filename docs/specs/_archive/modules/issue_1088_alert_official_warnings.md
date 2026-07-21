---
entity_id: issue_1088_alert_official_warnings
type: feature
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [trip-alert, alerts, official-alerts, epic-1073, epic-1073-slice-4]
workflow: alert-1088-official-path
---

# Amtliche Warnungen als eigenständiger Alert-Trigger (Epic #1073 Slice 4)

## Approval

- [ ] Approved (PO, ...)

## Purpose

Amtliche Warnungen (Vigilance, Météo des forêts, Massiv-Sperren, GeoSphere AT — Quelle
`get_official_alerts_for_location()`, Slice 3/#1087 bereits im Trip-Briefing sichtbar) lösen
heute **keinen** Sofort-Alert aus. Dieses Slice macht eine neu aufgetretene oder gestiegene
amtliche Warnstufe zu einem **eigenständigen Alert-Auslöser** — additiv zur bestehenden
Wetter-Delta-Logik, unabhängig davon ob das Wetter selbst stabil ist. Ein neuer, von der
Briefing-Anzeige-Checkbox (`official_alerts_enabled`, Slice 3) **strukturell getrennter**
Toggle (`official_alert_triggers_enabled`) steuert ausschließlich diesen Sofort-Alert-Auslöser.

## Source

- **File:** `src/services/trip_alert.py`, `src/services/notification_service.py`,
  `src/app/trip.py`, `src/app/loader.py`, `internal/model/trip.go`, `internal/handler/trip.go`,
  `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`
- **Identifier:** `TripAlertService.check_official_alert_triggers()` (neu),
  `TripAlertService.check_and_send_alerts(..., official_notices=...)` (erweitert),
  `NotificationService.send_deviation_alert(..., official_notices=...)` (erweitert),
  `NotificationService.send_official_alert()` (neu, Standalone-Fall),
  `Trip.official_alert_triggers_enabled`, `AlertStateService` (unverändert wiederverwendet)

> **Schicht-Hinweis:** Betroffen sind alle drei Schichten — Python-Core (`src/app/`,
> `src/services/`), Go-API (`internal/model/trip.go`, `internal/handler/trip.go`) und Frontend
> (`frontend/src/lib/components/alerts-tab/`). **Abweichung von der ursprünglichen
> Kontext-Annahme:** Anders als im Kontext-Dokument vermerkt ("kein Go-Pendant nötig, rein
> Python-seitig") zeigt die Code-Verifikation, dass `internal/model/trip.go` bereits mehrere
> alert-spezifische Felder führt (`AlertRules`, `AlertCooldownMinutes`, `AlertQuietFrom/To`,
> `OfficialAlertsEnabled` — alle mit RMW-Merge in `internal/handler/trip.go`). Der neue Toggle
> braucht daher **sehr wohl** ein Go-Pendant, exakt nach demselben Muster wie
> `OfficialAlertsEnabled` (#1087) — sonst kann der Wert über `PUT /api/trips/{id}` (den
> produktiven Speicherpfad des Frontends) gar nicht persistiert werden.

## Estimated Scope

- **LoC:** ~130–160 src (höher als die ursprüngliche Kontext-Schätzung von ~80/-10, da (a) das
  Go-Pendant zusätzlich MODIFY erfordert und (b) die Bündelungslogik in
  `notification_service.py` einen weiteren Berührungspunkt hat, der im Kontext-Dokument nicht
  vollständig erfasst war); Tests separat (echte Scheduler-/Fake-Quelle-Läufe, potenziell
  umfangreich wie bei Slice 3 AC-1/AC-3)
- **Files:** 8 MODIFY (kein CREATE) + 1+ neue Testdatei(en):
  `src/services/trip_alert.py`, `src/services/notification_service.py`, `src/app/trip.py`,
  `src/app/loader.py`, `internal/model/trip.go`, `internal/handler/trip.go`,
  `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`,
  `frontend/src/lib/types.ts` (Trip-Interface-Ergänzung)
- **Effort:** high (Alert-Versand-Pfad mit mehreren Gate-Interaktionen, Full-Stack-Toggle,
  Bündelungslogik gegen Doppel-Spam)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::get_official_alerts_for_location()` (#1033/#1034) | Upstream, unverändert | Reine Fkt Koordinaten→Warnliste, fail-soft pro Quelle, wirft nie; Registry deckt FR+AT bereits ab, IT (#1086) kommt automatisch dazu |
| `src/services/official_alerts/models.py::OfficialAlert` | Upstream, unverändert | Frozen DTO `source, hazard, level, label, valid_from, valid_to, url, region_label` — `level` ist bereits numerisch (1–4), wird direkt als Zustandswert wiederverwendet |
| `src/services/alert_state.py` | **Unverändert wiederverwendet** (keine Code-Änderung nötig) | Generischer `dict[str, {last_reported_value: float, reported_at}]`-Store — bereits offen genug für einen neuen Key-Namespace `official_alert:<region_label>:<hazard>`; `level` (int 1–4) passt verlustfrei in den bestehenden `float`-Slot |
| `src/services/trip_alert.py::check_radar_alerts()` | Muster-Referenz | Struktur-Vorbild für die neue Methode: pro Trip iterieren, Segment-Auswahl, fail-soft try/except, Doppel-Alert-Guard über `alert_state` |
| `src/services/trip_report_scheduler.py:660-670` | Muster-Referenz (Slice 3) | Fetch-Gating + Dedupe-nach-Koordinate-Pattern für `get_official_alerts_for_location()`-Aufrufe |
| `src/output/renderers/alert/model.py::AlertMessage` (ADR-0011, #917) | Bewusst NICHT erweitert | Kanonisches Event-Modell (`AlertEvent \| OnsetEvent`) für die vier generischen Renderer in `render.py`; s. Architektur-Entscheidung unten, warum hier kein dritter Event-Typ eingeführt wird |
| `src/output/renderers/alert/official_alerts.py::render_official_alerts_plain()` (#1087) | Wiederverwendung | Liefert bereits das kompakte Zeilenformat `"Amtliche Warnung: {label}"` — wird als Text-Block an die bestehende Alert-Mail angehängt statt eines neuen Renderers |
| `internal/model/trip.go:109::OfficialAlertsEnabled *bool` (#1087) | Muster-Referenz | Pointer-Bool-Toggle-Pattern für das neue Feld `OfficialAlertTriggersEnabled` |
| `internal/handler/trip.go:234-235` Merge-Block (#1087) | Muster-Referenz | `if req.X != nil`-RMW-Merge-Pattern für das neue Feld |
| `src/app/trip.py:201::official_alerts_enabled` (#1087) | Muster-Referenz | Pointer-Semantik-Vorbild für `official_alert_triggers_enabled` |
| `src/app/loader.py:416-440,1097-1098` (#1087) | Muster-Referenz | RMW-Load/Save-Pattern für das neue Feld |
| `frontend/.../AlertsTab.svelte:49,88-104,135-140` (#1087) | Muster-Referenz | Auto-Save-Pfad + `ChannelToggle`-Einbindung für die zweite, eigenständige Checkbox |
| `tests/tdd/test_issue_1040_alerts_toggle.py` | Test-Vorbild | Mock-freies Fake-Quelle-Pattern (`register_official_alert_source`, Call-Counter) |

## Implementation Details

**(1) Neue, generische Detektions-Methode (kein Versand, fail-soft, keine Zustandsschreibung):**

```python
# src/services/trip_alert.py, TripAlertService
def check_official_alert_triggers(self, trip: "Trip") -> list["OfficialAlert"]:
    """Liefert amtliche Warnungen, die NEU sind oder deren Level gestiegen ist
    ggü. dem letzten gemeldeten Stand (alert_state). Fail-soft: jede Quelle
    einzeln try/except, Toggle-Gate zuerst. Schreibt KEINEN alert_state — das
    übernimmt der Aufrufer erst nach erfolgreichem Versand (Konsistenz mit
    dem Wetter-Delta-Pfad, Zeilen 201-210)."""
    if trip.official_alert_triggers_enabled is False:
        return []
    from services.official_alerts import get_official_alerts_for_location
    from services.alert_state import AlertStateService

    cached = self._get_cached_weather(trip)
    if not cached:
        return []
    seen: set[tuple[float, float]] = set()
    all_alerts: list[OfficialAlert] = []
    for sw in cached:
        if sw.has_error:
            continue
        coord = (round(sw.segment.start_point.lat, 3), round(sw.segment.start_point.lon, 3))
        if coord in seen:
            continue
        seen.add(coord)
        try:
            all_alerts.extend(get_official_alerts_for_location(*coord))
        except Exception as e:
            logger.warning(f"official_alert_triggers: Quelle fehlgeschlagen fuer {trip.id}: {e}")

    state = AlertStateService(self._user_id).load(trip.id)
    new_or_escalated = []
    for a in all_alerts:
        key = f"official_alert:{a.region_label}:{a.hazard}"
        prev = state.get(key)
        if prev is None or a.level > prev.get("last_reported_value", 0):
            new_or_escalated.append(a)
    return new_or_escalated
```

**(2) Einbindung in `check_all_trips()` + Bündelung — Zeile ~357-361 heute:**

```python
# src/services/trip_alert.py::check_all_trips()
for trip in load_all_trips(user_id=self._user_id):
    ...  # bestehende has_active_rules/expired/cached-Checks unveraendert
    official_notices: list["OfficialAlert"] = []
    try:
        official_notices = self.check_official_alert_triggers(trip)
    except Exception as e:
        logger.error(f"Official alert trigger check failed for trip {trip.id}: {e}")

    try:
        weather_sent = self.check_and_send_alerts(
            trip, cached, official_notices=official_notices,
        )
        if weather_sent:
            alerts_sent += 1
        elif official_notices:
            # Kein Wetter-Delta-Alert gefeuert, aber neue/gestiegene amtliche
            # Warnung(en) -- eigenstaendiger Versand (PO-Entscheidung 1).
            if self._send_official_alert_only(trip, official_notices):
                alerts_sent += 1
    except Exception as e:
        logger.error(f"Alert check failed for trip {trip.id}: {e}")
```

`check_and_send_alerts()` erhält einen neuen optionalen Parameter `official_notices:
list["OfficialAlert"] = None`; wird ein Alert wegen Wetter-Delta tatsächlich versendet
(Zeile 193 `_send_alert(...)`), werden die `official_notices` an `_send_alert` durchgereicht
und in denselben Versand gebündelt (kein zweiter Call). `_send_official_alert_only()` (neu,
kleine private Methode) reproduziert NUR die generischen Sicherheits-Gates (QuietHours,
Throttle/Cooldown, Tageslimit — dieselben Aufrufe wie in `check_and_send_alerts()` Schritt
1/1b/1c), aber **ohne** die weather-delta-spezifischen Gates (`has_active_rules`,
`_filter_significant_changes`), da ein eigenständiger amtlicher Trigger laut PO-Entscheidung
1 unabhängig vom Wetter-Delta-Status feuern soll.

**(3) Bündelung im Versand — `_send_alert()` und `NotificationService`:**

```python
# src/services/trip_alert.py::_send_alert()
def _send_alert(self, trip, weather, changes, official_notices=None) -> bool:
    result = self._notification_service.send_deviation_alert(
        trip=trip, weather=weather, changes=changes,
        effective_channels=self._effective_alert_channels(trip),
        official_notices=official_notices or [],
    )
    if result.sent:
        self._record_official_alert_state(trip.id, official_notices or [])
    return result.sent
```

```python
# src/services/notification_service.py — send_deviation_alert() erweitert um
# official_notices; _dispatch_alert_message() haengt einen Text-Block an
# html/plain/telegram_body an (NICHT an sms_body — analog Slice-3-AC-6-
# Praezedenzfall "SMS bewusst ohne Paritaet"):
def _dispatch_alert_message(self, alert_msg, effective_channels, *, official_notices=None, ...):
    ...
    html, plain = render_alert_email(alert_msg)
    telegram_body = render_alert_telegram(alert_msg)
    sms_body = render_alert_sms(alert_msg)
    if official_notices:
        from output.renderers.alert.official_alerts import render_official_alerts_plain
        entries = [(a.region_label, [a]) for a in official_notices]
        extra_lines = render_official_alerts_plain(entries)
        extra_text = "\n".join(f"⚠️ {l}" for l in extra_lines)
        plain += "\n\n" + extra_text
        html = html.replace("</body></html>", f"<p>{_esc(extra_text)}</p></body></html>")
        telegram_body += "\n\n" + extra_text
    ...
```

Ein neuer Standalone-Pfad `NotificationService.send_official_alert(trip, notices,
effective_channels)` baut Subject/Body direkt aus `render_official_alerts_plain()` (ohne
`AlertMessage`/`render.py`, da keine `AlertEvent`s existieren) und versendet über dieselbe
Kanal-Infrastruktur wie `send_deviation_alert`.

**(4) Persistenz — neues Toggle-Feld, RMW Pflicht:**

```python
# src/app/trip.py, analog Zeile 201
official_alert_triggers_enabled: Optional[bool] = None  # Issue #1088: None/True=aktiv

# src/app/loader.py — load (analog 416-440):
official_alert_triggers_enabled=data.get("official_alert_triggers_enabled"),
# save (analog 1097-1098), NUR wenn is not None (False muss persistieren):
if trip.official_alert_triggers_enabled is not None:
    data["official_alert_triggers_enabled"] = trip.official_alert_triggers_enabled
```

```go
// internal/model/trip.go, nach Zeile 109 (OfficialAlertsEnabled)
OfficialAlertTriggersEnabled *bool `json:"official_alert_triggers_enabled,omitempty"`
```

```go
// internal/handler/trip.go::tripUpdateRequest + UpdateTripHandler-Merge, analog 154/234-235
OfficialAlertTriggersEnabled *bool `json:"official_alert_triggers_enabled,omitempty"`
// ...
if req.OfficialAlertTriggersEnabled != nil {
    existing.OfficialAlertTriggersEnabled = req.OfficialAlertTriggersEnabled
}
```

**(5) Frontend — zweite, eigenständige Checkbox (analog #1087-Auto-Save-Pfad):**

```svelte
<!-- frontend/src/lib/components/alerts-tab/AlertsTab.svelte -->
<script lang="ts">
  let officialAlertTriggersEnabled = $state<boolean>(
    trip.official_alert_triggers_enabled ?? true,
  );
  function buildOfficialAlertTriggersSaveFn() {
    const enabled = officialAlertTriggersEnabled;
    return async () => {
      const updated = await api.put<Trip>(`/api/trips/${trip.id}`, {
        official_alert_triggers_enabled: enabled,
      });
      onTripUpdate?.(updated);
    };
  }
  function makeOfficialAlertTriggersToggleHandler() {
    return (checked: boolean) => {
      officialAlertTriggersEnabled = checked;
      saveController?.schedule(buildOfficialAlertTriggersSaveFn());
    };
  }
</script>

<ChannelToggle
  label="Amtliche Warnungen lösen Alert aus"
  checked={officialAlertTriggersEnabled}
  onchange={makeOfficialAlertTriggersToggleHandler()}
  testid="alerts-tab-official-alert-triggers-toggle"
/>
```

Beide Checkboxen (`alerts-tab-official-alerts-toggle` aus Slice 3 und die neue
`alerts-tab-official-alert-triggers-toggle`) leben nebeneinander auf der
Alerts-Konfigurationsseite, unabhängig voneinander speicherbar (zwei getrennte
`PUT`-Bodies über denselben `saveController`).

## Expected Behavior

- **Input:** Trip mit mindestens einer aktuellen/zukünftigen Etappe, deren Segment-Startpunkt
  in einer Region mit aktiver amtlicher Warnung liegt; `Trip.official_alert_triggers_enabled`
  (Bool oder fehlend/`null`, Default-Verhalten = aktiv).
- **Output:** Ist der Toggle `true`/fehlend, prüft jeder periodische Alert-Zyklus
  (`check_all_trips()`) zusätzlich zum Wetter-Delta amtliche Warnungen. Eine neue oder
  gestiegene Warnstufe löst — vorbehaltlich QuietHours/Throttle/Tageslimit — einen Alert aus,
  auch ohne Wetter-Delta. Feuert im selben Zyklus zusätzlich ein Wetter-Delta-Alert, wird die
  amtliche Warnung in **derselben** Nachricht gebündelt (kein zweiter Versand). Ist der Toggle
  explizit `false`, findet kein zusätzlicher Fetch/Trigger statt (Call-Counter der Quelle = 0
  für den Trigger-Pfad) — die Briefing-Anzeige (Slice 3, `official_alerts_enabled`) bleibt davon
  unberührt.
- **Side effects:** Bei erfolgreichem Versand wird `alert_state.py` um Keys
  `official_alert:<region_label>:<hazard>` ergänzt (verhindert Wiederholungs-Spam bei
  unverändertem Level). Bei Quellenausfall (Exception) wird der betroffene Alert-Zyklus für
  ALLE Trips fortgesetzt (fail-soft, kein Crash).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `official_alert_triggers_enabled` nicht auf `false` gesetzt,
  stabiler/unveränderter Wetterlage (kein Wetter-Delta-Alert würde feuern) und einer über eine
  echte registrierte Test-Quelle (`register_official_alert_source()`) gelieferten, noch nie
  gemeldeten amtlichen Warnung für die Segment-Koordinate, When `check_all_trips()` bzw.
  `check_official_alert_triggers()` + Versandpfad ausgeführt wird, Then wird ein Alert über
  mindestens einen konfigurierten Kanal (E-Mail) versendet, der die Warnung enthält — auch ohne
  jedes Wetter-Delta.
  - Test: Echte Test-Quelle mit bekanntem Level registrieren, echten `TripAlertService`-Lauf
    (kein Mock) gegen einen Trip mit unveränderter Cache-/Fresh-Weather (0 Changes) ausführen,
    tatsächlich zugestellte Mail (Stalwart `gregor-test@henemm.com`, IMAP-Abruf) auf sichtbares
    Warnungs-Label prüfen — kein `assert 'x' in file.read_text()`.

- **AC-2:** Given derselbe Trip mit `official_alert_triggers_enabled=false` und derselben
  Test-Quelle mit Aufruf-Zähler, When der Alert-Zyklus läuft, Then wird die Test-Quelle über den
  Trigger-Pfad **nicht** aufgerufen (Call-Counter = 0 für diesen Pfad) und kein Alert wird
  versendet — die Slice-3-Briefing-Anzeige-Checkbox (`official_alerts_enabled`) bleibt davon
  unberührt und weiterhin unabhängig testbar (separates Aufruf-Verhalten im Briefing-Pfad).
  - Test: `official_alert_triggers_enabled=False` setzen, `official_alerts_enabled` unverändert
    `true` lassen, echten Alert-Zyklus-Lauf + separaten Scheduler-Briefing-Lauf ausführen, je
    eigenen Call-Counter der Fake-Quelle für beide Pfade getrennt prüfen.

- **AC-3:** Given ein Trip von Nutzer A mit `official_alert_triggers_enabled=true` gespeichert
  über `PUT /api/trips/{id}` mit einem Request-Body, der **nur** dieses Feld enthält, When
  anschließend derselbe Trip über `PUT /api/trips/{id}` mit einem Body ohne dieses Feld erneut
  gespeichert wird (z. B. nur `name` geändert), Then bleibt `official_alert_triggers_enabled`
  weiterhin `true` (Read-Modify-Write-Merge, kein Zurückfallen auf Default/Verlust — Hintergrund
  BUG-DATALOSS-GR221/#102) UND alle anderen unveränderten Felder (`stages`, `alert_rules`,
  `official_alerts_enabled`) sind byte-identisch zum Zustand vor dem zweiten Save. Der identische
  Ablauf wird für einen unabhängigen Trip von Nutzer B wiederholt (Cross-User-Isolation).
  - Test: Zwei echte `PUT /api/trips/{id}`-Calls gegen den laufenden Go-Handler, gespeicherten
    Trip aus `data/users/<user>/trips/` laden, Feld-für-Feld-Vergleich vor/nach dem zweiten Save;
    Ablauf für zwei getrennte `user_id`-Verzeichnisse wiederholt.

- **AC-4:** Given eine registrierte Test-Quelle, deren `fetch()` eine `RuntimeError` wirft
  (simulierter Quellenausfall, keine gemockte Bibliotheksfunktion — eine echte, strukturell
  fehlerhafte Quelle über die Registry), When `check_all_trips()` für einen betroffenen Trip UND
  weitere, nicht betroffene Trips läuft, Then bricht der Alert-Zyklus nicht ab (kein
  Exception-Propagation aus `check_official_alert_triggers()`), die übrigen Trips werden normal
  geprüft, und für den betroffenen Trip wird — sofern kein anderweitiger Trigger vorliegt — kein
  amtlicher Alert versendet (aber auch kein Crash-Log über den Zyklus hinaus).
  - Test: Fehlerhafte Test-Quelle registrieren, `check_all_trips()` über mehrere Trips (einer
    betroffen, einer nicht) laufen lassen, Rückgabewert (Anzahl gesendeter Alerts für die
    unbetroffenen Trips) und Abwesenheit einer Exception im Aufrufer prüfen.

- **AC-5:** Given ein Trip, bei dem im selben Alert-Zyklus SOWOHL ein signifikantes
  Wetter-Delta (über `_filter_significant_changes`) ALS AUCH eine neue amtliche Warnung
  vorliegen, When `check_all_trips()` läuft, Then wird genau **ein** Alert versendet (nicht
  zwei), der sowohl den Wetter-Delta-Block als auch einen zusätzlichen Abschnitt für die
  amtliche Warnung enthält.
  - Test: Echter Scheduler-/Alert-Lauf mit sowohl verändertem `fresh_weather` (Delta über
    Schwelle) als auch aktiver Test-Quelle; zugestellte Mail (IMAP) auf genau eine Nachricht mit
    beiden Inhaltsblöcken prüfen (Anzahl der im Test-Postfach neu eingetroffenen Mails = 1).

- **AC-6:** Given eine amtliche Warnung wurde bereits mit Level 2 gemeldet (Eintrag
  `official_alert:<region_label>:<hazard>` in `alert_state.py` vorhanden), When im nächsten
  Zyklus dieselbe Warnung weiterhin Level 2 liefert, Then wird **kein** erneuter Alert für diese
  Warnung versendet (Dedupe). Steigt der Level anschließend auf 3, wird beim übernächsten Zyklus
  **erneut** ein Alert versendet.
  - Test: Test-Quelle mit steuerbarem Level; drei aufeinanderfolgende
    `check_official_alert_triggers()`-Läufe (Level 2, Level 2 erneut, Level 3) gegen denselben
    `alert_state`-Datenbestand; Alert-Versand-Ergebnis (True/False) je Lauf prüfen.

- **AC-7:** Given ein Trip-Alert wird via SMS-Kanal versendet (`send_sms=true` in effektiven
  Kanälen) UND eine amtliche Warnung liegt gebündelt vor, When der Versand erfolgt, Then enthält
  die SMS **keinen** Text-Zusatz für die amtliche Warnung (dokumentierte Nicht-Parität, analog
  Slice-3-AC-6) und das SMS-Zeichenlimit bleibt unverändert eingehalten — E-Mail und Telegram
  enthalten den Zusatz weiterhin.
  - Test: Echter `_dispatch_alert_message()`-Aufruf mit `official_notices` gesetzt und
    SMS-Kanal aktiv; erzeugten SMS-Text mit/ohne `official_notices` auf Gleichheit prüfen,
    E-Mail-/Telegram-Body auf Vorhandensein des Zusatzes prüfen.

## Known Limitations

- **Radar-Onset-Pfad (`radar_alert_service.py`/`check_radar_alerts()`) nicht angebunden:** Dieses
  Slice bindet ausschließlich den Wetter-Delta-Pfad (`check_and_send_alerts`/`check_all_trips`)
  an. Eine Anbindung an den kürzeren Radar-Cooldown-Zyklus würde die Versand-Frequenz amtlicher
  Warnungen unkontrolliert erhöhen und den Scope sprengen — Empfehlung: separates Folge-Issue,
  falls gewünscht.
- **Quiet-Hours/Throttle/Tageslimit-Interaktion für den Standalone-Pfad:** `_send_official_alert_only()`
  reproduziert dieselben generischen Gates wie der Wetter-Delta-Pfad (bewusste Design-Entscheidung,
  s. Implementation Details (2)), aber es gibt kein dediziertes AC dafür in diesem Slice — sollte
  sich in der Implementierung ein abweichendes Timing-Verhalten zeigen, ist das gegen die
  bestehende `_is_quiet_hours`/`_is_throttled_with_cooldown`-Semantik zu validieren, nicht neu zu
  erfinden.
- **Ein Alert je Warnung/Level-Sprung:** Steigt der Level in einem einzigen Zyklus um mehrere
  Stufen (z. B. 1→4), wird dies als EIN Ereignis gemeldet, nicht als mehrere Zwischenstufen.
- **SMS bewusst ohne Parität:** Wie in Slice 3 (AC-6) dokumentiert — keine Nachbesserung in
  diesem Slice.

## Out of Scope

- **Nowcast-Optimierung (Slice 5, #1089).**
- **Neue Alert-Quellen:** Die Registry ist bereits länderneutral (FR live, AT/GeoSphere live seit
  #1085, IT/#1086 kommt automatisch dazu) — keine neue Quelle in diesem Slice.
- **Granularität pro Alert-Quelle:** Der neue Toggle schaltet alle Quellen gemeinsam ein/aus,
  keine Auswahl einzelner Quellen oder Hazard-Typen.
- **Tiefere Radar-Onset-Anbindung (`radar_alert_service.py`):** Siehe Known Limitations —
  bewusst nicht Teil dieses Slice, ggf. Folge-Issue.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Folgt etablierten, bereits per ADR-0016 (#1034) und in Slice 3 (#1087)
  legitimierten Mustern (Pointer-Bool-Toggle, Fetch-Gating, RMW-Merge, fail-soft
  Registry-Konsum). Eine bewusste, dokumentierte Design-Entscheidung (keine neue ADR, aber
  festzuhalten): Die amtliche Warnung wird **als Text-Anhang** an die bestehende
  E-Mail-/Telegram-Alert-Nachricht angehängt, **nicht** als dritter kanonischer Event-Typ in
  `src/output/renderers/alert/model.py::AlertMessage` (`AlertEvent | OnsetEvent`) modelliert.
  Grund: Die vier generischen Renderer in `render.py` (`render_subject/_email/_telegram/_sms`)
  verzweigen aktuell binär über `msg.source is not None` (Deviation vs. Onset) und referenzieren
  `AlertEvent`-spezifische Helfer (`over_thr()`, `_sorted()`, `_val()`) — ein dritter Event-Typ
  müsste alle vier Renderer um einen weiteren Zweig erweitern, was Umfang und Risiko dieses
  Slice deutlich über die von Epic #1073 vorgegebene Slice-Größe hinaus verschieben würde. Der
  Text-Anhang reicht für eine kurze, informative Zusatzzeile (Vorbild: bereits bewährtes
  Kurzformat aus `render_official_alerts_plain()`, Slice 3) und hält die Bündelung auf den
  Dispatch-Layer (`notification_service.py`) begrenzt, ohne das kanonische ADR-0011-Modell für
  die anderen drei Alert-Arten zu verändern.

## Changelog

- 2026-07-08: Initial spec created (Epic #1073 Slice 4, Issue #1088).
