---
entity_id: telegram_format
type: reference
version: "1.5"
status: active
created: 2026-10-21
updated: 2026-11-16
tags: [telegram, channel, renderer, inbound, reference]
---

# Telegram-Format — Referenz (Ist-Stand)

> **Hinweis (PO 2026-10-31, ADR-0104):** Die Kurzform (Token-Zeile) von SMS, Premium-SMS und Telegram ist nie sprachabhängig: sie bleibt in jeder Sprache (Konto-Sprache de/en) unverändert und wird nicht übersetzt.

Beschreibt, wie der Kanal **Telegram** heute rendert, versendet und Befehle annimmt. Reiner
Ist-Stand aus dem Code (Stand 2026-10-21), keine Bewertung. Entscheidungen: ADR-0012
(`parse_mode="HTML"`), ADR-0014 (Multi-Bubble), ADR-0095 (Kanal-Parität). Kürzel-/Token-Vertrag der
Kurzform: `docs/reference/sms_format.md`.

## 1. Transport

| Eigenschaft | Wert |
|---|---|
| API | Telegram Bot API `sendMessage` / `editMessageText` / `answerCallbackQuery` / `setMyCommands` |
| Empfänger | `telegram_chat_id` aus `user.json` (einziger Schreiber `POST /api/internal/telegram-connect`, #2141) |
| Längenlimit | **4096 Zeichen je Nachricht** (`MAX_MESSAGE_LENGTH`). Länger → gekürzt; bei HTML tag-sicher (`_truncate_html` schließt offene Tags), sonst hart. Kein Aufteilen auf mehrere Nachrichten |
| Formatierung | `parse_mode="HTML"` für formatierte Nachrichten (`<b>`, `<pre>`); Nutzdaten laufen durch dieselbe `_esc()`-Maskierung wie E-Mail-HTML (ADR-0012). Default bleibt `parse_mode=None` |
| HTML-Fehler | Antwortet Telegram mit HTTP 400 auf eine HTML-Nachricht, wird **einmal ohne `parse_mode`** nachgesendet (Tags gestrippt, Entities unescaped) |
| Drossel | Sende-Slot je Chat (`telegram_rate_limit_max_per_window`); Wartezeit hart gedeckelt auf 30 s (`SEND_SLOT_MAX_WAIT_SECONDS`); 429 → `retry_after` (Fallback 1 s) |
| Tabellenbudget | `CHANNEL_LIMITS["telegram"]` = max. 8 Tabellenspalten (inkl. Zeit/Ort), 4096 Zeichen |

## 2. Varianten

Der Stil wird je Trip/Vergleich über `report_config.telegram_style` gewählt: `rich` (Default) oder
`kurzform` (#1260).

| Variante | `rich` | `kurzform` |
|---|---|---|
| **Trip-Briefing** | **Multi-Bubble** (ADR-0014): Folge einzelner `sendMessage`-Aufrufe, `parse_mode="HTML"`. Reihenfolge: Kopf → ggf. „amtliche Warnungen nicht abrufbar“ → ggf. Starkregen-Kurzfristhinweis → ggf. amtliche Warnungen → Kurzübersicht (alle konfigurierten Metriken) → je Segment/Ziel eine `<pre>`-Tabelle → optional Ausblick → Aktionen-Bubble mit Inline-Keyboard (nur letzte Bubble trägt `reply_markup`). Scheitern Bubbles, folgt ein Hinweis „unvollständig“ | **eine** Nachricht mit dem SMS-Text (`report.sms_text`), `parse_mode=None`, keine Bubbles/Knöpfe |
| **Ortsvergleich-Briefing** | **eine** Nachricht aus `render_compare_telegram()` (kein Score/Rang, ≤ 4096 Zeichen), `parse_mode=None`: alle Zeilen der Telegram-Liste je Ort (Plätze 1–7 in Zeile 1, ab Platz 8 in Zeile 2, kein Kappungshinweis), danach je Ort der 3-Tages-Ausblick (Kopf „Ausblick“, Form wie Trip-Telegram; Schalter aus/leere Ausblick-Liste → entfällt). Amtliche Warnung je Ort als Klartext (keine HTML-Tags, Ortsnamen wortgetreu, #3047). Ohne gespeicherte Grundauswahl („nie eingestellt“) dieselben Zeilen in derselben Folge wie die Vergleichstabelle der Mail, Zeilen ohne Wert entfallen ohne Zähler (B-L4). Warndienst nicht erreichbar: Hinweiszeile „⚠️ Amtliche Warnungen aktuell nicht abrufbar …“ in Nutzersprache nach dem Kopf, vor den Orten (B-L2) | SMS-Vergleichstext (`render_compare_sms`), eine Nachricht, `parse_mode=None` (`scheduler_dispatch_service.py:697`) |
| **Änderungs-/Radar-Alarm** | eine Nachricht aus `alert/render.py::render_telegram()` (fette Kopfzeile, dieselben Sätze wie die E-Mail, #2020), `parse_mode="HTML"`; Ortsvergleich ggf. je Ort aufgefächert | **eine** gemeinsame Nachricht mit dem SMS-Alarmtext, Vorrang vor dem Fan-out je Ort (#1467 K-6) |
| **Amtliche Warnung** | reiche Warnvorlage `render_official_alert_telegram` (+ Entwarnung), `parse_mode="HTML"`, ohne Betreffzeile | SMS-Text, `parse_mode=None` |
| **Befehlsantwort** | Klartext-Bestätigung, optional mit Inline-Keyboard (Zoom-Navigation per `callback_query` + `editMessageText`, #655) | — |

**Hervorhebung im Trip-Briefing (Profil-Ampel, #2792 S1c-4b):** Die Hervorhebung folgt der Profil-Ampel des Abos, nicht mehr `sms_threshold`: Spitzenwert `@{h}` ab gelb oder schlechter (beidseitig), Gewitter ab „leicht“, Temperatur mit Stunde nur ab Gelb. Die Regeln stehen in `sms_format.md` §3.2 und §3.2a.
- **`kurzform`:** sendet den SMS-Text, daher gilt der Token-Vertrag der SMS unverändert.
- **`rich`:** behält sein eigenes Zeilenformat (Symbol, Leerzeichen, Wert, Temperatur mit Dezimalstelle, zweistellige Stunde), z. B. `T -5.0@08` und `G 30@04` (Fixture `tests/fixtures/befehl_antwortzeit/golden_berichte.json`). Dieselben Hervorhebungsregeln gelten, nur die Schreibweise ist eine andere.
- Die Alarm-Stundenzeilen (Änderungs-Alarm) nutzen dieselbe Ampel des Abos.
- Vergleichs-Telegram (`render_compare_telegram`, #3047 Runde 7 B-L3): Eine Zeile auf **Einfach** trägt bei Ampel-Größen (Temperatur, Wind, Böen, Regen, Regenwahrscheinlichkeit, Sicht, UV, Neuschnee, gefühlte Temperatur) die Marke `@{h}` wie das Trip-Telegram, wenn der Tageswert nach der Ampel des Ortsvergleichs gelb oder schlechter ist; `h` ist die Spitzen- (obere Grenze) bzw. Tiefststunde (untere Grenze) der Stundenwerte in Ortszeit, z. B. `Böen mäßig@14`. Grün: keine Marke. Roh bleibt unverändert.

**Bezugszeitraum der Kurzübersicht (`rich`, Trip, #3047 Runde 7 B-L1):** Alle Zeilen der Kurzübersicht werden über das eingestellte Tagesfenster bewertet (Standard 4–19 Uhr, sonst `day_window_start_hour`/`_end_hour`, ADR-0035), aus derselben Punktmenge wie SMS und Mail: Gehzeit der Etappen ab Fensterbeginn, nach der Ankunft das Ziel bis Fensterende. Spitzenwert und `@{h}` stimmen damit mit der SMS überein (Fenster 10–19: `G 60@16` ⇔ SMS `G45@10(60@16)`, nie eine Stunde vor 10; Standard: `R 2.0@04` ⇔ SMS `R2.0@4`). Ausnahme wie in SMS und Mail-Kachel: Temperatur und gefühlte Temperatur zeigen die Gehzeit-Spanne (#1417), abends mit dem Nachtwert als Untergrenze. Die frühere Regel „nur Gewitter wechselt aufs Fenster, alle anderen Größen bleiben bei der Gehzeit“ (#1498) ist damit abgelöst (ADR-0095). Die Segment-Tabellen zeigen weiterhin die Gehzeit-Stunden der Etappe, dieselben Stunden wie die Etappentabelle der Mail.

**Roh/Einfach je Zeile im Trip-Briefing (`rich`, #3063 Punkt 2, #3047 Runde 7 AC-22):** Kurzübersicht und Segment-Tabellen formatieren jede Zeile der Telegram-Liste nach ihrer Roh/Einfach-Wahl, mit derselben Regel wie die Mail (`build_format_modes` der Telegram-Liste an `fmt_val`). Beispiel Windrichtung: Roh `WD 250°`, Einfach `WD W` (Einfach und mit Wind gewählt: in der Windzeile `W 20 W`). Bewölkung: Roh `CT 70`, Einfach Wolkensymbol.

**Kappungshinweis (`rich`, Trip, #1741):** Bei mehr als 7 Zeilen zeigt die Tabelle die ersten 7 stündlich, alle Zeilen stehen in der Kurzübersicht; der Hinweis „… +N weitere Wettergrößen nur als Tageswert (Telegram-Limit)" steht in der Kontosprache (`allgemein.telegram_limit.route.*`, en „… +N more weather values as daily value only (Telegram limit)", #3047 Runde 7).

**Radar-Alarm im Ortsvergleich mit mehreren Orten (#1767):** `rich` sendet **eine** Nachricht: Kopf `<b>Regen-Alarm: N Orte</b>` (Katalog `alarm.regen.buendel`), danach je Ort eine Zeile wie in der E-Mail (`Zermatt · Regen in 5 Min: ab 14:05 · leichter Regen`), sortiert nach Beginn, zuletzt `Quelle: …`; kein Namens-Join im Kopf, kein `km 0–0`. `kurzform` sendet den SMS-Alarmtext `1:R@14:05 3:R@14:40` (`sms_format.md` §3.4i). Ein auslösender Ort unverändert.

**Kopfzeile im Ortsvergleich-Alarm (#2598):** der Ortsname steht genau einmal, ohne Kilometerangabe; Ereigniszeilen nennen den Ort statt `km 0–0`. Änderung 1 Ort: `<b>Ort Eins · ↑ Böen</b>`, Zeile `Ort Eins · stärkste Stunde 14:00`; Bündel: `<b>Ort Eins, Ort Zwei · 2 über Schwelle</b>`; Beginn-Verschiebung: `Gewitter-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)`; Radar 1 Ort: `<b>Ort Eins · Regen in 30 Min</b>`. Trip unverändert (`<b>GR20 · Segment 3 · ↑ Böen</b>`).

**Stundenzeilen im Änderungs-Alarm (`rich`, #1737):** Unter der Kopfzeile jedes Ereignisses steht je betroffener Stunde eine Zeile `HH:MM | alt → neu` (Ortszeit), dieselben Stunden wie in der E-Mail. Trip: Zellformat (ROH oder EINFACH) des Telegram-Briefings desselben Trips; Ortsvergleich: Werte roh, nur unter betroffenen Orten. Höchstens 6 stärkste Stunden in Zeitfolge plus Hinweiszeile „betroffen HH:MM–HH:MM"; Summen-Metriken tragen die Summe in der Kopfzeile. Ohne Anker nur der neue Wert, ohne Stundenreihe unverändert. Nur Daten, keine Empfehlung. Die Kurzform (`kurzform`) sendet den SMS-Alarmtext mit der Zeitspanne `HH-HH` (`sms_format.md` §3.4f).

**Farbsatz im Änderungs-Alarm (#2793 S2b):** Für Ampel-Metriken trägt `rich` dieselben Farbsätze wie die E-Mail (Katalog `alarm.ampel.*`, z. B. „Böen von gelb auf orange gestiegen: 40 km/h → 55 km/h", Entwarnung „Entwarnung Böen: von orange auf gelb zurückgegangen (…)"), statt der Schwellen-Zeile; die Stand-/Vergleichszeile bleibt. `kurzform` sendet den SMS-Alarmtext mit dem Farbpaar `:{X}>{Y}` (`sms_format.md` §3.4h). Nullgradgrenze und Beginn-Verschiebung (D4) unverändert.

## 3. Befehlseingang (Inbound)

Telegram **hat** einen Befehlseingang — push-basiert, kein Poll-Job (`inbound_telegram_poll`
entfernt, #637/#1369).

- **Weg:** Telegram → `POST /api/webhooks/telegram/inbound` (Go, öffentlich; einziger
  Auth-Träger ist der Header `X-Telegram-Bot-Api-Secret-Token`, kein Secret im Pfad, #1814;
  die frühere Route mit Secret im Pfad ist entfernt) →
  `POST /api/internal/telegram-webhook` (Python, Dedupe über `update_id`) →
  `InboundTelegramReader._process_update`.
- **Nutzerzuordnung:** über die Chat-ID (`lookup_user_by_telegram_chat_id`), nie Fallback auf
  `default`.
- **Eingabeformen:** Freitext-Befehle ohne Präfix und Slash-Befehle aus dem Bot-Menü
  (`BOT_COMMANDS`, deutsch + englisch, z. B. `/heute`, `/morgen`, `/jetzt`, `/gewitter`, `/strecke`,
  `/ruhetag`, `/status`, `/pause`, `/skip`, `/stop`, `/weiter`, `/kuerzel`, `/report`,
  `/startdatum`); Inline-Knöpfe liefern `callback_query`. Das Bot-Menü wird beim Start des
  Python-Core gesetzt (`_init_telegram_bot_menu`).
- **Verarbeitung/Antwort:** gemeinsamer `TripCommandProcessor` (`channel="telegram"`), Antwort über
  `send_command_reply_telegram` an denselben Chat. Telegram-Antworten tragen Emojis
  (`with_emoji = channel == "telegram"`), Ad-hoc-Verläufe ausgeschrieben (nicht Kurzform, s.
  `sms_format.md` §5a).

## Sprache

Telegram hat zwei Stile. Die Sprache folgt dem Stil und dem Befehlswort (ADR-0104 Nr. 5).

**Normalstil** (Trip- bzw. Ortsvergleich-Ziel ohne `telegram_style == "kurzform"`): Briefings, Hinweise
und Antworten stehen in der **Kontosprache** (`resolve_user_lang`). Ein englisches Befehlswort (z. B.
`TODAY`, `RESTDAY`) ergibt eine englische Antwort, auch bei deutschem Konto (`telegram_englisch`,
`src/services/trip_command_processor.py`).

**Kopfzeile des Trip-Briefings (#3052):** Die Briefing-Art steht in der Kontosprache, z. B. „Abend 15.07.2026“ (de) bzw. „Evening 15.07.2026“ (en). Sie kommt aus demselben Katalog wie die Mail (`mail.kopf.typ_morning|evening|alert`) über den gemeinsamen Helfer `briefing_typ()` in `src/output/renderers/briefing_typ.py`; Mail und Telegram zeigen damit dieselbe Art. Unbekannte Typen fallen auf die Großschreibung des Typnamens zurück. Das Datum bleibt unverändert.

**Stufenwörter (#2784):** Gewitter-Stufe (z. B. „leicht" / „light"), Wind- und Regen-Adjektive folgen der Kontosprache in Fußzeile, Kurzübersicht, Segment-Tabellen des Briefings und in den Stundenzeilen des Änderungs-Alarms. Bewusst deutsch bleibt der Gewitterteil der Ausblick-Zeile (Entscheidung #2665). Kürzel (`TH`, `VS`, `FZ`) bleiben in jeder Sprache unverändert. Der Kopf der Zeitspalte in der Segment-Tabelle ist dagegen kein Kürzel, sondern Nutzertext und folgt der Kontosprache über den Katalogschlüssel `telegram.tabelle.zeit` (Deutsch „Zt“, Englisch „Hr“; zweistellig wegen der 32-Zeichen-Tabellenbreite, #3014).

**Kurzstil** (`telegram_style == "kurzform"`): die Kurzform bleibt in jeder Sprache unverändert, Kürzel
und Befehlswörter eingeschlossen. Die Antwort ist englisch wie bisher; der Konto-Wert ändert nichts an
der Token-Zeile.

**Befehlswörter:** beide Sprachen werden erkannt (`wort` und `wort_en` aus `_COMMAND_SPECS`). Das
Bot-Menü (`BOT_COMMANDS` in `src/output/channels/telegram.py`) zeigt die Befehle deutsch und englisch;
das Menü ist botweit und bleibt deutsch (P7 #2669, Known Limitations); die Zeilen tragen
`# i18n-fest` (#2751, `docs/reference/gates_und_ratschen.md`, Abschnitt „i18n-Ratschen").

**Woher:** Katalogbereiche `telegram.*`, `inbound.*` und `allgemein.*` (`src/i18n/messages/{de,en}/`).

**Prüfung:** Golden-Tests `tests/golden/telegram_briefing/` und `tests/test_telegram_briefing_golden.py`
(deutsche Ausgabe byte-genau); Kurzform-Token über `tests/test_metric_tokens_eingefroren.py`.

## 4. Quelle im Code

| Was | Datei:Zeile |
|---|---|
| Längenlimit 4096 | `src/output/channels/telegram.py:25` |
| Tag-sichere Kürzung | `src/output/channels/telegram.py:53` (`_truncate_html`) |
| Bot-Menü-Befehle | `src/output/channels/telegram.py:132` (`BOT_COMMANDS`), `:691` (`set_my_commands`), `api/main.py:72` |
| Sende-Drossel | `src/output/channels/telegram.py:327` (`_reserve_send_slot`) |
| Versand + 400-Fallback ohne `parse_mode` | `src/output/channels/telegram.py:474`, `:534`, `:560` |
| Zoom-Navigation | `src/output/channels/telegram.py:637` (`edit_message_text`), `:668` (`answer_callback_query`) |
| Bubble-Datentyp / Briefing-Renderer | `src/output/renderers/narrow.py:380`, `:659` (`render_telegram_bubbles`) |
| Kopf Briefing-Art (Nutzersprache) | `src/output/renderers/narrow.py:781`, Helfer `src/output/renderers/briefing_typ.py:10` (`briefing_typ`, mit Mail geteilt) |
| Hinweis „unvollständig“ | `src/output/renderers/narrow.py:640` |
| Spalten-/Zeichenbudget | `src/output/renderers/channel_layout.py:48` |
| Briefing-Versand (kurzform / Bubble-Schleife) | `src/services/notification_service.py:786`, `:804` |
| Vergleichs-Renderer / -Versand | `src/output/renderers/comparison.py:696`, `src/services/notification_service.py:1359` |
| Alarm-Renderer / -Versand | `src/output/renderers/alert/render.py:1483`, `src/services/notification_service.py:1809`, `:1870`, `:1978` |
| Amtliche Warnung | `src/services/notification_service.py:1174`, `:1294` |
| Webhook Go / Python | `internal/handler/telegram_webhook.go:39`, `internal/router/router.go:171`, `api/routers/webhook.py:53` |
| Inbound-Verarbeitung | `src/services/inbound_telegram_reader.py:159`, `:408`, `:582` |
| Befehlsantwort | `src/services/notification_service.py:2153` |

## 5. Änderungen

| Version | Datum | Änderung |
|---|---|---|
| 1.5 | 2026-11-16 | Ortsvergleich-Briefing (#3047 Runde 7): „nie eingestellt“ folgt der Mail-Tabelle (B-L4); Hinweis „Warnungen nicht abrufbar“ (B-L2); Einfach bei Ampel-Größen mit `@{h}` nach der Ampel des Ortsvergleichs (B-L3). |
| 1.4 | 2026-11-16 | Ortsvergleich-Briefing (#3047 Runde 7, AC-24): alle Zeilen der Telegram-Liste je Ort (Plätze 1–7 in Zeile 1, ab Platz 8 in Zeile 2, kein Kappungshinweis), danach je Ort der 3-Tages-Ausblick (Kopf „Ausblick“, Form wie Trip-Telegram; Schalter aus/leere Ausblick-Liste → entfällt). Amtliche Warnung im Ortsvergleich als Klartext, weil die Nachricht mit `parse_mode=None` hinausgeht (vorher erschienen `<b>…</b>` und `&amp;` wörtlich). |
