---
entity_id: feat_1001_telegram_redesign
type: feature
created: 2026-07-03
updated: 2026-07-03
status: draft
version: "1.0"
tags: [telegram, output, briefing, multi-bubble, inline-keyboard]
---

<!-- Issue #1001 — Telegram-Ausgabe neu bauen: echte Segment-Tabelle, Multi-Bubble,
     Kurzübersicht, Inline-Keyboard. Ersetzt fachlich #635, #614/615 (Text-Anhang-Teil),
     #887, #612-AC4. Absorbiert den fachlichen Kern von #623/#640 (beide draft), die
     danach neu spezifiziert werden. -->

# Feature #1001 — Telegram-Ausgabe neu bauen (Multi-Bubble-Format)

## Approval

- [ ] Approved

## Purpose

Die Telegram-Briefing-Ausgabe wird von einer einzelnen Prosa-Nachricht auf mehrere
einzeln zitierbare Nachrichten ("Bubbles") mit echten Monospace-Tabellen, einer immer
aktiven Kurzübersicht und einem Inline-Keyboard für Aktionen umgestellt — nach einer
bereits vorliegenden externen Design-Vorgabe (Claude-Design-Projekt "Gregor Zwanzig",
Datei `Gregor 20 - Telegram Vorschau.html`). Ziel ist echte tabellarische Lesbarkeit
auf dem engsten Ausgabekanal des Produkts, ohne die 8-Spalten-Grenze der Bot-API-
Darstellung zu sprengen.

## Source

- **File:** `src/output/renderers/narrow.py` — neue Funktion `render_telegram_bubbles()`
  ersetzt `render_narrow()` für `channel == "telegram"` vollständig (Breaking Replace).
  Entfernt: `_tg_segment_line()`, `_tg_extra_detail_line()`, `_tg_day_footer()`,
  der Text-Befehls-Footer-Block (Zeile 531-536) und die `cmd_hint`-Zeile. Wiederverwendet:
  `_narrow_table()` (Zeile 115-151, bislang nur für den abgeschalteten Signal-Kanal
  aktiv), `_wrap()`, `_compact_label()`, `_tg_vortag_line()`.
- **File:** `src/formatters/trip_report.py` (Zeile 182-253) — Verkabelung auf
  `render_telegram_bubbles()`, Entfernung des `telegram_kurzform`-Textanhang-Zweigs
  (Zeile 226-238).
- **File:** `src/app/models.py` — `TripReport.telegram_text: Optional[str]` (Zeile 677)
  wird zu `TripReport.telegram_bubbles: list[str]`; neues Feld
  `TripReport.telegram_actions_markup: Optional[dict]` transportiert das Inline-Keyboard
  der letzten (Aktionen-)Bubble getrennt von den reinen Text-Bubbles. `telegram_kurzform`
  (Zeile 570 auf `UnifiedWeatherDisplayConfig`) wird wirkungslos (Feld bleibt aus
  Altdaten-Kompatibilität bestehen, siehe Known Limitations).
- **File:** `src/services/trip_report_scheduler.py` (Zeile 631-640) — Multi-Send-Schleife
  über `report.telegram_bubbles`; `report.telegram_actions_markup` wird ausschließlich an
  die letzte Nachricht angehängt. Fehlerpolitik: Abbruch nach erstem Fehlschlag, ein
  Log-Eintrag, kein Teil-Retry.
- **File:** `src/services/trip_command_processor.py` (Zeile 100-724) — neue Callback-
  Aktionen für die Aktionen-Bubble (Trip-Übersicht, Pause, Überspringen, Spalten ändern,
  Hilfe), Callback-Namen mit eigenem Präfix (siehe Implementation Details) statt
  Kollision mit den bereits produktiv genutzten `dd_*`-Drilldown-Callbacks.
- **File:** `src/services/inbound_telegram_reader.py` — neue Handler-Zweige für die
  neuen Callback-Namen, analog zum bestehenden `_callback_to_body()`-Dispatch
  (Zeile 269-275).
- **File:** `src/services/preview_service.py` (Zeile 216-236) —
  `render_telegram_preview()` liefert zusätzlich die Bubble-Liste zurück.
