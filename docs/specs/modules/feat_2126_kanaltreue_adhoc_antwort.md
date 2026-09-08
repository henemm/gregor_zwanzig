---
entity_id: feat_2126_kanaltreue_adhoc_antwort
type: module
created: 2026-09-06
updated: 2026-09-08
status: draft
version: "1.1"
tags: [kanaltreue, adhoc-abruf, trip-command-processor, trip-report-scheduler, epic-2133]
---

# Kanaltreue der Ad-hoc-Antwort

## Approval

- [x] Approved — PO-Freigabe am 2026-09-06 (inkl. AC-4: Anfrage über einen im Trip
  deaktivierten Kanal wird dennoch über genau diesen Kanal beantwortet)

## Purpose

Eine Ad-hoc-Anfrage (`heute` / `morgen`) löst heute den regulären Briefing-Fan-out über
**alle** im Trip aktivierten Kanäle aus — unabhängig davon, über welchen Kanal die Anfrage
gestellt wurde. Diese Spec zieht den bereits an anderer Stelle dokumentierten Grundsatz
„Antwort auf gleichem Kanal" (`docs/specs/modules/inbound_command_channels.md:90`) auf den
einen Pfad nach, der sich ihm bislang entzieht, weil er nicht über `confirmation_body`
antwortet, sondern den vollständigen Briefing-Versand auslöst. Scheibe **S3** von Epic #2133,
Ticket #2126.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_resolve_channel_flags` (neu), `send_on_demand_report`,
  `_send_trip_report_outcome`, `_build_trip_report_request`
- **Aufrufende Datei:** `src/services/trip_command_processor.py`
  (`_handle_query`, `_trigger_on_demand`)

Python-Core (`src/services/`) — keine Berührung mit Go (`internal/`) oder Frontend.

## Estimated Scope

- **LoC:** ~900 (Produktivcode +55 bis +85, Tests **+817 gemessen** — die ursprüngliche
  Schätzung „+120 bis +180" war zu niedrig: acht ACs, davon vier mit Positivkontrolle und zwei
  mit Zwei-Nutzer-Aufbau)
- **Files:** 4 Code/Test-Dateien + 2 Doku
- **Effort:** medium
- **Risk:** MEDIUM — vier Versandpfade (Slot-Briefing, Ad-hoc-Abruf, Test-Versand,
  `report`-Kommando) teilen sich denselben Wirkort; ein Fehler dort wäre unsichtbar, weil ein
  zu wenig versendeter Kanal beim planmässigen Briefing niemandem sofort auffällt.
- **LoC-Limit:** 250 wird gerissen → `workflow.py set-field loc_limit_override 1000`
  (500 reicht nach der RED-Messung nicht).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `InboundMessage.channel` (`trip_command_processor.py:61`) | field | Herkunftskennung — bereits vorhanden, bricht heute nur an `:627` ab |
