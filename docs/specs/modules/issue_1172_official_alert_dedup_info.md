---
entity_id: issue_1172_official_alert_dedup_info
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [bugfix, alerts, official-alerts, notification, dedup]
---

# Issue #1172: Amtliche Warn-Mail — Entdopplung + Kerninfos

## Approval

- [ ] Approved

## Purpose

Die standalone amtliche Warn-Mail (`[Trip] Amtliche Warnung`, Plain-Text, Issue #1088)
wiederholt aktuell dieselbe Warnzeile einmal je betroffener Etappen-Koordinate (z.B.
12× „Amtliche Warnung: Hitze" bei 12 Etappen in derselben Warnregion) und nennt weder
Schwere-Stufe noch Region noch Gültigkeitszeitraum. Dieses Modul entdoppelt die
Warnungen an der Quelle (`TripAlertService.check_official_alert_triggers`) nach
`(region_label, hazard)` und führt eine neue, alert-spezifische Plain-Formatfunktion
ein, die je echter Warnung Schwere-Wort, Region und Gültigkeitszeitraum ausgibt — ohne
den geteilten Compare-/Briefing-Renderer (`official_alerts.py`) zu verändern.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `class TripAlertService`, `def check_official_alert_triggers`

> Betroffene Schicht: Python-Core/Domain-Backend (`src/services/`,
> `src/output/renderers/`) — kein Go-API-, kein Frontend-Code betroffen. Verifiziert per
> Grep auf `check_official_alert_triggers`, `send_official_alert`, `_dispatch_alert_message`
> — alle drei liegen in `src/services/` bzw. `src/output/renderers/alert/`.

## Estimated Scope

- **LoC:** ~90-130 (neue Dedup-Helper-Funktion, neue Plain-Formatfunktion, zwei
  Call-Site-Anpassungen, Tests)
- **Files:** 3 Produktivdateien (`src/services/trip_alert.py`,
  `src/output/renderers/alert/official_alerts.py`, `src/services/notification_service.py`)
  + 1 neue Testdatei
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/models.py::OfficialAlert` | dataclass | Feldquelle: `source, hazard, level(1-4), label, valid_from, valid_to, url, region_label` — unverändert |
| `src/services/official_alerts/__init__.py::get_official_alerts_for_location` | function | Liefert die Roh-Warnungen pro Koordinate, unverändert |
| `src/services/alert_state.py::AlertStateService` | service | Bestehende Folge-Versand-Dedupe (`last_reported_value`), unverändert — arbeitet bereits auf `(region_label, hazard)`-Keys |
| `src/utils/timezone.py::tz_for_coords`, `local_fmt` | utility | Lokalzeit-Formatierung von `valid_from`/`valid_to` |
| `src/output/renderers/alert/official_alerts.py::collect_trip_alert_entries` | function | Dedup-Vorbild (Briefing-Pfad), Gruppierungslogik als Referenz für den neuen Alert-Dedup-Helper |
| `src/services/notification_service.py::send_official_alert`, `_dispatch_alert_message` | function | Beide Aufrufer des Plain-Renderers für amtliche Warnungen — beide profitieren automatisch von der Quellen-Dedup |

## Implementation Details

**1. Dedup an der Render-Grenze (robuster Ort)** — neue Helper-Funktion
`dedupe_official_alerts(alerts: list) -> list` in
`src/output/renderers/alert/official_alerts.py`, die nach dem Schlüssel
`(a.region_label, a.hazard)` gruppiert und je Gruppe den Repräsentanten mit dem
höchsten `a.level` behält (bei Gleichstand: erstes Vorkommen, analog
`collect_trip_alert_entries`-Reihenfolge-Erhalt).

**Warum an der Render-Grenze statt nur an der Quelle:** Die Dedup wird INNERHALB der
neuen `render_official_alert_notice_plain()` aufgerufen (Detail 2), damit die
ausgegebene Mail GARANTIERT dedupliziert ist — unabhängig davon, welcher Aufrufer die
Notices liefert (defensiv, testbar mit direkt konstruierten Duplikaten). Zusätzlich
wird `dedupe_official_alerts` in `check_official_alert_triggers`
(`src/services/trip_alert.py:920`) vor der State-Schleife (Zeile 953) angewendet, damit
`_record_official_alert_state` keine 12 identischen Keys schreibt (Sekundär-Hygiene, das
sichtbare Verhalten garantiert bereits die Render-Grenze). Der Fix an der Quelle allein
wäre end-to-end nur mit echten, aktuell aktiven Warnungen prüfbar (flaky) — die Dedup im
Formatter macht AC-1 deterministisch ohne Mock.

**2. Neue Plain-Formatfunktion** (`src/output/renderers/alert/official_alerts.py`,
NEU, unterhalb von `render_official_alerts_plain`):

```
def render_official_alert_notice_plain(
    alerts: list["OfficialAlert"], tz: "ZoneInfo | None" = None,
) -> list[str]:
    """Standalone-Alert-Format (Issue #1172): dedupliziert die Warnungen
    (dedupe_official_alerts) und rendert pro echter Warnung einen Block mit
    Schwere-Wort, Region und lokalem Gueltigkeitszeitraum. NICHT identisch mit
    render_official_alerts_plain() (Compare/Briefing bleiben unveraendert)."""
```

Die Funktion ruft ZUERST `alerts = dedupe_official_alerts(alerts)` auf, DANN rendert sie
je verbleibender Warnung einen Block. Damit ist die Ausgabe unabhängig vom Aufrufer
dedupliziert.

Level-Wort-Mapping (Vigilance-Skala, `models.py`-Docstring): 1=gruen/unkritisch,
2=gelb, 3=orange, 4=rot. Emoji-Praefix analog PO-Beispiel (🟢/🟡/🟠/🔴). Format je
Warnung (3 Zeilen, Leerzeile zwischen mehreren Warnungen):
```
🟠 ORANGE — {label}
Region: {region_label or "unbekannt"}
Gültig: {valid_from lokal} – {valid_to lokal}
```
`valid_from`/`valid_to` fehlend → Zeile „Gültig: unbekannt". `tz=None` → UTC-Fallback
(`ZoneInfo("UTC")`), Format `local_fmt(dt, tz, "%a %d.%m. %H:%M")`.

**3. Call-Site-Anpassung `notification_service.py`:**

- `send_official_alert` (Zeile 378-420): `tz` wird aus `trip.waypoints[0]`
  (falls vorhanden, sonst `ZoneInfo("UTC")`) via `tz_for_coords` bestimmt; Aufruf
  wechselt von `render_official_alerts_plain(entries)` auf
  `render_official_alert_notice_plain(notices, tz=alert_tz)`. `entries`-Zeile 393
  entfällt (nicht mehr benötigt).
- `_dispatch_alert_message` (Zeile 460-494): bekommt neuen optionalen Parameter
  `alert_tz: Optional[ZoneInfo] = None`; die drei Aufrufer `send_deviation_alert`
  (Zeile 336-344), `send_location_deviation_alert` (Zeile 369-376) und
  `send_radar_alert` (Zeile 451-458) reichen ihr bereits vorhandenes lokales
  `alert_tz` durch. Innerhalb von `_dispatch_alert_message` wechselt der
  `official_notices`-Block (Zeile 482-494) von `render_official_alerts_plain(entries)`
  auf `render_official_alert_notice_plain(official_notices, tz=alert_tz)`.

**4. Ausdrücklich NICHT verändert:** `render_official_alerts_plain()` und
`render_official_alerts_html()` (Compare-Mail-Warnzeile + Trip-Briefing-Warnblock,
`plain.py:202`, `html.py`, `compact.py`, Compare `comparison.py`/`compare_html.py`) —
byte-gleich, kein neuer Call-Site-Wechsel dort. `collect_trip_alert_entries()`
unverändert.

## Expected Behavior

- **Input:** Trip mit N Etappen, deren Wetterdaten (`cached`) N identische amtliche
  Warnungen (gleiche `region_label`+`hazard`, ggf. unterschiedliches `level`) über
  `get_official_alerts_for_location()` liefern.
- **Output:** Standalone-Alert-Mail (Email+Telegram, identischer Body) enthält GENAU
  EINEN Warnblock mit dem höchsten aufgetretenen `level`, Region und lokalem
  Gültigkeitszeitraum — statt N wiederholter Zeilen ohne Kontext.
- **Side effects:** Keine Änderung an `AlertStateService`-Persistenz-Format
  (`official_alert:{region_label}:{hazard}`-Keys bleiben identisch — die Dedup erfolgt
  vor der State-Prüfung, nicht in der State-Struktur selbst). Compare-Mail und
  Trip-Briefing (Renderer unverändert) zeigen weiterhin ihr bisheriges Format.

## Acceptance Criteria

- **AC-1:** Given ein Test-Trip mit mehreren Etappen, deren Koordinaten in derselben
  amtlichen Warnregion liegen (gleiche `region_label`+`hazard`) / When der amtliche
  Alert-Trigger den Standalone-Versand auslöst / Then enthält die versendete Mail an
  gregor-test@henemm.com GENAU EINEN Warnblock für diese Warnung, nicht N wiederholte
  Zeilen.
  - Test: echter Alert-Versand über `_send_official_alert_only(trip, notices)` mit
    `notices` = mehrere direkt konstruierte, identische `OfficialAlert`-Objekte (gleiche
    `region_label`+`hazard`) an gregor-test@henemm.com, danach IMAP-Abruf (`GZ_IMAP_*`)
    und Zählen der Warnblock-Vorkommen im Body — Erwartung: genau EINS. Deterministisch
    ohne Mock (die Notices werden real konstruiert, der Versand-/Render-/IMAP-Pfad läuft
    echt); die Dedup an der Render-Grenze garantiert das Ergebnis unabhängig von aktuell
    aktiven realen Warnungen.

- **AC-2:** Given eine amtliche Warnung mit bekanntem `level`, `region_label`,
  `valid_from`/`valid_to` / When die Standalone-Alert-Mail gerendert und versendet
  wird / Then enthält der Mail-Body für diese Warnung Schwere-Stufe als Wort (z.B.
  „ORANGE"), den Regionsnamen und einen lesbaren Gültigkeitszeitraum (Start–Ende).
  - Test: echter Versand an gregor-test@henemm.com mit einer präparierten
    `OfficialAlert` (level=3, region_label="Haute-Corse", valid_from/valid_to
    gesetzt), IMAP-Abruf, Prüfung dass Body alle drei Bestandteile (Schwere-Wort,
    Regionsname, beide Zeitpunkte lokal formatiert) enthält.

- **AC-3:** Given mehrere `OfficialAlert`-Objekte mit identischem
  `(region_label, hazard)` aber unterschiedlichem `level` (z.B. 2 und 4) / When die
  neue Dedup-Funktion `dedupe_official_alerts` darauf angewendet wird / Then liefert
  sie genau ein Objekt für diese Gruppe mit `level == 4` (Maximum), nicht das erste
  oder ein gemitteltes; unterschiedliche `(region_label, hazard)` bleiben getrennt.
  - Test: echte `OfficialAlert`-Instanzen (keine Mocks) mit identischem
    `region_label`/`hazard` und Levels `[2, 4, 3]` plus eine Warnung mit anderem
    `hazard` durch `dedupe_official_alerts` schicken, Ergebnis auf Länge 2 prüfen und
    dass die kollabierte Gruppe `level == 4` trägt.

- **AC-4:** Given die geteilten Renderer `render_official_alerts_plain`/`_html`
  (Compare-Mail + Trip-Briefing) / When die Dedup- und Anreicherungs-Änderung aus
  diesem Fix eingespielt wird / Then bleiben Compare-Warnzeile und
  Trip-Briefing-Warnblock byte-gleich zum Vorzustand — keine Regression.
  - Test: `uv run pytest tests/tdd/test_issue_1087_trip_official_alerts.py
    tests/tdd/test_issue_1110_compare_mail_v2.py
    tests/tdd/test_issue_1150_compare_validator_hourly.py
    tests/tdd/test_issue_1088_official_alert_triggers.py` läuft vollständig grün
    (bestehende Suite, keine Anpassung an Erwartungswerten dieser Tests nötig, da
    `render_official_alerts_plain`/`_html` unverändert bleiben).

- **AC-5:** Given der Telegram-Kanal ist für einen Trip aktiv / When derselbe
  amtliche Alert-Trigger wie in AC-1 feuert / Then erhält der Telegram-Alert
  denselben deduplizierten und angereicherten Inhalt wie die E-Mail (identischer
  Warnblock-Text, keine separate Kürzung ohne Kerninfos).
  - Test: echter Standalone-Alert-Versand über `_send_official_alert_only` mit
    `effective_channels={"email", "telegram"}` gegen den Staging-/Test-Bot
    (`GZ_TELEGRAM_LIVE=1`, opt-in gemäß Projektregel), Vergleich des Telegram-Body-
    Strings mit dem IMAP-abgerufenen Email-Plain-Body auf inhaltliche Gleichheit
    (gleiche Warnblöcke, gleiche Schwere-Wörter, gleiche Region/Zeitraum).

## Known Limitations

- HTML-Variante der neuen Kerninfos ist NICHT Teil dieses Fixes — der Standalone-
  Alert-Versand (`send_official_alert`, `_dispatch_alert_message`) nutzt ausschließlich
  Plain-Text (Email `html=False` bzw. `plain_text_body`). `render_official_alerts_html`
  bleibt unverändert und unbenutzt in diesem Pfad.
- Quell-Link (`OfficialAlert.url`) wird bewusst NICHT ausgegeben — PO-Entscheidung
  (Dedup + Kerninfos, kein Quell-Link).
- Die Lokalzeit-Bestimmung für `valid_from`/`valid_to` nutzt die Koordinaten des
  ersten Trip-Segments bzw. `trip.waypoints[0]` (Standalone-Pfad), nicht die exakten
  Koordinaten der jeweiligen Warnregion selbst (die `OfficialAlert` nicht als Feld
  trägt) — bei Trips, die mehrere Zeitzonen durchqueren, ist dies eine Näherung
  („lokal zur Tour" statt „lokal zur Warnregion" im engsten Sinn). Für die
  betroffenen Warnregionen (FR-Vigilance, AT-GeoSphere) liegt dies praktisch nie
  auseinander, da beide Quellen jeweils nur EINE Zeitzone abdecken.
- SMS bleibt weiterhin ohne amtliche-Warnungs-Zusatztext (bestehende Nicht-Parität,
  Slice-3-AC-6, unverändert durch diesen Fix).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix innerhalb der bestehenden Architektur aus #1087
  (geteilter Renderer) und #1088 (Standalone-Alert-Pfad). Es wird keine neue
  architekturelle Entscheidung getroffen — im Gegenteil, die zentrale Design-
  Entscheidung dieses Fixes ist bewusst, die bestehende ADR-0011-Leitplanke
  (ein gemeinsamer Renderer für Compare/Briefing) NICHT zu verletzen, indem die
  Anreicherung in eine neue, alert-spezifische Funktion ausgelagert wird statt den
  geteilten Renderer zu erweitern.

## Changelog

- 2026-07-09: Initial spec created