- **File:** `api/routers/preview.py` (Zeile 96-119) — Endpoint `GET
  /api/preview/{trip_id}/telegram` liefert zusätzlich `bubbles: list[str]` neben dem
  bestehenden `body`-Feld (additiv, rückwärtskompatibel).

> **Schicht-Hinweis:** Alle Kern-Dateien liegen im Python-Backend
> (`src/services/`, `src/app/`, `src/formatters/`, `src/output/renderers/`, `api/routers/`).
> `internal/handler/preview_proxy.go` (Go, reines JSON-Passthrough) ist **nicht** betroffen.
> Frontend (`frontend/src/...`) ist explizit **nicht** Teil dieses Features (siehe Known
> Limitations).

## Estimated Scope

- **LoC:** 400–600 (überschreitet das 250-LoC-Standardlimit; `loc_limit_override` auf 600
  gesetzt, User-bestätigt am 2026-07-03)
- **Files:** 8 Kern-Dateien (Backend) + 13 identifizierte Bestands-Testdateien zur
  Migration (siehe Test Coverage) + mindestens 1 neue Testdatei für die Bubble-Logik
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.output.renderers.narrow._narrow_table()` | intern (Funktion) | Bestehende Monospace-Tabellen-Logik, wird für Segment-/Ziel-/Ausblick-Bubbles reaktiviert statt neu gebaut |
| `src.output.renderers.channel_layout.render_for_channel()` / `CHANNEL_LIMITS["telegram"]` | intern (Funktion/Konstante) | Liefert `table_columns` (max. 8 Spalten inkl. Zeit) für Segment-Tabellen — bleibt unverändert |
| `src.app.metric_catalog.get_metric().compact_label` / `.col_label` | intern (Funktion) | Kürzel-Quelle für Tabellen-Header UND Kurzübersicht-Bubble — bewusst statt `SMS_SYMBOL_BY_METRIC` (Mockup fordert "gleiche Quelle wie E-Mail-Tabellenkopf") |
| `src.output.tokens.builder.build_token_line()`, `TokenLine`, `HourlyValue` | intern (Modul) | Min/Max/Peak@Stunde-Berechnung hinter der Kurzübersicht-Bubble (ganztägig, alle konfigurierten Metriken) |
| `src.outputs.telegram.TelegramOutput.send()` | intern (Klasse/Methode) | Unveränderter Versand-Baustein; `parse_mode="HTML"` + `suppress_subject_line=True` + optional `reply_markup` pro Bubble-Aufruf. Rückgabewert `message_id` als Erfolgsnachweis |
| `src.services.trip_command_processor.py` Inline-Keyboard-Pattern (Zeile 100-128) | intern (Konvention) | Vorbild für `{"inline_keyboard": [[{"text": ..., "callback_data": ...}]]}`-Struktur der Aktionen-Bubble |
| `docs/adr/0012-telegram-parse-mode-html.md` | ADR | Bereits akzeptierte Entscheidung für `parse_mode="HTML"` + `_esc()`-Escaping — dieses Feature wendet die Entscheidung erstmals auf Briefings (statt nur Alerts) an |
| `docs/specs/modules/issue_360_signal_channel_renderer.md` | Spec (überholt) | Ursprungs-Spec der Tabellen-Logik — #1001 kehrt zur dort spezifizierten Tabellen-Darstellung zurück, jetzt kanal-exklusiv für Telegram statt geteilt mit Signal |
| `docs/specs/modules/issue_635_telegram_weather_readable.md` | Spec (abgelöst) | PO-Entscheidung "Prosa statt Tabelle" — wird durch #1001 fachlich aufgehoben |
| `docs/specs/modules/issue_614_615_telegram_kurzform.md` | Spec (teilweise abgelöst) | Text-Anhang-Mechanik entfällt; die zugrunde liegende Idee (Tages-Kurzform) lebt als eigene Bubble weiter, jetzt mit anderer Kürzel-Quelle |
| `docs/specs/modules/fix_887_report_inkonsistenz.md` | Spec (abgelöst) | Ursprung der jetzt entfernten `_tg_extra_detail_line()`; Bug #994 (kaputte Klammern darin) wird durch Entfernung des Codes miterledigt |

## Implementation Details

### Neuer Rückgabetyp `TelegramBubble`

```python
@dataclass(frozen=True)
class TelegramBubble:
    text: str
    reply_markup: Optional[dict] = None   # nur bei der Aktionen-Bubble gesetzt
