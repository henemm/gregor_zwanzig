# Context: feat-2126-kanaltreue-adhoc-antwort

**Issue:** #2126 — Ad-hoc-Anfrage soll nur auf dem Eingangsweg beantwortet werden
**Epic:** #2133 „Ad-hoc-Abruf so reich wie das Briefing", Scheibe **S3**
**Erstellt:** 2026-09-06 · **Track:** Full Process
**Basis:** `origin/main` @ `366ec4de` (enthält den #2134-Katalog-Umbau an `_trigger_on_demand`)

## Request Summary

Eine Ad-hoc-Anfrage (`heute` / `morgen`) soll auf dem Weg beantwortet werden, über den sie
gestellt wurde — und nur dort. Zweiter, vom PO nachgereichter Teil: sie soll auch **an den
tatsächlichen Absender** gehen, nicht an eine fest hinterlegte Adresse. Kanaltreue heißt
zweierlei: richtiger **Weg** und richtige **Adresse**.

## Ist-Stand — was die Bestandserhebung ergeben hat

### A) Der Weg: die Herkunftskennung existiert bereits und bricht an EINER Stelle ab

`InboundMessage.channel` (`src/services/trip_command_processor.py:61`) trägt den Eingangsweg und
wird von beiden Readern korrekt gesetzt. Im Prozessor ist sie sogar in aktivem Gebrauch — die
Drilldown-Zweige reichen `msg.channel` durch (`:585`, `:607`) und steuern damit die
Emoji-Darstellung (`with_emoji = channel == "telegram"`, `:883`, `:982`, `:1008`).

**Der Abbruch ist eine einzige Zeile:** `:627` ruft `_handle_query(trip, actual_query_key,
msg.received_at, msg.user_id)` — ohne `msg.channel`, im Unterschied zu den unmittelbaren
Nachbarzeilen. Von dort fehlt die Information die gesamte Kette hinunter:

```
trip_command_processor.py:627   _handle_query(...)                     ← channel fällt hier weg
  :736  _handle_query(self, trip, query_key, received_at, user_id)
  :759-762  Zweige heute/morgen
  :826  _trigger_on_demand(self, trip, report_type, label, user_id)    ← kein channel
  :845  TripReportSchedulerService(user_id=...).send_on_demand_report(trip, report_type)
trip_report_scheduler.py
  :1095 send_on_demand_report(self, trip, report_type) -> OnDemandErgebnis
  :1132 _send_trip_report_outcome(..., on_demand=True, angefordert=True, target_date=zieltag)
  :1166 _send_trip_report_outcome(self, trip, report_type, allow_test_fallback=False,
                                  on_demand=False, catchup_prefix=None,
                                  angefordert=False, target_date=None) -> str
  :1484 _build_trip_report_request(...)
  :1743-1752  ← HIER fallen die vier Kanal-Flags
notification_service.py
  :448  send_trip_report(request)   → :552-666 tatsächlicher Versand je Kanal
```

Die Kanal-Auflösung selbst (wortgleich an **zwei** Stellen: `:1743-1752` Haupt-Request,
`:1371-1379` No-Data-Hint-Zweig):

```python
send_email       = not config or config.send_email
send_sms         = config is not None and config.send_sms and sms_allowed(self._user_id)
send_premium_sms = config is not None and config.send_premium_sms and premium_sms_allowed(...)
send_telegram    = config is not None and config.send_telegram
```

### B) Es gibt nur ZWEI Eingangswege, nicht vier

| Weg | Ist er ein Befehlskanal? | Beleg |
|---|---|---|
| **E-Mail** | ✅ ja | `inbound_email_reader.py:144-154` baut `InboundMessage(channel="email", …)` → `process()` |
| **Telegram** | ✅ ja | `inbound_telegram_reader.py:229-236` (Poll + Webhook laufen durch dasselbe `_process_update`), Callback-Query-Pfad `:325-332` |
| **SMS (regulär)** | ❌ **existiert nicht** | `channel="sms"` kommt in keinem `InboundMessage(...)`-Aufruf in `src/`+`api/` vor |
| **Premium-SMS (Garmin)** | ❌ **nur Adress-Lerner** | `inbound_sms_reader.py:162-171`: erkennt den `inreachlink.com`-Marker, meldet **nur die Absendernummer** an `POST /api/internal/premium-sms-learn`; der Nachrichtentext wird verworfen, es entsteht nie ein `InboundMessage` |

Das Ticket formuliert AC-2 als „analog für SMS und Premium-SMS". Für zwei der vier genannten
Wege beschreibt das einen Fall, den es heute nicht gibt. Premium-SMS als Eingangsweg ist
**Scheibe S4** des Epics und hängt ausdrücklich von S3 ab („sonst kostet jede Satellitenfrage
vier Antworten").

### C) Alle anderen Befehle sind längst kanaltreu

`ruhetag`, `abbruch`, `pause`, `status`, `hilfe` usw. geben ihre Bestätigung über
`CommandResult.confirmation_body` zurück, die der jeweilige Reader auf seinem eigenen Draht
verschickt. Kanaltreue entsteht dort durch die Architektur (getrennte Reader, getrennter
Rückweg). Betroffen ist **ausschliesslich** der `heute`/`morgen`-Vollbriefing-Pfad, der den
regulären Versand-Fan-out benutzt.

### D) Planmässig vs. angefordert: zwei Flags, aber ohne Wirkung auf die Kanalwahl

`on_demand` und `angefordert` kommen bis zur Auflösungsstelle durch, haben aber bewusst
verschiedene Bedeutung (Docstring `trip_report_scheduler.py:1186-1214`): `on_demand` hat sieben
andere Wirkstellen, `angefordert` fliesst **nur** in `briefing_log.json`. Die Formel
`:1743-1752` fragt **keines von beiden** ab. Es gibt heute also keinen Unterschied in der
Kanalwahl zwischen Slot-Briefing und Ad-hoc-Abruf.

Durch dieselbe Kette laufen ausserdem: Test-Versand (`send_test_report_outcome`) und das
`report`-Kommando (`_trigger_report`). Alarme laufen **separat**
(`notification_service.py::send_official_alert` / `_dispatch_alert_message`, eigene
Vier-Kanal-Auflösung) und sind nicht Teil dieser Kette.

### E) Deaktivierter Kanal: heute keine stille Lücke, sondern eine stille UMLEITUNG

- **Alle vier deaktiviert** → `no_channel_configured=True` (`notification_service.py:533-540`)
  → `"no_channels"` → `_on_demand_failure_body` (`trip_command_processor.py:465-469`) liefert
  eine explizite Fehlermeldung. Sauber.
- **Nur der anfragende Draht deaktiviert** (der eigentliche #2126-Fall) → das System sendet über
  die anderen aktiven Kanäle und meldet Erfolg. Der Fragende bekommt auf seinem Draht nichts vom
  Briefing zu sehen. Das ist AC-4 des Tickets — und die heutige Antwort darauf ist nicht
  „stiller Nichtversand", sondern eine **stille Umleitung mit Erfolgsmeldung**.

### F) Die Adresse: Behauptung bestätigt, aber die Wirkung ist eine andere als gedacht

**Bestätigt:**
- `send_command_reply_email` (`notification_service.py:1795-1807`) ruft `EmailOutput.send()`
  **ohne** `to=`, obwohl der Parameter existiert (`email.py:607-617`) → Rückfall auf
  `settings.mail_to` (`email.py:647-650`).
- `send_command_reply_telegram(result, chat_id, settings)` (`:1809-1826`) benutzt `chat_id`
  **nur im Fehler-Log** (`:1825`). `TelegramOutput.send()` (`telegram.py:379-382`) hat dafür
  überhaupt keinen Parameter — der Chat kommt immer aus `self._settings.telegram_chat_id`
  (`telegram.py:403`). Dasselbe Muster in `send_telegram_message` (`:1828-1845`) und
  `edit_telegram_message_text` (`:1847-1868`).

**Wichtige Korrektur an der Ticket-Prämisse:** Die Begründung „fällt heute nicht auf, weil es
dieselbe Person ist" ist zu schwach — es ist kein Zufall, sondern Konstruktion. Beide Reader
lösen vor der Antwort `user_settings = base_settings.with_user_profile(user_id)` auf, und
`user_id` wird per `lookup_user_by_telegram_chat_id` / `lookup_user_by_email`
(`app/loader.py:1220-1264`) **exakt über den Treffer auf `telegram_chat_id` / `mail_to` im
Profil** gefunden. Für einen erkannten Nutzer ist die hinterlegte Adresse per Konstruktion
identisch mit der Absenderadresse — auch bei vielen Nutzern.

**Sichtbar wird der Defekt nur, wenn kein Profil-Treffer existiert** (`user_id == "default"`):
Der Registrierungshinweis an eine unbekannte Telegram-`chat_id`
(`inbound_telegram_reader.py:181-194`, `:305-317`) geht an den `telegram_chat_id` des
Default-/Betreiberprofils statt an den fremden Chat, der gerade geschrieben hat. Analog
„Trip nicht gefunden" per E-Mail (`inbound_email_reader.py:106`, `:121-132`).

**Empfänger-Override ist strukturell nur bei E-Mail möglich:**

| Kanal | Signatur | Empfänger-Parameter | Ohne Parameter |
|---|---|---|---|
| E-Mail | `EmailOutput.send(subject, body, html=True, plain_text_body=None, to=None, …)` (`email.py:607`) | ✅ `to` | `settings.mail_to` |
| Telegram | `TelegramOutput.send(subject, body, reply_markup=None, *, parse_mode=None, suppress_subject_line=False)` (`telegram.py:379`) | ❌ | `settings.telegram_chat_id` |
| SMS | `SevenIoChannelBase.send(subject, body)` (`seven_io_base.py:155`) | ❌ | `settings.sms_to` (`sms.py:41-42`) |
| Premium-SMS | dieselbe Signatur, `PremiumSmsOutput` | ❌ | `settings.premium_sms_reply_to` (`premium_sms.py:64-73`, inkl. 30-Tage-TTL) |

Es gibt **kein** `send_command_reply_sms` / `send_command_reply_premium_sms` — nur E-Mail und
Telegram haben Kommando-Antwortfunktionen.

Alle vier Empfängerfelder sind pro Nutzer über `Settings.with_user_profile(user_id)`
(`app/config.py:355-405`) überschreibbar; Infrastruktur (SMTP-Host, Bot-Token) bleibt global.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py` | `InboundMessage` (`:56-63`), `process` (`:545`), Abbruchzeile `:627`, `_handle_query` (`:736`), `_trigger_on_demand` (`:826`), `_on_demand_failure_body` (`:465`) |
| `src/services/trip_report_scheduler.py` | `send_on_demand_report` (`:1095`), `_send_trip_report_outcome` (`:1166`), `_build_trip_report_request` (`:1484`), Kanal-Auflösung (`:1743-1752`, `:1371-1379`), `_append_briefing_log` (`:1931`) |
| `src/services/notification_service.py` | `send_trip_report` (`:448`), Versand je Kanal (`:552-666`), `send_command_reply_email` (`:1795`), `send_command_reply_telegram` (`:1809`) |
| `src/services/inbound_email_reader.py` | `_process_single` (`:94-162`), `_authorize` (`:188-202`), Default-Fall (`:106`, `:121-132`) |
| `src/services/inbound_telegram_reader.py` | `_process_update` (`:151-284`), Callback-Pfad (`:325-332`), Unbekannt-Chat-Hinweis (`:181-194`, `:305-317`) |
| `src/services/inbound_sms_reader.py` | Premium-SMS-Adress-Lerner (`:162-171`) — belegt, dass dieser Weg kein Befehlskanal ist |
| `src/output/channels/email.py` | `send(..., to=None, …)` (`:607`), Rückfall (`:647-650`) |
| `src/output/channels/telegram.py` | `send()` ohne chat_id-Parameter (`:379-382`), Chat aus Settings (`:403`) |
| `src/output/channels/sms.py`, `premium_sms.py`, `seven_io_base.py` | `_resolve_recipient()`, kein Override |
| `src/app/config.py` | `with_user_profile` (`:355-405`), `can_send_*` (`:305`, `:407`, `:424`) |
| `src/app/loader.py` | `lookup_user_by_email` / `lookup_user_by_telegram_chat_id` (`:1220-1264`) |
| `src/services/user_tier.py` | `sms_allowed` (`:9-20`), `premium_sms_allowed` (`:23-42`), beide fail-closed |

## Existing Patterns

- **Herkunftskennung wird bereits durchgereicht** — die Drilldown-Zweige (`:585`, `:607`) sind
  das vorhandene Muster; `_handle_query` ist die Ausnahme, nicht die Regel. Die Änderung folgt
  einem Bestandsmuster, sie erfindet keines.
- **Zwei Wirkflags nebeneinander** (`on_demand`, `angefordert`) mit bewusst getrennter
  Bedeutung — das Projekt trennt Anlass-Flags schon heute, statt eines zu überladen.
- **Fail-closed bei Berechtigungen** (`user_tier.py`) — fehlende/kaputte `user.json` heisst
  „nicht erlaubt", nicht „erlaubt".
- **Empfänger pro Nutzer über `with_user_profile`**, Infrastruktur global.

## Dependencies

- **Upstream (was wir benutzen):** `InboundMessage.channel`, `Settings.with_user_profile`,
  `report_config`-Flags, `sms_allowed`/`premium_sms_allowed`.
- **Downstream (was auf uns aufbaut):** `briefing_log.channels` — geschrieben in
  `_append_briefing_log` (`:1931`) aus `result.sent_channels`, nur im Erfolgsfall
  (`:1619-1622`); Kanal-Bezeichner sind die String-Literale `"email"` (`notification_service.py:555`),
  `"sms"` (`:584`), `"premium_sms"` (`:602`), `"telegram"` (`:625`/`:662`). Gelesen von Go
  (`GET /api/cockpit/status` → Cockpit-Kachel „Was geht heute raus", #393) und von
  `briefing_slots._log_bezeugt_versand` (überspringt `angefordert=True`, AC-12).
- **Epic-Abhängigkeit:** Scheibe **S4** (Premium-SMS erreicht den Kommandoverarbeiter) baut
  ausdrücklich auf dieser Scheibe auf.

## Existing Specs

| Spec | Inhalt |
|---|---|
| `docs/specs/modules/inbound_command_channels.md:90` | Design-Prinzip „Antwort auf gleichem Kanal" — auf **Kanal**-Ebene, ohne Aussage zur Adresse |
| `docs/specs/modules/trip_command_processor.md:65` | Prozessor „ist für den Antwort-Kanal verantwortlich" (Kanalwahl, nicht Adresswahl) |
| `docs/specs/modules/telegram_webhook_inbound.md:85,116` | „Antwort an Nutzer via bestehender TelegramOutput-Pfad" |
| `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md:254-257` | Grenzt Kanaltreue ausdrücklich als S3/#2126 ab |

Keine Spec formuliert bisher „die Antwort geht an dieselbe Adresse, von der die Anfrage kam" als
geprüfte Zusicherung. `docs/adr/` enthält nichts zu Antwortadressen (ADR-0049 führt Premium-SMS
als vierten Kanal ein, ohne Bezug hierzu).

## Test-Ist-Stand: nichts bewacht die Zusicherung

- **Kein** Test prüft, dass eine `heute`/`morgen`-Anfrage nur auf dem anfragenden Kanal
  beantwortet wird. Konsistent damit, dass die Information den Versand nie erreicht — es gibt
  heute nichts zu bewachen.
- **Kein** Kern-Test prüft den tatsächlichen Empfänger einer Kommando-Antwort (kein `To:`-Header,
  keine `chat_id` im Telegram-Payload, keine SMS-Zielnummer).
- `tests/tdd/test_issue_1009_1019_inbound_robustness.py:458-487` (live, `GZ_TELEGRAM_LIVE=1`)
  prüft nur, dass `"/start"` **im Text** vorkommt — er würde den Adress-Defekt nicht fangen,
  weil im Live-Aufbau `settings.telegram_chat_id` zufällig mit der Test-Chat-ID übereinstimmt.
- Nachbartests ohne Kanalprüfung: `test_send_idempotenz_lock.py`,
  `test_briefing_slot_idempotenz.py`, `test_adhoc_abruf_am_telegram_draht.py` (Kommando-Erkennung),
  `test_issue_1069_tier_channel_gating.py` (Tier-Gating, unabhängig vom Anfrageweg).

### Wächter, der bei Signaturänderungen zu beachten ist

`tests/test_success_status_guard.py` führt eine Registry mit Schlüsseln
`"<datei>::<funktion>::<index>"` — **namensbasiert über einen AST-Scanner, nicht
zeilennummernbasiert**. Relevant: `"…trip_command_processor.py::_trigger_on_demand": 1`
(`:1866`) und `"…::_handle_query": 4` (`:1882`). Ein zusätzlicher `channel`-Parameter bricht den
Wächter **nicht**. Er bricht, wenn (a) `_trigger_on_demand` umbenannt oder aufgespalten wird
oder (b) `success` künftig tatsächlich vom `outcome` abhängt — dann ist die Registry bewusst zu
pflegen (Kopfkommentar `:1966f`: „Erwartung wird zur Behebung NICHT gekürzt").

## Risks & Considerations

1. **Geteilte Auflösungsstelle — AC-3 ist das eigentliche Risiko.** Wer bei `:1743-1752`
   filtert, ohne den Anlass sauber zu unterscheiden, beschneidet auch planmässige Briefings,
   Test-Versand und das `report`-Kommando. Das Duplikat bei `:1371-1379` darf dabei nicht
   vergessen werden.
2. **Zwei wortgleiche Vorkommen der Formel** — eine Änderung an nur einer Stelle erzeugt genau
   die Art von halbem Fix, die grün aussieht.
3. **AC-2 ist für die Hälfte der genannten Wege heute unerfüllbar** (kein SMS-Befehlskanal,
   Premium-SMS verwirft den Text). Die Spec muss das ausdrücklich abgrenzen, statt eine
   unerfüllbare Zusicherung zu formulieren.
4. **AC-4 braucht eine Produktentscheidung**, keine technische: Fragt jemand über einen Draht,
   der im Trip deaktiviert ist — antworten oder ablehnen? Heute wird still umgeleitet und Erfolg
   gemeldet.
5. **Adress-Teil: Telegram/SMS/Premium-SMS haben keinen Empfänger-Parameter.** Der Empfänger
   steckt im `Settings`-Objekt. Eine Adress-Zusicherung ist entweder über
   `with_user_profile`-Auflösung zu bewachen (was heute schon korrekt ist) oder erfordert einen
   Eingriff in die Kanal-Signaturen. Das ist eine echte Zuschnitt-Entscheidung für die Analyse.
6. **Mutations-Gegenprobe muss an der WIRKSTELLE ansetzen.** Ein Test, der nur prüft, dass
   `channel` im `InboundMessage` steht (wie `test_inbound_telegram_reader.py:217`), bewacht
   nichts — die Zusicherung wirkt erst an der Kanal-Auflösung bzw. an
   `briefing_log.channels` / `result.sent_channels`.
7. **Nebenbefund aus #2124 nicht vorschnell zuordnen.** Am 30.08. buchte ein On-Demand-Versand
   um 19:33:23 UTC nur `["email"]`, ein zweiter um 19:34:57 alle vier. Das fiel in das Zeitfenster
   des nginx-60-Sekunden-Abbruchs (#2124) und könnte der GUI-„senden"-Pfad gewesen sein, nicht
   der Ad-hoc-Abruf. Vor jeder Erklärung ist zu messen, welcher Pfad diese Einträge erzeugte —
   sonst wird eine Kanaleinschränkung auf eine bereits anderweitig erklärte Ursache gebaut.
8. **Mandantentrennung:** `send_on_demand_report` läuft über
   `TripReportSchedulerService(user_id=user_id)`; jeder neue datenbewegende Pfad ist mit **zwei
   verschiedenen Nutzern** zu testen.
9. **Referenzfeger nach Signaturänderung** (Hinweis der Parallelsitzung): nach jeder
   Signaturänderung `grep -rln "<funktionsname>" tests/ src/` — Signatur-Wächter liegen
   regelmässig in fremden Testdateien. Werden zusätzliche Abrufe eingebaut statt nur die Signatur
   erweitert, schlägt dieser Feger nicht an; dann nach dem Naht-Namen fegen.

## Offene Fragen für die Analyse-Phase

- **Zuschnitt Weg vs. Adresse:** Beide Teile in eine Scheibe, oder Adresse getrennt? Der
  Adressteil ist heute für erkannte Nutzer *funktional korrekt* und nur *unbewacht* — der Weg-Teil
  ist funktional falsch.
- **AC-4-Verhalten** (antworten vs. ablehnen bei deaktiviertem Anfrage-Draht).
- **Unbekannter Absender** (`user_id == "default"`): Antwort an den Fragenden ist heute nicht
  möglich und geht an den Betreiber. Reparieren oder ausdrücklich ausgrenzen?
- **Wo greift die Einschränkung?** Am Request-Aufbau (`_build_trip_report_request`) oder als
  eigener Parameter durch die Kette — und wie bleibt die Wirkung für Slot-Briefings garantiert
  unverändert.

*(Alle vier Fragen sind im Abschnitt `## Analysis` beantwortet.)*

---

## Analysis

### Type

**Feature.** Kein Bugfix: Das heutige Verhalten war nie anders spezifiziert. Die Spec
`inbound_command_channels.md:90-91` formuliert das Prinzip „Antwort auf gleichem Kanal" zwar
bereits — aber ausdrücklich für `CommandResult.confirmation_body`, den kurzen Bestätigungstext,
den der Reader selbst verschickt. Der `heute`/`morgen`-Pfad entzieht sich dem, weil er nicht über
`confirmation_body` antwortet, sondern den regulären Briefing-Versand auslöst. **#2126 erfindet
keine neue Regel, sondern zieht den einen Pfad nach, der sich der bereits dokumentierten Regel
entzieht.**

### Technical Approach (Entscheidung)

**Wirkort und Transportweg sind zu trennen.**

1. **Wirkort — eine neue Hilfsfunktion, die das bestehende Duplikat beseitigt.** Die vier
   Kanal-Flags werden heute an zwei wortgleichen Stellen berechnet (`trip_report_scheduler.py:1743-1752`
   Hauptpfad, `:1371-1379` No-Data-Hint-Zweig). Beide ziehen in
   `_resolve_channel_flags(config, user_id, restrict_to_channel=None)`. Die Einschränkung greift
   dort, **wo die Flags entstehen**, nicht wo sie verbraucht werden. `NotificationService` bleibt
   unverändert — es kennt „Kanaltreue" nicht, es bekommt bereits korrekte Flags.
2. **Transportweg — rein additive, keyword-only Parameter mit Default `None`.**
   `_handle_query` → `_trigger_on_demand` → `send_on_demand_report` → `_send_trip_report_outcome`
   → `_build_trip_report_request`. `None` ist das neutrale Element: exakt die alte Formel.
   **Ein Default auf einen Kanalnamen scheidet aus** — er würde für jeden Aufrufer, der nichts
   angibt, still eine Einschränkung erzeugen, also genau den Fehler bauen, den wir beheben.
3. **Der Parameter bleibt optional, er wird NICHT zur Pflicht.** `send_on_demand_report` hat einen
   produktiven Aufrufer und **neun** in Tests (`test_timeline_folgt_der_ortszeit.py:821`,
   `test_send_idempotenz_lock.py:410,415,458`, `test_issue_1087_trip_official_alerts.py:236`,
   `test_briefing_slot_idempotenz.py:970,991,1112`, `test_official_alert_time_window.py:347`).
   Ein Pflichtparameter zwänge neun Testdateien, die Idempotenz-Sperren, Alarm-Zeitfenster und
   Zeitachse prüfen, zu einer Kanalangabe, die dort nichts bedeutet — Lärm statt Explizitheit.

**AC-4-Bypass: die Richtung ist der kritische Punkt.** Für den anfragenden Kanal muss die
Einschränkung die **Trip-Konfiguration überschreiben** (`send_X = True`, wenn `X` der anfragende
Kanal ist), nicht zusätzlich UND-verknüpfen. Andernfalls kippt AC-4 von „stille Umleitung" auf
„stilles Nichts" — schlechter als heute. Die Tier-Gates (`sms_allowed`, `premium_sms_allowed`)
werden dabei **nicht** übersprungen: überschrieben wird die Trip-Einstellung, nicht die
Berechtigung. In dieser Scheibe ist das ohnehin gegenstandslos, weil nur E-Mail und Telegram
`_handle_query` erreichen können.

### Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `msg.channel` bei `:627` mitgeben; `_handle_query` (`:736`) und `_trigger_on_demand` (`:826`) nehmen den Kanal entgegen und reichen ihn an `send_on_demand_report` |
| `src/services/trip_report_scheduler.py` | MODIFY | neue `_resolve_channel_flags(...)`; beide Formelstellen (`:1743-1752`, `:1371-1379`) darauf umstellen; keyword-only Parameter durch `send_on_demand_report` (`:1095`), `_send_trip_report_outcome` (`:1166`), `_build_trip_report_request` (`:1687`) |
| `src/services/notification_service.py` | — | **keine Änderung**; `TripReportRequest` (`:60-124`) bekommt kein neues Feld |
| `tests/tdd/test_adhoc_antwort_kanaltreue.py` | CREATE | neue Testdatei, nach Verhalten benannt |
| `docs/specs/modules/inbound_command_channels.md` | MODIFY | Prinzip „Antwort auf gleichem Kanal" auf den angeforderten Briefing-Pfad ausweiten |
| `docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md` | CREATE | Spec dieser Scheibe |

Nicht betroffen (belegt): Go (`internal/store/log.go:24`, `cockpit.go:21`, `briefing_history.go:25`
lesen `briefing_log` nur), Frontend, Alarme (`_effective_alert_channels`,
`trip_alert.py:2871-2925`, eigene Auflösung ohne `TripReportRequest`),
`test_issue_1069_tier_channel_gating.py` (liest die vier bestehenden Flags, setzt den neuen
Parameter nicht).

### Scope Assessment

- **Dateien:** 4 Code/Test + 2 Doku
- **Geschätzte LoC:** Produktivcode +55 bis +85, Tests +120 bis +180 → **~180-265**
- **LoC-Limit:** 250. Wird voraussichtlich gerissen → `workflow.py set-field loc_limit_override 500`
  setzen, sobald `status` es zeigt, statt am Ende Tests zu kürzen.
- **Risk Level: MEDIUM.** Additive Signaturen, ein einziger Wirkort, Alarme und Go unberührt —
  aber vier Versandpfade teilen sich diesen Wirkort, und der Fehler wäre unsichtbar (zu wenige
  Kanäle beim planmässigen Briefing merkt niemand sofort).

### Dependencies

- **Aufwärts:** `InboundMessage.channel`, `report_config`, `sms_allowed`/`premium_sms_allowed`,
  `Settings.with_user_profile`.
- **Abwärts:** `briefing_log.channels` (Go liest es für die Cockpit-Kachel „Was geht heute raus")
  — nach der Änderung stehen bei **angeforderten** Briefings weniger Kanäle drin. Das ist die
  gewollte Wirkung und zugleich der beste Messpunkt für einen Test ohne Stellvertreter.
- **Epic:** Scheibe **S4** (Premium-SMS erreicht den Kommandoverarbeiter) baut hierauf auf.

### Zuschnitt-Entscheidung: Weg und Adresse trennen

Teil B des Tickets zerfällt in zwei verschiedene Fälle, die nicht denselben Pfad betreffen:

| Fall | Stand | Zuordnung |
|---|---|---|
| **Erkannter Nutzer** | funktional korrekt (`with_user_profile` setzt `mail_to`/`telegram_chat_id` aus genau dem Profil, das über die Absenderadresse gefunden wurde), aber **unbewacht** | **in dieser Scheibe** — als reiner Regressionstest, kein Produktivcode, kein Risiko |
| **Unbekannter Absender** (`user_id == "default"`) | **kaputt**: Registrierungshinweis geht an die Betreiber-Adresse statt an den Fragenden | **eigenes Issue** — anderer Pfad (`inbound_telegram_reader.py:181-194`, `:305-317`; `inbound_email_reader.py:106`, `:121-132`), erreicht den Report-Versand nie |

Nebenbefund-Triage: Der zweite Fall ist nutzersichtbares Fehlverhalten (Kriterium a) und
verdient nach Projektregel ein eigenes Issue statt einer Sammel-Zeile.

### Zwei Mutationen, an denen sich die Gegenprobe messen muss

1. **Halber Fix am Duplikat.** Einschränkung nur an `:1743-1752` anwenden, den
   `send_no_data_hint`-Zweig `:1371-1379` vergessen. Fängt **nur** ein Test, der einen
   On-Demand-Abruf mit vollständigem Wetterausfall **und** gesetztem Kanal auslöst. Ein Test, der
   nur den Erfolgspfad abdeckt, bleibt grün.
2. **Bypass-Richtung verdreht.** Das Override (`send_telegram = True`, wenn der Anfrageweg
   Telegram ist) zurück zu einem UND mit `config.send_telegram` drehen. Fängt **nur** ein Test,
   dessen Trip-Fixture den anfragenden Kanal **explizit deaktiviert** hat. Standard-Fixtures mit
   allen Kanälen aktiv fangen das nicht.

Beide zwingen die RED-Phase zu mindestens zwei Fällen jenseits des Happy Path.

### Weitere Risiken

- **Nachweis am Draht, nicht am Literal.** Ein Test, der `send_on_demand_report(channel="telegram")`
  direkt aufruft, bewacht die Verdrahtung **nicht** — die Bildungsstelle ist `msg.channel` im
  `InboundMessage`. Der Nachweis muss bei `TripCommandProcessor.process(InboundMessage(channel=…))`
  beginnen und am tatsächlichen Versand bzw. an `briefing_log.channels` enden.
- **Referenzfeger nach der Signaturänderung** ist Pflicht: `grep -rln` über `tests/` und `src/`.
  Rund 24 fremde Testdateien rufen `_send_trip_report_outcome`/`_build_trip_report_request`
  direkt auf, mehrere als **Unterklasse, die die Methode überschreibt**. Die Einschätzung, dass
  keyword-only + Default `None` sie alle unberührt lässt, ist aus Zweck-Lektüre abgeleitet und
  **nicht gemessen** — in `/40-tdd-red` ist ein vollständiger Lauf über diese Dateien zu fahren.
- **Zwei Nutzer testen** (Mandantentrennung): `send_on_demand_report` läuft über
  `TripReportSchedulerService(user_id=…)`.
- **Nebenbefund #2124 nicht vorschnell zuordnen** (siehe Risiko 7 oben) — der `["email"]`-Eintrag
  vom 30.08. fiel in das nginx-Abbruchfenster und war womöglich der GUI-„senden"-Pfad.

### Open Questions

- [ ] **AC-4 — Produktentscheidung für den PO:** Fragt jemand über einen Kanal, der im Trip
      deaktiviert ist — antworten oder ablehnen? Empfehlung: **antworten** (Konfiguration wird für
      den Anfrageweg überschrieben). Begründung: Die Empfangslage ist unterwegs unvorhersehbar;
      wer über einen Draht schreibt, hat ihn damit als den gerade verfügbaren ausgewiesen. Eine
      Ablehnung wäre schlechter als die heutige stille Umleitung, weil der Wanderer dann gar
      nichts bekommt. Geht als AC in die Spec.
- [x] Wirkort der Einschränkung — entschieden (Hilfsfunktion an der Entstehungsstelle).
- [x] AC-3-Garantie — entschieden (keyword-only, Default `None`).
- [x] Zuschnitt Weg/Adresse — entschieden (erkannter Nutzer hier als Test, unbekannter Absender
      eigenes Issue).
- [x] AC-2-Abgrenzung — SMS und Premium-SMS sind heute keine Befehlskanäle; die Spec grenzt sie
      ausdrücklich als Scheibe S4 aus, statt eine unerfüllbare Zusicherung zu formulieren.
