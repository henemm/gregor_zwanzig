# S4b — Inventur für GREEN (aus Phase 5, 2026-10-25)

RED-Lauf: `tests/tdd/test_sms_recipient_contract.py` → 58 failed, 20 passed, 0 error
(`test-red-output.txt`). Grün und gewollt: AC-10 (18, Regressionswächter „nichts verstummt")
und AC-11 (2, echter Reader-Pfad). AC-9, AC-13, AC-14 Sandbox/Herkunft sind nur wegen der
neuen Namen rot und werden nach GREEN zu Regressionswächtern.

Helper: `tests/helpers/sms_empfaenger.py` — `profil_sms`, `profil_rueckadresse`, `zeitstempel`,
Migrationshilfen `mit_profil_sms`, `mit_profil_rueckadresse`, Fabriken `sms_ausgang`,
`verifikations_ausgang`, `premium_ausgang` (Profil-Default `tier: premium`).

## Testentscheidungen, die GREEN kennen muss

- AC-6 ruft den Routen-Handler (`internal.router` → `.endpoint`) direkt auf, nicht `TestClient`
  (dessen Event-Loop braucht `socketpair`, gesperrt durch `--disable-socket`). Eine entweichende
  Sperre (`OutputConfigError`/`ChannelBlockedError`) gilt als „nicht gesendet".
- „Drossel" = Zähler `sms_daily_limit`; beim Block muss die Reservierung per `release_reservation`
  zurückgegeben werden bzw. darf nicht verbraucht werden.
- AC-14 `ohne_empfaenger`: Empfängerprüfung muss VOR dem Sandbox-Key-Guard laufen (heute wirft der
  Guard zuerst ein schlichtes `OutputConfigError`), erwartet `ChannelBlockedError`.
- Form-/Mismatch-/Verifikations-Blocks: Tests verlangen nur, dass ein `reason_code` gesetzt ist.
  Fest vorgegeben: `sms_no_recipient`, `premium_sms_no_reply_address`, `premium_sms_reply_address_stale`.

## Bestandstests, die in GREEN umgestellt werden müssen

Direkte Instanziierung `SMSOutput(` / `PremiumSmsOutput(`:
- tests/tdd/test_adhoc_kurzform_verlauf.py
- tests/tdd/test_channel_metric_matrix.py
- tests/tdd/test_channel_origin_guard_parity.py
- tests/tdd/test_issue_608_sms_seven_io.py (live — zusätzlich mit `-m live` fahren)
- tests/tdd/test_issue_936_sms_stub.py (live — zusätzlich mit `-m live` fahren)
- tests/tdd/test_kurzform_zeigt_gefuehlte_temperatur.py
- tests/tdd/test_onset_shift_alert.py
- tests/tdd/test_sms_test_isolation.py
- tests/test_premium_sms_reply_future_timestamp.py
- tests/test_sms_versand_nur_bestaetigte_nummer.py
- tests/test_success_status_guard.py
- tests/unit/test_channel_blocked_missing_recipient.py
- tests/unit/test_premium_sms_versand.py

`get_channel("sms"/"premium_sms")`: tests/tdd/test_issue_608_sms_seven_io.py, tests/unit/test_premium_sms_versand.py

Ersatzklassen am Modulsymbol (brauchen Parameter `recipient=`):
- tests/helpers/transport_mitschrift.py
- tests/tdd/_official_alert_allclear_fixtures.py
- tests/tdd/test_briefing_anchor_survives_dispatch_failure.py
- tests/tdd/test_compare_premium_sms_versand.py
- tests/tdd/test_premium_sms_kommandopfad.py
- tests/tdd/test_sms_tageslimit.py

Widerspricht dem neuen Vertrag (umschreiben oder löschen):
- tests/test_sms_verification_code_endpoint.py::test_endpunkt_adressiert_nie_die_im_profil_gespeicherte_fremde_nummer

Kandidaten, einzeln prüfen (NotificationService über SMS/Premium mit Nummer nur in den Settings,
nicht bestätigt im Profil — verstummen in GREEN); sicher betroffen: test_sms_tageslimit.py.
- tests/helpers/: transport_mitschrift.py, trip_outlook_channels.py
- tests/tdd/: _befehl_e2e_fixtures.py, _einstellung_auslieferung_fixtures.py, test_alert_addendum_sms.py,
  test_alert_etappen_praefix_kurzform.py, test_alert_hour_rows.py, test_alert_preview_compare_paritaet.py,
  test_compare_alert_recipient_settings.py, test_compare_briefing_anchor_and_memory_reset.py,
  test_compare_premium_sms_versand.py, test_compare_radar_alert_telegram_style.py,
  test_inbound_email_sender_authentication.py, test_issue_1069_tier_channel_gating.py,
  test_kanaltreue_adhoc_antwort.py, test_onset_ende_kanalparitaet.py, test_onset_ende_textstellen.py,
  test_onset_menge_kanalparitaet.py, test_onset_reichweite_guete_kanalparitaet.py,
  test_premium_sms_kommandopfad.py, test_radar_alert_telegram_style.py,
  test_starkregen_kurzfristhinweis.py, test_trip_outlook_dispatch_mail.py
- tests/unit/: test_alert_channel_premium_sms.py, test_premium_sms_versand.py

Hinweis: `touched_tests_gate` blockt den GREEN-Commit, wenn ein `tests/unit/`-Test der berührten
Dateien rot wird — die Umstellung gehört in denselben Commit.
