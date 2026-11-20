# Runbook — Staging-Prüfkonto mit Mockup-Daten (Issue #2967)

Spec: `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md` · Skript: `scripts/staging_pruefkonto_mockupdaten.py`

## Zweck

Der Elementlisten-Abgleich (#2913) vergleicht das Mockup `mockup-hub-fassung4.html` mit dem
Staging-Prüfkonto. Damit er keine Scheinabweichungen meldet, füllt das Seed-Skript das Konto
mit den Mockup-Beispieldaten: Trip „GR221 Mallorca“ (4 Etappen, Vorlage Alpen-Trekking,
Metrik-Flags wie im Mockup), eigene Vorlage „Mallorca Frühling“, Orts-Vergleich
„Münsterland“ (Münster, Telgte, Tecklenburg; Morgen-Briefing 07:00) und alle vier Kanäle
(E-Mail, SMS, Telegram, Premium-SMS) mit fiktiven Testwerten. An echte Geräte geht nichts:
Telegram und Premium-SMS verbinden mit fiktiven Werten ohne Versand; der SMS-Bestätigungscode,
den die Go-API im Premium-Tarif beim Eintragen der Nummer auslöst, läuft über den
Sandbox-Schlüssel von Staging (siehe „Sperre gegen echten SMS-Versand“), bestätigt wird mit dem
Code der Staging-Route `staging-code`.

## Prüfkonto

Eigenes Staging-Konto (Muster `GZ_E2E_EN_*`), Schlüssel in der Staging-`.env`:
`GZ_PRUEFKONTO_USER`, `GZ_PRUEFKONTO_PASS`, `GZ_PRUEFKONTO_MAIL`. Der Seed meldet sich nur damit an;
fehlen die Schlüssel, endet er mit Exit 2 vor jedem Aufruf. `GZ_AUTH_USER`/`GZ_AUTH_PASS` ist das
geteilte Konto `default`, das rund 50 andere Staging-E2E-Tests nutzen; Premium-Tarif und verbundene
Kanäle dort würden diese Tests verändern. Darum nutzt der Seed es nie (und lehnt die Nutzer-id
`default` zusätzlich ab).

## Aufruf (nur auf dem Staging-Host)

```bash
IDS=$(uv run python scripts/staging_pruefkonto_mockupdaten.py) && export $IDS   # ELEMENTLISTE_TRIP_ID / _ORTE_ID
set -a; . /home/hem/gregor_zwanzig_staging/.env; set +a                        # GZ_PRUEFKONTO_* (Quotes entfernt)
cd frontend && GZ_AUTH_USER="$GZ_PRUEFKONTO_USER" GZ_AUTH_PASS="$GZ_PRUEFKONTO_PASS" \
  npm run elementliste:abgleich -- [--sprache en]                              # Abgleich liest nur
```

Der Abgleich meldet sich mit `GZ_AUTH_USER`/`GZ_AUTH_PASS` an; für den Seed-Stand müssen diese
auf die Prüfkonto-Werte zeigen, sonst liest er das Konto `default` (ohne die Seed-IDs).

Optionen: `--basis-url URL` (nur `https://staging.gregor20.henemm.com`), `--intern-url URL`
(nur `http://localhost:8091`), `--env-datei PFAD` (Standard `/home/hem/gregor_zwanzig_staging/.env`).

| Exit | Bedeutung |
|---|---|
| 0 | Soll-Zustand erreicht; stdout: `ELEMENTLISTE_TRIP_ID=…` und `ELEMENTLISTE_ORTE_ID=…` |
| 1 | API-/Datenfehler: Login abgelehnt, HTTP-Fehler, 409 `chat_id_already_linked` (fremde Chat-ID), 429 Ratebremse der Premium-SMS-Verknüpfung (wird nicht wiederholt) |
| 2 | Aufruf-/Schutzfehler: Prod- oder fremde Basis-URL (auch `http://` statt `https://`), Loopback-Ziel nicht `localhost:8091`, `.env`-Schlüssel fehlen, aktiver Live-SMS-Schlüssel `GZ_SEVEN_API_KEY` in der `.env` |

## Hinweise

- **Loopback-Port 8091:** Telegram- und Premium-SMS-Verbindung laufen über die internen Routen
  der Staging-Go-API (`gregor-api-staging`, `GZ_PORT=8091`) direkt am Port, nicht über nginx.
  Darum funktioniert das Skript nur auf dem Staging-Host; von woanders scheitert es vor dem
  ersten Schreibzugriff.
- **Core-Secret:** kommt aus der Staging-`.env` (`GZ_CORE_SHARED_SECRET`), bleibt nur im Speicher
  und erscheint in keiner Ausgabe. Zugang des Prüfkontos: `GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS`.
- **Idempotent:** zweiter Lauf ändert nichts, verbindet keinen Kanal erneut und löst keine
  Ratebremse aus. Geschrieben wird nur Read-Modify-Write auf die eigenen Seed-Datensätze;
  andere Daten des Kontos bleiben unverändert.
- **Tarif zuerst:** der Tarif wird auf Premium gesetzt, bevor Trip, Orte und Vergleich angelegt
  werden. Sonst würde die Free-Grenze (3 Trips, 2 Vergleiche, 10 Orte) ein Konto mit weiteren
  eigenen Datensätzen mit `409 quota_exceeded` abbrechen lassen.
- **Sperre gegen echten SMS-Versand:** im Premium-Tarif verschickt die Go-API beim Eintragen der
  SMS-Nummer einen Bestätigungscode. Darum bricht das Skript mit Exit 2 ab, bevor es irgendetwas
  schreibt, wenn die Staging-`.env` einen aktiven Live-Schlüssel `GZ_SEVEN_API_KEY` führt
  (in jeder Schreibweise, die der Python-Core liest: auch mit `export `, kleingeschrieben oder mit
  Leerzeichen um `=`; auskommentierte Zeile oder leerer Wert zählen nicht; der Wert wird nie
  ausgegeben). Staging
  versendet nur über den Sandbox-Schlüssel `GZ_SEVEN_SANDBOX_KEY`. Beim zweiten Lauf ist die
  Nummer schon bestätigt, es wird kein Code mehr ausgelöst.
- **Tarif und Zähler bei jedem Lauf:** jeder Lauf (auch der zweite) setzt den Tarif auf Premium
  und die Tageszähler `sms` und `premium_sms` auf 0 (`POST /api/auth/staging-seed`). Ein seit
  dem letzten Lauf verbrauchter Zähler steht danach wieder auf 0.
- **E-Mail-Empfänger:** Konto-Adresse plus eine fiktive `.invalid`-Adresse. Hat das Konto keine
  Mail-Adresse, endet der Lauf mit Exit 1 vor dem ersten Schreibzugriff (nie ein leerer Empfänger).
- **Gespeicherte Form:** die Go-API speichert das Morgen-Briefing als `07:00:00`; das Skript
  vergleicht mit genau dieser Form, damit der zweite Lauf den Vergleich nicht neu schreibt.
- **Kanalauswahl (#3151, Mockup `mockup-hub-fassung4.html` Z.373-374):** Trip und Vergleich
  bekommen Briefing per E-Mail und Telegram (SMS, Premium-SMS aus), Alarme auf allen vier
  Kanälen mit Dringlichkeits-Schwellen E-Mail/Telegram `LOW` (gering), SMS `MODERATE` (mittel),
  Premium-SMS `HIGH` (hoch). Trip: `report_config`, `alert_channels`, `alert_channel_thresholds`;
  Vergleich: `send_*` und `alert_channels` ausdrücklich (sonst leitet die Go-API es aus den
  Briefing-Schaltern ab). Die drei Unterobjekte werden je Kanal gemerged: fremde Schlüssel und
  Felder bleiben, ein zweiter Lauf schreibt nichts.
- **Kein echter Versand trotz Alarmen auf allen Kanälen und täglichem Vergleich:** auf Staging
  (`GZ_ENV=staging`) leitet `Settings.with_user_profile` jeden Versand über `for_testing()`
  (`src/app/config.py`): E-Mail über Stalwart statt Resend (Konto-Adresse = Test-Postfach,
  Zweitadresse `.invalid`), SMS und Premium-SMS nur mit `GZ_SEVEN_SANDBOX_KEY` (Sperre
  `seven_io_base._guard_test_mode_sandbox_key`, Live-Schlüssel auskommentiert), Telegram nur mit
  dem Test-Bot und nur an die Test-Chat-ID (`telegram._guard_test_mode_bot_token`,
  `_guard_test_mode_target_chat`); die Chat-ID des Seeds ist fiktiv. Der Trip liegt in der
  Vergangenheit. Darum bleibt der Vergleich auf `schedule: daily`; fiele einer dieser Belege weg,
  gehört er auf `manual`.
- **Danach Abgleich DE und EN** (je ca. 8 Min., nicht parallel mit demselben Konto); die Berichte
  sind Grundlage der Neuklassifizierung der Besitzerliste (#3151).
- Die Rückadresse der Premium-SMS wird bei Bedarf neu gelernt (Stempel = Laufzeit), damit sie
  „frisch“ bleibt; die Datumswerte im Mockup-Text sind Beispielwerte.
