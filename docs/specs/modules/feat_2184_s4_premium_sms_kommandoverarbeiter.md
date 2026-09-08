---
entity_id: feat_2184_s4_premium_sms_kommandoverarbeiter
type: module
created: 2026-09-07
updated: 2026-09-08
status: draft
version: "1.1"
tags: [premium-sms, garmin-inreach, inbound, trip-command-processor, trip-selection, gewitter-herkunft, epic-2133]
---

# Premium-SMS erreicht den Kommandoverarbeiter

## Approval

- [x] Approved — PO-Freigabe am 2026-09-08. Beide offenen Punkte im Abschnitt „Offene Fragen
  für die PO-Freigabe" sind mit der Empfehlung abgenommen: Gewitter-Herkunft auf
  Premium-SMS/SMS wird unterdrückt (AC-8), die Erstverbindungsnachricht wird wie ein
  unbekannter Befehl beantwortet (AC-3).

## Purpose

Eine eingehende Garmin-inReach-Nachricht (Kennzeichen `inreachlink.com`) löst heute
ausschliesslich das Lernen der Rückadresse aus — der eigentliche Nachrichtentext wird
verworfen, `TripCommandProcessor` wird nie aufgerufen. Diese Scheibe schliesst die letzte
der vier Eingangswege, die im Epic #2133 als fehlend benannt sind: Premium-SMS wird zu
einem vollwertigen Ad-hoc-Abrufkanal, auf demselben `TripCommandProcessor`, der Katalog-
und Kanaltreue (S1/S3) bereits generisch bedienen kann. Weil dieser Kanal zum dritten
Erzeuger von `InboundMessage` wird, fällt zugleich die bisher rein strukturelle Sicherung
der PO-Abwahl „SMS/Premium-SMS ohne Gewitter-Herkunft" weg — diese Scheibe ersetzt sie
durch einen echten Kanal-Guard. Scheibe **S4** von Epic #2133, Ticket #2184.

## Ist-Stand (nachgemessen 2026-09-08 gegen `ccd7c955`)

