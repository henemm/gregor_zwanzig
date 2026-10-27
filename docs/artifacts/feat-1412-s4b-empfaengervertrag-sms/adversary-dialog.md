# Adversary Dialog — feat-1412-s4b-empfaengervertrag-sms
Spec: docs/specs/modules/fix_1412_s4b_empfaengervertrag_sms.md
Datum: 2026-10-25 13:36

## Checkliste
- [x] **Input:** jeder SMS- oder Premium-SMS-Sendeversuch (Briefing, Hinweis, Amtswarnung,
- [x] **Output:** Die Nachricht geht nur an die belegte Nummer; sonst
- [x] **Side effects:** Logs nennen Nutzer-ID, nie die Telefonnummer. Alarm-Buchungen
- [x] **AC-1:** Given ein SMS-Ausgang, der ohne Empfänger-Objekt gebaut wurde / When er eine Nachricht senden soll / Then wird der Versand mit `ChannelBlockedError` (`reason_code=sms_no_recipient`) abgelehnt und es findet kein einziger HTTP-Versuch statt; dasselbe gilt für den Premium-SMS-Ausgang ohne Empfänger (dort mit dem bestehenden `reason_code=premium_sms_no_reply_address`, damit die Alarm-Buchung unverändert greift).
- [x] **AC-2:** Given ein Nutzer, dessen Nummer in der `user.json` hinterlegt, aber nicht bestätigt ist (`sms_verified_number` leer oder abweichend), oder dessen Nummer leer ist, oder der gar kein Profil hat / When für ihn per SMS gesendet werden soll / Then wird mit `reason_code=sms_no_recipient` geblockt, ohne HTTP-Versuch; bei bestätigter Nummer geht die SMS an genau diese, frisch aus der `user.json` gelesene Nummer.
- [x] **AC-3:** Given die `user.json` eines Nutzers fehlt oder ist unlesbar und in der `.env` ist eine globale Betreibernummer `GZ_SMS_TO` gesetzt / When für diesen Nutzer per SMS gesendet werden soll / Then wird geblockt und die Betreibernummer erhält nichts (Cross-Tenant-Lücke geschlossen); `with_user_profile` liefert in beiden `base`-Pfaden `sms_to=None`.
- [x] **AC-4:** Given Einstellungen, die per `model_copy` die Nummer eines anderen Nutzers tragen, während der Empfänger über die Fabrik für Nutzer B gebaut wurde / When gesendet wird / Then geht die SMS ausschließlich an die Nummer von B (frisch aus B's `user.json`), nie an die Nummer in den Settings; weicht die Nummer im Payload vom Empfänger ab, blockt der einzige Ausgang `_post` vor der Drossel mit Mismatch-Block und es gibt keinen HTTP-Versuch.
- [x] **AC-5:** Given ein Nutzer mit gelernter Premium-SMS-Rückadresse, die frisch ist / When ein Premium-SMS-Versand ausgelöst wird / Then geht die Nachricht nur an diese Rückadresse; fehlt die Rückadresse, liegt ihr Zeitstempel in der Zukunft oder ist er älter als 30 Tage, wird weiterhin mit `premium_sms_no_reply_address` bzw. `premium_sms_reply_address_stale` geblockt (Codes unverändert, damit die Alarm-Buchung weiter greift).
- [x] **AC-6:** Given der Verifikations-Endpunkt erhält von Go einen Bestätigungscode für eine Nummer / When die Nummer gleich `pending_sms_to` (bzw. `sms_to`) aus der frischen `user.json` dieses Nutzers und strikt E.164 ist / Then geht der Code an genau diese unbestätigte Nummer; bei jeder anderen Nummer (auch einer wohlgeformten fremden) wird geblockt, ohne HTTP-Versuch.
- [x] **AC-7:** Given der Premium-SMS-Kanal / When jemand versucht, dort den Zweck `verification` zu verwenden / Then ist das nicht möglich (der Zweck existiert nur am SMS-Typ), und `verification` wird nie zum Weg, mit dem ein Aufrufer an eine beliebige Nummer sendet.
- [x] **AC-8:** Given eine Nummer, die nicht der Form genügt (auch in Produktion, ohne Testmodus) / When gesendet werden soll / Then wird vor jedem HTTP-Versuch geblockt: `verification` verlangt strikt `^\+[1-9]\d{7,14}$`; die Nummer eines `user_profile`-SMS-Empfängers darf nur Ziffern, `+`, Leerzeichen, `-` und Klammern enthalten, mit 7 bis 15 Ziffern; Premium verlangt `^\+?[1-9]\d{7,14}$`.
- [x] **AC-9:** Given ein Bestandskonto, dessen bestätigte Nummer in einer tolerant geschriebenen Form gespeichert ist (z. B. mit Leerzeichen oder Bindestrichen) / When für diesen Nutzer gesendet wird / Then wird die SMS ausgeliefert und die **gespeicherte Form** unverändert an den Anbieter übergeben (kein Ausschluss, kein Ziffernumbau).
- [x] **AC-10:** Given alle produktiven Aufrufer (Briefing, Kein-Daten-Hinweis, Amtswarnung, Ortsvergleich, Ortsvergleich-Amtswarnung, Alarme) / When ein Nutzer mit bestätigter Nummer bzw. frischer Rückadresse eine Meldung auslöst / Then wird weiterhin ausgeliefert; es verstummt kein Weg. Das gilt für Premium-SMS-Alarme in Trip UND Ortsvergleich, einschließlich Regen- und Radar-Alarmen.
- [x] **AC-11:** Given ein Nutzer schickt einen Befehl per Premium-SMS über den echten Eingang `inbound_sms_reader`, und die Rückadresse wurde unmittelbar davor gelernt / When die Antwort gesendet wird / Then geht sie über den Profil-Empfänger an die gelernte Rückadresse (identisch mit dem Absender); lernt Go nicht (z. B. Kollision #2328, 409), gibt es keine Antwort.
- [x] **AC-12:** Given die Debug-CLI ohne Nutzer (globale `.env`) oder ein direkter `get_channel("sms")` / `get_channel("premium_sms")` / When der Kanal angefordert und gesendet wird / Then wird mit klarer Meldung abgelehnt, nicht still über `settings.sms_to` gesendet.
- [x] **AC-13:** Given zwei Nutzer A und B mit jeweils eigener bestätigter Nummer bzw. Rückadresse / When für beide gesendet wird, auch unmittelbar nacheinander in derselben Instanz / Then erreicht Nutzer A nie die Nummer von B und umgekehrt (Mandantentrennung, SMS und Premium-SMS).
- [x] **AC-14:** Given der Sandbox-Key-Guard und der Herkunfts-Guard (`_guard_code_origin`) / When ein Versand durch den neuen Empfängercheck läuft / Then greifen beide Guards weiterhin unverändert, und die Prüfreihenfolge in `_post` ist Form -> Herkunft -> Guards -> Drossel; ein geblockter Versuch verbraucht keinen Drosselplatz.

## Dialog

### Runde 1
**Adversary:** Diff gelesen (8 Produktivdateien), Vertragstests und Nachbardateien gelaufen: 149 passed (adversary-test-output.txt), Zusatzlauf live-markierte/Paritaet/Einzel-Waehlpunkt: 50 passed, 2 skipped (Live-Credentials fehlen).
Pruefpunkte:
- AC-1 PROVEN: src/output/channels/seven_io_base.py:114 blockt ohne Empfaenger-Typ mit NO_RECIPIENT_REASON (src/output/channels/sms.py:29 sms_no_recipient, src/output/channels/premium_sms.py:60 bestehender Premium-Code).
- AC-2/3 PROVEN: src/output/channels/recipient.py:134 liest frisch aus user.json; src/app/config.py:421 setzt sms_to=None in beiden base-Pfaden.
- AC-4 PROVEN: Mismatch in _post (src/output/channels/seven_io_base.py:117, Aufruf :185) vor httpx.post.
- AC-5 PROVEN: src/output/channels/premium_sms.py:70 check_reply_address, Codes/TTL (30 Tage, :50) unveraendert, aufgerufen aus src/output/channels/recipient.py:196.
- AC-6/7 PROVEN: src/output/channels/recipient.py:146 bindet an pending_sms_to or sms_to; Go validiert E.164 vor SaveUser (internal/handler/auth.go:1125, internal/store/e164.go:13) und sendet smsZielnummer (internal/handler/sms_verify.go:48): Vergleich passt. PremiumSmsRecipient (recipient.py:165) hat keine verification-Fabrik.
- AC-8/9 PROVEN: src/output/channels/recipient.py:106 und :125; gespeicherte Form unveraendert gesendet.
- AC-10 PROVEN: alle 13 Aufrufstellen in src/services/notification_service.py (:812, :835, :993, :1005, :1403, :1421, :1536, :1554, :1776, :1806, :2160, :2180, :2233) nutzen _sms_output() bzw. _premium_sms_output() (:638-650), jeweils im try. Suche ueber src/ api/ scripts/ cmd/: kein weiterer produktiver Aufrufer von SMSOutput, PremiumSmsOutput oder get_channel fuer sms/premium_sms; api/routers/internal.py:195 umgestellt; src/app/cli.py:256-282 geht ueber get_channel und blockt jetzt bewusst (src/output/channels/base.py:123).
- AC-11/12/13 PROVEN (Reader-Pfad ueber notification_service.py:2233; get_channel wirft OutputConfigError).
- AC-14: Die Reihenfolgeaenderung des Entwicklers ist ZULAESSIG. Spec Kernregel 6 und AC-14 verlangen Form -> Herkunft -> Guards -> Drossel; die alte Reihenfolge (Sandbox vor Herkunft) steht nicht in der Spec. Beide Guards unveraendert (seven_io_base.py:129-170), beide werfen OutputConfigError, kein neuer Fehlerpfad. Drossel: _sms_gate_reserve liegt vor dem try, Empfaenger-Bau im try, release_reservation im except an allen Stellen: produktiv korrekt, getestet aber nur an einer Stelle (F001).
- Verifikations-Endpunkt: Block liefert HTTP 403 sms_recipient_blocked (api/routers/internal.py:197); Go wertet jeden Nicht-2xx als Fehler, loggt, laesst den Code gueltig (internal/handler/sms_verify.go:104). Sinnvoll; 422 sms_not_configured bleibt (internal.py:189).
- Logs: nennen Nutzer-ID (seven_io_base.py:111, :218; recipient.py:160), aber kein Test haelt "nie die Nummer" fest (F002).

Findings:
- F001 (MEDIUM, edge_case): src/services/notification_service.py:812 (und :835, :993, :1005, :1403, :1421, :1536, :1554, :1776, :1806, :2160, :2180, :2233). Spec: Der Empfaenger wird an allen Stellen im try nach _sms_gate_reserve gebaut. Mutation: Empfaenger-Bau vor das try gezogen an Briefing-SMS (:812), Alarm-SMS (:2160), Alarm-Premium (:2180), Befehlsantwort (:2233): je 149 passed. Nur der Kein-Daten-Hinweis wird auf "Block verbraucht keinen Drosselplatz" geprueft (tests/tdd/test_sms_recipient_contract.py:368, :1012). Im Ernstfall wuerde ein Block die Reservierung nicht freigeben und den Aufruf abbrechen.
  Code reference: src/services/notification_service.py:812
- F002 (MEDIUM, edge_case): src/output/channels/seven_io_base.py:218 und :111. Expected Behavior: Logs nennen Nutzer-ID, nie die Telefonnummer. Mutationen k1 (Erfolgslog mit Nummer) und k2 (Blocklog mit Nummer): je 149 passed. Kein caplog in Vertragsdatei oder Endpunkttest.
  Code reference: src/output/channels/seven_io_base.py:221
- F003 (LOW, anti_pattern): src/output/channels/recipient.py:124 (SmsRecipient.__post_init__, analog PremiumSmsRecipient). Kernregel 1: nur ueber Fabriken erzeugbar. Mutation r (TypeError -> pass): 149 passed.
  Code reference: src/output/channels/recipient.py:126
- F004 (LOW, anti_pattern): src/output/channels/base.py:123. test_ac12 akzeptiert auch ValueError und prueft nur den Kanalnamen; Mutation w (Zweig entfernt, "Unknown output channel: sms") bleibt im Vertragstest gruen, faellt nur im Bestandstest tests/unit/test_premium_sms_versand.py::test_channel_name_premium_sms_resolves_to_the_premium_channel. Ebenso faengt test_ac5 [31_tage] TTL+1 Tag nicht (nur die Unit-Tests).
  Code reference: src/output/channels/base.py:123
**Implementierer:** (offen, Rueckmeldung des Orchestrators auf F001-F004 steht aus)

### Runde 2
**Adversary:** Gegenprobe zur Reihenfolge-Abweichung. Mutation i (Empfaengercheck hinter die Guards): test_ac14_empfaengerpruefung_laeuft_vor_herkunft_und_guards[ohne_empfaenger|unfoermig] rot. Mutation i2 (Sandbox-Guard entfernt): test_ac14_sandbox_guard_im_testmodus_bleibt_wirksam rot. Zweite Frage, an der Wirkstelle geprueft: Premium-Fallback auf Settings (uv) rot in drei Tests; with_user_profile beide base-Pfade rot (ac3[fehlt], ac3[kaputt]); Status 403->200 rot im Endpunkttest. c2 (pending/sms_to vertauscht) faengt nur der Endpunkttest, also die Wirkstelle. Ergebnis: Produktivcode ohne Defekt, aber F001/F002 sind Zusicherungen ohne Waechter.
**Implementierer:** (offen)

### Runde 3 (Re-Verify nach Fix-Loop 1)
**Adversary:** Produktivdateien unveraendert (byte-gleich mit den Sicherungen). Neue/verschaerfte Tests in tests/tdd/test_sms_recipient_contract.py gelesen und auf Wirkstelle geprueft:
- test_f001_block_an_jedem_aufrufer_gibt_die_reservierung_frei_und_bricht_nicht_ab: laeuft ueber alle 9 echten Aufrufer x sms/premium_sms plus Befehlsantwort durch den echten NotificationService, prueft Sink leer und Tageszaehler unveraendert, also dort, wo es wirkt. F001 BEHOBEN.
- test_f002_logs_nennen_die_nutzer_id_nie_die_nummer: caplog ueber Erfolg und drei Blockfaelle, Ziffernfolge-Vergleich (faengt auch Formatvarianten), Erfolgslog muss Nutzer-ID nennen. F002 BEHOBEN.
- test_f003_empfaenger_sind_nur_ueber_die_fabriken_erzeugbar: Direktkonstruktion mit und ohne falschem Schluessel wirft TypeError. F003 BEHOBEN.
- test_ac12 (src/output/channels/base.py:123): verengt auf OutputConfigError beim Anfordern, Kanalname geprueft. test_f004_frist_der_rueckadresse_ist_genau_30_tage: 29 Tage geht raus, 30 Tage + 1 Stunde blockt (src/output/channels/premium_sms.py:70). F004 BEHOBEN.
Mutationen erneut gefahren (Ergebnis siehe Tabelle Runde 3), jede rot im passenden Test, Restore je per Byte-Vergleich bestaetigt. Neuer Lauf: 172 passed (adversary-test-output.txt, Abschnitt Runde 3). Keine neuen Findings. Zitierte Produktivdateien: api/routers/internal.py:191, src/app/config.py:421, src/output/channels/base.py:123, src/output/channels/premium_sms.py:70, src/output/channels/recipient.py:124, src/output/channels/seven_io_base.py:111, src/output/channels/sms.py:29, src/services/notification_service.py:638.
**Implementierer:** Fix-Loop 1 nur Tests, siehe oben.

## Mutationstabelle

| ID | Mutation | Datei | Rot | Urteil |
|---|---|---|---|---|
| a | Mismatch-Pruefung in _post entfernt | seven_io_base.py | test_ac4_abweichendes_payload_ziel_blockt_im_einzigen_ausgang[sms,premium_sms] (2) | gefangen |
| b1 | Rueckfall auf settings.sms_to in for_user | recipient.py | ac4 (dienst_mit_model_copy, ausgang_ignoriert_settings, drosselplatz), ac2, ac9, ac13 u. a. (25) | gefangen |
| c | Verification akzeptiert jede Nummer | recipient.py | test_ac6_fremde_unfoermige_oder_profillose_nummer_blockt[fremd,kein_profil], ac6, ac7, Endpunkttest (5) | gefangen |
| c2 | Bindung sms_to vor pending_sms_to | recipient.py | nur test_sms_verification_code_endpoint.py::test_endpunkt_adressiert_nie_die_im_profil_gespeicherte_fremde_nummer | gefangen (Wirkstelle) |
| d | Formpruefung nur im Testmodus | seven_io_base.py | test_ac8_... und test_ac6_...[ohne_plus] (17) | gefangen |
| e1 | Empfaenger-Bau vor try (Alarm-SMS :2160) | notification_service.py | keiner (149 passed) | UEBERLEBT (F001) |
| e1b | dito Briefing-SMS (:812) | notification_service.py | keiner | UEBERLEBT (F001) |
| e1p | dito Alarm-Premium (:2180) | notification_service.py | keiner | UEBERLEBT (F001) |
| e1r | dito Befehlsantwort (:2233) | notification_service.py | keiner | UEBERLEBT (F001) |
| e2 | release_reservation am Alarm-SMS-Block entfernt | notification_service.py | test_sms_tageslimit.py::test_f002_rollback_bei_transportfehler_an_weiteren_sendestellen[radar_sms] | gefangen |
| f1 | with_user_profile ohne Profil: base statt sms_to=None | config.py | test_ac3_...[fehlt] | gefangen |
| f2 | dito bei kaputtem Profil | config.py | test_ac3_...[kaputt] | gefangen |
| g1 | Premium-TTL 30 -> 31 Tage | premium_sms.py | test_premium_sms_versand.py::test_reply_to_older_than_ttl_blocks_send, test_the_two_block_cases_carry_distinct_machine_codes (Vertragstest nicht) | gefangen |
| g2 | Zukunfts-Check entfernt | premium_sms.py | test_ac5_...[zukunft-premium_sms_reply_address_stale] | gefangen |
| h | Alarm-SMS wieder auf nackten SMSOutput(self._settings) | notification_service.py | test_ac10_kein_produktiver_aufrufer_verstummt[alarm_trip,alarm_ortsvergleich,regen_radar_trip,regen_radar_ortsvergleich-sms] (4) | gefangen |
| i | Empfaengercheck hinter die Guards | seven_io_base.py | test_ac14_empfaengerpruefung_laeuft_vor_herkunft_und_guards[ohne_empfaenger,unfoermig] | gefangen |
| i2 | Sandbox-Guard in send entfernt | seven_io_base.py | test_ac14_sandbox_guard_im_testmodus_bleibt_wirksam | gefangen |
| k1 | Erfolgslog nennt Nummer statt Nutzer-ID | seven_io_base.py | keiner | UEBERLEBT (F002) |
| k2 | Blocklog haengt Nummer an | seven_io_base.py | keiner | UEBERLEBT (F002) |
| l | Verifikations-Block 403 -> 200 | internal.py | test_endpunkt_adressiert_nie_die_im_profil_gespeicherte_fremde_nummer | gefangen |
| m | Premium ohne Empfaenger: anderer reason_code | premium_sms.py | test_ac1_premium_ohne_empfaenger_wird_geblockt_ohne_http, test_ac1_einziger_ausgang_post_blockt_ohne_empfaenger[premium_sms] | gefangen |
| r | Fabrik-Schluesselpruefung entfernt | recipient.py | keiner | UEBERLEBT (F003) |
| t | Bestaetigungs-Check (sms_verified_number) entfernt | recipient.py | test_ac2_...[unbestaetigt,abweichend], ac4 Drossel, ac14 Drossel[sms], test_sms_versand_nur_bestaetigte_nummer.py (6) | gefangen |
| uv | Premium-Fallback auf Settings (Nummer + Zeitstempel) | recipient.py | test_ac5_...[fehlend], test_ac5_alarm_buchung_...[fehlend], test_ac14_geblockter_versuch_...[premium_sms] | gefangen |
| w | get_channel-Block entfernt | base.py | nur Bestandstest test_premium_sms_versand.py::test_channel_name_premium_sms_resolves_to_the_premium_channel; Vertragstest test_ac12_... gruen (F004) | gefangen (Bestandstest) |

Alle Mutationen per String-Ersetzung mit Sicherungskopie im Scratchpad; nach jeder wurde der Originalstand per Byte-Vergleich bestaetigt (RESTORED_OK).


### Mutationen Runde 3 (Re-Verify)

| ID | Mutation | Rot | Urteil |
|---|---|---|---|
| e1 | Empfaenger-Bau vor try, Alarm-SMS :2160 | test_f001_...[alarm_trip,alarm_ortsvergleich,regen_radar_trip,regen_radar_ortsvergleich-sms] (4) | behoben |
| e1b | dito Briefing-SMS :812 | test_f001_...[briefing-sms] | behoben |
| e1p | dito Alarm-Premium :2180 | test_f001_...[alarm_trip,alarm_ortsvergleich,regen_radar_trip,regen_radar_ortsvergleich-premium_sms] (4) | behoben |
| e1r | dito Befehlsantwort :2233 | test_f001_...[befehlsantwort-premium_sms] | behoben |
| k1 | Erfolgslog nennt Nummer | test_f002_logs_nennen_die_nutzer_id_nie_die_nummer (Grund: Erfolgslog ohne Nutzer-ID) | behoben |
| k2 | Blocklog haengt Nummer an | test_f002_logs_nennen_die_nutzer_id_nie_die_nummer (Grund: Nummer im Log) | behoben |
| r | Fabrik-Schluesselpruefung entfernt | test_f003_empfaenger_sind_nur_ueber_die_fabriken_erzeugbar | behoben |
| w | get_channel-Block entfernt | test_ac12_...[sms], test_ac12_...[premium_sms], plus Bestandstest | behoben |
| g1 | TTL 30 -> 31 Tage | test_f004_frist_der_rueckadresse_ist_genau_30_tage[alter1-True], plus 2 Unit-Tests | behoben |
| a | Stichprobe: Mismatch-Pruefung entfernt | test_ac4_abweichendes_payload_ziel_blockt_im_einzigen_ausgang[sms,premium_sms], test_f002 | weiter gefangen |
| c | Stichprobe: Verification akzeptiert jede Nummer | test_ac6_..., test_ac7_..., Endpunkttest (5) | weiter gefangen |

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Die Vorbedingungen (Go schreibt user.json vor dem Python-Aufruf, E.164-Pruefung in Go vor dem Speichern) wurden am Code belegt: internal/handler/auth.go:1125, internal/handler/auth.go:1410, internal/handler/sms_verify.go:48, internal/store/e164.go:13.

## Confirmations

- AC-1: Ohne Empfaenger Block ohne HTTP
  Status: CONFIRMED
  Code reference: src/output/channels/seven_io_base.py:111
- AC-2: Nur bestaetigte Profilnummer, frisch gelesen
  Status: CONFIRMED
  Code reference: src/output/channels/recipient.py:137
- AC-3: Ohne Profil kein Betreiber-Rueckfall, sms_to=None
  Status: CONFIRMED
  Code reference: src/app/config.py:424
- AC-4: Mismatch-Block in _post vor Drossel
  Status: CONFIRMED
  Code reference: src/output/channels/seven_io_base.py:115
- AC-5: Premium-Rueckadresse mit unveraenderten Codes und TTL
  Status: CONFIRMED
  Code reference: src/output/channels/premium_sms.py:70
- AC-6: Verifikationscode nur an die gebundene Nummer
  Status: CONFIRMED
  Code reference: api/routers/internal.py:194
- AC-7: Zweck verification nur am SMS-Typ
  Status: CONFIRMED
  Code reference: src/output/channels/recipient.py:168
- AC-8: Formpruefung bedingungslos je Kanal
  Status: CONFIRMED
  Code reference: src/output/channels/recipient.py:130
- AC-9: Gespeicherte tolerante Form unveraendert
  Status: CONFIRMED
  Code reference: src/output/channels/recipient.py:137
- AC-10: Alle Aufrufer auf Empfaenger-Fabrik umgestellt
  Status: CONFIRMED
  Code reference: src/services/notification_service.py:638
- AC-11: Befehlsantwort ueber Profil-Empfaenger
  Status: CONFIRMED
  Code reference: src/services/notification_service.py:2233
- AC-12: get_channel lehnt sms/premium_sms ab
  Status: CONFIRMED
  Code reference: src/output/channels/base.py:123
- AC-13: Mandantentrennung, frisch je Aufruf
  Status: CONFIRMED
  Code reference: src/output/channels/recipient.py:137
- AC-14: Reihenfolge Form, Herkunft, Guards, Drossel
  Status: CONFIRMED
  Code reference: src/output/channels/seven_io_base.py:203
- Zusatz: RECIPIENT_TYPE und NO_RECIPIENT_REASON des SMS-Kanals
  Status: CONFIRMED
  Code reference: src/output/channels/sms.py:29

## Verdict
**VERIFIED** (nach Fix-Loop 1)

- F001 behoben, F002 behoben, F003 behoben, F004 behoben. Keine offenen Findings.
- Tests: 172 passed, 0 failed (Vertragsdatei + 4 Begleitdateien). Alle zuvor ueberlebenden Mutationen werden jetzt von einem passenden Test gefangen.
- Hinweis: die frueheren Verdict-Zeilen (BROKEN, Runde 1/2) gelten fuer den Stand vor Fix-Loop 1.

## Geprüfte Dateien

- sha256:972a91b078db0092678a1914e4b59e8c9d38c81d64a78348e1ad0f8e0434c5b5  src/output/channels/base.py
- sha256:bc37c9d74e20fc284e30cf692345810fc8bab7187808b4ea4d0a7c0372eee1ef  src/output/channels/recipient.py
- sha256:31ce485294c1635a0ad20260096aadae6d7fbdd9c1ad0fec2dbe2cac7be4a77b  src/output/channels/seven_io_base.py
- sha256:e277e8379b807e10a060291c05f17f64a1bb8c64f20afab706dbe0593d1f9080  src/services/notification_service.py

## Prüfbasis

- base: 692d0486a04f29565f80d0ada9d62bf2e7d35cc3
- blob:4e69c321d03a648c0ea6aeb1a036d0acfda0013f  src/output/channels/base.py
- blob:f97866a35e7f8c3ccb9439d4c27b11979057b5ff  src/output/channels/recipient.py
- blob:c024461d27095803a2d0fde911c8e9064db9ede3  src/output/channels/seven_io_base.py
- blob:124a486f131e9617c1746ac03042ab36d62f1c0f  src/services/notification_service.py

## Geprüfte Dateien

- sha256:e9e2952a0fef51c3f4b83970bc9016651cf5dca6fee08ec9bd41ba5bbaa9ca27  api/routers/internal.py
- sha256:fe4e563cd2791697b991c435b5ea4707947674f1aa8352b5f9f7d004a4e4e960  src/app/config.py
- sha256:972a91b078db0092678a1914e4b59e8c9d38c81d64a78348e1ad0f8e0434c5b5  src/output/channels/base.py
- sha256:5b768ca9db2b76b08644bcfa04e756f9438c6a57d0ba6e0bdb13f6123a256605  src/output/channels/premium_sms.py
- sha256:bc37c9d74e20fc284e30cf692345810fc8bab7187808b4ea4d0a7c0372eee1ef  src/output/channels/recipient.py
- sha256:31ce485294c1635a0ad20260096aadae6d7fbdd9c1ad0fec2dbe2cac7be4a77b  src/output/channels/seven_io_base.py
- sha256:fee2390149068e7d443f8bf59f2d8838233abb92779d298a90b8b21ea391aba6  src/output/channels/sms.py
- sha256:e277e8379b807e10a060291c05f17f64a1bb8c64f20afab706dbe0593d1f9080  src/services/notification_service.py

## Prüfbasis

- base: 692d0486a04f29565f80d0ada9d62bf2e7d35cc3
- blob:3a311684b59bc70cf1017757cb782a7c7da85517  api/routers/internal.py
- blob:274e4c5e341081d8417ba215eb1842eb7a8c9909  src/app/config.py
- blob:4e69c321d03a648c0ea6aeb1a036d0acfda0013f  src/output/channels/base.py
- blob:920ba033c472e30b0e590175fc957ae2e8e733b5  src/output/channels/premium_sms.py
- blob:f97866a35e7f8c3ccb9439d4c27b11979057b5ff  src/output/channels/recipient.py
- blob:c024461d27095803a2d0fde911c8e9064db9ede3  src/output/channels/seven_io_base.py
- blob:b19d49cea2fe0068d79e5e0aec4a621317e7e074  src/output/channels/sms.py
- blob:124a486f131e9617c1746ac03042ab36d62f1c0f  src/services/notification_service.py

## Geprüfte Dateien

- sha256:e9e2952a0fef51c3f4b83970bc9016651cf5dca6fee08ec9bd41ba5bbaa9ca27  api/routers/internal.py
- sha256:fe4e563cd2791697b991c435b5ea4707947674f1aa8352b5f9f7d004a4e4e960  src/app/config.py
- sha256:972a91b078db0092678a1914e4b59e8c9d38c81d64a78348e1ad0f8e0434c5b5  src/output/channels/base.py
- sha256:5b768ca9db2b76b08644bcfa04e756f9438c6a57d0ba6e0bdb13f6123a256605  src/output/channels/premium_sms.py
- sha256:bc37c9d74e20fc284e30cf692345810fc8bab7187808b4ea4d0a7c0372eee1ef  src/output/channels/recipient.py
- sha256:31ce485294c1635a0ad20260096aadae6d7fbdd9c1ad0fec2dbe2cac7be4a77b  src/output/channels/seven_io_base.py
- sha256:fee2390149068e7d443f8bf59f2d8838233abb92779d298a90b8b21ea391aba6  src/output/channels/sms.py
- sha256:e277e8379b807e10a060291c05f17f64a1bb8c64f20afab706dbe0593d1f9080  src/services/notification_service.py

## Prüfbasis

- base: 692d0486a04f29565f80d0ada9d62bf2e7d35cc3
- blob:3a311684b59bc70cf1017757cb782a7c7da85517  api/routers/internal.py
- blob:274e4c5e341081d8417ba215eb1842eb7a8c9909  src/app/config.py
- blob:4e69c321d03a648c0ea6aeb1a036d0acfda0013f  src/output/channels/base.py
- blob:920ba033c472e30b0e590175fc957ae2e8e733b5  src/output/channels/premium_sms.py
- blob:f97866a35e7f8c3ccb9439d4c27b11979057b5ff  src/output/channels/recipient.py
- blob:c024461d27095803a2d0fde911c8e9064db9ede3  src/output/channels/seven_io_base.py
- blob:b19d49cea2fe0068d79e5e0aec4a621317e7e074  src/output/channels/sms.py
- blob:124a486f131e9617c1746ac03042ab36d62f1c0f  src/services/notification_service.py