| `sms_allowed` / `premium_sms_allowed` (`src/services/user_tier.py`) | function | Tier-Gates, bleiben auch im Override-Fall wirksam |
| `TripReportConfig` (`src/app/models.py:1104`; Trip-Einstellungen `send_email`/`send_sms`/`send_premium_sms`/`send_telegram`) | model | Wird für den anfragenden Kanal überschrieben, sonst unverändert gelesen |
| `Settings.with_user_profile` (`src/app/config.py:355`) | function | Löst Empfängeradresse für erkannten Nutzer bereits korrekt auf (hier nur Regressionstest, kein neuer Code) |
| `briefing_log.channels` (`_append_briefing_log`, `trip_report_scheduler.py:1931`) | field | Downstream-Konsument (Go-Cockpit-Kachel #393) — Messpunkt für die Tests dieser Spec |

## Implementation Details

### Wirkort: neue Hilfsfunktion ersetzt zwei wortgleiche Formelstellen

Die vier Kanal-Flags werden heute an **zwei** identischen Stellen berechnet
(`trip_report_scheduler.py:1743-1752` im Haupt-Request, `:1371-1379` im
No-Data-Hint-Zweig):

```python
send_email       = not config or config.send_email
send_sms         = config is not None and config.send_sms and sms_allowed(self._user_id)
send_premium_sms = config is not None and config.send_premium_sms and premium_sms_allowed(...)
send_telegram    = config is not None and config.send_telegram
```

Beide Stellen ziehen in eine gemeinsame Hilfsfunktion, die die Einschränkung dort anwendet,
**wo die Flags entstehen**, nicht wo sie verbraucht werden:

```python
def _resolve_channel_flags(
    self,
    config: TripReportConfig | None,
    user_id: str,
    *,
    restrict_to_channel: str | None = None,
) -> tuple[bool, bool, bool, bool]:
    """Liefert (send_email, send_sms, send_premium_sms, send_telegram).

    `restrict_to_channel` überschreibt für den genannten Kanal die
    Trip-Konfiguration (send_X = True) und setzt alle anderen Kanäle auf
    False — es wird nicht zusätzlich UND-verknüpft. Tier-Gates
    (sms_allowed/premium_sms_allowed) werden dabei NICHT übersprungen:
    überschrieben wird die Trip-Einstellung, nicht die Berechtigung.
    `None` ist das neutrale Element und liefert exakt die alte Formel.
    """
    if restrict_to_channel is not None:
        return (
            restrict_to_channel == "email",
            restrict_to_channel == "sms" and sms_allowed(user_id),
            restrict_to_channel == "premium_sms" and premium_sms_allowed(user_id),
            restrict_to_channel == "telegram",
        )

    send_email = not config or config.send_email
    send_sms = config is not None and config.send_sms and sms_allowed(user_id)
    send_premium_sms = (
        config is not None and config.send_premium_sms and premium_sms_allowed(user_id)
    )
    send_telegram = config is not None and config.send_telegram
    return send_email, send_sms, send_premium_sms, send_telegram
```

`NotificationService` bleibt **unverändert** — es kennt „Kanaltreue" nicht, es bekommt bereits
korrekt aufgelöste Flags. `TripReportRequest` bekommt kein neues Feld.

### Transportweg: additive, keyword-only Parameter mit Default `None`

```
trip_command_processor.py
  :627   _handle_query(trip, actual_query_key, msg.received_at, msg.user_id, channel=msg.channel)
  :736   _handle_query(self, trip, query_key, received_at, user_id, *, channel=None)
  :826   _trigger_on_demand(self, trip, report_type, label, user_id, *, channel=None)
         → TripReportSchedulerService(user_id=user_id).send_on_demand_report(
               trip, report_type, restrict_to_channel=channel)
trip_report_scheduler.py
  :1095  send_on_demand_report(self, trip, report_type, *, restrict_to_channel=None) -> OnDemandErgebnis
  :1166  _send_trip_report_outcome(..., restrict_to_channel=None) -> str
  :1687  _build_trip_report_request(..., restrict_to_channel=None)   ← Definition
         (Aufrufstelle ist :1484)
         → _resolve_channel_flags(config, self._user_id, restrict_to_channel=restrict_to_channel)
  :1361-1385  No-Data-Hint-Zweig — liegt IN _send_trip_report_outcome selbst, nicht im
         Request-Bau. Er speist vier Keyword-Argumente an send_no_data_hint(...) und muss
         seine Flags aus DEMSELBEN _resolve_channel_flags-Aufruf beziehen. Wer nur den
         Request-Bau umstellt, baut exakt Mutation 1.
```

`None` ist an jeder Stelle das neutrale Element: exakt die alte Formel, keine Einschränkung.
Ein Default auf einen Kanalnamen scheidet aus — er würde für jeden Aufrufer, der nichts angibt,
still eine Einschränkung erzeugen. Der Parameter bleibt **optional**: `send_on_demand_report`
hat einen produktiven Aufrufer und neun bestehende Testaufrufe
(`test_timeline_folgt_der_ortszeit.py`, `test_send_idempotenz_lock.py`,
`test_issue_1087_trip_official_alerts.py`, `test_briefing_slot_idempotenz.py`,
`test_official_alert_time_window.py`), die keine Kanalangabe machen und keine Einschränkung
erhalten dürfen.

## Expected Behavior

- **Input:** `InboundMessage(channel="email"|"telegram", …)` mit Anfragewort `heute`/`morgen`,
  verarbeitet von `TripCommandProcessor.process`.
- **Output:** Der ausgelöste Briefing-Versand erreicht **ausschliesslich** den anfragenden
  Kanal — unabhängig davon, welche Kanäle der Trip sonst aktiviert hat. Ist der anfragende
  Kanal im Trip deaktiviert, wird er für diese eine Antwort dennoch bedient (Override), sofern
  ein etwaiges Tier-Gate ihn erlaubt.
- **Side effects:** `briefing_log.channels` enthält bei angeforderten Briefings künftig nur
  noch den anfragenden Kanal statt aller im Trip aktivierten Kanäle. Planmässige
  Slot-Briefings, Test-Versand und das `report`-Kommando bleiben unverändert
  mehrkanalig, weil sie `restrict_to_channel` nicht setzen.

## Acceptance Criteria

- **AC-1:** Given ein Trip hat alle vier Kanäle aktiviert (E-Mail, SMS, Premium-SMS,
  Telegram) / When ein Nutzer per E-Mail `heute` sendet / Then wird das Briefing
  ausschliesslich per E-Mail versendet und `briefing_log.channels == ["email"]`.
  - Test: `TripCommandProcessor.process(InboundMessage(channel="email", text="heute", …))`
    auslösen, tatsächlichen Versand über `briefing_log.channels` bzw.
    `result.sent_channels` prüfen — kein direkter Aufruf von `send_on_demand_report`.

- **AC-2:** Given derselbe Trip mit allen vier aktivierten Kanälen / When derselbe Nutzer
  per Telegram `morgen` sendet / Then wird das Briefing ausschliesslich per Telegram
  versendet und `briefing_log.channels == ["telegram"]`.
  - Test: `TripCommandProcessor.process(InboundMessage(channel="telegram", text="morgen", …))`
    auslösen, Versand über `briefing_log.channels` prüfen.

- **AC-3:** Given ein planmässiger Slot-Auslöser (kein Anfrageweg), ein Test-Versand oder das
  `report`-Kommando / When einer dieser drei Pfade ein Briefing auslöst / Then werden weiterhin
  **alle** im Trip aktivierten Kanäle bedient, unverändert zum Stand vor dieser Änderung.
  - Test: je ein Bestandsaufruf ohne `restrict_to_channel` (Slot-Auslösung,
    `send_test_report_outcome`, `report`-Kommando) — `briefing_log.channels`/`sent_channels`
    enthält weiterhin alle aktivierten Kanäle, keine Regression durch den neuen Parameter.
  - **Falle:** Das `report`-Kommando läuft über **denselben Draht mit derselben
    Herkunftskennung** (`trip_command_processor.py:675` → `_trigger_report`). Wer die
    Einschränkung an `msg.channel` in `process()` festmacht statt am `heute`/`morgen`-Zweig in
    `_handle_query` (`:759-762`), beschneidet `report` mit — der Wirkort ist der
    Anfragewort-Zweig, nicht der Nachrichteneingang.

- **AC-4:** ✅ *PO-Entscheidung am 2026-09-06 erteilt: antworten statt ablehnen.*
  Given der anfragende Kanal ist im Trip **deaktiviert** (z. B. `send_telegram = False`) /
  When der Nutzer trotzdem über diesen Kanal `heute`/`morgen` anfragt / Then wird
  **geantwortet**, und zwar genau über diesen einen Kanal (Trip-Konfiguration wird für diesen
  Kanal überschrieben) — statt heute stiller Umleitung auf die anderen aktiven Kanäle mit
  Erfolgsmeldung. Begründung: Die Empfangslage unterwegs ist unvorhersehbar; wer über einen
  Draht schreibt, hat ihn damit als den gerade verfügbaren ausgewiesen. Eine Ablehnung wäre
  schlechter als die heutige stille Umleitung, weil der Wanderer dann gar nichts bekäme.
  - Test: Trip-Fixture mit `send_telegram = False`, Anfrage per Telegram → Versand geht
    dennoch per Telegram hinaus, `briefing_log.channels == ["telegram"]`.

- **AC-5:** Given ein Nutzer ohne SMS-Tier-Berechtigung (`sms_allowed(user_id) == False`) /
  When er über einen SMS-artigen Kanal anfragen würde bzw. `restrict_to_channel="sms"`
  aufgelöst wird / Then bleibt `send_sms` auch im Override-Fall `False` — das Override
  überschreibt nur die Trip-Einstellung, nicht die Tier-Berechtigung.
  - Test: zwei **echte** Nutzerprofile auf der Platte — eines ohne SMS-Tier, eines mit —,
    beide durch `_resolve_channel_flags(config, user_id, restrict_to_channel="sms")`. Ohne
    Tier `send_sms == False`, mit Tier `send_sms == True`. Kein Stub von `sms_allowed`: die
    fail-closed-Auflösung aus `user.json` ist Teil der Zusicherung. (Direkter Aufruf der
    Auflösungsfunktion ist hier zulässig und notwendig, weil SMS heute kein Eingangsweg ist
    und der Fall den Draht gar nicht erreichen kann — siehe Known Limitations.)

- **AC-6:** Given ein Briefing-Lauf, bei dem sämtliche Wetterdaten ausfallen (Hinweistext statt
  Briefing) und für den eine Kanaleinschränkung gesetzt ist / When der No-Data-Hint-Zweig
  (`trip_report_scheduler.py:1361-1385`) den Hinweistext versendet / Then bezieht er seine vier
  Kanal-Flags aus **derselben** `_resolve_channel_flags`-Auflösung wie der Haupt-Request und
  geht ausschliesslich an den eingeschränkten Kanal.
  - Test: Lauf mit vollständigem Wetterausfall und gesetztem `restrict_to_channel` auslösen;
    Hinweistext-Versand geht nur an diesen Kanal (fängt Mutation 1 — den halben Fix, der nur
    den Request-Bau anpasst und `:1361-1385` vergisst). Partner-Positivkontrolle ohne
    Einschränkung belegt, dass der Zweig überhaupt erreicht wird und sonst mehrkanalig ist.
  - **Faktenkorrektur zur ursprünglichen Fassung (2026-09-06, aus der RED-Phase):** Die erste
    Fassung dieses AC beschrieb einen *On-Demand-Abruf* mit Wetterausfall. Diesen Fall gibt es
    nicht: Der Zweig läuft nur unter `if not on_demand:` (`:1363`), und
    `send_on_demand_report` setzt immer `on_demand=True` (`:1132-1133`). Beim Ad-hoc-Ausfall
    antwortet stattdessen der Prozessor selbst über `_on_demand_failure_body`
    (`trip_command_processor.py:453-484`, gerufen `:846-855`) — dieser Weg ist von Haus aus
    kanaltreu. Die Zusicherung bleibt inhaltlich dieselbe (der Ausfallhinweis darf nicht am
    eingeschränkten Kanal vorbeigehen), nur der Auslöser ist korrekt benannt.

- **AC-6b:** Wächter gegen die falsche Reparatur. Given ein Ad-hoc-Abruf mit vollständigem
  Wetterausfall / When er verarbeitet wird / Then bleibt es bei **genau einer** Ausfallmeldung —
  der synchronen Antwort des Prozessors. Der No-Data-Hint-Zweig darf **nicht** für On-Demand
  geöffnet werden; wer das tut, erzeugt eine doppelte Ausfallmeldung.
  - Test: Ad-hoc-Abruf mit Totalausfall auslösen, Zahl der abgesetzten Ausfallmeldungen prüfen.

- **AC-7:** Given ein per E-Mail erkannter Nutzer (Profiltreffer über die Absenderadresse) /
  When er `heute` anfragt / Then trägt die versendete Antwort als `To:` genau die
  Absenderadresse dieses Nutzerprofils; analog trägt eine Telegram-Antwort die `chat_id`
  desselben Profils (Regressionstest — die Auflösung selbst ist bereits korrekt und wird durch
  diese Spec nicht verändert).
  - Test: Anfrage mit bekanntem Absender/`chat_id` durchlaufen lassen, tatsächlichen
    Empfänger im Versand (`To:`-Header bzw. `chat_id` im Telegram-Payload) prüfen — kein
    Dateiinhalt-Check, sondern Prüfung am tatsächlich gesendeten Objekt.

- **AC-8:** Mandantentrennung. Given zwei verschiedene Nutzer mit je eigenem Trip, eigener
  E-Mail-Adresse und eigener `chat_id` / When beide unabhängig voneinander per E-Mail bzw.
  Telegram anfragen / Then erhält jeder Nutzer seine Antwort auf seinem eigenen Weg an seine
  eigene Adresse — keine Kreuzung zwischen den beiden Nutzern.
  - Test: beide Anfragen in einem Testlauf gegen `TripReportSchedulerService(user_id=…)` mit
    unterschiedlichen `user_id`, Prüfung, dass Nutzer A nichts an die Adresse von Nutzer B
    sendet und umgekehrt.

## Mutations-Gegenprobe

- **Mutation 1 — halber Fix am Duplikat:** `restrict_to_channel` nur in
  `_build_trip_report_request`/Haupt-Request-Formel (`:1743-1752`) anwenden, den
  No-Data-Hint-Zweig (`:1371-1379`) unverändert auf der alten Formel belassen. **Muss AC-6**
  rot werden lassen — ein Test, der nur den Erfolgspfad (AC-1/AC-2) prüft, bleibt fälschlich
  grün.
- **Mutation 2 — Bypass-Richtung verdreht:** Das Override in `_resolve_channel_flags` von
  `restrict_to_channel == "telegram"` zurück zu einem UND mit `config.send_telegram` drehen
  (`restrict_to_channel == "telegram" and config.send_telegram`). **Muss AC-4** rot werden
  lassen — Standard-Fixtures mit allen Kanälen aktiv (AC-1/AC-2) fangen das nicht, nur eine
  Fixture mit explizit deaktiviertem Anfragekanal tut es.

## Known Limitations

- **SMS und Premium-SMS als Eingangsweg sind heute nicht möglich.** Regulär-SMS ist kein
  Befehlskanal (`InboundMessage(channel="sms", …)` kommt nirgends vor), Premium-SMS ist nur
  Adress-Lerner und verwirft den Nachrichtentext (`inbound_sms_reader.py:162-171`). Diese Spec
  formuliert dafür bewusst **keine** unerfüllbare Zusicherung — `_resolve_channel_flags` ist so
  gebaut, dass sie für alle vier Kanalnamen korrekt auflöst, sobald sie eintreffen können.
  Premium-SMS als Eingangsweg ist Scheibe **S4** von Epic #2133 und baut ausdrücklich auf
  dieser Scheibe auf.

  🔴 **Nachtrag (#2184, S4 Epic #2133, 2026-09-08): Überholt für Premium-SMS.** Seit #2184
  verarbeitet `InboundSmsReader` den vor dem Garmin-Kennzeichen `inreachlink.com` stehenden
  Text als Befehl und ruft `TripCommandProcessor` auf — Premium-SMS ist damit der dritte
  Erzeuger von `InboundMessage` (`channel="premium_sms"`), diese Scheibe trägt wie oben
  vorausgesagt. Regulär-SMS bleibt weiterhin **kein** Befehlskanal. Details:
  `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md`,
  `docs/specs/modules/inbound_command_channels.md`.
- **Unbekannter Absender (`user_id == "default"`) — durch #2168 erledigt.** Die frühere Fassung
  dieses Punkts behauptete, der Registrierungshinweis gehe auf **drei** Pfaden an das
  Default-/Betreiberprofil. Nachgemessen hielt davon nur einer stand:
  - Telegram-Text-Nachricht (`inbound_telegram_reader.py:181-196`) — **war** betroffen,
    seit #2168 behoben: der Hinweis geht an die anfragende `chat_id`.
  - Telegram-Callback-Query (`:305-317`) — **war nie betroffen**: `edit_telegram_message_text`
    bekommt `chat_id=chat_id` explizit übergeben; `settings` liefert dort nur das Bot-Token.
  - E-Mail (`inbound_email_reader.py:106`) — **war nie betroffen**: `_authorize` verwirft einen
    unbekannten Absender **vor** jeder Antwortstelle, es geht überhaupt keine Antwort raus.
  Der Pfad erreicht `_handle_query`/`send_on_demand_report` weiterhin nie und ist damit von
  dieser Spec strukturell nicht erfasst; ein eigenes Issue ist dafür nicht mehr offen.
- **Adress-ACs (AC-7/AC-8) sind für Test-Nutzer und Staging strukturell blind.**
  `Settings.with_user_profile` setzt `force_test` bei einer Test-User-ID oder `env == "staging"`
  (`src/app/config.py:369`) und verwirft dann die Profil-`telegram_chat_id` (`:387`). Testkennungen
  für AC-7/AC-8 dürfen daher **nicht** auf ein Test-Präfix normalisiert werden — sonst prüfen
  beide ACs nichts mehr. Auf Staging ist die Adress-Zusicherung aus demselben Grund nicht
  messbar; sie gehört in die Kern-Schicht.

- **`briefing_log.channels` enthält bei angeforderten Briefings künftig weniger Kanäle als
  bisher.** Das ist die gewollte Wirkung dieser Spec, wirkt sich aber auf die von Go gelesene
  Cockpit-Kachel „Was geht heute raus" (#393) aus — bei angeforderten Briefings zeigt sie
  künftig nur noch den tatsächlich bedienten Kanal, nicht mehr alle Trip-Kanäle.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec folgt einem bereits dokumentierten Grundsatz
  (`inbound_command_channels.md:90`, „Antwort auf gleichem Kanal") und einem bestehenden Muster
  im Code (Herkunftskennung wird bereits an anderen Stellen durchgereicht, `:585`/`:607`). Sie
  eröffnet keine neue Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth) und lässt
  ADR-0049 (Premium-SMS als vierter Kanal) unberührt — kein neues ADR nötig.
  `_resolve_channel_flags` erfüllt dabei ausdrücklich die **Folgepflicht aus ADR-0049**
  (`docs/adr/0049-premium-sms-vierter-kanal.md:115-117`: „Wer eine neue Stelle baut, die ein
  Kanal-Set auflöst, muss `premium_sms` mitführen oder begründen, warum nicht"): Premium-SMS ist
  als viertes Tupel-Element geführt, mit eigenem Tier-Gate `premium_sms_allowed()` statt
  `sms_allowed()` — im Override- wie im Normalfall (AC-5).

## Changelog

- 2026-09-08 (Docs-Nachtrag, kein Code geändert): Known-Limitations-Punkt „SMS und Premium-SMS
  als Eingangsweg sind heute nicht möglich" um Nachtrag zu #2184 (Epic #2133 S4) ergänzt —
  Premium-SMS ist seither der dritte `InboundMessage`-Erzeuger. Ursprüngliche Aussage bleibt
  stehen (historisch korrekt zum Zeitpunkt dieser Spec), nur als überholt markiert.
- 2026-09-06: Initial spec created
- 2026-09-06: AC-5 auf echte Nutzerprofile statt gestubbtem `sms_allowed` umgestellt
- 2026-09-06: PO-Freigabe erteilt (AC-4 bestätigt: antworten statt ablehnen)
- 2026-09-06 (RED-Phase, Faktenkorrekturen ohne Zieländerung): AC-6 auf den tatsächlich
  existierenden Auslöser umformuliert (der No-Data-Hint-Zweig ist für On-Demand strukturell
  unerreichbar) und um AC-6b als Wächter gegen die doppelte Ausfallmeldung ergänzt;
  `ReportChannelConfig` → `TripReportConfig`; Definitionszeile von `_build_trip_report_request`
  auf `:1687` korrigiert; AC-3 um die `report`-Falle ergänzt; `force_test`-Grenze der Adress-ACs
  als Known Limitation aufgenommen; LoC-Schätzung auf den gemessenen Wert gezogen.
