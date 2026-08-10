# Context: feat-1676-s1-premium-sms-rueckkanal

Issue: **#1676** (Scheibe S1). Verwandt: #735 (SMS-Inbound, offen), #1533 (Generalprobe auf dem Gerät, offen).

## Request Summary

Premium-SMS an den Garmin inReach braucht einen Rückkanal: Das System muss eingehende SMS an die gemietete seven.io-Nummer `4916092172595` abholen, daraus die Rückadresse des Garmin-Geräts lernen und pro Nutzer mit Zeitstempel speichern. Die Nummer ist flüchtig — Garmin vergibt sie je Gespräch und sie kann sich ändern. S1 umfasst **nur** Empfangen, Erkennen, Lernen, Speichern — keine Befehlsausführung, keine Bestätigungs-SMS, kein Frontend.

## Gemessener Ist-Stand der seven.io-API (2026-08-10, read-only)

Nicht aus der Doku übernommen, sondern gegen das echte Konto gemessen:

- `GET https://gateway.seven.io/api/journal/inbound` liefert eine **flache JSON-Liste**. Felder je Eintrag: `id`, `from`, `to`, `text`, `timestamp`, `reply_to_message_id`, `price`.
- **`limit` und `date_from` filtern wirklich** (`date_from` mit Zukunftsdatum → `[]`). Das Journal wächst also nicht unbegrenzt in die Antwort — die Sorge aus der Planung ist ausgeräumt.
- **Der Sandbox-Schlüssel liest dasselbe Produktiv-Journal.** `GZ_SEVEN_SANDBOX_KEY` gegen `journal/inbound` liefert identische Daten wie der Produktiv-Key. Der Sandbox-Key isoliert nur den **Sende**pfad, nicht den Lesepfad.
- Auth-Header ist `X-Api-Key` (nicht `Authorization: Bearer` wie im Vorlagecode).
- Belegter Garmin-Erstkontakt im Journal:
  `08:30:14 · von 4917717816902 · an 4916092172595 · "Test über App inreachlink.com/g-0Oh3D2H2f… (51.9956, 7.7136)"`
- **Der Versandweg ans Gerät ist bewiesen** (PO manuell durchgeführt, Beleg im `journal/outbound`, nachgemessen):
  `09:17:23 · von 4916092172595 · an die Garmin-Relaisnummer · dlr: DELIVERED · connection: website`
  Eine SMS mit unserer Rufnummer als Absender erreicht das Gerät. Offen bleibt allein, ob der **App-Weg** sich identisch verhält: die 26 bisherigen App-Versände laufen mit `connection: http` und Absender „Gregor Zwan"; mit gefülltem `sms_from` hat die App noch nie gesendet.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/inbound_email_reader.py:37-92` | Vorbild: `poll_and_process(settings) -> int` |
| `src/services/inbound_telegram_reader.py:83-118` | Zweites Vorbild desselben Musters |
| `api/routers/scheduler.py:110-139` | Globale Trigger-Endpoints der Inbound-Reader — hier kommt der neue dazu |
| `internal/scheduler/scheduler.go:145-156` | Cron-Liste; `recordRun` (379-383, 530-544) liefert `last_run` automatisch |
| `internal/model/user.go:11-22` | `SmsTo`, `TelegramChatID` vorhanden — Rückadress-Feld fehlt |
| `internal/handler/telegram_connect.go:169-209` | Vorbild für localhost-only Bindungs-Endpoint |
| `internal/model/tier.go`, `internal/handler/auth.go:504` | Tier-System (free/standard/premium) existiert bereits |
| `src/app/loader.py:1189-1234` | `lookup_user_by_email()` / `lookup_user_by_telegram_chat_id()` — Muster der Nutzer-Auflösung |
| `src/output/channels/sms.py:34-101` | Sendepfad; prüft HTTP **und** fachlichen Antwortcode; Sandbox-Guard 34-75 |
| `src/app/config.py:154-163` | `sms_from` existiert, wird im Betrieb nie gefüllt |
| `src/app/egress_guard.py:52` | `gateway.seven.io` bereits als `TEST_ACCESS` inventarisiert — kein neuer Eintrag nötig |
| `src/services/forecast_budget.py:49` | Muster für globalen (nicht nutzerbezogenen) State unter `get_data_root()/diagnostics/` |