| Glied | Stand | Beleg |
|---|---|---|
| Journal-Poll erkennt Garmin-Nachrichten am Kennzeichen | ✅ | `src/services/inbound_sms_reader.py:162` |
| Absendernummer wird gelernt, `user_id` kommt in der Erfolgsantwort zurück | ✅ (Antwort wird **ignoriert**) | `internal/handler/premium_sms_connect.go:31-117`, Erfolgsantwort `{"status":"ok","user_id":...}` (`:115`) |
| Nachrichtentext | 🔴 **wird verworfen**, kein `InboundMessage` entsteht | `inbound_sms_reader.py:161,166-167` (`payload = {"from": sender}` — `text` fliesst nirgends hinein) |
| `TripCommandProcessor`/`InboundMessage.channel` | ✅ bereits kanalneutral, kennt `"premium_sms"` bereits aus S3 | `trip_command_processor.py:56-63`, `_resolve_channel_flags` (S3, #2126) |
| Versandkanal für die Antwort | ✅ vorhanden, ungenutzt für Kommando-Antworten | `src/output/channels/premium_sms.py::PremiumSmsOutput.send(subject, body)` |
| `send_command_reply_*`-Familie | ✅ für email/telegram vorhanden, **fehlt** für premium_sms | `src/services/notification_service.py:1795-1826` |
| Gewitter-Herkunft im Kommando-Pfad | 🔴 nur **strukturell** ausgeschlossen, nicht per Guard | `trip_command_processor.py:1373-1376`, `:1444-1448`, `:1502-1503` — Kommentare behaupten „es gibt keinen SMS-/Premium-SMS-Kommandopfad", genau das widerlegt #2184 |
| Trip-Auswahlregel für Kanal-Reader ohne Trip-Namen im Text | ✅ existiert, aber nur im Telegram-Reader, nicht geteilt | `inbound_telegram_reader.py:385-406` (`_find_active_trip`) |

## Source

- **File:** `src/services/inbound_sms_reader.py`
- **File:** `src/services/notification_service.py`
- **File:** `src/services/trip_command_processor.py`
- **File:** `src/services/trip_selection.py` (neu)
- **File:** `src/services/inbound_telegram_reader.py` (Delegations-Hülle)
- **Identifier:** `InboundSmsReader._poll_journal` (Garmin-Zweig, `:160-209`),
  `NotificationService.send_command_reply_premium_sms` (neu),
  `pick_active_trip(trips, now_utc)` (neu, `trip_selection.py`),
  `_fmt_day_agg`/`_fmt_gewitter`/`_fmt_timeline` (`trip_command_processor.py:1360-1513`,
  bekommen `channel`-Parameter), `_find_active_trip` (wird Delegations-Hülle)
- Go (`internal/handler/premium_sms_connect.go`) bleibt **unverändert** — die
  benötigte Information (`user_id`) liefert der Endpunkt bereits, sie wird nur bisher
  nicht konsumiert.

## Estimated Scope

- **LoC:** Produktivcode ~110–150, Tests ~220–330 → **~330–480 gesamt**. S3 (#2126,
  dieselbe Risikoklasse: mehrere Versandpfade, Zwei-Nutzer-Isolation,
  Mutations-Gegenprobe) schätzte +120–180 und landete real bei +817 (Testanteil) —
  die Schätzung hier ist entsprechend konservativ nach oben gezogen.
- **Files:** 5 Produktivdateien (1 CREATE, 4 MODIFY) + 3 Testdateien (2 CREATE, 1 MODIFY)
  + 2 Doku (diese Spec, `inbound_command_channels.md`)
- **Effort:** medium
- **Risk:** MEDIUM–HIGH — der neue Zweig liegt unmittelbar neben der F001-Dedup-
  Zeigersemantik des produktionskritischen Lern-Polls; ein falsch platziertes `except`
  könnte den Zeiger fälschlich stehen lassen oder eine Verarbeitungs-Exception als
  „vorübergehender Lernfehler" fehlklassifizieren — mit Kostenwirkung pro Poll-Zyklus
  (Satelliten-SMS).
- **LoC-Limit:** 250 wird gerissen → `loc_limit_override` steht bereits auf 400.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `InboundMessage`/`TripCommandProcessor.process` (`trip_command_processor.py:56-63,567`) | class/method | Bereits kanalneutral — nur Aufrufer fehlt für `premium_sms` |
| `_resolve_channel_flags` (S3, `trip_report_scheduler.py`) | function | Löst `heute`/`morgen` bereits korrekt auf `premium_sms` auf — **keine Änderung nötig** |
| `PremiumSmsOutput` (`src/output/channels/premium_sms.py`) | class | Versandkanal für die Kommando-Antwort, inkl. 30-Tage-Frischesperre |
| `Settings.with_user_profile` (`src/app/config.py:366`) | function | Liefert `premium_sms_reply_to`/`_at` für die soeben gelernte Adresse |
| `POST /api/internal/premium-sms-learn` (`internal/handler/premium_sms_connect.go`) | endpoint | Liefert `user_id` in der Erfolgsantwort — bereits vorhanden, wird konsumiert statt verworfen |
| Fix F001 (Dedup-Zeiger-Semantik, `inbound_sms_reader.py:12-27`) | invariant | Der neue Verarbeitungsschritt darf NICHT in die Zeiger-Logik der Lernanfrage eingreifen |
| `pick_active_trip(trips, now_utc)` (neu, `src/services/trip_selection.py`) | function | Geteilte Auswahlregel (Ortstag-Overlap, Zukunfts-Fallback) — `load_all_trips` bleibt im jeweiligen Reader |
| `_find_active_trip` (`inbound_telegram_reader.py:385-406`) | method | Wird zur zweizeiligen Delegations-Hülle um `pick_active_trip`, bit-identisches Verhalten |
| `thunder_signal_label`/Gewitter-Formatierer (`trip_command_processor.py:1360-1513`) | function | Bekommen `channel`-Parameter und einen Herkunfts-Guard für `sms`/`premium_sms` |
| `briefing_log.channels` (Go-Cockpit-Kachel) | field | Downstream-Messpunkt: bei Premium-SMS-Anfragen künftig `["premium_sms"]` |
| `api/routers/scheduler.py:167-168` → `internal/scheduler/scheduler.go:470-517` | contract | `last_failed_count` speist `ok`/`partial` im Go-Scheduler-Status — der neue Zweig darf ihn nicht erhöhen |

## Implementation Details

### 1. Trip-Auswahl als geteilter Baustein (Schnitt NACH dem Laden)

Neues Modul `src/services/trip_selection.py`:

```python
def pick_active_trip(trips: list[Trip], now_utc: datetime) -> Trip | None
```

Bit-identisch die heutige Auswahlregel aus `inbound_telegram_reader._find_active_trip`
(`:385-406`): Overlap am **Ortstag dieses Trips** (`trip_local_today`, ADR-0044), Rückfall
auf den frühesten zukünftigen Trip. `load_all_trips(user_id)` bleibt **im jeweiligen
Reader** — `_find_active_trip` wird zur zweizeiligen Hülle
(`trips = load_all_trips(user_id)` → `return pick_active_trip(trips, now_utc)`), der
SMS-Reader macht dasselbe mit eigenem Import.

Begründung für den Schnitt: `load_all_trips` mit ins Modul zu ziehen würde vier bestehende
Testdateien treffen, die `services.inbound_telegram_reader.load_all_trips` auf dem
Modulpfad patchen (`test_inbound_telegram_reader.py:58-131`,
`test_befehlspfade_folgen_ortszone.py:362-490`,
`test_bug_824_archived_trip_filter.py:184-208`, `_telegram_live_fixture.py:347`) — wanderte
der Aufruf, griffen alle vier Patches ins Leere und liefen still gegen echte Daten statt
gegen Fixtures (falsches Grün). Der gewählte Schnitt lässt sie unberührt.

### 2. Befehlstext extrahieren

Reale Garmin-Nachricht (Beleg #1676 S1, 2026-08-10):
`"Test über App inreachlink.com/g-0Oh3D2H2f… (51.9956, 7.7136)"` — der vom Nutzer
eingegebene Text steht **vor** dem Kennzeichen, danach folgen Garmin-generierter Link und
Koordinaten. Extraktion: `text.split(GARMIN_MARKER, 1)[0].strip()`.

### 3. Ablauf im Garmin-Zweig von `_poll_journal` (`:160-209`)

Nach dem bestehenden, unveränderten Lernaufruf (`httpx.post(LEARN_ENDPOINT, ...)`):

1. Nur bei `response.status_code == 200` **und** `dry_run == False` weiterverarbeiten
   (Trockenlauf bleibt nebenwirkungsfrei; 4xx/409 = keine eindeutige Zuordnung, keine
   Antwortadresse bekannt, keine Verarbeitung, wie heute).
2. `user_id = response.json().get("user_id")` — fehlt der Schlüssel oder ist er leer
   (der 200er-Vertrag ist bisher durch **keinen** Contract-Test abgesichert): loggen,
   **keine** Verarbeitung, keine Antwort. Kein Rückfall auf `"default"` (Cross-User-
   Datenleck-Verbot).
3. Befehlstext extrahieren (s. o.); leer nach Extraktion → wie ein unbekannter Befehl
   behandeln (Konsistenz mit `_parse_command`, kein Sonderfall).
4. `load_all_trips(user_id)` + `pick_active_trip(trips, now_utc)` → aktiven Trip
   ermitteln (kein Trip-Name im Satelliten-Text — jedes Zeichen kostet).
5. `InboundMessage(trip_name=<aktiver Trip>, body=<Befehlstext>, sender=sender,
   channel="premium_sms", received_at=..., user_id=user_id)` bauen.
6. `TripCommandProcessor().process(inbound)` aufrufen.
7. Bei `not result.suppress_email_reply`: Antwort über
   `NotificationService().send_command_reply_premium_sms(result, user_settings)` senden,
   mit `user_settings = base_settings.with_user_profile(user_id)`.
8. Schritte 3–7 laufen in einem **eigenen, nachgelagerten** `try/except`, das
   Verarbeitungsfehler nur loggt — es darf den Dedup-Zeiger (der bereits nach dem
   Lernaufruf feststeht) nicht beeinflussen und **keinen** `failed`-Zähler aus F001
   auslösen (dieser bleibt exklusiv der Lernanfrage selbst vorbehalten).

### 4. Neue Notification-Methode

```python
def send_command_reply_premium_sms(
    self, result: CommandResult, settings: Settings,
) -> None:
    """Sendet eine Command-Bestätigung per Premium-SMS."""
    try:
        PremiumSmsOutput(settings).send(
            subject=result.confirmation_subject,
            body=result.confirmation_body,
        )
        logger.info(f"Premium-SMS confirmation sent: {result.confirmation_subject}")
    except Exception as e:
        logger.error(f"Failed to send premium-sms confirmation: {e}")
```

Direktes Spiegelbild von `send_command_reply_email` (`notification_service.py:1795-1807`).

### 5. Gewitter-Herkunft für `sms`/`premium_sms` per Guard unterdrücken

Die PO-Abwahl „SMS und Premium-SMS bleiben ohne Herkunft" (`feat_1680_s5a_…md:337` AC-12,
`feat_1680_s5b_…md:456` AC-9) war bisher **strukturell** durch die Annahme abgesichert,
`InboundMessage` habe genau zwei Erzeuger (E-Mail, Telegram) — festgeschrieben in drei
Kommentaren (`trip_command_processor.py:1373-1376`, `:1444-1448`, `:1502-1503`). Mit dem
dritten Erzeuger aus #2184 fällt diese Sicherung weg. Ersatz: die drei Formatierer
`_fmt_day_agg` (GLANCE), `_fmt_gewitter` (GEWITTER) und `_fmt_timeline` bekommen einen
`channel`-Parameter (Muster wie `with_emoji = channel == "telegram"` bei `:928`, `:1027`,
`:1053`), Guard `zeige_herkunft = channel not in ("sms", "premium_sms")`. Die drei
Kommentare werden auf die neue, echte Begründung umgeschrieben — sonst bliebe eine falsche
Begründung im Code stehen.

## Expected Behavior

- **Input:** Garmin-inReach-SMS mit Kennzeichen `inreachlink.com`, Absender einem
  Premium-Nutzer eindeutig zuordenbar (R3-Auflösung erfolgreich, `user_id` im 200er-Body).
- **Output:** Der vor dem Kennzeichen stehende Text wird als Befehl verarbeitet;
  `heute`/`morgen` lösen das volle Briefing **ausschliesslich per Premium-SMS** aus (S3
  greift bereits generisch), jeder andere gültige Befehl liefert die bestehende
  `confirmation_body`-Antwort per Premium-SMS — ohne Gewitter-Herkunftszusatz. Ein
  unbekannter Befehl liefert die „Unbekannter Befehl"-Antwort, ebenfalls per Premium-SMS.
- **Side effects:** Keine Änderung am Lern-/Dedup-Verhalten (F001 unverändert). Keine
  Änderung an E-Mail-/Telegram-Pfaden (dort bleibt die Gewitter-Herkunft sichtbar). Keine
  Änderung an `last_failed_count`-Semantik durch reine Verarbeitungsfehler.

## Acceptance Criteria

- **AC-1:** Given eine Garmin-Nachricht `"heute inreachlink.com/g-xxx (lat, lon)"` von einer
  eindeutig zuordenbaren Premium-Nutzernummer / When der Journal-Poll läuft / Then wird das
  Tagesbriefing ausgelöst und **ausschliesslich per Premium-SMS** zugestellt
  (`briefing_log.channels == ["premium_sms"]`), ohne dass eine eigene Codezeile für die
  Kanalauswahl nötig ist (S3 trägt bereits).

- **AC-2:** Given eine Garmin-Nachricht mit einem bekannten Bare-Keyword (z. B. `"status"`)
  vor dem Kennzeichen / When der Poll läuft / Then geht die `confirmation_body` des
  Kommandoverarbeiters unverändert per Premium-SMS an die gelernte Rückadresse zurück.

- **AC-3:** Given eine Garmin-Nachricht, deren Text vor dem Kennzeichen zu keinem bekannten
  Befehl passt / When der Poll läuft / Then erhält der Nutzer dieselbe „Unbekannter
  Befehl"-Antwort wie über E-Mail/Telegram, per Premium-SMS — kein stilles Verwerfen.

- **AC-4:** Given eine Garmin-Nachricht, deren Absendernummer der Lernaufruf **nicht**
  eindeutig zuordnen kann (HTTP 409, `no_unique_premium_candidate`) / When der Poll läuft /
  Then wird **kein** `TripCommandProcessor`-Aufruf ausgelöst und keine Antwort versendet —
  unverändert zum heutigen Stand (keine bekannte Zieladresse).

- **AC-5:** Given der Origin ist nicht `production` und `GZ_PREMIUM_SMS_POLL_DRYRUN=1`
  (Trockenlauf) / When eine Garmin-Nachricht mit gültigem Befehlstext eintrifft / Then wird
  weder `TripCommandProcessor.process` aufgerufen noch **eine einzige** Premium-SMS über
  `PremiumSmsOutput`/den seven.io-POST abgesetzt — die Beobachtung erfolgt am tatsächlichen
  Versandaufruf, nicht nur am Zähler `learned == 0`, sonst bliebe ein Trockenlauf mit
  echtem Satelliten-Versand unentdeckt.

- **AC-6:** Given eine Exception während der Kommandoverarbeitung (Textextraktion,
  Trip-Auswahl, `process()` oder Antwortversand) **nach** einem erfolgreichen Lernaufruf /
  When der Poll läuft / Then bleibt der Dedup-Zeiger korrekt auf dieser Nachricht stehen
  (wie bei jedem regulären Erfolg der Lernanfrage), der nächste Journal-Eintrag wird normal
  weiterverarbeitet, **und** `last_failed_count` bleibt bei `0` — ein reiner
  Verarbeitungsfehler darf nicht als vorübergehender Lernfehler (F001) fehlklassifiziert
  werden und darf den Go-Scheduler-Status nicht von `ok` auf `partial` kippen.

- **AC-7:** Mandantentrennung. Given zwei Premium-Nutzer mit je eigener gelernter
  Rückadresse und eigenem aktiven Trip / When beide unabhängig voneinander eine
  Garmin-Nachricht senden / Then erhält jeder Nutzer die Antwort auf seinen eigenen Trip
  bezogen an seine eigene gelernte Nummer — keine Kreuzung.

- **AC-8:** Gewitter-Herkunft ist kanalabhängig, in beide Richtungen geprüft. Given eine
  Wetterlage mit Gewittersignal, die im GLANCE-, GEWITTER- oder Timeline-Formatierer einen
  Herkunftszusatz erzeugen würde / When dieselbe Lage einmal per E-Mail/Telegram-Anfrage und
  einmal per Premium-SMS/SMS-Anfrage formatiert wird / Then enthält die E-Mail-/
  Telegram-Antwort den Herkunftszusatz unverändert, während die Premium-SMS-/SMS-Antwort ihn
  über **alle drei** Formatierer hinweg nicht enthält — ein Guard nur in einem der drei
  Formatierer genügt nicht.

- **AC-9:** Given der Lernaufruf antwortet mit HTTP 200, aber ohne verwertbaren
  `user_id`-Schlüssel im Body (fehlt oder leer) / When der Poll läuft / Then wird **keine**
  Kommandoverarbeitung ausgelöst und **kein** Rückfall auf einen Default- oder
  Betreiber-Nutzer vorgenommen — der 200er-Vertrag wird nicht stillschweigend vorausgesetzt.

- **AC-10:** Given eine Garmin-Nachricht mit dem Text `"heute"` vor dem Kennzeichen / When
  der Poll läuft / Then geht **genau eine** Premium-SMS heraus — das ausgelöste Briefing.
  Es gibt **keine** zusätzliche, separate Kommando-Bestätigungs-SMS neben dem Briefing für
  denselben Vorgang.

## Mutationen, an denen sich die Gegenprobe messen muss

1. **`if not result.suppress_email_reply` entfernen.** Ein Test, der nur „bei `heute`
   kommt eine Premium-SMS" prüft, bleibt grün — die Briefing-SMS kommt ja. Fängt es nur:
   ein Test, der **genau eine** abgesetzte Premium-SMS zählt, nicht zwei (AC-10).
2. **`break` bei `:179`/`:209` zu `continue`.** Fängt nur ein Test über **zwei**
   Poll-Läufe, der den Zeigerstand nachmisst — nicht einer, der `learned == 0` prüft.
3. **Herkunfts-Guard in nur einem der drei Formatierer.** Fängt nur ein parametrisierter
   Test über alle drei Pfade (GLANCE, GEWITTER, Timeline) mit einer Fixture, die garantiert
   eine Zutat mit Gewittersignal trägt (AC-8).
4. **`response.json().get("id")` statt `.get("user_id")`.** Ein Ein-Nutzer-Test bleibt
   grün, weil der Rückfall auf die Basis-Settings eine plausible SMS erzeugt. Fängt nur der
   Zwei-Nutzer-Test (AC-7) bzw. der gezielte Test auf fehlenden `user_id`-Schlüssel (AC-9).
5. **Verarbeitungs-`except` in den Lernblock hineingezogen.** Fängt nur ein Test, der den
   Lernaufruf **erfolgreich** mockt und `process()` werfen lässt und dann prüft: Zeiger
   wandert **und** `last_failed_count == 0` (AC-6).
6. **Dry-Run-Gate hinter die Verarbeitung geschoben.** Fängt nur ein Test, der den
   Premium-SMS-Versand selbst beobachtet und **null** Aufrufe fordert — nicht einer, der
   nur `learned == 0` prüft (AC-5).

## Known Limitations

- **Antwortlänge/Kurzform-Darstellung ist NICHT Teil dieser Scheibe.** `PremiumSmsOutput.
  send()` hat kein Limit, `subject` wird verworfen (`seven_io_base.py:167`). Eine
  Drilldown-Antwort mit vielen Stunden kann als Premium-SMS lang werden (mehrteilige,
  kostenpflichtige SMS). Die Kürzungsregel/Verlaufsdarstellung für die Kurzform ist
  explizit Scheibe **S5** des Epics; diese Scheibe liefert nur die bereits bestehende
  `confirmation_body` unverändert aus.
- **Erste Verbindungsnachricht des Geräts** ("Test über App …", ohne Befehlsabsicht) fällt
  unter AC-3 (Unbekannter Befehl) und löst eine kostenpflichtige Antwort-SMS aus — analog
  zum bestehenden Verhalten bei E-Mail/Telegram für unbekannte Nutzertexte.
- **`selectable=false`-Metriken, Katalog-Lücken:** unverändert von S1 geerbt, hier nicht
  neu betroffen.

## Offene Fragen für die PO-Freigabe

- **(a) Gewitter-Herkunft auf Premium-SMS unterdrücken?** Empfehlung: **ja** (AC-8, wie in
  dieser Spec beschrieben). Ohne den Guard würde der neue Kommandopfad ab Merge die bereits
  getroffene PO-Entscheidung „SMS/Premium-SMS ohne Herkunft" (`feat_1680_s5a_…md:337`,
  `feat_1680_s5b_…md:456`) unterlaufen — auf einem Kanal, der pro Zeichen Geld und
  Garmin-Kontingent kostet.
