---
entity_id: premium_sms_format
type: reference
version: "1.1"
status: active
created: 2026-10-21
updated: 2026-11-06
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

**Hervorhebung (#2792 S1c-4b):** Da der Text der SMS entspricht, gilt auch hier die Profil-Ampel des Abos: Spitzenwerte `@{h}` ab gelb oder schlechter (beidseitig), Gewitter ab „leicht“, Temperatur mit Stunde nur ab Gelb. Die Regeln stehen in `sms_format.md` §3.2 und §3.2a; `sms_threshold` wirkt nicht mehr.

## 2. Unterschiede zur normalen SMS

| | SMS (`sms`) | Premium-SMS (`premium_sms`) |
|---|---|---|
| Absender | konfigurierbar (`sms_from`) | **fest** Dienstnummer `4916092172595` (`PREMIUM_SMS_SENDER`) |
| Empfänger | `sms_to`, nur wenn bewiesen (`sms_verified_number`, #2406); `SmsRecipient.for_user` liest frisch aus `user.json`, nie `GZ_SMS_TO` (#1412 S4b) | **ausschließlich die gelernte Rückadresse** `premium_sms_reply_to` (`PremiumSmsRecipient.for_user`, #1412 S4b); `sms_to` wird nie gelesen |
| Fehlt das Ziel | Kanal gilt als nicht konfiguriert | **fail-closed mit Grund** (`ChannelBlockedError` → `blocked_channels`): `premium_sms_no_reply_address`, `premium_sms_reply_address_stale` (älter 30 Tage oder Zeitstempel in der Zukunft) |
| Tarif | `standard` + `premium` | **nur `premium`** (eigenes Gate `premium_sms_allowed`) |
| Tageskontingent | Zähler `sms` | eigener Zähler `premium_sms` (Briefings + Alarme); Befehlsantworten zählen in den eigenen Zähler `premium_sms_reply` (15/Tag bei Premium) und verbrauchen nie das Alarm-Kontingent (`purpose="reply"`, ADR-0116; vorher Reply-Reserve +3 auf demselben Zähler, #2412) |
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

**Radar-Verschärfung (#2848):** Ein Trip-Radar-Alarm, der per Mengen-Durchbruch (#2065) gegen einen Radar-Alarm desselben Ereignisses durchkommt, trägt nach dem Ortskopf und vor dem Radar-Token das Token `UP <Y>><X> ` (zuletzt gemeldete > jetzt gemessene Menge in mm, z. B. `UP 3.1>7.3`; ASCII/GSM-7, nie übersetzt). Der Platz ist vom Limit reserviert, Zonen-Kürzel weichen zuerst; die Premium-SMS-Grenze (153) bleibt eingehalten. Vertrag in `sms_format.md` §3.4g.

**Farbpaar (#2793 S2b):** Der Änderungs-Alarm trägt am Ereignis-Token das Farbpaar `:{X}>{Y}` (G/Y/O/R, z. B. `G40->55:Y>O`, Entwarnung `G55->35:O>Y`), vor `@HH-HH`, nie übersetzt, GSM-7; Gewitter (`TH:M->H`) und D4-Metriken ohne Suffix. Die Premium-SMS-Grenze (153) bleibt eingehalten. Vertrag in `sms_format.md` §3.4h.

**Radar-Alarm im Ortsvergleich mit mehreren Orten (#1767):** Lösen mehrere Orte gleichzeitig aus, nennt der Alarmtext jeden Ort mit Ortsnummer, sortiert nach Beginn (`1:R@14:05 3:R@14:40`), ohne Namenskopf; bei Platzmangel ` +k` am Ende (k = nicht genannte Orte). Derselbe Text wie SMS und Telegram-Kurzform, gerendert mit 140 Zeichen. Ein auslösender Ort unverändert (`Zermatt: R@14:05`). Vertrag in `sms_format.md` §3.4i.

## 4. Befehlseingang (Rückkanal)

- **Weg:** Garmin-Gerät schreibt an die Dienstnummer → seven.io-Journal. `premium_sms_poll`
  (Go-Cron `*/5`, zusätzlich Push-Kick über `POST /api/webhooks/sms/{secret}`, ADR-0088) →
  `POST /api/scheduler/inbound-sms` → `InboundSmsReader._poll_journal`.
- **Filter:** nur Journal-Einträge mit `to == SERVICE_NUMBER` (#2323); alles andere wird
  übersprungen.
- **Zuordnung (ADR-0116):** Python meldet die Absendernummer (+ optional Verknüpfungs-Code am
  Textanfang: neu `XX`+5 Buchstaben+3 Ziffern, Bestandscodes `XX`+3 Buchstaben+3 Ziffern bleiben
  gültig; ohne I/L/O/0/1, Groß-/Kleinschreibung egal) an `POST /api/internal/premium-sms-learn`. Go
  löst auf **Premium-Konten** auf: ein **gültiger Code gewinnt immer**, auch gegen einen frischen
  Treffer eines anderen Kontos (Garmin vergibt Nummern aus einem Pool neu); sonst genau ein frischer
  Treffer auf gespeicherte `premium_sms_reply_to` → dieser Nutzer (ein Vertipper im Code kippt die
  eigene Zuordnung nicht); nie Fallback auf `default`. Bei Erfolg wird die Rückadresse gelernt und
  bei **allen anderen Konten entfernt** (eine Nummer gehört höchstens einem Konto). Ausgehend sendet
  `PremiumSmsRecipient.for_user` nur, wenn die Nummer genau einem Konto gehört (sonst
  `premium_sms_no_reply_address`).
- **Code:** mehrfach verwendbar, ohne Ablauf (unterwegs der einzige Weg zur Neuverknüpfung);
  „Code erneuern" im Konto entwertet den alten. Bremse gegen Durchprobieren: 3 Fehlversuche je
  Absendernummer und 30 insgesamt je gleitender Stunde.
- **Verbindung trennen:** `DELETE /api/auth/premium-sms-reply` (Konto-Karte) löscht Rückadresse und
  Zeitstempel; der Code bleibt bis zum Erneuern.
- **Mitteilung bei Änderungen (ADR-0116):** ein per Premium-SMS ausgeführter zustandsändernder
  Befehl (`pause`, `stop`, `weiter`, `ruhetag`, `startdatum`, `skip`) löst zusätzlich eine kurze
  Mitteilung per E-Mail (nur bestätigte Adresse) und Telegram (falls verbunden) aus: was, wann, über
  welchen Kanal, wie zurücknehmen. Höchstens 10 je Nutzer und Tag, fail-soft; lesende Befehle lösen
  nichts aus (`src/services/premium_sms_aenderungshinweis.py`).
- **Journal-Abruf:** `limit=100` je Abruf. Ist die Seite voll und überlappt nicht mit dem
  Lesezeiger, steht eine Warnung „möglicherweise abgeschnitten" im Log (Verhalten unverändert).
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

## Sprache

Der Premium-SMS-Kanal ist Kurzform-Kanal (`_KURZFORM_KANAELE = ("premium_sms", "sms")`,
`src/services/trip_command_processor.py`). Die Kurzform ist in jeder Konto-Sprache unverändert
(ADR-0104, Präzisierung 2026-10-31; ADR-0042 Platzgrenze).

**Was bleibt:** Token-Zeile, Kürzel, `sms_code`, `compact_label`, `col_label`, das Zeichenbudget von
160 Zeichen in GSM-7. Die Antworten auf Rückkanal-Befehle sind wie bisher englisch, unabhängig vom
Konto.

**Was sich ändert:** nur die Eingabe. Jedes Befehlswort wird in der deutschen oder englischen Form
erkannt (`wort` und `wort_en` in `_COMMAND_SPECS`).

**Woher:** Kürzel-Bedeutungen aus `sms.*` im Katalog (`src/i18n/messages/{de,en}/sms.json`).

**Prüfung:** Golden-Tests für die Kurzform (`tests/golden/sms/`, `tests/test_sms_golden.py`) und der
Token-Wächter `tests/test_metric_tokens_eingefroren.py`.

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