## Existing Patterns

- **Inbound-Reader:** Python-Kern hält die Fachlogik, Go-Cron ist reiner Auslöser über einen globalen FastAPI-Endpoint. Zwei bestehende Reader folgen exakt diesem Muster; der dritte fügt sich ein, statt etwas Neues zu erfinden.
- **`last_run`-Pflicht** erfüllt sich von selbst über `s.recordRun(...)` — kein Zusatzcode.
- **Nutzer-Auflösung** über linearen Scan der `data/users/<uid>/user.json`, wie bei E-Mail und Telegram.
- **Go ist bislang der einzige Schreiber von `user.json`.** Diese Grenze wird eingehalten (Tech-Lead-Entscheid 2026-08-10): das Lernen der Rückadresse geht über einen neuen internen, localhost-only Go-Endpoint, nicht über einen Python-Direktzugriff.

## Dependencies

- **Upstream:** seven.io `journal/inbound`; `GZ_SEVEN_API_KEY`; Egress-Guard; Go-Store (`store.LoadUser`/`SaveUser`).
- **Downstream:** S2 (Premium-SMS-Kanal) liest die gelernte Rückadresse; S3 zeigt sie an; #735 kann auf diesem Reader die Befehlsauswertung aufsetzen.

## Existing Specs

- `docs/specs/modules/inbound_command_channels.md` — bestehende Inbound-Kanäle
- `docs/specs/modules/egress_guard_sms.md` — seven.io im Egress-Inventar
- `docs/features/architecture.md:8-9` und `docs/adr/0015-dual-stack-zielarchitektur.md` — Dual-Stack-Grenze

## Risks & Considerations

1. **Erkennungszeichen ist einfach belegt, nicht bewiesen.** Der PO hat entschieden (2026-08-10), die Rückadresse **nur** aus Nachrichten mit `inreachlink.com`-Kennzeichen zu lernen. Beleg dafür ist genau **eine** gemessene Garmin-Nachricht. Dass jede Geräte-Nachricht dieses Kennzeichen trägt, ist plausibel, aber ungeprüft → Nachweis gehört in #1533. Verhalten bei fehlendem Kennzeichen ist bewusst **fail-closed**: nichts lernen, nicht senden, sichtbar melden.
2. **„Zuletzt gesehene gewinnt" allein ist widerlegt.** Im selben Journal steht `09:19` eine Nachricht vom privaten Handy des PO (`4915158450319`). Eine reine Rezenz-Regel hätte die Garmin-Adresse von `08:30` damit überschrieben und Briefings zum Premium-Tarif ans falsche Ziel geschickt — still. Die Überschreib-Regel gilt deshalb nur **innerhalb** der als Garmin erkannten Nachrichten.
3. **Sandbox isoliert den Lesepfad nicht** (gemessen). Ohne ausdrückliche Sperre liest Staging das echte Produktiv-Journal und lernt echte Geräte-Adressen in seinen Datenbestand. Braucht einen Origin-/Umgebungs-Guard analog `sms.py:34-75`.
4. **Mandantentrennung:** Die Absendernummer ist vor dem Erstkontakt unbekannt, eine Zuordnung „Nummer → Nutzer" also nicht vorab möglich. Bei mehr als einem Premium-Nutzer ist eine echte Kopplung (Pairing) nötig; solange es genau einen gibt, trägt die Tier-Regel. Diese Grenze wird ausgewiesen, nicht wegdefiniert → Folge-Issue.
5. **Kein Rückfall auf `"default"`** bei der Nutzer-Auflösung — das wäre ein Cross-User-Datenleck.
6. **Dedup-Zeiger** gehört nach `get_data_root()/diagnostics/`, nicht als `data/last_sms_id.txt` wie im Vorlagecode (der ist nicht datenwurzel-konform, vgl. #1633).
7. **App-Weg noch ungemessen.** Dass der Versand ans Gerät funktioniert, ist über die seven.io-Website belegt (`connection: website`). Unsere App sendet über `connection: http` und hat `sms_from` noch nie gefüllt. Gleicher Endpunkt, gleiches Feld — geringes Risiko, aber es gehört in #1533 gemessen, nicht angenommen.
