---
entity_id: premium_sms_format
type: reference
version: "1.0"
status: active
created: 2026-10-21
updated: 2026-10-21
tags: [premium-sms, garmin, inreach, sms, channel, inbound, reference]
---

# Premium-SMS-Format (Garmin inReach) — Referenz (Ist-Stand)

> **Hinweis (PO 2026-10-31, ADR-0104):** Die Kurzform (Token-Zeile) von SMS, Premium-SMS und Telegram ist nie sprachabhängig: sie bleibt in jeder Sprache (Konto-Sprache de/en) unverändert und wird nicht übersetzt.

Beschreibt den vierten Kanal **`premium_sms`** (Satellitengerät Garmin inReach, Versand über
seven.io). Reiner Ist-Stand aus dem Code (Stand 2026-10-21), keine Bewertung. Entscheidungen:
ADR-0049 (eigener Kanal), ADR-0095 (Kanal-Parität, Alarm-Kanal in Trip und Ortsvergleich), ADR-0022
(ASCII-Faltung). **Inhalt und Token-Vertrag sind die der normalen SMS** — SSOT bleibt
`docs/reference/sms_format.md`; hier stehen nur die Unterschiede.

## 1. Format

| Eigenschaft | Wert |
|---|---|
| Nachrichtentext | **unverändert der SMS-Text** (`report.sms_text` bzw. SMS-Alarmtext) — kein eigener Renderer, damit SMS und Premium-SMS inhaltlich nicht auseinanderlaufen |
| Länge Trip-Briefing | ≤ 160 Zeichen (Renderer-Aufruf mit `max_length=160`), Kürzungsrangfolge `sms_format.md` §6 |
| Länge Vergleich/sonst | `CHANNEL_LIMITS["premium_sms"]` = 153 Zeichen, 0 Tabellenspalten (Vorsorge, damit kein Pfad auf die Telegram-Grenzen 4096 zurückfällt) |
| Zeichensatz | ASCII/GSM-7 über `fold_ascii()` (ADR-0022): Umlaut-Digraphen, dann `anyascii`; nicht faltbar → `?`. Ein GSM-7-fremdes Zeichen schaltete auf UCS-2 und halbierte das Budget |
| Ad-hoc-Verlauf (Befehl) | Kurzform `sms_format.md` §5a, immer **genau eine** Nachricht (`_KURZFORM_KANAELE = ("premium_sms", "sms")`) |
| Mehrteilig | nein — jede Sendung ist ein einzelner seven.io-Aufruf |

## 2. Unterschiede zur normalen SMS