```

`render_telegram_bubbles(...) -> list[TelegramBubble]` ersetzt `render_narrow()` für
Telegram vollständig; die Funktionssignatur übernimmt dieselben Parameter wie
`render_narrow()` (`segments`, `seg_tables`, `dc`, `report_type`, `tz`, `trip_name`,
`friendly_keys`, `stability_result`, `multi_day_trend`, `day_comparison`) — pure
function, kein I/O.

`trip_report.py` flacht das Ergebnis für die transiente `TripReport`-DTO ab:

```python
bubbles = render_telegram_bubbles(...)
telegram_bubbles = [b.text for b in bubbles]
telegram_actions_markup = bubbles[-1].reply_markup if bubbles else None
```

### Bubble-Reihenfolge (gemäß Mockup-Struktur)

1. **Kopf-Bubble** — Trip-Name, Report-Typ, Datum, ggf. Wetterlage-Label (WL). Ersetzt
   die bisherigen Header-Zeilen (narrow.py Zeile 433-446).
2. **Kurzübersicht-Bubble** — ALLE konfigurierten Metriken (`dc.get_enabled_metric_ids()`,
   nicht nur `table_columns`) als Kürzel-Zeile für den ganzen Tag, Min/Max/Peak@Stunde-
   Stil über `build_token_line()`. Immer vorhanden (kein Schalter). Übernimmt zusätzlich
   den Inhalt der bisherigen `_tg_day_footer()` (Gewitter/Sicht/0°C-Grenze) und der
   `_tg_vortag_line()` (Top-3-Abweichungen ggü. Vortag, #752) als Fußzeile innerhalb
   derselben Bubble — beide Bausteine bleiben inhaltlich erhalten, wandern aber aus dem
   Fließtext in diese eine Bubble.
3. **Segment-Bubbles** (eine pro Segment) — Mini-Header `"{Segment-Bezeichnung} ·
   {km-Range} · {Höhen-Range}"` gefolgt von einer `_narrow_table()`-Tabelle. km-Range aus
   `seg.start_point.distance_from_start_km`–`seg.end_point.distance_from_start_km`,
   Höhen-Range aus `↑{seg.ascent_m:.0f} m ↓{seg.descent_m:.0f} m`. Versand mit
   `parse_mode="HTML"`, Tabelle in `<pre>…</pre>` gewrappt, Zellinhalte über dieselbe
   `_esc()`-Maskierung wie im E-Mail-HTML (ADR-0012) escaped.
4. **Ziel-Bubble** — wie Segment-Bubbles, für den Etappen-Zielpunkt (`segment_id ==
   "Ziel"`), eigene Tabelle.
