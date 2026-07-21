---
entity_id: issue_651_telegram_query_glance
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [telegram, inbound, query, glance, epic-639]
---

# #651 — Telegram-Abfrage-Befehle (`/s /h /m /hg`) + Tier-1-Glance

## Approval

- [x] Approved (PO 'go' 2026-06-07)

## Purpose

Ergänzt den Telegram-Bot um **lesende, non-destruktive** Abfrage-Befehle und eine
kompakte „Glance"-Zusammenfassung der heute **und** morgen aktiven Etappe. Teil 2/6
von Epic #639 — erfüllt dessen AC-1 (kontextuelle Info-Dichte).

## Source

- **File:** `src/services/trip_command_processor.py` (neue Query-Handler + Glance-Formatter)
- **File:** `src/services/inbound_telegram_reader.py` (Kurzbefehl-Mapping `/s /h /m /hg`)
- **File:** `src/services/weather_extractor.py` (Datenquelle, #652 — read-only genutzt)
- **Identifier:** `TripCommandProcessor`, `InboundTelegramReader._parse_command`, `CommandResult`

> **Schicht:** Reines Python-Backend (`src/services/`). Kein Go, kein Frontend.
> Der Webhook-Eingang (`api/routers/webhook.py` → `_process_update`) bleibt unverändert;
> Button-Klicks (`callback_query`) sind explizit NICHT Teil dieses Issues (→ #655).

## Estimated Scope

- **LoC:** ~200–250 (Query-Handler, Glance-Formatter, Kurzbefehl-Mapping; Tests separat)
- **Files:** 3 Source (`trip_command_processor.py`, `inbound_telegram_reader.py`, ggf. kleiner Helper) + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TelegramOutput.send(reply_markup=)` | upstream (#650 ✅) | Buttons auf den Draht legen |
| `WeatherExtractor` | upstream (#652 ✅) | Snapshot-Daten ohne Report-Build |
| `Trip.stages` / `Stage.date` | model | Aktive-Etappe-Auflösung aus `received_at` |
| `CommandResult` | DTO | wird um optionales `reply_markup` erweitert (additiv) |

## Implementation Details

### 1. Read-only Query-Befehle (TripCommandProcessor)

Neue Query-Schlüssel, die den Trip **nie** verändern (kein `save_trip`, kein
`_append_command_log`, kein `_delete_snapshot`):

| Query-Key | Bedeutung | Telegram-Kurzbefehl |
|-----------|-----------|---------------------|
| `glance`  | Tier-1-Übersicht heute + morgen | `/s` (und `/status`) |
| `heute`   | Glance nur heute | `/h` |
| `morgen`  | Glance nur morgen | `/m` |
| `heute_gewitter` | Gewitter-Fokus heute (kompakt) | `/hg` |

Langform ebenfalls akzeptiert: `### query: glance` usw.

Dispatch erweitert: Query-Keys laufen über einen separaten read-only Pfad
`_handle_query(trip, query_key, received_at, user_id)`, der **vor** dem
verändernden Dispatch greift und garantiert keine Schreib-Helper aufruft.

### 2. Aktive-Etappe-Auflösung

```
heute_stage  = stage in trip.stages mit stage.date == received_at.date()  (lokal)
morgen_stage = stage in trip.stages mit stage.date == received_at.date() + 1 Tag
```
Existiert keine passende Etappe (Trip noch nicht gestartet / schon vorbei),
wird das im Text klar benannt („Heute keine geplante Etappe").

### 3. Glance-Formatter

Aus `WeatherExtractor.timeline(trip.id)` die `TimelinePoint`s nach
`arrival_time`-Datum auf heute/morgen filtern und kompakt aggregieren:
- Temperatur: min/max über die Tagespunkte
- Wind/Böen: max
- Niederschlag: Summe bzw. max-Wahrscheinlichkeit (`pop_max_pct`)
- Gewitter: höchstes `thunder_level_max`

Kompakte, emoji-gestützte Textzeilen (sonnentauglich). Bei fehlendem Snapshot:
klarer Hinweistext statt Fehler, Buttons trotzdem vorhanden.

### 4. Buttons (reply_markup)

`CommandResult` bekommt optionales Feld `reply_markup: Optional[dict] = None`
(additiv, Default None → Email-Pfad bit-identisch). Für `glance` werden zwei
Buttons gesetzt:

```json
{"inline_keyboard": [[
  {"text": "📋 Timeline heute",  "callback_data": "tl_today"},
  {"text": "📋 Timeline morgen", "callback_data": "tl_tomorrow"}
]]}
```

`inbound_telegram_reader._process_update` reicht `result.reply_markup` an
`TelegramOutput.send(...)` durch.

### 5. Kurzbefehl-Mapping (inbound_telegram_reader)

`_parse_command` erkennt zusätzlich `/s /h /m /hg` (mit führendem Slash) und
mappt sie auf die Query-Keys. `### query: <key>` und nackte Query-Keys ebenfalls.
`_VALID_COMMANDS` wird um die Query-Keys erweitert.

## Expected Behavior

- **Input:** Telegram-Text `/s`, `/h`, `/m`, `/hg` (oder `### query: glance` etc.).
- **Output:** Kompakte Glance-Textantwort; bei `/s` zusätzlich zwei Inline-Buttons.
- **Side effects:** **KEINE** — kein Trip-Save, kein `command_log.json`-Eintrag,
  keine Snapshot-Löschung.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer sendet `/s` (bzw. `/status` oder `### query: glance`),
  When der Bot antwortet, Then enthält die Textantwort eine Zusammenfassung für die
  **heute** UND **morgen** aktive Etappe, und die Antwort trägt ein `reply_markup`
  mit den Buttons „Timeline heute" und „Timeline morgen".
  - Test: `InboundMessage(channel="telegram", body="### query: glance", received_at=<Tag mit Etappe heute+morgen>)` → `CommandResult.confirmation_body` nennt beide Etappen-Tage und Wetterwerte; `CommandResult.reply_markup["inline_keyboard"]` enthält zwei Buttons mit den erwarteten Texten. Snapshot via echtem `WeatherSnapshotService.save` (kein Mock).

- **AC-2:** Given irgendein lesender Abfrage-Befehl (`/s /h /m /hg`),
  When er verarbeitet wird, Then bleibt der Trip-Zustand unverändert: kein neuer
  Eintrag in `command_log.json` und keine Etappen-Datumsverschiebung.
  - Test: vor/nach Verarbeitung `command_log.json`-Inhalt und alle `stage.date`-Werte
    byte-genau identisch (echte Datei-I/O gegen `tmp_path`).

- **AC-3:** Given `/h` bzw. `/m`, When verarbeitet, Then enthält die Antwort die
  Glance NUR für den jeweiligen Tag (heute bzw. morgen) und nennt den korrekten Tag.
  - Test: `/h` → Body nennt heutiges Etappendatum, nicht das morgige; `/m` umgekehrt.

- **AC-4:** Given `/hg`, When verarbeitet, Then enthält die Antwort den
  Gewitter-Status für heute (auch wenn Gewitter in der Standard-Glance knapp ist),
  als eigene fokussierte Zeile.
  - Test: Snapshot mit `thunder_level_max` gesetzt → `/hg`-Body nennt das Gewitter-Level
    explizit für heute.

- **AC-5:** Given die Kurzbefehle treffen über den Telegram-Inbound-Pfad ein,
  When `_parse_command` sie verarbeitet, Then werden `/s /h /m /hg` korrekt auf die
  Query-Keys gemappt (kein „Unbekannter Befehl").
  - Test: `InboundTelegramReader._parse_command("/hg")` → `("heute_gewitter", None)` o.ä.;
    der bestehende verändernde Pfad (`ruhetag 2`) bleibt unverändert grün.

- **AC-6:** Given kein Wetter-Snapshot für den Trip existiert, When `/s` gesendet wird,
  Then antwortet der Bot mit einem klaren Hinweistext (kein Crash, kein leerer Body)
  und die Buttons sind trotzdem vorhanden.
  - Test: kein `save` → `glance`-Body enthält Hinweis „kein Snapshot/keine Wetterdaten";
    `reply_markup` weiterhin gesetzt.

## Non-Goals (explizit ausgeschlossen)

- **Button-Klick-Verarbeitung** (`callback_query`, `editMessageText`) → #655.
- **Tier-2 Timeline-Rendering** (vertikale Wegpunktliste) → #653.
- **Tier-3 Drilldown** (stündliche Einzelmetrik) → #654.
- Änderung des Email-`### status`-Verhaltens (bleibt Etappenliste).
