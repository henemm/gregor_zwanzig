# Context: Mail-Redesign Telegram (#614) + SMS (#615)

## Request Summary
Folge-Issues zu #613 (E-Mail-Redesign „Gregor 20 — Mail Vorschau"). Die **Telegram**-
und **SMS**-Ausgabe des Briefings sollen 1:1 nach den JSX-Entwürfen aussehen
(`WM2_TelegramBubble`, `WM2_SMSLine`/`SMSPreview`).

## Entwurfsquellen (Handoff-Bundle)
- `claude-code-handoff/handoff-2026-06-04-v3/.../jsx/screen-trip-edit-v2-weather.jsx`
  → `WM2_TelegramBubble` (Z.375), `WM2_SMSLine` (Z.421), `WM2_TG_LIMIT = 8` (Z.14)
- `.../jsx/screen-output-preview.jsx` → `SMSPreview` (Z.446), Kurzcode-Legende

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/output/renderers/narrow.py` | **#614** — Telegram/Signal Monospace-Renderer (render_narrow) |
| `src/output/renderers/channel_layout.py` | CHANNEL_LIMITS: telegram max_table_cols=8/max_chars=4096, sms 0/140 |
| `src/formatters/trip_report.py:163-173` | ruft render_narrow("telegram") → `TripReport.telegram_text` |
| `src/services/trip_report_scheduler.py:479-487` | sendet telegram_text via TelegramOutput.send() |
| `src/outputs/telegram.py` | Transport (Bot API) — unverändert |
| `src/output/tokens/{builder,render,metrics,dto}.py` | **#615** — SMS-Kurzcode-Token-System |
| `src/output/renderers/sms/__init__.py` | render_sms() wrappt render_line() |
| `src/formatters/sms_trip.py:107-166` | SMSTripFormatter.format_sms() High-Level |
| `src/services/preview_service.py:164-200` | SMS-Preview (echter SMS-Versand noch nicht im Scheduler!) |

## Ist-Zustand

### Telegram (#614)
`render_narrow("telegram", ...)` erzeugt bereits eine Monospace-Tabelle: Trip-Header +
`Report Datum` + pro Segment `Seg N HH-HH` + adaptive Tabelle (`Zt` + Metrik-Spalten,
Spaltenbreite an Inhalt angepasst) + Detail-Zeile. Limit: Zeit + 7 Metriken (max_table_cols=8).

### SMS (#615)
Token-System erzeugt bereits Kurzcode-Zeile, z.B.:
`GR20 E3: N12 D24 R0.2@15(2.5@17) PR20%@11(80%@17) W18@10(28@15) G25@10(40@15) TH:M@16(H@18)`
Golden-Master-getestet gegen `sms_format.md v2.0/v2.1` (5 Golden-Files in `tests/golden/sms/`).

## Delta Ist → Soll (Entwurf)

### #614 Telegram — echte Render-Änderungen
1. Segment-Kopfzeile: `KHW 403 · Seg. 1 · 08–10 h` (heute: `Seg 1 08-10`, Trip-Header separat)
2. **Feste** Spaltenbreite (7 Zeichen, JSX `padEnd(7)`/`slice(0,6)`) statt adaptiv
3. Entwurf zeigt **8 Metrik-Spalten ohne Zeit-Spalte** (Stunde steckt im Kopf `08–10 h`)
4. **`telegramSuffix`** (Tages-Max-Zeile): überzählige Metriken als „Tages-Max"-Zeile
   unter der Tabelle statt wegfallen — NEU, braucht Konfig-Feld
5. Hinweis-Banner („X Metriken passen nicht…") ist **Editor-Preview-UI**, NICHT Teil der
   gesendeten Nachricht

### #615 SMS — Delta vs. bestehendes Format
- SOLL `TH5%@12` = Gewitter als **Prozent**; Code heute `TH:M@16` = Level L/M/H
- SOLL `Z:WATCH:2447` = **Ziel-Risiko** (Watch/High + Zahl); Code heute `Z:HIGH208,209` = Fire-Zonen
- SOLL **ohne** Peak-Klammern `(2.5@17)`; Code heute mit Peaks
- SOLL **mehrteilige SMS** `KHW_00B+1: …` für Folgetag — heute einzeilig, NICHT implementiert
- JSX-Kommentar: `// Beispiel im Spec-Format (KHW_00b)` → der Designer wollte **dem Spec folgen**

## Existing Specs
- `docs/specs/modules/issue_360_signal_channel_renderer.md` (narrow.py)
- `docs/specs/modules/sms_format.md` v2.0/v2.1 (SMS-Token-Wire-Format, autoritativ + Golden-Master)
- `docs/specs/modules/output_channel_renderers.md`
- `docs/specs/modules/output_token_builder.md`

## PO-Entscheidung (2026-06-06) — finaler Scope
- **#615 SMS:** Kein Folgetag-Mehrteiler, **kein Umbau** des SMS-Wire-Formats. Bestehendes
  Format ist spec-korrekt. JSX-Abweichungen (TH%, Z:WATCH) → Design-Request.
- **#614 / Kern-Feature:** Telegram bekommt eine **konfigurierbare Option**, zusätzlich zur
  bestehenden Tabelle die kompakte **SMS-Kurzform anzuhängen** (gleiche Render-Logik wie SMS).
  Weil Telegram 4096 Zeichen erlaubt, läuft die Kurzform **ohne Truncation** → trägt ALLE
  Metriken als „Tages-Max", auch jene über dem 8-Spalten-Tabellenlimit.
- Telegram-Tabellen-Kosmetik (Segment-Kopf, feste Spalten) NICHT in Scope.

## Umsetzung (technisch machbar bestätigt)
- `SMSTripFormatter.format_sms(segments, stage_name, report_type, tz, max_length)` nimmt
  dieselben `segments` wie der Telegram-Pfad in `trip_report.py` → Kurzform aus identischen Daten.
- Neues additives Konfig-Feld (Trip), Read-Modify-Write-Merge in API.
- `trip_report.py`: wenn Flag gesetzt, Kurzform mit hohem `max_length` bauen und an
  `telegram_text` anhängen (Trennzeile/Label).

## Risks & Considerations
- **Scope-Spannung #615:** Reifes, golden-master-getestetes SMS-Format (sms_format.md) vs.
  handgeschriebenes JSX-Beispiel. Der JSX-Kommentar sagt selbst „Beispiel im Spec-Format" —
  die Abweichungen (TH%, Z-Bedeutung, Peaks) sind vermutlich Mockup-Ungenauigkeiten, nicht
  gewollter Redesign. Echte Lücke: **mehrteilige SMS für Folgetag**.
- **Zwei Workflows:** #614 und #615 sind getrennte Kanäle, je eigener Renderer. Gemeinsam
  sprengen sie das 250-LoC-Limit. Empfehlung: nacheinander, #614 zuerst.
- **`telegramSuffix` Konfig:** neues Per-Trip/Kanal-Feld → Schema-Additiv + ggf. Frontend-Toggle.
- Datenverlust-Risiko gering (additive Felder), aber `data_schema_backup.py`-Pfad beachten falls models.py berührt.