5. **Ausblick-Bubble** (nur wenn `multi_day_trend` nicht leer) — 3-Tage-Trend-Tabelle mit
   Kopfzeilen analog zur E-Mail-Outlook-Tabelle, ersetzt den bisherigen Freitext-Block
   (narrow.py Zeile 486-522). Absorbiert den fachlichen Kern von #623/#640 (`
   format_trend_tokens()`-Rechenlogik bleibt wiederverwendet); beide Ursprungs-Issues
   bleiben draft und werden NICHT in #1001 als eigenständige Spec abgeschlossen.
6. **Aktionen-Bubble** — Text "Aktionen" + Inline-Keyboard (Trip-Übersicht, Pause,
   Überspringen, Spalten ändern, Hilfe). Ersetzt den Text-Befehls-Footer (narrow.py
   Zeile 531-536, Issue #612-AC4). Trägt als einzige Bubble ein `reply_markup`.

### Zeilenbreiten-Grenze für Segment-/Ziel-/Ausblick-Tabellen

Der bereits gebaute Wegwerf-Prototyp dieser Session hat `<pre>`+`parse_mode="HTML"`
empirisch gegen den echten Staging-Bot bestätigt, aber auch gezeigt, dass eine zu breite
Tabelle auf dem iPhone umbricht. Für #1001 gilt: eine neue Konstante
`_TG_TABLE_WIDTH = 32` (analog zur bestehenden `_LINE_WIDTH`/`_TG_PROSE_WIDTH`-Konvention
in `narrow.py`) begrenzt die Gesamtbreite jeder Tabellenzeile hart. Der exakte Wert wird
in der TDD-Phase gegen einen erneuten realen Staging-Bot-Versand (Screenshot-Vergleich
oder Zeilenlängen-Messung) verifiziert und bei Bedarf nachjustiert — AC-9 verlangt eine
dokumentierte, eingehaltene Obergrenze, nicht zwingend genau diesen Zahlenwert.

### Callback-Namenskonvention (Aktionen-Bubble)

Bestehende Drilldown-Callbacks nutzen bereits das Präfix `dd_` (z.B. `dd_hours_today`,
`trip_command_processor.py` Zeile 109-127) sowie `tl_` (Timeline). Die neuen
Aktionen-Bubble-Callbacks verwenden das Präfix `act_` (z.B. `act_overview`, `act_pause`,
`act_skip`, `act_columns`, `act_help`), um jede Kollision mit bestehenden und mit den in
Issue #704 (draft, "Telegram Interactive Navigation") vorgesehenen Namen auszuschließen.

### Fehlerpolitik im Scheduler

```python
for i, bubble_text in enumerate(report.telegram_bubbles):
    markup = report.telegram_actions_markup if i == len(report.telegram_bubbles) - 1 else None
    try:
        TelegramOutput(self._settings).send(
            subject=report.email_subject, body=bubble_text,
            reply_markup=markup, parse_mode="HTML", suppress_subject_line=True,
        )
    except OutputError as e:
        logger.error(f"Telegram bubble {i+1}/{len(report.telegram_bubbles)} send failed for {trip.name}: {e}")
        break  # kein Teil-Retry, keine Lücken-Sequenz
```

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/narrow.py` | MODIFY (Rewrite) | Neue Funktion `render_telegram_bubbles()`, `TelegramBubble`-Dataclass; Prosa-Pfad entfernt (`_tg_segment_line`, `_tg_extra_detail_line`, `_tg_day_footer`), `_narrow_table()` für Telegram reaktiviert |
| `src/formatters/trip_report.py` | MODIFY | Verkabelung auf `render_telegram_bubbles()`; `telegram_kurzform`-Textanhang-Zweig entfernt |
| `src/app/models.py` | MODIFY | `telegram_text` → `telegram_bubbles: list[str]` + neues Feld `telegram_actions_markup: Optional[dict]` (transient, kein Persistenz-Migrationsrisiko) |
| `src/services/trip_report_scheduler.py` | MODIFY | Multi-Send-Schleife statt Single-Send; Abbruch-bei-Fehler-Politik |
| `src/services/trip_command_processor.py` | MODIFY | Neue `act_*`-Callback-Definitionen + Inline-Keyboard-Aufbau für die Aktionen-Bubble |
| `src/services/inbound_telegram_reader.py` | MODIFY | Neue Handler-Zweige für `act_*`-Callbacks im bestehenden Dispatch |
| `src/services/preview_service.py` | MODIFY (additiv) | `render_telegram_preview()` gibt zusätzlich die Bubble-Liste zurück |
| `api/routers/preview.py` | MODIFY (additiv) | `bubbles: list[str]` zusätzlich zu `body` in der JSON-Antwort |
| `src/app/models.py` (frontend-seitiges Gegenstück) | — | `WeatherV2Kanaele.svelte` (Frontend, außerhalb Backend-Scope-Zählung): `telegram_kurzform`-Toggle entfernt oder deaktiviert — separater kleiner Edit, kein eigener Kern-Dateizähler |

**Explizit NICHT in #1001:** `ChannelPreviewBlock.svelte`/`ChannelPreviewCard.svelte`
(Frontend-Kanalvorschau, Folge-Ticket), `internal/handler/preview_proxy.go` (Go,
unverändert), `src/outputs/telegram.py` (Versand-Methode selbst bleibt unverändert),
`src/services/trip_alert.py` (eigenständiger Alert-Versandpfad, nicht Briefing-Format).

