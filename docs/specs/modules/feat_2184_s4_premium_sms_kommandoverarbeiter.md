---
entity_id: feat_2184_s4_premium_sms_kommandoverarbeiter
type: module
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [premium-sms, garmin-inreach, inbound, trip-command-processor, epic-2133]
---

# Premium-SMS erreicht den Kommandoverarbeiter

## Approval

- [ ] Approved — noch nicht vorgelegt (Feature-Planung, Freigabe folgt in `/30-write-spec`)

## Purpose

Eine eingehende Garmin-inReach-Nachricht (Kennzeichen `inreachlink.com`) löst heute
ausschliesslich das Lernen der Rückadresse aus — der eigentliche Nachrichtentext wird
verworfen, `TripCommandProcessor` wird nie aufgerufen. Diese Scheibe schliesst die letzte
der vier Eingangswege, die im Epic #2133 als fehlend benannt sind: Premium-SMS wird zu
einem vollwertigen Ad-hoc-Abrufkanal, auf demselben `TripCommandProcessor`, der Katalog-
und Kanaltreue (S1/S3) bereits generisch bedienen kann. Scheibe **S4** von Epic #2133,
Ticket #2184.

## Ist-Stand (nachgemessen 2026-09-07)

| Glied | Stand | Beleg |
|---|---|---|
| Journal-Poll erkennt Garmin-Nachrichten am Kennzeichen | ✅ | `src/services/inbound_sms_reader.py:162` |
| Absendernummer wird gelernt, `user_id` kommt in der Erfolgsantwort zurück | ✅ (Antwort wird **ignoriert**) | `internal/handler/premium_sms_connect.go:31-117`, Erfolgsantwort `{"status":"ok","user_id":...}` (`:115`) |
| Nachrichtentext | 🔴 **wird verworfen**, kein `InboundMessage` entsteht | `inbound_sms_reader.py:161,166-167` (`payload = {"from": sender}` — `text` fliesst nirgends hinein) |
| `TripCommandProcessor`/`InboundMessage.channel` | ✅ bereits kanalneutral, kennt `"premium_sms"` bereits aus S3 | `trip_command_processor.py:56-63`, `_resolve_channel_flags` (S3, #2126) |
| Versandkanal für die Antwort | ✅ vorhanden, ungenutzt für Kommando-Antworten | `src/output/channels/premium_sms.py::PremiumSmsOutput.send(subject, body)` |
| `send_command_reply_*`-Familie | ✅ für email/telegram vorhanden, **fehlt** für premium_sms | `src/services/notification_service.py:1795-1826` |

## Source

- **File:** `src/services/inbound_sms_reader.py`
- **File:** `src/services/notification_service.py`
- **Identifier:** `InboundSmsReader._poll_journal` (Garmin-Zweig, `:160-179`),
  `NotificationService.send_command_reply_premium_sms` (neu)
- Go (`internal/handler/premium_sms_connect.go`) bleibt **unverändert** — die
  benötigte Information (`user_id`) liefert der Endpunkt bereits, sie wird nur bisher
  nicht konsumiert.

## Estimated Scope

- **LoC:** ~90–150 Produktivcode, Tests vermutlich deutlich mehr — S3 (#2126, dieselbe
  Risikoklasse: mehrere Versandpfade, Zwei-Nutzer-Isolation, Mutations-Gegenprobe) hatte
  eine Schätzung von +120–180 und landete real bei +817 (Testanteil). Realistisch ist ein
  `loc_limit_override` bereits vor der RED-Messung einzuplanen.
- **Files:** 2 Produktivdateien + 1 Testdatei (+ ggf. Spec-Update)
- **Effort:** medium
- **Risk:** MEDIUM — Fehler im neuen Zweig dürfen den bestehenden, produktionskritischen
  Lern-Poll (Fix F001, dedup-Zeiger) nicht beschädigen; ein falsch platziertes `except`
  könnte den Zeiger fälschlich stehen lassen oder eine Verarbeitungs-Exception als
  "vorübergehender Lernfehler" fehlklassifizieren.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `InboundMessage`/`TripCommandProcessor.process` (`trip_command_processor.py:56-63,567`) | class/method | Bereits kanalneutral — nur Aufrufer fehlt für `premium_sms` |
| `_resolve_channel_flags` (S3, `trip_report_scheduler.py`) | function | Löst `heute`/`morgen` bereits korrekt auf `premium_sms` auf — **keine Änderung nötig** |
| `PremiumSmsOutput` (`src/output/channels/premium_sms.py`) | class | Versandkanal für die Kommando-Antwort, inkl. 30-Tage-Frischesperre |
| `Settings.with_user_profile` (`src/app/config.py:355`) | function | Liefert `premium_sms_reply_to`/`_at` für die soeben gelernte Adresse |
| `POST /api/internal/premium-sms-learn` (`internal/handler/premium_sms_connect.go`) | endpoint | Liefert `user_id` in der Erfolgsantwort — bereits vorhanden, wird konsumiert statt verworfen |
| Fix F001 (Dedup-Zeiger-Semantik, `inbound_sms_reader.py:12-27`) | invariant | Der neue Verarbeitungsschritt darf NICHT in die Zeiger-Logik der Lernanfrage eingreifen |

## Implementation Details

### Befehlstext extrahieren

Reale Garmin-Nachricht (Beleg #1676 S1, 2026-08-10):
`"Test über App inreachlink.com/g-0Oh3D2H2f… (51.9956, 7.7136)"` — der vom Nutzer
eingegebene Text steht **vor** dem Kennzeichen, danach folgen Garmin-generierter Link und
Koordinaten. Extraktion: `text.split(GARMIN_MARKER, 1)[0].strip()`.

### Ablauf im Garmin-Zweig von `_poll_journal` (`:160-179`)

Nach dem bestehenden, unveränderten Lernaufruf (`httpx.post(LEARN_ENDPOINT, ...)`):

1. Nur bei `response.status_code == 200` **und** `dry_run == False` weiterverarbeiten
   (Trockenlauf bleibt Spec-treu ohne Nebenwirkung; 4xx = keine Zuordnung möglich, keine
   Antwortadresse bekannt, keine Verarbeitung, wie heute).
2. `user_id = response.json().get("user_id")` — kommt bereits aus dem Endpunkt, keine
   neue Nutzerauflösung in Python nötig (kein Duplikat zu `lookup_user_by_*`).
3. Befehlstext extrahieren (s.o.); leer nach Extraktion → wie ein unbekannter Befehl
   behandeln (Konsistenz mit `_parse_command`, kein Sonderfall).
4. `InboundMessage(trip_name=<aktiver Trip>, body=<Befehlstext>, sender=sender,
   channel="premium_sms", received_at=..., user_id=user_id)` bauen. Trip-Ermittlung
   folgt dem Telegram-Muster (`_find_active_trip`, kein Trip-Name im Satelliten-Text —
   jedes Zeichen kostet) statt dem E-Mail-Muster (Betreff-Klammer).
5. `TripCommandProcessor().process(inbound)` aufrufen.
6. Bei `not result.suppress_email_reply`: Antwort über
   `NotificationService().send_command_reply_premium_sms(result, user_settings)` senden,
   mit `user_settings = base_settings.with_user_profile(user_id)`.
7. Schritte 3–6 laufen in einem **eigenen** `try/except`, das Verarbeitungsfehler nur
   loggt — es darf den Dedup-Zeiger (der bereits nach dem Lernaufruf feststeht) nicht
   beeinflussen und keinen `failed`-Zähler aus F001 auslösen (dieser bleibt exklusiv der
   Lernanfrage selbst vorbehalten).

### Neue Notification-Methode

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

## Expected Behavior

- **Input:** Garmin-inReach-SMS mit Kennzeichen `inreachlink.com`, Absender einem
  Premium-Nutzer eindeutig zuordenbar (R3-Auflösung erfolgreich).
- **Output:** Der vor dem Kennzeichen stehende Text wird als Befehl verarbeitet;
  `heute`/`morgen` lösen das volle Briefing **ausschliesslich per Premium-SMS** aus (S3
  greift bereits generisch), jeder andere gültige Befehl liefert die bestehende
  `confirmation_body`-Antwort per Premium-SMS.
- **Side effects:** Keine Änderung am Lern-/Dedup-Verhalten (F001 unverändert). Keine
  Änderung an E-Mail-/Telegram-Pfaden.

## Acceptance Criteria (Entwurf — Freigabe folgt in `/30-write-spec`)

- **AC-1:** Given eine Garmin-Nachricht `"heute inreachlink.com/g-xxx (lat, lon)"` von
  einer eindeutig zuordenbaren Premium-Nutzernummer / When der Journal-Poll läuft / Then
  wird das Tagesbriefing ausgelöst und **ausschliesslich per Premium-SMS** zugestellt
  (`briefing_log.channels == ["premium_sms"]`), ohne dass eine eigene Codezeile für die
  Kanalauswahl nötig ist (S3 trägt bereits).

- **AC-2:** Given eine Garmin-Nachricht mit einem bekannten Bare-Keyword (z. B.
  `"status"`) vor dem Kennzeichen / When der Poll läuft / Then geht die
  `confirmation_body` des Kommandoverarbeiters unverändert per Premium-SMS an die
  gelernte Rückadresse zurück.

- **AC-3:** Given eine Garmin-Nachricht, deren Text vor dem Kennzeichen zu keinem
  bekannten Befehl passt / When der Poll läuft / Then erhält der Nutzer dieselbe
  "Unbekannter Befehl"-Antwort wie über E-Mail/Telegram, per Premium-SMS — kein stilles
  Verwerfen.

- **AC-4:** Given eine Garmin-Nachricht, deren Absendernummer der Lernaufruf **nicht**
  eindeutig zuordnen kann (HTTP 409, `no_unique_premium_candidate`) / When der Poll läuft
  / Then wird **kein** `TripCommandProcessor`-Aufruf ausgelöst und keine Antwort
  versendet — unverändert zum heutigen Stand (keine bekannte Zieladresse).

- **AC-5:** Given der Origin ist nicht `production` und `GZ_PREMIUM_SMS_POLL_DRYRUN=1`
  (Trockenlauf) / When eine Garmin-Nachricht mit gültigem Befehlstext eintrifft / Then
  wird **kein** `TripCommandProcessor`-Aufruf ausgelöst und **keine** Premium-SMS
  versendet — der Trockenlauf bleibt frei von Nebenwirkungen (bestehende Spec-Zusicherung
  aus #1676 S1, hier auf den neuen Zweig fortgeschrieben).

- **AC-6:** Given eine Exception during der Kommandoverarbeitung (Schritt 3–6, z. B. Trip
  nicht ladbar) **nach** einem erfolgreichen Lernaufruf / When der Poll läuft / Then
  bleibt der Dedup-Zeiger korrekt auf dieser Nachricht stehen (wie bei jedem regulären
  Erfolg der Lernanfrage) und der nächste Journal-Eintrag wird normal weiterverarbeitet —
  ein Verarbeitungsfehler darf nicht als vorübergehender Lernfehler (F001) fehlklassifiziert
  werden und die Schleife nicht abbrechen.

- **AC-7:** Mandantentrennung. Given zwei Premium-Nutzer mit je eigener gelernter
  Rückadresse und eigenem aktiven Trip / When beide unabhängig voneinander eine
  Garmin-Nachricht senden / Then erhält jeder Nutzer die Antwort auf seinen eigenen Trip
  bezogen an seine eigene gelernte Nummer — keine Kreuzung.

## Known Limitations

- **Antwortlänge/Kurzform-Darstellung ist NICHT Teil dieser Scheibe.** Eine
  Drilldown-Antwort mit vielen Stunden kann als Premium-SMS lang werden (mehrteilige SMS,
  Kostenwirkung). Die Kürzungsregel/Verlaufsdarstellung für die Kurzform ist explizit
  Scheibe **S5** des Epics; diese Scheibe liefert nur die bereits bestehende
  `confirmation_body` unverändert aus.
- **Erste Verbindungsnachricht des Geräts** ("Test über App …", ohne Befehlsabsicht) fällt
  unter AC-3 (Unbekannter Befehl) und löst eine kostenpflichtige Antwort-SMS aus — analog
  zum bestehenden Verhalten bei E-Mail/Telegram für unbekannte Nutzertexte. Abweichendes
  Verhalten (z. B. Erstverbindung ohne Befehlsantwort) wäre eine Sonderregel für genau
  diesen Kanal und widerspräche dem Leitsatz "jeder Kanal, dieselbe Aussage" — nicht
  empfohlen, aber PO-Entscheidung bei Spec-Freigabe.
- **`selectable=false`-Metriken, Katalog-Lücken:** unverändert von S1 geerbt, hier nicht
  neu betroffen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Folgt demselben, bereits dokumentierten Grundsatz wie S3
  (`inbound_command_channels.md:90`, „Antwort auf gleichem Kanal") und lässt ADR-0049
  (Premium-SMS als vierter Kanal) unberührt — `premium_sms` wird nicht neu eingeführt,
  nur als Eingangsweg an einen bereits kanalneutralen Verarbeiter angeschlossen. Kein
  neues ADR nötig.

## Changelog

- 2026-09-07: Initial spec created (Feature-Planung, Scheibe S4 von Epic #2133)