- **(b) Erstverbindungsnachricht wie unbekannten Befehl behandeln?** Empfehlung: **ja**
  (AC-3 greift unverändert). Konsistent mit dem Epic-Leitsatz „jeder Kanal, dieselbe
  Aussage"; eine Bestätigung "deine erste Nachricht ist angekommen" hat für den Wanderer
  sogar eigenen Wert. Kostet eine SMS — als bekannte Grenze oben dokumentiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Folgt demselben, bereits dokumentierten Grundsatz wie S3
  (`inbound_command_channels.md:90`, „Antwort auf gleichem Kanal") und lässt ADR-0049
  (Premium-SMS als vierter Kanal) unberührt — `premium_sms` wird nicht neu eingeführt,
  nur als Eingangsweg an einen bereits kanalneutralen Verarbeiter angeschlossen. Die
  Extraktion von `pick_active_trip` folgt der Präzedenz `src/services/trip_day.py`
  („Verschoben aus `services.trip_command_processor` (#1470) — bit-identisches Verhalten").
  Kein neues ADR nötig.

## Changelog

- 2026-09-07: Initial spec created (Feature-Planung, Scheibe S4 von Epic #2133)
- 2026-09-08: Freigabereife Fassung nach Analyse-Phase — Trip-Auswahl als geteilter
  Baustein `trip_selection.pick_active_trip` ergänzt (`_find_active_trip` wird
  Delegations-Hülle); Gewitter-Herkunfts-Guard für `sms`/`premium_sms` über alle drei
  Formatierer als AC-8 ergänzt; `user_id`-Guard bei fehlendem 200er-Feld als AC-9 ergänzt;
  AC-5 auf tatsächlich beobachteten Versandaufruf verschärft (statt nur `learned == 0`);
  AC-6 um `last_failed_count == 0` ergänzt; AC-10 (genau eine Premium-SMS bei `heute`)
  neu; Mutations-Gegenprobe (6 Mutationen) aus der Analyse übernommen; Scope auf 5
  Produktivdateien (1 CREATE, 4 MODIFY) + 3 Testdateien korrigiert, `loc_limit_override`
  auf 400; zwei offene PO-Punkte mit Empfehlung explizit ausgewiesen.