## Expected Behavior

- **Input:** Ein Trip mit Telegram als aktivem Kanal (`config.send_telegram=True`),
  Segment-Wetterdaten, `UnifiedWeatherDisplayConfig` mit >=1 konfigurierten Metriken.
- **Output:** Statt einer Telegram-Nachricht mit Prosa-Text werden mehrere separate
  Bot-API-`sendMessage`-Aufrufe ausgelöst (Kopf, Kurzübersicht, N Segmente, Ziel,
  optional Ausblick, Aktionen) — jede mit eigener `message_id`. Segment-/Ziel-/
  Ausblick-Bubbles enthalten echte spaltenausgerichtete Monospace-Tabellen. Die
  Aktionen-Bubble trägt ein Inline-Keyboard.
- **Side effects:** `TripReport.telegram_text` existiert nicht mehr (Breaking Change des
  transienten DTOs, kein Persistenz-Impact). Preview-API liefert zusätzlich zum
  bestehenden `body`-Feld ein `bubbles`-Array. Der bisherige Text-Befehls-Footer
  verschwindet aus der Ausgabe, die Text-Befehle selbst bleiben aber funktionsfähig.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Telegram als aktivem Kanal und einer Etappe mit
  mindestens 2 Segmenten / When der Scheduler das Morgen-Briefing an den Staging-Bot
  sendet / Then gehen beim Chat `8346977700` mehrere `sendMessage`-Aufrufe mit jeweils
  eigener `message_id` ein (mindestens 5: Kopf, Kurzübersicht, >=1 Segment, Ziel,
  Aktionen) statt einer einzigen Nachricht.
  - Test: Echter Versand gegen `GregorZwanzigStaging_bot`, Anzahl zurückgegebener
    `message_id`-Werte zählen — kein Mock der Bot-API.

- **AC-2:** Given ein Segment mit konfigurierten `table_columns` / When die zugehörige
  Segment-Bubble gerendert und real verschickt wird / Then enthält sie eine per
  `<pre>`+`parse_mode="HTML"` gesendete, spaltenausgerichtete Monospace-Tabelle mit
  Zeit-Spalte + bis zu 7 Metrik-Spalten (max. 8 Gesamt-Spalten), keine
  `_tg_segment_line()`-Prosa-Zeile mehr.
  - Test: Echter Staging-Bot-Versand, `message_id` als Zustellnachweis, Tabellenstruktur
    (Header-Zeile + ausgerichtete Spalten) im tatsächlich gesendeten Text prüfen.

- **AC-3:** Given ein Trip mit mehr als 8 konfigurierten Metriken (überschreitet also das
  Tabellen-Spaltenlimit) / When ein Briefing für diesen Trip gesendet wird / Then
  enthält die Kurzübersicht-Bubble ALLE konfigurierten Metriken als Kürzel-Zeile
  (`metric_catalog.compact_label`), unabhängig vom 8-Spalten-Limit, und die Bubble
  erscheint bei JEDEM Trip — auch bei `telegram_kurzform=false` oder unbesetztem Feld.
  - Test: Zwei reale Trips (`telegram_kurzform=false` und `=true`) real senden, in
    beiden Fällen die Kurzübersicht-Bubble in den empfangenen Nachrichten nachweisen.

- **AC-4:** Given die Aktionen-Bubble mit Inline-Keyboard wurde real an den Staging-Bot
  gesendet / When ein Callback (z.B. `act_pause`) über einen echten
  `InboundTelegramReader.handle_callback_query()`-Roundtrip verarbeitet wird / Then ist
  der resultierende Trip-Zustand identisch zu dem, der durch den Text-Befehl "pause"
  ausgelöst wird.
  - Test: Echter Callback-Query-Roundtrip gegen laufenden Reader-Code, Trip-Zustand
    (z.B. `paused_until`) vor/nach dem Klick vergleichen — kein Mock.

