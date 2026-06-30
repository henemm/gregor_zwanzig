---
entity_id: issue_919_radar_alert_canonical
type: feature
created: 2026-06-30
updated: 2026-06-30
status: implemented
workflow: feat-919-radar-alert-canonical
---

# Radar-Alert auf kanonischen Renderer migrieren (#919)

## Approval

- [x] Approved

## Purpose

Migriert den Radar-/Nowcast-Alert-Pfad auf den kanonischen Alert-Renderer (Issue #917), sodass beide Alert-Typen (Abweichungs-Alert und Onset-Alert) dieselben vier Renderer durchlaufen (`render_subject`, `render_email`, `render_telegram`, `render_sms`). Die Datei `src/outputs/radar_alert.py` wird danach gelöscht; doppeltes Format-Wissen existiert dann nicht mehr im Projekt.

## Source

- **File:** `src/output/renderers/alert/model.py` (Datenmodell-Erweiterung)
- **File:** `src/output/renderers/alert/render.py` (Renderer-Erweiterung, Onset-Zweige)
- **File:** `src/services/trip_alert.py` (Aufruf-Umbau in `check_radar_alerts`)
- **Identifier:** `class OnsetEvent`, `class AlertMessage`, `def check_radar_alerts`

> **Schicht:** Python-Backend (`src/output/`, `src/services/`). Kein Frontend, kein Go-API.

## Estimated Scope

- **LoC:** ~120 (+) / ~80 (−)
- **Files:** 5 (model.py +, render.py +, trip_alert.py ~, radar_alert.py −, tests +)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/alert/model.py` | module | Datenmodell; wird um `OnsetEvent` + `cooldown_display` erweitert |
| `src/output/renderers/alert/render.py` | module | Vier-Kanal-Renderer; erhält Onset-Zweige |
| `src/services/trip_alert.py` | service | `check_radar_alerts` konstruiert künftig `AlertMessage(OnsetEvent(...))` |
| `src/outputs/radar_alert.py` | module | Wird gelöscht nach Migration |
| `src/services/radar_service.py` | service | Liefert `result.onset_minutes`, `result.is_convective`, `source_label()` |

## Implementation Details

### Datenmodell (`model.py`)

Neue, eigenständige Dataclass für Onset-Ereignisse — kein Mischmodell mit `AlertEvent`:

```python
@dataclass(frozen=True)
class OnsetEvent:
    onset_minutes: int       # Minuten bis Niederschlagsbeginn
    onset_time: str          # "HH:MM" lokale Zeit
    km_from: float
    km_to: float
    is_convective: bool      # True = Gewitter, False = Regen
    intensity_label: str     # z.B. "leichter Regen", "Starkregen"
    source_label: str        # z.B. "Radar (DWD)"
```

`AlertMessage` erhält zwei neue Felder:

```python
events: tuple[AlertEvent | OnsetEvent, ...]   # Union statt nur AlertEvent
cooldown_display: str | None = None            # NEU: Pflichttext Cooldown-Hinweis
```

`km_span` muss beide Event-Typen unterstützen (beide tragen `km_from`/`km_to`).

### Renderer (`render.py`)

Jede der vier `render_*`-Funktionen erhält einen Branch am Anfang:

```python
if msg.source is not None:
    return _render_*_onset(msg)
# bisheriger Deviation-Pfad bleibt unverändert
```

**Betreff-Format (`_render_subject_onset`):**
- Nicht-konvektiv: `[<trip_short>] km <a>–<b> · Regen in <m> Min`
- Konvektiv: `[<trip_short>] km <a>–<b> · Gewitter in <m> Min`

**E-Mail HTML/Plain (`_render_email_onset`):**
- H1: `Regen in <m> Min` oder `Gewitter in <m> Min`
- Datenzeile: `km <a>–<b> · <intensity_label> ab <onset_time>`
- Fusszeile: `Stand: heute <stand_at> · km <a>–<b> · Quelle: <source_label>`
- Cooldown-Block: `Du erhältst diese Warnung höchstens einmal in <cooldown_display>`

**Telegram (`_render_telegram_onset`):**
- Erste Zeile fett: `**<trip_short> · km <a>–<b> · Regen/Gewitter in <m> Min**`
- Folgezeile: `<onset_time> · <intensity_label> · <source_label>`

**SMS GSM-7 max 140 Zeichen (`_render_sms_onset`):**
- Token-Format: `<trip-kompakt> km<a>-<b>: R!<min>` (Regen) oder `TH!<min>` (Gewitter)
- `!` ist der Onset-Marker analog zu `+`/`-` beim Deviation-Token
- Längenüberlauf: Suffix `+k` wie beim Deviation-Pfad

### Aufruf-Umbau (`trip_alert.py`)

Der bisherige Block ab Zeile 737 (Import `build_radar_alert_*`, Aufruf) wird ersetzt durch Konstruktion von `OnsetEvent` + `AlertMessage` und Aufruf der vier kanonischen `render_*`-Funktionen. Mail-Versand erhält `html`- und `plain`-Part aus `render_email(msg)`. Telegram-Versand erhält Text aus `render_telegram(msg)`.

### Löschung

Nach grünen Tests: `src/outputs/radar_alert.py` per `git rm` entfernen. Alle Importe in `trip_alert.py` bereinigen.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/model.py` | MODIFY | `OnsetEvent` hinzufügen, `AlertMessage.cooldown_display` hinzufügen, `km_span` union-fähig machen |
| `src/output/renderers/alert/render.py` | MODIFY | Onset-Zweige in alle vier `render_*`-Funktionen, private `_render_*_onset`-Helfer |
| `src/services/trip_alert.py` | MODIFY | `check_radar_alerts` nutzt `AlertMessage(OnsetEvent(...))` statt `build_radar_alert_*` |
| `src/outputs/radar_alert.py` | DELETE | Wird nach Migration per `git rm` entfernt |
| `tests/tdd/test_issue_919_radar_alert_canonical.py` | CREATE | TDD-Tests für alle 8 ACs |

### Estimated Changes

- Files: 5
- LoC: +120 / −80

## Test Plan

### Automated Tests (TDD RED)

- [x] **Test 1 (AC-1):** GIVEN ein `AlertMessage` mit einem `OnsetEvent` (`is_convective=False`, `onset_minutes=12`, `km_from=5.0`, `km_to=18.0`, `source="Radar (DWD)"`) WHEN `render_subject(msg)` aufgerufen wird THEN enthält der Rückgabe-String `"km 5"` und `"Regen in 12 Min"` und enthält weder `"%"` noch `"→"`.

- [x] **Test 2 (AC-2):** GIVEN ein `AlertMessage` mit einem `OnsetEvent` (`is_convective=True`, `onset_minutes=8`) WHEN `render_subject(msg)` aufgerufen wird THEN enthält der Rückgabe-String `"Gewitter in 8 Min"` und enthält nicht das Wort `"Regen"`.

- [x] **Test 3 (AC-3):** GIVEN ein `AlertMessage` mit einem `OnsetEvent` und `cooldown_display="2 Stunden"` WHEN `render_email(msg)` aufgerufen wird THEN enthält der HTML-Part `"Radar (DWD)"` und der Plain-Part `"höchstens einmal in"`.

- [x] **Test 4 (AC-4):** GIVEN ein `AlertMessage` mit einem `OnsetEvent` (`onset_time="14:35"`, `source_label="Radar (DWD)"`) WHEN `render_telegram(msg)` aufgerufen wird THEN enthält der Rückgabe-String `"14:35"` und `"Radar (DWD)"`.

- [x] **Test 5 (AC-5, nicht-konvektiv):** GIVEN ein `AlertMessage` mit einem `OnsetEvent` (`is_convective=False`, `onset_minutes=12`) WHEN `render_sms(msg)` aufgerufen wird THEN enthält der Rückgabe-String `"R!12"`, ist maximal 140 Zeichen lang und enthält ausschliesslich GSM-7-Zeichen.

- [x] **Test 6 (AC-5, konvektiv):** GIVEN ein `AlertMessage` mit einem `OnsetEvent` (`is_convective=True`, `onset_minutes=8`) WHEN `render_sms(msg)` aufgerufen wird THEN enthält der Rückgabe-String `"TH!8"`.

- [x] **Test 7 (AC-6):** GIVEN ein `TripAlertService` mit `_mail_sink` und einem Trip mit positivem Nowcast WHEN `check_radar_alerts` aufgerufen wird THEN enthält `subject` an `_mail_sink` den Text `"Regen in"` oder `"Gewitter in"`, und `build_radar_alert_subject` / `build_radar_alert_body` werden nicht aufgerufen.

- [x] **Test 8 (AC-8):** GIVEN ein `AlertMessage` mit `AlertEvent`-Events und `source=None` WHEN alle vier `render_*`-Funktionen aufgerufen werden THEN sind die Ausgaben identisch zum vorherigen Deviation-Format (Regression-Guard per Snapshot-Vergleich).

## Acceptance Criteria

- **AC-1:** Given ein Radar-Onset-Alert (nicht-konvektiv, Regen) / When `render_subject(msg)` aufgerufen wird mit `msg.source != None` / Then enthält der Betreff `km <a>–<b>` und `Regen in <m> Min`; kein Δ-Prozentsatz, kein Wert-Pfeil.

- **AC-2:** Given ein Radar-Onset-Alert (konvektiv, Gewitter) / When `render_subject(msg)` aufgerufen wird / Then enthält der Betreff `Gewitter in <m> Min` und nicht das Wort `Regen`.

- **AC-3:** Given ein Radar-Onset-Alert mit gesetztem `cooldown_display` / When `render_email(msg)` aufgerufen wird / Then enthält der HTML-Part die Quellenangabe (z.B. "Radar (DWD)") und der Plain-Part den Cooldown-Text ("höchstens einmal in").

- **AC-4:** Given ein Radar-Onset-Alert / When `render_telegram(msg)` aufgerufen wird / Then enthält der Text die Onset-Uhrzeit (HH:MM) und die Quellenangabe.

- **AC-5:** Given ein Radar-Onset-Alert / When `render_sms(msg)` aufgerufen wird / Then enthält der SMS-Text einen `!`-Onset-Token (`R!<min>` oder `TH!<min>`), ist maximal 140 Zeichen lang und enthält ausschliesslich GSM-7-Zeichen.

- **AC-6:** Given `check_radar_alerts` erzeugt einen Alert / When dieser versendet wird / Then werden `build_radar_alert_subject` und `build_radar_alert_body` nicht mehr aufgerufen; stattdessen wird `AlertMessage` mit `OnsetEvent` konstruiert und durch die kanonischen `render_*`-Funktionen geleitet.

- **AC-7:** Given die Datei `src/outputs/radar_alert.py` / When die Migration abgeschlossen ist / Then existiert diese Datei nicht mehr im Repository (`git ls-files src/outputs/radar_alert.py` liefert keinen Treffer).

- **AC-8:** Given ein bestehender Abweichungs-Alert (Deviation) mit `msg.source = None` / When `render_subject`, `render_email`, `render_telegram` und `render_sms` aufgerufen werden / Then sind die Ausgaben identisch zu den Ausgaben vor dieser Änderung (keine Regression).

## Known Limitations

- SMS-Versand für Radar-Alerts ist noch nicht konfigurierbar — `render_sms` wird implementiert, aber der Versand-Pfad in `check_radar_alerts` wird in einem Folge-Issue angeschlossen.
- Live-Vorschau des Radar-Alerts im Frontend (analog Issue #918 Slice 3) ist Out of Scope.
- Neue Radar-Datenquellen sind Out of Scope.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (bereits dokumentiert für Issue #917)
- **Rationale:** Die Erweiterung folgt dem in ADR-0011 vorgesehenen additiven Erweiterungs-Muster: `OnsetEvent` ist eine zweite eigenständige Event-Art neben `AlertEvent`; die gemeinsame Hülle `AlertMessage` bleibt im Kern unverändert. Kein Mischmodell, kein Breaking Change für den Deviation-Pfad.

## Changelog

- 2026-06-30: Initial spec created
- 2026-06-30: Implemented — 10 tests grün, `src/outputs/radar_alert.py` gelöscht, status auf `implemented` gesetzt
