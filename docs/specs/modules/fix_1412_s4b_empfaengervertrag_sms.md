---
entity_id: fix_1412_s4b_empfaengervertrag_sms
type: module
created: 2026-10-25
updated: 2026-10-25
status: draft
version: "1.0"
tags: [sms, premium-sms, empfaengervertrag, mandantentrennung, egress, verification, 1412]
workflow: feat-1412-s4b-empfaengervertrag-sms
issue: 1412
---

# Fix #1412 Scheibe S4b — Empfängervertrag SMS und Premium-SMS: Versand nur an belegte Nummern

## Approval

- [ ] Approved

## Purpose

S4a (Telegram) hat den Empfänger zu einem belegten Objekt gemacht. S4b überträgt
den Vertrag auf den seven.io-Transport, also auf **SMS** und **Premium-SMS**
(gemeinsame Basis `SevenIoChannelBase`), und ergänzt den Zweck `verification`
(Bestätigungscode an eine noch unbestätigte Nummer, #2406).

Heute greift der Transport selbst nach `settings.sms_to` bzw. nach
`settings.premium_sms_reply_to/_at`. Fachlich ist die SMS-Seite zwar schon
fail-closed (`Settings.with_user_profile` setzt `sms_to` nur bei bestätigter
Nummer), strukturell ist es aber dieselbe Lücke wie vor S4a: Wer die Einstellungen
per `model_copy` mit einer anderen Nummer versieht, sendet ungeprüft dorthin. Genau
das tut heute der Verifikations-Endpunkt (`api/routers/internal.py:190-196`,
`model_copy(update={"sms_to": req.to})`), und ein zweiter, versehentlicher
`model_copy` wäre davon nicht unterscheidbar.

Dazu kommt eine in der Analyse gefundene **Mandantenlücke**: Fehlt die `user.json`
eines Nutzers oder ist sie kaputt, gibt `with_user_profile` die Basis-Einstellungen
zurück (`src/app/config.py:418-427`). Diese tragen die globale
`GZ_SMS_TO`-Betreibernummer aus der `.env`, `can_send_sms()` (:461-467) lässt sie
passieren, und der Transport sendet an die Nummer des Betreibers statt an die des
Nutzers. Eine Profil-Fabrik ohne Rückfall schließt das.

Ergebnis: Der Transport sendet nur noch an einen ausdrücklich übergebenen,
über eine Fabrik belegten Empfänger. Fehlt er, wird geblockt (Default-Block mit
`reason_code`). Die Prüfung sitzt im einzigen Ausgang `_post`, vor der Drossel.

## Was diese Scheibe NICHT tut (Klartext)

- Kein Entfernen von `Settings.sms_to` und `can_send_sms()`. Beide bleiben vorerst
  als Bereitschaftsgate (7 Stellen), sind aber keine Empfängerquelle mehr. Entfernen
  ist eine Nachfolge-Aufgabe.
- Kein Go-Anteil. Die Go-Seite (`internal/handler/sms_verify.go`, `internal/model/user.go`)
  bleibt unverändert; die Reihenfolge `SaveUser` -> `dispatchSmsVerificationCode`
  wird nur als Voraussetzung belegt, nicht geändert.
- Kein Lesen von `sms_verification.json` (Go-Datei). Das koppelte Python an Go-Schema
  und Dateirechte, bei geringem Gewinn.
- Kein SMS-ContextVar und kein Zweck `inbound_reply` für SMS/Premium-SMS.
- Kein E-Mail-Anteil. C3-20 (E-Mail-Divergenzen gequoteter Local-Part / `, garbage`)
  gehört nicht in diese Scheibe und bleibt in #1412 offen. E-Mail hat dieselbe
  `base`-Rückkehr in `with_user_profile`, ist aber durch den
  Registered-Address-Guard (`email.py:738-806`, ADR-0087) geschützt.
- Kein neuer Struktur-Wächter (Regel-Budget): Der Default-Block ist die Struktur;
  `tests/tdd/test_egress_single_dial_point.py` bleibt unverändert gültig.
- Kein Test-Knopf für SMS (es gibt keinen; `channel_test_service.py` kennt nur
  E-Mail und Telegram).

## Source

- **Identifier:** `SevenIoChannelBase` (Konstruktor, `_post`, `_resolve_recipient`), `SMSOutput`, `PremiumSmsOutput`, neu `SmsRecipient` / `PremiumSmsRecipient`, ergänzt `RecipientPurpose.verification`
- **File:** `src/output/channels/recipient.py` (besteht seit S4a; kein Namenskonflikt)
- **File:** `src/output/channels/seven_io_base.py`, `src/output/channels/sms.py`,
  `src/output/channels/premium_sms.py`, `src/output/channels/base.py`
- **File:** `src/services/notification_service.py`, `api/routers/internal.py`,
  `src/app/config.py`

> **Schicht-Hinweis:** nur Python-Core (`src/`, `api/`). Kein Go-, kein
> Frontend-Anteil (ADR-0015, ADR-0062/0076: Python ist einziger seven.io-Transport).

## Estimated Scope

- **Files:** produktiv 7 (`recipient.py`, `seven_io_base.py`, `sms.py`,
  `premium_sms.py`, `notification_service.py`, `internal.py`, `base.py`) plus
  `config.py` (zwei Rückgabepfade). Tests: neuer Helper, neue Vertragstestdatei,
  Umstellung von ca. 14 Bestandstestdateien.
- **LoC:** produktiv ca. **+180 / −65**. Das Workflow-Limit (250) zählt nur
  produktive Spec-Dateien. Kein Override erwartet; vor jeder Änderung
  `workflow.py status` fragen. Tests zählen nicht.
- **Effort:** medium
- **Risiko:** MEDIUM. Wegen des Default-Blocks verstummt jeder übersehene Aufrufer.
  Premium-SMS ist Alarmkanal in Trip UND Ortsvergleich (sicherheitsrelevant).
  Deshalb werden **alle** Aufrufer in einem Zug umgestellt, kein
  „Legacy erlaubt"-Übergang.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RecipientPurpose`, `TelegramRecipient` (`recipient.py`, S4a) | Typ | Vorbild; `RecipientPurpose` wird um `verification` ergänzt |
| `loader.get_data_dir` / Profil-Loader | Funktion | die Fabriken lesen `user.json` frisch; `ValueError` bei ungültiger `user_id` wird abgefangen |
| `Settings.with_user_profile` (`config.py:418-457`) | Config | beide `base`-Rückgabepfade setzen `sms_to=None` |
| `SevenIoChannelBase._post` (`seven_io_base.py:155`) | Methode | einziger geschützter httpx-Ausgang; Prüfung vor der Drossel |
| `ChannelBlockedError` (mit `reason_code`) | Exception | Block-Signal |
| `_guard_code_origin` (:127), Sandbox-Key-Guard (:108) | Guards | bleiben unverändert |
| `alert_log.py` | Konsument | Alarm-Buchung hängt an `premium_sms_no_reply_address` / `premium_sms_reply_address_stale` |
| `internal/handler/sms_verify.go:48-54, :73-127`, `auth.go:1394, :1410` | Go (nur lesend) | Reihenfolge: `user.json` (mit `pending_sms_to` bzw. `sms_to`) wird geschrieben, **bevor** Python aufgerufen wird |
| `tests/tdd/test_egress_single_dial_point.py` | Wächter | bleibt unverändert |

## Implementation Details

### Kernregeln

1. **Zwei Empfänger-Typen statt einem.** `SmsRecipient` und `PremiumSmsRecipient`
   haben je eine Quelle (bestätigte Nummer bzw. gelernte Rückadresse samt Alter)
   und je eine `reason_code`-Familie. Beide sind unveränderlich und nur über
   Fabriken erzeugbar (gemeinsamer `_FABRIK`-Schlüssel wie bei Telegram).
   `verification` gibt es **nur** am SMS-Typ; Premium-SMS kennt diesen Zweck nicht.
2. **Empfänger an der Instanz.** `SevenIoChannelBase.__init__(settings, *, recipient=None)`;
   die `send`-Signaturen bleiben gleich. Der Empfänger trägt die `user_id`; es gibt
   bewusst **kein** `Settings.user_id` (sonst öffnet `model_copy` die Lücke wieder).
3. **`SmsRecipient.for_user(user_id, settings)`** (Zweck `user_profile`): liest
   `sms_to` und `sms_verified_number` **frisch aus der `user.json`** (beide getrimmt,
   gleiche Regel wie `config.py:439-443`), nie aus den Settings. Kein Profil,
   unbestätigt (`sms_verified_number != sms_to`) oder leer: Block mit
   `reason_code=sms_no_recipient`. `GZ_SMS_TO` aus der `.env` wird nie gelesen.
4. **`PremiumSmsRecipient.for_user(user_id, settings)`** (Zweck `user_profile`):
   liest `premium_sms_reply_to/_at` frisch aus der `user.json`. Die bestehenden Blocks
   wandern in die Fabrik und behalten ihre Codes und Konstanten (TTL 30 Tage):
   fehlend oder leer: `premium_sms_no_reply_address`; Zeitstempel in der Zukunft oder
   älter als 30 Tage: `premium_sms_reply_address_stale`. Die Konstanten und
   `reason_code`s bleiben in `premium_sms.py` definiert.
5. **`SmsRecipient.verification(user_id, number)`** (Zweck `verification`) ist eng
   gebunden: `strip(number) == strip(pending_sms_to or sms_to)` aus der **frischen**
   `user.json` (entspricht Go `smsZielnummer`, `sms_verify.go:48-54`), dazu strikte
   E.164 `^\+[1-9]\d{7,14}$`. Jede andere Nummer ist ein Block. Damit ist `req.to`
   keine freie Eingabe mehr und `verification` kein Generalschlüssel für beliebige
   Nummern.
6. **Prüfort ist `_post`, nicht `send`.** Reihenfolge: Form -> Herkunft/Mismatch ->
   `_guard_code_origin` -> Sandbox-Key-/Testmodus-Guards -> Drossel. Kein Empfänger
   ⇒ Block. Payload-`to` ≠ Empfängernummer ⇒ Mismatch-Block (Muster
   `telegram.py:302-325`). Die `_post`-Signatur bleibt unverändert.
7. **Formprüfung bedingungslos** (auch in Produktion, auch im Testmodus):
   - `verification`: strikt `^\+[1-9]\d{7,14}$`.
   - `user_profile` (SMS) **tolerant** für den Altbestand: erlaubt sind Ziffern, `+`,
     Leerzeichen, `-`, `(`, `)`, mit 7 bis 15 Ziffern. Gesendet wird die **gespeicherte
     Form unverändert**, ohne Ziffernumbau, damit das ohne Formprüfung nachgetragene
     Bestandskonto nicht ausgesperrt wird. Die Bestandsform der Nummern auf Produktion
     wurde nicht gemessen (PO 2026-10-25: Zählung nicht nötig); die tolerante Regel
     macht die Spec davon unabhängig.
   - Premium: `^\+?[1-9]\d{7,14}$` (die Rückadresse ist das seven.io-`from`, Ziffern
     meist ohne `+`).
8. **Befehlsantwort Premium-SMS per `user_profile`** (gelernte Rückadresse), kein
   neuer ContextVar. Begründung: Der Reader antwortet nur im Lern-Erfolgspfad
   (`inbound_sms_reader.py:331-342`), dort ist die gelernte Rückadresse identisch mit
   `sender`. Bei der Kollision #2328 gibt es 409 und keine Antwort. `user_profile`
   bindet zusätzlich an TTL und Konto.
9. **Testmodus:** keine Test-Nummer nötig. Der Sandbox-Key sendet nie
   (`egress_guard_sms.md`); `for_user` liest auch im Testmodus das Profil.
10. **Debug-CLI / `get_channel`:** `get_channel("sms")` und `get_channel("premium_sms")`
    ohne Empfänger blocken mit klarer Meldung (wie S4a); die globale `.env` ist keine
    Empfängerquelle. Es gibt keinen Zweck `operator`.
11. **`with_user_profile`:** beide `base`-Rückgabepfade (`config.py:418-427`) setzen
    `sms_to=None`, damit das Bereitschaftsgate nicht täuscht. Premium-SMS ist hier
    nicht betroffen (`_premium_sms_reply_env_deny`, `config.py:28`).

### Aufrufer -> Zweck (Inventur aus der Analyse)

| Aufrufer | Stellen | Empfängerquelle -> Zweck |
|---|---|---|
| `notification_service.py` Briefing | :798 / :821 | `for_user` -> `user_profile` (SMS bzw. Premium) |
| `notification_service.py` Kein-Daten-Hinweis | :979 / :991 | `user_profile` |
| `notification_service.py` Amtswarnung | :1389 / :1407 | `user_profile` |
| `notification_service.py` Ortsvergleich | :1522 / :1540 | `user_profile` |
| `notification_service.py` Ortsvergleich-Amtswarnung | :1762 / :1792 | `user_profile` |
| `notification_service.py` Alarme (inkl. Regen/Radar) | :2146 / :2166 | `user_profile` |
| `send_command_reply_premium_sms` | :2204-2222 | `PremiumSmsRecipient.for_user` -> `user_profile` (Rückadresse, nicht `sender`) |
| `api/routers/internal.py` Verifikations-Code | :175-200 | `SmsRecipient.verification(req.user_id, req.to)`; `model_copy(update={"sms_to": ...})` entfällt |
| `base.py` `get_channel` / Debug-CLI | :125, :130 | Block mit klarer Meldung |

Der Empfänger wird an allen Stellen **im `try` nach `_sms_gate_reserve`** gebaut, damit
ein Block dieselbe Fehlerbehandlung durchläuft wie ein Versandfehler.

## Expected Behavior

- **Input:** jeder SMS- oder Premium-SMS-Sendeversuch (Briefing, Hinweis, Amtswarnung,
  Ortsvergleich, Alarme, Befehlsantwort, Bestätigungscode).
- **Output:** Die Nachricht geht nur an die belegte Nummer; sonst
  `ChannelBlockedError` mit `reason_code` und **kein** HTTP-Call. Legitime Wege
  verstummen nicht.
- **Side effects:** Logs nennen Nutzer-ID, nie die Telefonnummer. Alarm-Buchungen
  bleiben an die bisherigen `reason_code`s gebunden.

## Acceptance Criteria

Nachweisform für alle ACs: Kern-Test mit Sink am `httpx`-Rand (`_post` nicht
gestubbt, echter Versandversuch), `is_test_mode=False`, zwei Nutzer, Testdatei nach
Verhalten benannt: `tests/tdd/test_sms_recipient_contract.py`. Kein isolierter
Guard-Aufruf (Lehre #1288).

- **AC-1:** Given ein SMS-Ausgang, der ohne Empfänger-Objekt gebaut wurde / When er
  eine Nachricht senden soll / Then wird der Versand mit `ChannelBlockedError`
  (`reason_code=sms_no_recipient`) abgelehnt und es findet kein einziger HTTP-Versuch
  statt; dasselbe gilt für den Premium-SMS-Ausgang ohne Empfänger (dort mit dem
  bestehenden `reason_code=premium_sms_no_reply_address`, damit die Alarm-Buchung
  unverändert greift).
  - Test: echter `send`-Aufruf, Sink am httpx-Rand, 0 Aufrufe.

- **AC-2:** Given ein Nutzer, dessen Nummer in der `user.json` hinterlegt, aber nicht
  bestätigt ist (`sms_verified_number` leer oder abweichend), oder dessen Nummer leer
  ist, oder der gar kein Profil hat / When für ihn per SMS gesendet werden soll /
  Then wird mit `reason_code=sms_no_recipient` geblockt, ohne HTTP-Versuch; bei
  bestätigter Nummer geht die SMS an genau diese, frisch aus der `user.json` gelesene
  Nummer.
  - Test: vier Profilzustände (bestätigt, unbestätigt, leer, kein Profil); Sink prüft Zielnummer.

- **AC-3:** Given die `user.json` eines Nutzers fehlt oder ist unlesbar und in der
  `.env` ist eine globale Betreibernummer `GZ_SMS_TO` gesetzt / When für diesen Nutzer
  per SMS gesendet werden soll / Then wird geblockt und die Betreibernummer erhält
  nichts (Cross-Tenant-Lücke geschlossen); `with_user_profile` liefert in beiden
  `base`-Pfaden `sms_to=None`.
  - Test: `GZ_SMS_TO` gesetzt, kein/kaputtes Profil; 0 Sink-Aufrufe an die Betreibernummer; `sms_to is None` geprüft.

- **AC-4:** Given Einstellungen, die per `model_copy` die Nummer eines anderen Nutzers
  tragen, während der Empfänger über die Fabrik für Nutzer B gebaut wurde / When
  gesendet wird / Then geht die SMS ausschließlich an die Nummer von B (frisch aus
  B's `user.json`), nie an die Nummer in den Settings; weicht die Nummer im Payload
  vom Empfänger ab, blockt der einzige Ausgang `_post` vor der Drossel mit
  Mismatch-Block und es gibt keinen HTTP-Versuch.
  - Test: zwei Nutzer A und B, `model_copy` mit A's Nummer, Empfänger `for_user(B)`; zusätzlich ein Fall mit manipuliertem Payload-`to`; Drossel-Zähler bleibt bei Block unverändert.

- **AC-5:** Given ein Nutzer mit gelernter Premium-SMS-Rückadresse, die frisch ist /
  When ein Premium-SMS-Versand ausgelöst wird / Then geht die Nachricht nur an diese
  Rückadresse; fehlt die Rückadresse, liegt ihr Zeitstempel in der Zukunft oder ist
  er älter als 30 Tage, wird weiterhin mit `premium_sms_no_reply_address` bzw.
  `premium_sms_reply_address_stale` geblockt (Codes unverändert, damit die
  Alarm-Buchung weiter greift).
  - Test: vier Fälle (frisch, fehlend, Zukunft, 31 Tage); Sink und `reason_code` geprüft; Alarm-Buchung registriert den unveränderten Code.

- **AC-6:** Given der Verifikations-Endpunkt erhält von Go einen Bestätigungscode für
  eine Nummer / When die Nummer gleich `pending_sms_to` (bzw. `sms_to`) aus der
  frischen `user.json` dieses Nutzers und strikt E.164 ist / Then geht der Code an
  genau diese unbestätigte Nummer; bei jeder anderen Nummer (auch einer wohlgeformten
  fremden) wird geblockt, ohne HTTP-Versuch.
  - Test: echter Endpunktaufruf; Fälle: passende Nummer, fremde wohlgeformte Nummer, Nummer ohne `+`, Nutzer ohne Profil.

- **AC-7:** Given der Premium-SMS-Kanal / When jemand versucht, dort den Zweck
  `verification` zu verwenden / Then ist das nicht möglich (der Zweck existiert nur am
  SMS-Typ), und `verification` wird nie zum Weg, mit dem ein Aufrufer an eine
  beliebige Nummer sendet.
  - Test: `PremiumSmsRecipient` bietet keine `verification`-Fabrik; die SMS-`verification`-Fabrik akzeptiert nur die an das Profil gebundene Nummer (siehe AC-6).

- **AC-8:** Given eine Nummer, die nicht der Form genügt (auch in Produktion, ohne
  Testmodus) / When gesendet werden soll / Then wird vor jedem HTTP-Versuch geblockt:
  `verification` verlangt strikt `^\+[1-9]\d{7,14}$`; die Nummer eines
  `user_profile`-SMS-Empfängers darf nur Ziffern, `+`, Leerzeichen, `-` und Klammern
  enthalten, mit 7 bis 15 Ziffern; Premium verlangt `^\+?[1-9]\d{7,14}$`.
  - Test: z. B. `"abc"`, `"12; DROP"`, leer, 6 und 16 Ziffern, je Zweck/Kanal; 0 Sink-Aufrufe.

- **AC-9:** Given ein Bestandskonto, dessen bestätigte Nummer in einer tolerant
  geschriebenen Form gespeichert ist (z. B. mit Leerzeichen oder Bindestrichen) /
  When für diesen Nutzer gesendet wird / Then wird die SMS ausgeliefert und die
  **gespeicherte Form** unverändert an den Anbieter übergeben (kein Ausschluss, kein
  Ziffernumbau).
  - Test: Profil mit tolerant geschriebener, bestätigter Nummer; Sink sieht die Form byteidentisch.

- **AC-10:** Given alle produktiven Aufrufer (Briefing, Kein-Daten-Hinweis,
  Amtswarnung, Ortsvergleich, Ortsvergleich-Amtswarnung, Alarme) / When ein Nutzer mit
  bestätigter Nummer bzw. frischer Rückadresse eine Meldung auslöst / Then wird
  weiterhin ausgeliefert; es verstummt kein Weg. Das gilt für Premium-SMS-Alarme in
  Trip UND Ortsvergleich, einschließlich Regen- und Radar-Alarmen.
  - Test: je Aufrufer ein echter Versandpfad gegen den Sink (SMS und Premium); Alarmarten Regen/Radar in beiden Flächen.

- **AC-11:** Given ein Nutzer schickt einen Befehl per Premium-SMS über den echten
  Eingang `inbound_sms_reader`, und die Rückadresse wurde unmittelbar davor gelernt /
  When die Antwort gesendet wird / Then geht sie über den Profil-Empfänger an die
  gelernte Rückadresse (identisch mit dem Absender); lernt Go nicht (z. B. Kollision
  #2328, 409), gibt es keine Antwort.
  - Test: echter Reader-Pfad `_verarbeite_befehl`; Fälle: Lernen erfolgreich, Kollision.

- **AC-12:** Given die Debug-CLI ohne Nutzer (globale `.env`) oder ein direkter
  `get_channel("sms")` / `get_channel("premium_sms")` / When der Kanal angefordert
  und gesendet wird / Then wird mit klarer Meldung abgelehnt, nicht still über
  `settings.sms_to` gesendet.
  - Test: `get_channel` bzw. CLI-Aufruf ⇒ klare Fehlermeldung, 0 HTTP-Versuche.

- **AC-13:** Given zwei Nutzer A und B mit jeweils eigener bestätigter Nummer bzw.
  Rückadresse / When für beide gesendet wird, auch unmittelbar nacheinander in
  derselben Instanz / Then erreicht Nutzer A nie die Nummer von B und umgekehrt
  (Mandantentrennung, SMS und Premium-SMS).
  - Test: zwei Nutzer, abwechselnder Versand, Sink prüft jede Zielnummer.

- **AC-14:** Given der Sandbox-Key-Guard und der Herkunfts-Guard (`_guard_code_origin`)
  / When ein Versand durch den neuen Empfängercheck läuft / Then greifen beide Guards
  weiterhin unverändert, und die Prüfreihenfolge in `_post` ist Form -> Herkunft ->
  Guards -> Drossel; ein geblockter Versuch verbraucht keinen Drosselplatz.
  - Test: Sandbox-Key im Testmodus sendet nie echt; Block-Fall lässt den Drossel-Zähler unverändert.

## Known Limitations

Der Schutz gilt gegen Versehen und Regressionen (vergessene `model_copy`-Wege,
`.env`-Rückfall, falscher Mandant, neue Aufrufer mit nacktem
`SMSOutput(settings).send`). Gegen absichtlich bösartigen Code im selben Prozess hilft
er nicht (Python kennt keine Capability-Isolation).

`verification` ist an die Nummer in der frischen `user.json` gebunden. Diese Datei wird
über den Go-Profilfluss geschrieben (ADR-0087, S5); eine Nummer gelangt also nur über
diesen Fluss in den Herkunftsbeleg. Das Tageslimit für Codes liegt bei Go
(`sms/daily-usage`) und ändert sich nicht.

## Test Plan

- **Kern-Schicht (deterministisch, offline):** nur benannte Testdateien,
  `--disable-socket`.
  - Neu: `tests/tdd/test_sms_recipient_contract.py` (AC-1 bis AC-14) mit Sink am
    httpx-Rand, `is_test_mode=False`, zwei Nutzer.
  - Neu: `tests/helpers/sms_empfaenger.py` nach Vorbild
    `tests/helpers/telegram_empfaenger.py` (Profil mit bestätigter Nummer bzw.
    Rückadresse, Ausgang-Fabriken). Das erspart den Massenumbau der ca. 120 Dateien,
    die `sms_to`/`SMSOutput(`/`PremiumSmsOutput(` berühren; nur die Dateien, die
    tatsächlich Ausgänge instanziieren und ohne Empfänger blocken würden, werden
    umgestellt.
  - Umzustellen (ca. 14 Dateien), u. a.: `test_success_status_guard.py`,
    `test_sms_test_isolation.py`, `test_channel_origin_guard_parity.py`,
    `unit/test_channel_blocked_missing_recipient.py`,
    `test_premium_sms_reply_future_timestamp.py`,
    `test_sms_versand_nur_bestaetigte_nummer.py`, `unit/test_premium_sms_versand.py`.
  - **Live-markierte Tests mitziehen** (Lehre S4a: 21 `live`/`email`-Tests waren im
    Standardlauf unsichtbar): `tdd/test_issue_936_sms_stub.py` und
    `tdd/test_issue_608_sms_seven_io.py`. Der Kern-Lauf wird zusätzlich mit `-m live`
    gefahren (ein `-m "not live"`-Teillauf beweist nichts über sie).
  - Prüfling wird relativ zur Testdatei aufgelöst; keine Mock-Theater-Tests.
- **Mutations-Gegenprobe (Pflicht im Adversary):** u. a. Mismatch-Prüfung entfernen,
  Rückfall auf `settings.sms_to` wieder einbauen, `verification`-Bindung an
  `pending_sms_to` aufweichen, Formprüfung nur im Testmodus aktiv, Prüfung nach der
  Drossel; je Verfälschung muss ein Test aus der Vertragsdatei rot werden (WELCHER
  Test zählt).
- **Staging (ehrlich):** Staging läuft im Testmodus mit Sandbox-Key über
  `for_testing()` und kann den Produktiv-Block **nicht** belegen; das belegen allein
  die Kern-Tests. Staging belegt „nichts verstummt" über den echten Eingang:
  Bestätigungscode-Versand an eine Wegwerf-Nummer und ein SMS-Briefing.
  Der Nachweis einer **echten** SMS an die zweite seven.io-Nummer (Empfang selbst
  prüfbar) ist ein festzulegender Schritt der `/e2e-verify`-Phase: Im Repo ist
  dokumentiert, dass Premium-SMS per API-Send dort als `InfoSMS` und nicht als
  Premium-SMS-Antwort ankommt (`feat_2417_kurzform_englisch.md:335`, #2322/#2417-
  Kommentare). Ein konkretes Rezept für den echten Staging-Versand **trotz Sandbox-Key**
  (der Sandbox-Key sendet nie) wurde im Repo nicht gefunden; es wird in
  `/e2e-verify` festgelegt, nicht hier erfunden. Der Premium-SMS-Pfad wird, wie in
  #2417, im Kern über den echten `inbound_sms_reader` geprüft; ein Handy-Dialog des
  PO nach dem Prod-Deploy ist Nachkontrolle und blockiert den Deploy nicht.
- Mail-Validatoren entfallen (kein E-Mail-Pfad berührt).

## Randbedingungen

- **Multi-User:** Jeder datenbewegende Pfad wird mit zwei verschiedenen Nutzern
  getestet (AC-4, AC-13); echte `user_id`, nie `"default"`.
- Blockaden bleiben sichtbar (Fehler/Log), nie still verschluckt. Alle vier Kanäle
  bleiben gleichrangig; Alarme müssen weiter alle Kanäle erreichen (#1701).
- **Regel-Budget:** kein neues Gate, kein neuer Wächter.
- Schema-relevante Dateien werden nicht berührt.

## Risiken

- **Verstummte Aufrufer:** Ein übersehener Aufrufer blockt künftig statt zu senden.
  Gegenmaßnahme: vollständige Inventur (siehe Tabelle), alle Stellen in einem Zug,
  AC-10 deckt jeden Aufrufer mit echtem Versandpfad ab.
- **`verification` als Generalschlüssel:** durch die Bindung an die frische
  `user.json` und strikte E.164 ausgeschlossen (AC-6, AC-7).
- **Rennen mit Go:** belegt, dass `user.json` vor dem Python-Aufruf geschrieben
  wird (`auth.go:1394` vor `:1410`, Code synchron, Python-Aufruf asynchron). Sollte sich
  die Reihenfolge in Go ändern, blockt `verification` (fail-closed), statt falsch zu senden.
- **Ausschluss von Bestandskonten:** durch die tolerante `user_profile`-Regel und
  unveränderte Übergabe der gespeicherten Form vermieden (AC-9).
- **Unsichtbare Live-Tests:** die beiden live-markierten SMS-Tests werden mitgezogen.
- **LoC:** Größenordnung wie S4a; vor einem Override `workflow.py status` messen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Setzt ADR-0087 (Empfängerschutz), ADR-0003
  (Mandantentrennung), ADR-0049 (Premium-SMS als vierter Kanal) und ADR-0062/0076
  (Python einziger seven.io-Transport) um.
- **Bewusste Abweichungen vom S4-Konzept** (`docs/context/fix-1412-versandweg-basis.md:211-221`):
  kein `Settings.user_id` (Lücke über `model_copy`), kein Zweck `operator`
  (kein Produktiv-Aufrufer), zwei Empfänger-Typen statt einem.

## Changelog

- 2026-10-25: Initial spec created (S4b, aus `docs/context/feat-1412-s4b-empfaengervertrag-sms.md`)