- **AC-5:** Given eine Bubble im Versand-Loop schlägt fehl (`OutputError` von
  `TelegramOutput.send()`) / When `trip_report_scheduler.py` die Bubble-Schleife
  durchläuft / Then werden keine nachfolgenden Bubbles gesendet, und genau ein
  Fehler-Log-Eintrag entsteht (kein Teil-Retry, keine Lücken-Fortsetzung).
  - Test: Realen Fehlerpfad erzwingen (z.B. ungültige Test-Chat-ID in einer isolierten
    Test-Settings-Instanz), Anzahl tatsächlich zugestellter Nachrichten + Log-Aufrufe
    zählen.

- **AC-6 (Regression):** Given ein Nutzer sendet den Text-Befehl "report morning" /
  When `TripCommandProcessor` ihn verarbeitet / Then liefert er inhaltlich dieselbe
  Antwort wie vor der Umstellung — der bestehende Text-Parser bleibt unverändert
  funktionsfähig.
  - Test: Echter Text-Nachricht-Roundtrip über den Staging-Bot, Antworttext prüfen.

- **AC-7:** Given ein Trip mit Telegram-Vorschau / When
  `GET /api/preview/{trip_id}/telegram` gegen den laufenden `gregor-api`-Dienst
  aufgerufen wird / Then liefert die Antwort weiterhin ein valides `body`-String-Feld
  (Rückwärtskompatibilität) UND zusätzlich `bubbles: list[str]` mit der Liste der
  Einzelnachrichten, wobei `body` die mit einem Trennzeichen verbundenen Bubbles ist.
  - Test: Echter HTTP-Call gegen Staging, JSON-Antwort auf beide Felder prüfen.

- **AC-8:** Given ein Zellwert enthält ein Zeichen aus `&`, `<`, `>` (z.B. im
  Segment-Mini-Header via Trip-/Ortsnamen) / When die Bubble mit `parse_mode="HTML"`
  verschickt wird / Then liefert die Bot-API HTTP 200 + `ok:true` (kein 400-Parse-Fehler)
  und das Sonderzeichen erscheint korrekt escaped im `<pre>`-Block.
  - Test: Echter Versand mit präpariertem Testwert gegen Staging-Bot; erfolgreiche
    `message_id`-Rückgabe als Nachweis (ausbleibende `message_id`/400 = Fail).

- **AC-9:** Given eine Segment-Tabelle mit maximal 8 Spalten (Zeit + 7 Metriken) und den
  kürzestmöglichen `compact_label`-Kürzeln / When sie als `<pre>`-Block real an den
  Staging-Bot gesendet wird / Then überschreitet keine Tabellenzeile die in
  `_TG_TABLE_WIDTH` dokumentierte Zeichen-Obergrenze, sodass sie auf einem
  iPhone-Standardbildschirm nicht umbricht.
  - Test: Echter Versand + Zeilenlängen-Assertion in einem Rendering-Test gegen die
    dokumentierte Breitengrenze (kein reiner Dateiinhalts-Check, sondern die tatsächlich
    gerenderte Ausgabe wird geprüft).

- **AC-10:** Given ein Trip mit `telegram_kurzform=true` in gespeicherten Altdaten /
  When das Briefing gerendert wird / Then hat der Feldwert keinen Einfluss mehr auf das
  Ergebnis (Kurzübersicht erscheint unabhängig vom Wert), und der Frontend-Toggle in
  `WeatherV2Kanaele.svelte` ist entfernt oder wirkungslos deaktiviert.
  - Test: Zwei identische Trips mit unterschiedlichem `telegram_kurzform`-Wert real
    rendern/senden, resultierende Bubble-Listen bis auf den Trip-Namen auf Gleichheit
    prüfen.

## Known Limitations

- **Frontend-Kanalvorschau nicht umgebaut:** `ChannelPreviewBlock.svelte`/
  `ChannelPreviewCard.svelte` zeigen weiterhin nur den zusammengefügten `body`-String,
  nicht die einzelnen Bubbles. Multi-Bubble-Darstellung im Trip-Editor ist ein
  Folge-Ticket.
- **#623/#640 bleiben draft:** Der fachliche Kern (mehrtägiger Trend) fließt in die
  Ausblick-Bubble ein, aber beide Ursprungs-Issues werden NICHT durch #1001 als
  eigenständige Spezifikation abgeschlossen — falls zusätzliche Anforderungen über die
  Ausblick-Bubble hinausgehen, müssen sie nach #1001 neu spezifiziert werden.
