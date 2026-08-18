---
entity_id: feat_1439_starkregen_kurzfristhinweis
type: module
created: 2026-08-07
updated: 2026-08-07
status: draft
version: "1.0"
workflow: feat-1439-starkregen-minutely15
tags: [radar-nowcast, trip-briefing, email, telegram, alerts]
---

<!-- Issue #1439 -->

# Starkregen-Kurzfristhinweis im planmäßigen Trip-Briefing

## Approval

- [ ] Approved

## Purpose

Das planmäßige Trip-Briefing (Morgen-/Abend-Mail + Telegram) bekommt eine
kurze Hinweiszeile, wenn der bereits produktiv laufende `RadarNowcastService`
(Issue #656) für den Startpunkt des aktiven/nächsten Segments **Starkregen
innerhalb der nächsten `NOWCAST_HORIZON_MIN` Minuten** erkennt (Wert bei
Erstellung dieser Spec: 60 — seit Issue #1945 auf **180** angehoben, s.
Changelog). Das ist eine **Änderung**, kein Neubau: die Nowcast-
Infrastruktur existiert bereits (u.a. im 15-Minuten-Alarm-Poll,
`trip_alert.py`); es fehlt nur die Einbindung in den **planmäßigen**
Briefing-Versandpfad.

**Wichtige Grenze (durch die Nowcast-Technologie selbst gesetzt, keine
Implementierungslücke):** `RadarNowcastService` erkennt Regen ausschließlich
innerhalb eines `NOWCAST_HORIZON_MIN`-Fensters (180 Min, s. Changelog) ab
Abrufzeitpunkt. Der Hinweis kann daher
**keine** Tage- oder Stunden-vorher-Vorhersage für morgen leisten — bei einer
Abend-Mail (die die Etappe des Folgetags beschreibt) erscheint er nur, wenn
die Etappe zufällig kurz nach Versandzeit beginnt. Der reguläre
Niederschlags-Ausblick in der Stundentabelle bleibt davon unberührt und ist
weiterhin die maßgebliche Vorschau für spätere Stunden/Tage.

## Source

- **File:** `src/services/trip_report_scheduler.py` (MODIFY) — Ermittlung
  des Kurzfristhinweises (gated Fetch, Zeitfenster-Guard) und Übergabe an
  `TripReportRequest`
- **File:** `src/output/renderers/email/starkregen_hint.py` (NEU) —
  gemeinsamer Text-Baustein + `render_html()`/`render_plain()`, analog
  `unavailable_hint.py` (Issue #1348)
- **File:** `src/services/notification_service.py` (MODIFY) —
  `TripReportRequest` um `starkregen_hint_text: str | None` erweitern, an
  E-Mail- und Telegram-Renderer durchreichen
- **File:** `src/output/renderers/email/html.py` (MODIFY) — Hinweis-Box
  einbauen
- **File:** `src/output/renderers/email/plain.py` (MODIFY) — Hinweis-Zeile
  einbauen
- **File:** `src/output/renderers/narrow.py` (MODIFY) — Telegram-Bubble
  einbauen (`render_telegram_bubbles`, analog dem bestehenden
  „Amtliche Warnungen nicht abrufbar"-Block)
- **File:** `src/services/radar_service.py` (MODIFY, minimal) — bestehende
  private `_NOWCAST_HORIZON_MIN` (Wert bei Erstellung dieser Spec: 60, seit
  #1945: 180) bekommt einen öffentlichen Alias `NOWCAST_HORIZON_MIN`, damit
  der Zeitfenster-Guard im Scheduler dieselbe Zahl referenziert statt eine
  zweite Kopie zu pflegen
- **File:** `docs/specs/data_sources.md` (MODIFY, Governance-Nachtrag) —
  Eintrag für `minutely_15` als bereits seit #656 produktiv genutzte Quelle

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen im Python-Core
> (`src/services/`, `src/output/renderers/`) — keine Go-/Frontend-Berührung.

## Estimated Scope

- **LoC:** ~90–140 (größer als die ursprüngliche Grobschätzung von ~50–70,
  weil der Konsistenz-Mechanismus aus AC-6 einen zusätzlichen, aber sehr
  kleinen Eingriff braucht — Details siehe Implementation)
- **Files:** ~8 (siehe Source)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RadarNowcastService.get_nowcast()` (`src/services/radar_service.py`) | Service | Liefert `NowcastResult` (onset_minutes, intensity_label, source) für Koordinate |
| `INTENSITY_HEAVY` (`src/services/radar_service.py`) | Konstante | Schwellwert-Label für „Starkregen" (mm/h >= 4.0) |
| `alert_daily_limit.is_allowed(user_id, now, reason="nowcast")` (`src/services/alert_daily_limit.py`) | Gate | Tagesbudget-Prüfung — MUSS vor jedem neuen Nowcast-Fetch stehen (#1555) |
| `ThrottleStore` (`src/services/throttle_store.py`), Scope `"radar"` | Service | Bestehender Cooldown-Speicher für Radar-Alerts — wird für die Konsistenz-Pflicht (AC-6) wiederverwendet, keine neue State-Datei |
| `tz_for_coords()` (`src/utils/timezone.py`) | Utility | Ortszeit für die Uhrzeit-Formatierung der Hinweiszeile |
| `unavailable_hint.py`-Muster (`src/output/renderers/email/unavailable_hint.py`) | Vorbild | Struktur-Vorbild für den neuen Hinweis-Baustein (bewusst NICHT unter `renderers/alert/`, sonst greift das Warn-Renderer-Mail-Gate) |

## Implementation Details

### 1. Ermittlung im Scheduler (`trip_report_scheduler.py`)

Neue private Methode, aufgerufen in `_send_trip_report_outcome()` nachdem
`segments`/`trip_tz` feststehen, vor dem Bau von `TripReportRequest`:

```
def _build_starkregen_hint(self, trip, segments, tz, now_utc) -> Optional[str]:
    # 1. Aktives/naechstes Segment waehlen — dieselbe Auswahl wie
    #    TripAlertService.check_radar_alerts() (trip_alert.py:730-745)
    # 2. Naehe-Guard: Segment muss aktiv sein ODER innerhalb
    #    NOWCAST_HORIZON_MIN (180 Min, #1945) starten, sonst -> None
    # 3. Budget-Gate: alert_daily_limit.is_allowed(user_id, now_utc,
    #    reason="nowcast") -- False -> None, KEIN Fetch
    # 4. get_nowcast(lat, lon, priority="polling") -- Exception -> None
    #    (fail-soft, ADR-0018)
    # 5. Nur wenn intensity_label == INTENSITY_HEAVY und onset_minutes
    #    gesetzt -> Text bauen, sonst None
```

Die Segment-Auswahl (Schritt 1) und der Nähe-Guard (Schritt 2) laufen VOR
dem Budget-Gate und dem Fetch — ein zu weit entferntes Segment verursacht
weder einen Nowcast-Call noch Budgetverbrauch.

`priority="polling"` (nicht `"user_briefing"`): der Scheduler ist ein
Hintergrund-/Cron-Prozess wie der 15-Minuten-Alarm-Poll, kein direkter
Nutzerklick — dieselbe Einstufung wie `trip_alert.py:775`.

### 2. Text-Baustein (`starkregen_hint.py`, neu)

Eine einzige Funktion `format_starkregen_hint(intensity_label, onset_minutes,
*, tz) -> str`, die exakt dasselbe Format wie der bestehende
`RadarNowcastService.format_now_text()`-Zweig für Starkregen erzeugt
(„Starker Regen ab ca. HH:MM (in ~N Min)."), damit E-Mail und Telegram
wortgleich sind und die Formulierung nicht zweimal getrennt gepflegt wird.
Dazu je eine dünne `render_html()`/`render_plain()`-Funktion (Box bzw. Zeile,
Muster `unavailable_hint.py`).

### 3. Konsistenz-Pflicht (AC-6) — Wiederverwendung des bestehenden Radar-Throttles

Statt eines neuen State-Mechanismus wird der **bereits existierende**
Cooldown wiederverwendet, den `TripAlertService.check_radar_alerts()` selbst
als ALLERERSTE Prüfung liest (`trip_alert.py:757`,
`self._is_radar_throttled(trip.id, cooldown_min=...)` →
`ThrottleStore.is_throttled("radar", trip.id, ...)`):

Sobald der Kurzfristhinweis erfolgreich in einem Briefing versendet wurde,
schreibt der Scheduler `ThrottleStore(user_id).record("radar", trip.id,
now_utc)` — denselben Eintrag, den ein echter Radar-Alert nach Versand
ohnehin schreibt (`trip_alert.py:935`). Der nächste 15-Minuten-Poll für
denselben Trip ist dadurch für die reguläre Cooldown-Dauer
(`trip.alert_cooldown_minutes` bzw. Standard-Throttle) bereits an seiner
ERSTEN Prüfung blockiert — bevor er überhaupt einen zweiten Nowcast-Call
absetzt. Das verhindert strukturell sowohl einen widersprüchlichen
Alert-Wortlaut als auch einen doppelten Budgetverbrauch für dasselbe
Ereignis. Kein Eingriff in `trip_alert.py` oder `alert_state.py` nötig.

### 4. Renderer-Mail-Gate (Hinweis, keine AC)

`starkregen_hint.py` liegt unter `src/output/renderers/email/*.py` →
`renderer_mail_gate.py` greift automatisch. Vor Commit:
`tests/tdd/test_issue_811_mode_matrix.py` grün + frischer
`briefing_mail_validator.py`-Lauf (Marker `X-GZ-Mail-Type: trip-briefing`).

### 5. Governance-Nachtrag `data_sources.md`

Die Datei trägt die Klausel „Claude darf KEINE neuen Datenquellen oder
Parameter hinzufuegen ohne explizite Genehmigung." Der Nachtrag hier fügt
**keinen neuen Parameter** hinzu (minutely_15 läuft seit #656 in Prod) —
die PO-Freigabe dieser Spec-ACs (das reguläre `go`) deckt den Nachtrag mit
ab; der Eintrag bleibt bewusst auf eine Zeile beschränkt.

## Expected Behavior

- **Input:** Trip mit aktivem/nächstem Segment, dessen Startpunkt-Koordinate
  Starkregen (mm/h >= 4.0) innerhalb der nächsten `NOWCAST_HORIZON_MIN`
  Minuten (180, #1945) zeigt
- **Output:** Hinweiszeile „Starker Regen ab ca. HH:MM (in ~N Min)." in
  E-Mail (HTML + Plain) und Telegram-Bubble des planmäßigen Briefings;
  ohne Treffer/außerhalb des Fensters/ohne Budget entfällt die Zeile
  ersatzlos, das Briefing wird unverändert versendet
- **Side effects:** bei gerendertem Hinweis wird derselbe Radar-Cooldown
  geschrieben, den ein echter Radar-Alert schreiben würde (verhindert
  einen widersprüchlichen Folge-Alert im Cooldown-Fenster)

## Acceptance Criteria

- **AC-1:** Given ein Trip mit ausgeschöpftem Tagesbudget für
  `reason="nowcast"` (`alert_daily_limit.is_allowed(...)` liefert False) /
  When das planmäßige Briefing für diesen Trip gerendert wird / Then
  erscheint keine Starkregen-Kurzfristhinweis-Zeile, und
  `RadarNowcastService.get_nowcast()` wird für diesen Trip nicht
  aufgerufen — kein zusätzlicher Nowcast-Call trotz ausgeschöpftem Budget.
  - Test: Budget-Gate auf „nicht erlaubt" setzen, Briefing bauen, prüfen
    dass die Hinweis-Zeile fehlt UND `get_nowcast` (Spy/Zähler) nicht
    aufgerufen wurde.

- **AC-2:** Given die aktive/nächste Etappe eines Trips beginnt erst in
  mehr als `NOWCAST_HORIZON_MIN` (180, #1945) Minuten / When das
  planmäßige Briefing gerendert wird / Then erscheint kein
  Starkregen-Kurzfristhinweis und `RadarNowcastService.get_nowcast()` wird
  für diesen Trip nicht aufgerufen, selbst wenn ein injizierter Nowcast
  Starkregen melden würde.
  - Test: Segment-Startzeit auf „in 200 Minuten" (> 180) setzen, Fetch-Spy
    prüft Nicht-Aufruf; Segment-Startzeit auf „in 30 Minuten" (<= 180)
    setzen, Fetch wird aufgerufen (Gegenprobe im selben Test,
    `tests/tdd/test_starkregen_kurzfristhinweis.py::test_ac2_zeitfenster_guard_kein_fetch_ausserhalb_horizon`).

- **AC-3:** Given ein Trip, dessen aktive/nächste Etappe innerhalb der
  nächsten `NOWCAST_HORIZON_MIN` Minuten (180, #1945) beginnt UND
  `get_nowcast()` für den
  Etappen-Startpunkt `INTENSITY_HEAVY` mit gesetztem `onset_minutes`
  liefert / When das planmäßige Briefing versendet wird / Then enthalten
  sowohl die E-Mail (HTML und Plain) als auch die Telegram-Nachricht eine
  Hinweiszeile im Format „Starker Regen ab ca. HH:MM (in ~N Min)." mit
  identischer Uhrzeit in Ortszeit.
  - Test: Injizierten Nowcast mit `INTENSITY_HEAVY`, `onset_minutes=15`
    verwenden, Briefing für alle drei Ausgaben rendern, exakten
    Zeit-String in allen dreien vergleichen (kein Dateiinhalt-Grep,
    echte Renderer-Ausgabe).

- **AC-4:** Given eine Trip-Koordinate ohne verwertbare Nowcast-Antwort
  (Exception beim Fetch, oder `onset_minutes=None`, oder Intensität unter
  `INTENSITY_HEAVY`) / When das planmäßige Briefing gerendert wird / Then
  entfällt die Hinweiszeile ersatzlos, und das restliche Briefing wird
  ohne Fehler und unverändert versendet (ADR-0018 Fail-soft).
  - Test: `get_nowcast()` wirft eine Exception → Briefing-Versand-Ergebnis
    bleibt „sent", keine Hinweiszeile in E-Mail/Telegram, kein Crash.

- **AC-5:** Given ein Trip mit aktivem SMS-Kanal und einem Trigger, der bei
  E-Mail/Telegram einen Starkregen-Kurzfristhinweis auslösen würde / When
  das Briefing versendet wird / Then bleibt der SMS-Text unverändert (keine
  Kurzfristhinweis-Zeile in der SMS) — MVP-Scope ist ausschließlich E-Mail
  und Telegram, SMS ist bewusst zurückgestellt.
  - Test: Denselben Trigger-Trip mit `send_sms=True` rendern, SMS-Ausgabe
    vor/nach der Änderung byte-identisch vergleichen.

- **AC-6:** Given ein planmäßiges Briefing hat den Starkregen-Kurzfrist-
  hinweis erfolgreich versendet / When `TripAlertService.check_radar_alerts()`
  innerhalb des Cooldown-Fensters (`trip.alert_cooldown_minutes` bzw.
  Standard-Throttle) für denselben Trip erneut läuft / Then wird der
  Radar-Alert durch den bestehenden Throttle (`ThrottleStore`, Scope
  `"radar"`) unterdrückt, weil der Kurzfristhinweis denselben Cooldown-
  Eintrag geschrieben hat wie ein echter Radar-Alert — kein
  widersprüchlicher zweiter Hinweis für dasselbe Ereignis in kurzem
  Abstand.
  - Test (Mutations-Gegenprobe PFLICHT): Briefing mit Kurzfristhinweis
    versenden, danach `check_radar_alerts()` mit injiziertem Starkregen-
    Nowcast für denselben Trip aufrufen — Alert MUSS unterdrückt bleiben.
    Wird die `ThrottleStore.record(...)`-Zeile im Scheduler entfernt, MUSS
    genau dieser Test rot werden (nicht nur ein Test, der bloß prüft, dass
    die Hinweiszeile selbst existiert).

- **AC-7:** Given Gewitter/Hagel (`is_convective=True`, Label
  `INTENSITY_CONVECTIVE`) am Etappen-Startpunkt / When das planmäßige
  Briefing gerendert wird / Then erscheint KEIN Starkregen-Kurzfrist-
  hinweis (der ist ausschließlich für `INTENSITY_HEAVY` reserviert) — der
  bestehende, separate Gewitter/Hagel-Bereich (#1474/#1492) bleibt
  unberührt und wird durch dieses Feature nicht verdoppelt.
  - Test: Injizierten Nowcast mit `is_convective=True` verwenden, prüfen
    dass keine Starkregen-Zeile erscheint.

- **AC-8:** Given `docs/specs/data_sources.md` enthält aktuell keinen
  Eintrag für `minutely_15` / When diese Spec-Scheibe abgeschlossen wird /
  Then enthält die Datenquellen-Tabelle einen Nachtrags-Eintrag für
  `minutely_15` mit dem Hinweis „bereits seit #656 produktiv genutzt,
  Nachtrag".
  - Test: `# doc-compliance-test` — Datei enthält die Zeichenkette
    `minutely_15` in der Datenquellen-Tabelle.

## Known Limitations

- **Kein Tage-vorher-Hinweis:** Durch das `NOWCAST_HORIZON_MIN`-Fenster von
  `RadarNowcastService` (180 Min seit #1945, vorher 60 Min) greift der
  Kurzfristhinweis bei Abend-Mails (Etappe = Folgetag) weiterhin praktisch
  nur, wenn die Etappe zufällig innerhalb weniger Stunden nach Versandzeit
  beginnt. Das ist eine bewusste, technisch bedingte Grenze, keine
  Implementierungslücke — für eine echte Vorabend-Vorhersage bleibt die
  reguläre Stundentabelle maßgeblich.
- **SMS nicht im Scope:** Token-Format-Aufwand für SMS wird als eigenes
  Folge-Issue vorgemerkt (PO-Entscheidung, Deadline-getrieben).
- **Konsistenz-Mechanismus ist ein Cooldown, keine Wortlaut-Korrektur:**
  AC-6 verhindert einen WIDERSPRÜCHLICHEN Folge-Alert, indem er ihn ganz
  unterdrückt (bestehendes Cooldown-Verhalten) — er ändert NICHT den
  Wortlaut eines späteren Alerts, falls der Cooldown zwischenzeitlich
  abläuft und danach ein neuer, tatsächlich eigenständiger Regenschauer
  eintrifft (gewünschtes Verhalten, kein Bug).
- **Ortsvergleich/Compare nicht im Scope:** reines Trip-Briefing-Feature
  (Pendant-Gate `pendant_gate.py` greift nicht, da keine neue Compare-
  Komponente entsteht).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (nutzt ADR-0018 Fail-soft-Prinzip, keine neue
  Grundsatzentscheidung)
- **Rationale:** Reine Einbindung einer bestehenden, bereits
  ADR-konformen Service-Schicht (`RadarNowcastService`) in einen
  zusätzlichen Aufrufort. Kein neuer Provider, kein neues Datenmodell,
  keine neue Channel-Entscheidung.

## Changelog

- 2026-08-07: Initial spec erstellt — Issue #1439
- 2026-08-18: `NOWCAST_HORIZON_MIN` von 60 auf 180 Minuten angehoben —
  Issue #1945. Grund: Der Countdown-Alarm zeigte strukturell fast immer
  denselben Wert (~8 Min), weil die GeoSphere-INCA-Daten auf einem
  15-Min-Raster liegen, der Scheduler alle 15 Min prüft und der alte
  60-Min-Deckel den Alarm fast nur beim unmittelbar nächsten Rasterpunkt
  auslösen ließ. Reine Konstanten-Änderung in `radar_service.py`, kein
  neues Architektur-Muster; alle numerischen Erwähnungen des alten
  60-Min-Werts oben sind entsprechend aktualisiert. Details:
  `docs/specs/modules/fix_1945_nowcast_horizon.md`.
