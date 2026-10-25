# Context: feat-1412-s4b-empfaengervertrag-sms

## Request Summary
#1412 Scheibe S4b: Der Empfängervertrag aus S4a (Telegram) wird auf SMS und Premium-SMS übertragen.
Der seven.io-Transport sendet nur noch an einen ausdrücklich übergebenen, über Fabriken belegten
Empfänger. Fehlt er, wird geblockt. Neu kommt der Zweck `verification` hinzu (Bestätigungscode an eine noch
unbestätigte Nummer, #2406). Konzept: `docs/context/fix-1412-versandweg-basis.md:211-221, :250`.

## Ausgangslage (gemessen 2026-10-25, Stichproben gelesen)

- **Fachlich ist die SMS-Seite schon fail-closed:** `Settings.with_user_profile` (`src/app/config.py:439-443`)
  setzt `sms_to` nur, wenn `sms_verified_number == sms_to` (beide getrimmt), sonst `None`.
- **Strukturell ist es dieselbe Lücke wie vor S4a bei Telegram:** Der Transport greift selbst nach
  `settings.sms_to` (`src/output/channels/sms.py:41-50`). Wer Settings per `model_copy` mit einer anderen
  Nummer versieht, sendet ungeprüft an sie. Genau das tut heute legitim der Verifikations-Endpunkt
  (`api/routers/internal.py:190-196`, `model_copy(update={"sms_to": req.to})`). Ein zweiter, versehentlicher
  `model_copy` wäre nicht von ihm unterscheidbar.
- **Premium-SMS** liest `settings.premium_sms_reply_to` / `premium_sms_reply_at` (`premium_sms.py:64-100`).
  Das ist die vom Go-Lern-Endpunkt in `user.json` geschriebene Rückadresse. Es gibt bereits zwei Blocks
  (`premium_sms_no_reply_address`, `premium_sms_reply_address_stale`, TTL 30 Tage, `:42-50`), aber
  ebenfalls aus Settings, nicht aus einem belegten Empfänger-Objekt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/channels/recipient.py` | `RecipientPurpose` (:34, kanalübergreifend: `user_profile`, `inbound_reply`), `TelegramRecipient` (:47, Fabriken `for_user` :61, `inbound_reply` :81), ContextVar `_current_inbound_sender` (:27). S4b ergänzt `verification` und einen SMS-Empfänger-Typ |
| `src/output/channels/seven_io_base.py` | gemeinsame Basis SMS/Premium-SMS: `send` (:166-192), `_resolve_recipient` (:88), `_post` (:155, einziger httpx-Ausgang), `_guard_code_origin` (:127), Sandbox-Key-Guard (:108) |
| `src/output/channels/sms.py` | `_resolve_recipient` liest `settings.sms_to` (:41-50) |
| `src/output/channels/premium_sms.py` | `_resolve_recipient` liest die gelernte Rückadresse (:64-100). Absender fest `4916092172595` (:32) |
| `src/services/notification_service.py` | alle produktiven Aufrufer, Zweck `user_profile`: :798/:821 Briefing, :979/:991 Kein-Daten-Hinweis, :1389/:1407 Amtswarnung, :1522/:1540 Vergleich, :1762/:1792 Vergleich-Amtswarnung, :2146/:2166 Alarme. :2219 `send_command_reply_premium_sms` (Befehlsantwort) |
| `api/routers/internal.py:175-200` | Verifikations-Code-Versand, Zweck `verification`, Nummer aus dem Go-Aufruf |
| `src/services/inbound_sms_reader.py` | Premium-SMS-Eingang: Filter `to == SERVICE_NUMBER` (:240), `sender` (:243), Lernen über Go (:81, :248), Befehle `_verarbeite_befehl` (:316-415) mit `with_user_profile` (:342), Antwort über :393/:415 |
| `src/output/channels/base.py:125,130` | `get_channel` baut SMS/Premium-SMS. Einziger produktiver Aufrufer ist die Debug-CLI, die SMS praktisch nicht erreicht (`cli.py:64-66`) |
| `src/app/config.py` | `sms_to` (:224), `premium_sms_reply_*` (:28, :232), `with_user_profile` (:439-457), `for_testing` (:362-393, lässt `sms_to` unberührt, tauscht nur den API-Key) |
| `src/services/channel_test_service.py:41-80` | Test-Knopf kennt nur email/telegram. Für SMS gibt es keinen Knopf (kein M3-Pendant) |
| `internal/handler/sms_verify.go:82-113` | Go erzeugt und speichert den Code und ruft Python `/api/_internal/sms/verification-code` mit `{user_id,to,code}` |
| `internal/model/user.go:69-71` | `sms_verified_number`, `sms_verified_at`, `pending_sms_to` |

## Existing Patterns
- **S4a-Vorbild:** unveränderliches Empfänger-Objekt, nur über Fabriken erzeugbar. Empfänger an der Instanz
  (`TelegramOutput(settings, *, recipient=None)`), ohne Empfänger Default-Block mit `reason_code`,
  Formprüfung bedingungslos, Prüfung im einzigen Ausgang vor der Drossel. Der Empfänger trägt die `user_id`.
  Es gibt bewusst **kein** `Settings.user_id` (sonst öffnet `model_copy` die Lücke wieder).
- **Test-Helper aus S4a:** `tests/helpers/telegram_empfaenger.py` (`profil_chat`, `mit_profil_chat`, `profil_ausgang`,
  `im_update`, `antwort_ausgang`), ContextVar-Reset in `tests/conftest.py:160-167`, Vertragstests
  `tests/tdd/test_telegram_recipient_contract.py`, `tests/tdd/test_telegram_inbound_reply_contract.py`.
- **Block-Signal:** `ChannelBlockedError(reason_code=…)` wie bisher (`sms_no_recipient`, `premium_sms_*`).

## Zweck-Zuordnung der Aufrufer
| Aufrufer | Zweck | Nummer heute |
|---|---|---|
| notification_service (Briefing, Hinweis, Amtswarnung, Vergleich, Alarme), SMS | `user_profile` | bestätigte `sms_to` aus `user.json` (über `with_user_profile`) |
| dieselben, Premium-SMS | `user_profile` (gelernte Rückadresse) | `premium_sms_reply_to` aus `user.json` |
| `send_command_reply_premium_sms` | offen: `inbound_reply` oder `user_profile` | heute die Profil-Rückadresse, **nicht** `sender` des laufenden Eingangs. Der Eingang hat die Adresse unmittelbar davor gelernt |
| `internal.py` Verifikations-Code | `verification` | `req.to` aus Go (unbestätigt per Definition) |
| Debug-CLI / `get_channel` | Block mit klarer Meldung (wie S4a) | `settings.sms_to` |

## Dependencies
- Upstream: `Settings.with_user_profile`, `loader.get_data_dir`/Profil-Loader, `ChannelBlockedError`,
  `SevenIoChannelBase._post` (S3b-Ausgang), Sandbox-/Testmodus-Weichen (`is_test_user`, `env == "staging"`).
- Downstream: alle SMS/Premium-SMS-Versandpfade (Briefing, Alarme inkl. Regen/Radar, Amtswarnungen, Ortsvergleich,
  Befehlsantworten über inReach, SMS-Bestätigungscode des Registrierungs-/Profilflusses in Go).

## Existing Specs
- `docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md` (Vorlage. Ordnet S4b SMS und `verification` zu, :37, :119, :160-163)
- `docs/specs/modules/fix_1412_s3b_telegram_sms_ausgang.md`, `fix_1412_s5_go_empfaengerschutz.md` (Out of Scope nennt S4b, :188)
- `docs/specs/modules/sms_nummer_verifikation.md` (#2406), `egress_guard_sms.md`
- `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md`, `feat_1676_s2a_premium_sms_versand.md`,
  `feat_2184_s4_premium_sms_kommandoverarbeiter.md`, `fix_2328_premium_sms_rueckkanal_kollision.md`,
  `fix_2323_premium_sms_gate_generisch.md`
- ADRs: `0087-empfaengerschutz`, `0049-premium-sms-vierter-kanal`, `0062`/`0076` (Python einziger seven.io-Transport),
  `0092` (Test-Mail an bestätigte Profiladresse)

## Risks & Considerations
- **Default-Block lässt übersehene Aufrufer verstummen.** Deshalb alle Aufrufer in einem Zug umstellen (wie S4a),
  kein „Legacy erlaubt“-Übergang. Premium-SMS ist Alarmkanal in Trip und Ortsvergleich: Ein Verstummen dort ist
  nutzersichtbar und sicherheitsrelevant.
- **`verification` ist der engste Zweck:** Die Nummer ist per Definition unbestätigt. Der Zweck darf nur aus dem
  internen Endpunkt erreichbar sein (Go ruft mit Core-Auth). Er braucht eigene Grenzen (Form E.164,
  Testnummernraum im Testmodus, Tageslimit existiert schon in Go/`sms/daily-usage`). Es darf nicht passieren,
  dass `verification` zum Generalschlüssel wird, mit dem jeder Aufrufer an eine beliebige Nummer sendet.
- **Befehlsantwort Premium-SMS:** `sender` des laufenden Eingangs und die gelernte Rückadresse sind in der Regel identisch.
  Bei einer Kollision (#2328) können sie es nicht sein. Die Entscheidung `inbound_reply` (ContextVar wie Telegram) oder
  `user_profile` gehört in die Analyse.
- **Test-Massenumbau:** 120 Testdateien berühren `sms_to`/`SMSOutput(`/`PremiumSmsOutput(`. Ohne gemeinsamen
  Test-Helper (Vorbild `tests/helpers/telegram_empfaenger.py`) sprengt das jedes Maß. Live-markierte Tests
  mitziehen (Lehre S4a: 21 `live`/`email`-Tests waren im Standardlauf unsichtbar).
- **Formprüfung E.164** bedingungslos, auch in Produktion. Vorher messen, welche Form gespeicherte Nummern
  haben (mit/ohne `+`, seven.io akzeptiert beides). Sonst sperrt die Formprüfung Bestandskonten aus.
- **LoC:** Das Konzept schätzt S4a/b zusammen auf 300-500. S4a lag bei etwa +170/−40. Für S4b ist eine ähnliche Größe zu erwarten,
  vor dem Override `workflow.py status` messen.
- **Nachweis** muss ein echter Versandversuch an eine gesperrte Nummer sein (Sink am Transportrand), dazu auf Staging
  eine echte SMS/Premium-SMS an die zweite seven.io-Nummer (Empfang selbst prüfbar). Kein isolierter
  Guard-Aufruf (#1288-Muster).
- **C3-20 (aus #1199 übertragen):** E-Mail-Divergenzen gequoteter Local-Part / `, garbage`. Das ist E-Mail, nicht SMS,
  und gehört nicht in diese Scheibe. Bleibt im Issue offen.

## Analysis

### Type
Feature (Sicherheits-Härtung, Scheibe S4b von #1412)

### Neue Befunde aus der Analyse (gemessen 2026-10-25)
- **Cross-Tenant-Lücke über `GZ_SMS_TO`:** Fehlt `user.json` oder ist sie kaputt, gibt `with_user_profile` `base`
  zurück (`src/app/config.py:418-427`). Damit trägt `sms_to` die globale `.env`-Betreibernummer, `can_send_sms()`
  (:461-467) passiert und der Transport sendet an sie. Eine Profil-Fabrik schließt das. Zusätzlich setzen beide
  Rückgabepfade `sms_to=None`, damit das Bereitschaftsgate nicht täuscht. Premium-SMS ist nicht betroffen
  (`_premium_sms_reply_env_deny`, `config.py:28`). E-Mail hat dieselbe `base`-Rückkehr, ist aber durch den
  Registered-Address-Guard (`email.py:738-806`, ADR-0087) geschützt, deshalb nicht in Scope und kein eigenes Issue.
- **Nummernformen verschieden:** `sms_to` ist `+E.164` (Go prüft `^\+[1-9]\d{7,14}$` erst seit 2026-09-23, `036aa01e4`,
  `internal/store/e164.go`). Die Premium-Rückadresse ist das seven.io-`from`, Ziffern **ohne** `+`, von Go ungeprüft
  übernommen (`premium_sms_connect.go:141`). Python prüft die Form heute nirgends.
- **Bestandsform NICHT gemessen:** `/var/lib/gregor/users` ist für `hem` gesperrt, der sudo-Lesezugriff wurde von der
  Auto-Mode-Prüfung abgelehnt (Production Reads). Laut #2406-Kommentar hat der Backfill genau **ein** Bestandskonto
  (`henning`) nachgetragen, und zwar byteidentisch ohne Formprüfung. Die Spec darf deshalb nicht von einer Messung
  abhängen (siehe Formprüfung unten). Eine reine Zählung (nur Formklassen, keine Werte) kann der PO erlauben.
  Skript: `nummernform.py` im Session-Scratchpad.
- **Go-Reihenfolge Verifikation belegt:** `auth.go:1394` `SaveUser` (schreibt `pending_sms_to` bzw. `sms_to`),
  dann `auth.go:1410` `dispatchSmsVerificationCode`, der den Code **synchron** in `sms_verification.json` ausstellt
  (`sms_verify.go:73-90`) und erst danach **asynchron** Python aufruft (:117-127). Wenn Python läuft, steht die
  Zielnummer also schon in `user.json`.
- **Befehlsantwort Premium-SMS:** Der Reader antwortet nur, wenn Go gelernt und eine `user_id` geliefert hat
  (`inbound_sms_reader.py:331-342`). Gelernte Rückadresse und `sender` sind dann identisch. Bei der Kollision #2328
  gibt es 409 und keine Antwort. Ein SMS-ContextVar existiert nicht.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/channels/recipient.py` | MODIFY | `RecipientPurpose.verification`. Neue Typen `SmsRecipient` (Fabriken `for_user`, `verification`) und `PremiumSmsRecipient` (Fabrik `for_user`), gemeinsamer `_FABRIK`-Schlüssel, Profil-Loader frisch aus `user.json` |
| `src/output/channels/seven_io_base.py` | MODIFY | Konstruktor `recipient=None`. Prüfung im **einzigen Ausgang `_post` (:155)** vor der Drossel: kein Empfänger ⇒ Block, Payload-`to` ≠ Empfänger ⇒ Mismatch-Block, Form bedingungslos (S4a-Muster `telegram.py:302-325`) |
| `src/output/channels/sms.py` | MODIFY | `_resolve_recipient` liest nur `self._recipient`, nie `settings.sms_to` |
| `src/output/channels/premium_sms.py` | MODIFY | Fehlend-/Zukunft-/TTL-Blocks wandern in `PremiumSmsRecipient.for_user`. Konstanten und `reason_code`s bleiben hier definiert und stabil |
| `src/services/notification_service.py` | MODIFY | alle 12 Aufrufstellen (798/821, 979/991, 1389/1407, 1522/1540, 1762/1792, 2146/2166) und `send_command_reply_premium_sms` (:2204-2222): Empfänger **im `try` nach `_sms_gate_reserve`** bauen |
| `api/routers/internal.py` | MODIFY | `:175-200` `model_copy(update={"sms_to": req.to})` entfällt, `SmsRecipient.verification(req.user_id, req.to)`. `ValueError` aus `get_data_dir` abfangen |
| `src/output/channels/base.py` | MODIFY | `get_channel` sms/premium_sms ohne Empfänger ⇒ klarer Block (wie S4a) |
| `src/app/config.py` | MODIFY | beide `base`-Rückgabepfade von `with_user_profile` ⇒ `sms_to=None` |
| `tests/helpers/sms_empfaenger.py` | CREATE | Helper nach Vorbild `telegram_empfaenger.py` (Profil mit bestätigter Nummer / Rückadresse, Ausgang-Fabriken) |
| `tests/tdd/test_sms_recipient_contract.py` | CREATE | Vertragstests, Sink am httpx-Rand, `is_test_mode=False`, zwei Nutzer |
| 14 Testdateien, die Outputs instanziieren | MODIFY | u. a. `test_success_status_guard.py`, `test_sms_test_isolation.py`, `test_channel_origin_guard_parity.py`, `unit/test_channel_blocked_missing_recipient.py`, `test_premium_sms_reply_future_timestamp.py`, `test_sms_versand_nur_bestaetigte_nummer.py`, `unit/test_premium_sms_versand.py`. **Live:** `tdd/test_issue_936_sms_stub.py`, `tdd/test_issue_608_sms_seven_io.py` (im Standardlauf unsichtbar, `-m live` mitfahren) |
| `docs/specs/modules/fix_1412_s4b_empfaengervertrag_sms.md` | CREATE | Spec (Phase 3) |

### Scope Assessment
- Files: ca. 8 produktiv, ca. 16 Tests
- Estimated LoC (produktiv): +180/−65, Größe wie S4a. Vor einem Override `workflow.py status` messen
- Risk Level: MEDIUM. Ein übersehener Aufrufer verstummt. Premium-SMS ist Alarmkanal in Trip und Ortsvergleich

### Technical Approach
1. **Zwei Typen statt einem** (Plan-Bewertung). `SmsRecipient` und `PremiumSmsRecipient` haben je eine Quelle
   (bestätigte Nummer vs. gelernte Rückadresse + TTL) und je eine `reason_code`-Familie. `verification` gibt es
   nur am SMS-Typ, Premium-SMS kennt ihn nicht.
2. **`SmsRecipient.for_user(user_id, settings)`** liest `sms_to` + `sms_verified_number` frisch aus `user.json`
   (getrimmt, gleich wie `config.py:439-443`), nie aus Settings. Kein Profil, unbestätigt oder leer ⇒
   `sms_no_recipient`.
3. **`PremiumSmsRecipient.for_user`** liest `premium_sms_reply_to/_at` frisch. Die Blocks fehlend / Zukunft /
   älter als 30 Tage behalten `premium_sms_no_reply_address` / `premium_sms_reply_address_stale` (Alarm-Buchung in
   `alert_log.py` hängt daran).
4. **`SmsRecipient.verification(user_id, number)`** ist eng gebunden: `strip(number) == strip(pending_sms_to or sms_to)`
   aus der frischen `user.json` (= Go `smsZielnummer`, `sms_verify.go:48-54`), dazu strikte E.164. Das
   `sms_verification.json` von Go wird bewusst **nicht** gelesen. Das würde Python an Go-Schema und Dateirechte koppeln,
   und der Gewinn wäre gering, weil die Nummer ohnehin nur über den Go-Profilfluss in `user.json` gelangt.
   Damit ist `req.to` keine freie Eingabe mehr und `verification` kein Generalschlüssel.
5. **Prüfort `_post`**, nicht `send`, mit S4a-Reihenfolge Form → Herkunft/Mismatch → Guards → Drossel. Sonst
   umgeht jeder künftige `_post`-Aufrufer die Prüfung. Die Sandbox-/Herkunfts-Guards (:108, :127) bleiben.
6. **Formprüfung:** `verification` strikt `^\+[1-9]\d{7,14}$`. `user_profile` (SMS) tolerant für den Altbestand:
   erlaubt sind Ziffern, `+`, Leerzeichen, `-`, `()`, 7–15 Ziffern. Gesendet wird die gespeicherte Form ohne Ziffernumbau,
   damit das byteidentisch nachgetragene Konto nicht ausgesperrt wird. Premium: `^\+?[1-9]\d{7,14}$`.
7. **Befehlsantwort per `user_profile`** (gelernte Rückadresse), kein neuer SMS-ContextVar. Begründung: Antwort nur
   im Lern-Erfolgspfad, dort ist sie identisch mit `sender`. Bei Kollision gibt es ohnehin keine Antwort. `user_profile`
   bindet zusätzlich an TTL und Konto, `inbound_reply` vertraute nur dem unbewiesenen `from`.
8. **Testmodus:** keine Test-Nummer nötig. Der Sandbox-Key sendet nie (`egress_guard_sms.md`). `for_user` liest auch im
   Testmodus das Profil.
9. **Bleibt vorerst:** `Settings.sms_to`/`can_send_sms()` als Bereitschaftsgate (7 Stellen). Entfernen ist eine
   Nachfolge-Aufgabe, nicht S4b.
10. **Nachweis:** Kern: echter Versandversuch an eine gesperrte/fremde Nummer, Sink am httpx-Rand, zwei Nutzer, ohne
    Profil ⇒ kein Versand an `GZ_SMS_TO`. Staging: echte SMS/Premium-SMS an die zweite seven.io-Nummer, Empfang
    selbst prüfbar (bewährter Weg). Achtung: Staging nutzt über `for_testing()` den Sandbox-Key. Wie der echte
    Staging-Versand dafür läuft, legt die Spec fest (bisheriges Rezept aus #2417 übernehmen).

### Dependencies
- Upstream: `app.loader.get_data_dir`, `ChannelBlockedError`, `SevenIoChannelBase._post`, Sandbox-/Herkunfts-Guards,
  Go `SaveUser` → `dispatchSmsVerificationCode`-Reihenfolge.
- Downstream: alle SMS-/Premium-SMS-Versandpfade (Briefing, Kein-Daten-Hinweis, Amtswarnung, Ortsvergleich,
  Vergleich-Amtswarnung, Alarme inkl. Regen/Radar, Befehlsantwort inReach, SMS-Bestätigungscode).

### Open Questions
- [x] Bestandsform der SMS-Nummern auf Prod → PO 2026-10-25: Zählung nicht nötig. Die tolerante
      `user_profile`-Regel macht die Spec davon unabhängig
- [x] Befehlsantwort `inbound_reply` vs. `user_profile` → `user_profile` (s. o.)
- [x] Bindung `verification` → frische `user.json`, nicht `sms_verification.json`