- **Rate-Limit-Verhalten ungetestet bei Skalierung:** Bis zu ~10 `sendMessage`-Aufrufe
  pro Briefing sind gegen die reale Bot-API funktional verifiziert, aber nicht mit
  vielen parallelen Trips lastgetestet — nach Rollout beobachten.
- **`telegram_kurzform`-Feld bleibt strukturell erhalten:** Aus Altdaten-Kompatibilität
  wird das Feld auf `UnifiedWeatherDisplayConfig` nicht gelöscht, sondern nur
  wirkungslos gemacht (analog zur `confidence.selectable=false`-Konvention aus
  Issue #710) — kein aktiver Nutzungspfad mehr, aber kein Daten-Schema-Bruch für
  bestehende Trips.
- **`trip_alert.py` und die 7 Bot-Antwort-Call-Sites in `inbound_telegram_reader.py`
  bleiben unverändert** — eigenständige Einzelnachrichten-Pfade außerhalb des
  Briefing-Multi-Bubble-Formats.
- **`internal/handler/preview_proxy.go` (Go) bleibt unverändert** — reines
  JSON-Passthrough, keine Anpassung nötig für das neue `bubbles`-Feld.
- **Exakte `_TG_TABLE_WIDTH`-Zeichengrenze wird in der TDD-Phase final verifiziert**
  (siehe Implementation Details) — die Spec schreibt eine dokumentierte, harte
  Obergrenze vor, nicht zwingend einen bestimmten Zahlenwert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0014
- **Rationale:** Strukturelle, schwer umkehrbare Entscheidung: Breaking Replace des
  Rendering-Ausgabeformats für einen ganzen Kanal (Telegram), Ablösung von drei
  vorherigen, teils widersprüchlichen PO-Entscheidungen (#360 Tabelle → #635 Prosa →
  #614/615 Text-Anhang → jetzt Tabelle+Multi-Bubble) und Einführung eines neuen
  Versand-Musters (Multi-Message statt Single-Message) ohne bisherigen Präzedenzfall im
  Code. Erfüllt die ADR-Faustregel "eine bewusste Produkt-Grenze wird gezogen" und
  "Kanal-Darstellung wird grundlegend geändert". Siehe `docs/adr/0014-telegram-multi-bubble-format.md`.

## Test Coverage

**Zu migrierende Bestands-Testdateien** (referenzieren `render_narrow`, `telegram_text`,
`_tg_segment_line`, `_tg_extra_detail_line` oder `telegram_kurzform` — Specs dieser
Tests werden durch #1001 fachlich abgelöst):

- `tests/tdd/test_issue_887_report_inkonsistenz.py`
- `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`
- `tests/tdd/test_issue_623_trend_channels.py`
- `tests/tdd/test_issue_635_telegram_weather.py`
- `tests/tdd/test_issue_640_trend_threshold_times.py`
- `tests/tdd/test_issue_610_signal_backend_red.py`
- `tests/tdd/test_issue_612_report_on_demand.py`
- `tests/tdd/test_issue_614_telegram_kurzform.py`
- `tests/tdd/test_issue_360_channel_renderer.py`
- `tests/tdd/test_issue_363_signal_telegram_preview.py`
- `tests/tdd/test_issue_397_segment_timezone.py`
- `tests/tdd/test_day_comparison_integration.py`
- `tests/tdd/test_bug_397_output_localtime.py`

**Neue Tests (TDD-Phase, KEINE Mocks):**

- `tests/tdd/test_issue_1001_telegram_bubbles.py` — echter `render_telegram_bubbles()`-
  Output gegen reale Trip-/Segment-Fixtures geprüft (Bubble-Anzahl, -Reihenfolge,
  Tabellenstruktur, Zeilenbreiten-Grenze).
- Ergänzender E2E-Test gegen den Staging-Bot (`GregorZwanzigStaging_bot`, Chat
  `8346977700`) für AC-1, AC-2, AC-4, AC-5, AC-8, AC-9 — `sendMessage`→`message_id` als
  Nachweis, kein Read-Back (Bot-API-Eigenschaft), kein Mock.

## Changelog

- 2026-07-03: Initial spec erstellt — Issue #1001