| | SMS (`sms`) | Premium-SMS (`premium_sms`) |
|---|---|---|
| Absender | konfigurierbar (`sms_from`) | **fest** Dienstnummer `4916092172595` (`PREMIUM_SMS_SENDER`) |
| Empfänger | `sms_to`, nur wenn bewiesen (`sms_verified_number`, #2406); `SmsRecipient.for_user` liest frisch aus `user.json`, nie `GZ_SMS_TO` (#1412 S4b) | **ausschließlich die gelernte Rückadresse** `premium_sms_reply_to` (`PremiumSmsRecipient.for_user`, #1412 S4b); `sms_to` wird nie gelesen |
| Fehlt das Ziel | Kanal gilt als nicht konfiguriert | **fail-closed mit Grund** (`ChannelBlockedError` → `blocked_channels`): `premium_sms_no_reply_address`, `premium_sms_reply_address_stale` (älter 30 Tage oder Zeitstempel in der Zukunft) |
| Tarif | `standard` + `premium` | **nur `premium`** (eigenes Gate `premium_sms_allowed`) |
| Tageskontingent | Zähler `sms` | eigener Zähler `premium_sms`; Befehlsantworten dürfen eine Reply-Reserve über dem Grundlimit nutzen (`purpose="reply"`, #2412) |
| Befehlseingang | **keiner** (s. `sms_format.md` „Befehlseingang“) | **ja**, s. §4 |
| Transport | `SevenIoChannelBase.send` (gemeinsam, inkl. Sandbox-/Herkunftssperren) | dieselbe Basis |

## 3. Varianten

| Variante | Inhalt | Verdrahtung |
|---|---|---|
| Trip-Briefing | SMS-Briefingzeile | `Trip.report_config.send_premium_sms` |
| Ortsvergleich-Briefing | SMS-Vergleichstext (`render_compare_sms`) | `ComparePreset.send_premium_sms` (#2275) |
| Alarme (Änderung, Radar/Regen, amtlich, Entwarnung) | SMS-Alarmtext | `alert_channels.premium_sms`, Trip **und** Ortsvergleich, geteilte Auflösung `services/alert_channels.py` (ADR-0095) |
| Befehlsantwort | `CommandResult.confirmation_body` | `send_command_reply_premium_sms` |

**Änderungs-Alarm (#1737):** Der SMS-Alarmtext trägt am Ereignis-Token die Zeitspanne der betroffenen Stunden als `HH-HH` (ASCII-Bindestrich, GSM-7; Stufen-Tokens unverändert, ≤ 160 Zeichen). Stundenzeilen gibt es hier nicht; Vertrag in `sms_format.md` §3.4f.

## 4. Befehlseingang (Rückkanal)

- **Weg:** Garmin-Gerät schreibt an die Dienstnummer → seven.io-Journal. `premium_sms_poll`
  (Go-Cron `*/5`, zusätzlich Push-Kick über `POST /api/webhooks/sms/{secret}`, ADR-0088) →
  `POST /api/scheduler/inbound-sms` → `InboundSmsReader._poll_journal`.
- **Filter:** nur Journal-Einträge mit `to == SERVICE_NUMBER` (#2323); alles andere wird
  übersprungen.
- **Zuordnung:** Python meldet die Absendernummer (+ optional Verknüpfungs-Code `XX`+3 Buchstaben+3
  Ziffern am Textanfang) an `POST /api/internal/premium-sms-learn`. Go löst auf **Premium-Konten**
  auf: genau ein frischer Treffer auf gespeicherte `premium_sms_reply_to` → dieser Nutzer; sonst nur
  mit gültigem Code; nie Fallback auf `default`. Bei Erfolg wird die Rückadresse gelernt.
- **Befehl:** Text vor `inreachlink.com` (ohne Code) → `TripCommandProcessor`
  (`channel="premium_sms"`); ohne Namen wird das Ziel (Trip/Vergleich) aufgelöst, mehrdeutig →
  Hinweisantwort. Antwort per Premium-SMS an die gelernte Rückadresse.
- **Koordinaten (#2327, ADR-0102):** Garmin hängt hinter den Link die Position an, z. B.
  `Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370, 12.7678)`. `extract_position` liest
  die **letzte** Klammer `(<lat>, <lon>)` mit Dezimalpunkt (tolerant gegen Leerzeichen, negative
  Werte, andere Nachkommastellen; Unsinn oder `|lat| > 90` / `|lon| > 180` → kein Fix). Der
  Befehlstext vor dem Link bleibt unverändert. Erst **nach** der Zuordnung durch Go und **vor** der
  Befehlsantwort ruft `_verarbeite_befehl` `record_position_fix` (`src/services/position_fix.py`):
  liegt der Punkt höchstens **100 m** neben der Strecke der Heute-Etappe **genau eines** Trips des
  Nutzers (Abstand zur Strecke, nicht zum Trackpunkt), wird der Lotfußpunkt in
  `data/users/<user_id>/position_fix.json` gespeichert (Read-Modify-Write, ein älterer
  Journal-Zeitstempel ersetzt keinen jüngeren). Wirkung: die Positionsquelle
  (`trip_segments.position_at_time` / `points_with_passage_times`, Keyword `user_id`) rechnet ab
  dem Fix statt ab der Planposition — zum Meldezeitpunkt am Fix selbst, danach nach Plan-Tempo
  seit der Meldung fortgeschrieben (begrenzt auf das Etappenende; nach Ankunft oder am Folgetag
  wieder Planposition) — für Briefing, Alarm, Radar und Befehle in
  allen vier Kanälen gleich. Eine **reine Positions-SMS** (kein Befehlstext) nimmt den Fix auf und
  wird **nicht** beantwortet.

## 5. Quelle im Code

| Was | Datei:Zeile |
|---|---|
| Kanal, fester Absender, TTL 30 Tage | `src/output/channels/premium_sms.py:33`, `:49` |
| Empfänger-Auflösung / Sperrgründe | `src/output/channels/premium_sms.py:64` |
| Gemeinsamer seven.io-Transport | `src/output/channels/seven_io_base.py:166` |
| Zeichenbudget 153 | `src/output/renderers/channel_layout.py:55` |
| Briefing-Länge 160 | `src/output/renderers/trip_report.py:469` |
| ASCII-Faltung | `src/utils/ascii_fold.py:51` |
| Kurzform-Kanäle | `src/services/trip_command_processor.py:782` |
| Tarif-Gate / Kontingent | `src/services/user_tier.py:73`, `:82`; `internal/model/tier.go:23` |
| Versand Briefing / Vergleich / Alarme | `src/services/notification_service.py:761`, `:1461`, `:1331`, `:1583`, `:2085` |
| Befehlsantwort | `src/services/notification_service.py:2129` |
| Journal-Poll, Dienstnummer-Filter, Code-Zerlegung | `src/services/inbound_sms_reader.py:85`, `:96`, `:193`, `:239`, `:316` |
| Lern-Endpunkt (Go) | `internal/handler/premium_sms_connect.go:54`; TTL `internal/model/premium_sms.go:24` |
| Push-Kick | `internal/handler/inbound_webhooks.go:98` |
