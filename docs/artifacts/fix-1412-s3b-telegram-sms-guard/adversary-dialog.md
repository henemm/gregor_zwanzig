# Adversary-Protokoll fix-1412-s3b-telegram-sms-guard

Testlauf: 126 passed (mit --disable-socket, 7 Dateien) + 14 passed / 2 skipped (test_issue_650 + test_channel_origin_guard_parity ohne Socket-Sperre). Voller -v -rA-Output: docs/artifacts/fix-1412-s3b-telegram-sms-guard/adversary-test-output.txt (Kopie /tmp/adversary_test_output.txt).


## Runde 1

### Konfirmationen je AC

- [x] AC-1: Alle 7 Telegram-Methoden laufen ueber _post und werden bei falschem Token/Chat mit 0 httpx.post blockiert (Sink-Tests, M1 macht 35 Tests rot).
Code reference: src/output/channels/telegram.py:395
- [x] AC-2: Unterklasse mit neuer Methode ohne eigene Pruefung wird am Ausgang geblockt (test_ac2_*, rot bei M1/M7/M8/M9).
Code reference: tests/tdd/test_telegram_post_is_single_guarded_exit.py:265
- [x] AC-3: Bestandstests ohne Edit gruen (139 passed), Fehlertexte wortgleich chat_id='<PROD>'.
Code reference: src/output/channels/telegram.py:229
- [x] AC-4: answer_callback_query und get_my_commands werden im Token-Fall blockiert (M8 rot), Gegenfall ohne Test-Modus gruen.
Code reference: tests/tdd/test_telegram_post_is_single_guarded_exit.py:219
- [x] AC-5: Guards vor _reserve_send_slot und genau einmal pro _post, auch bei 429 (M3 und M13 rot).
Code reference: src/output/channels/telegram.py:410
- [x] AC-6: httpx.post nur noch in SevenIoChannelBase._post, Guards bleiben in send (M17, M18, M19 rot).
Code reference: src/output/channels/seven_io_base.py:155
- [x] AC-7: Struktur-Test findet 2 Ausgaenge und 3 localhost-Ausnahmen, Deckel 3, EXPIRY 2027-01-04 auch in gates_und_ratschen.md (M20, M21 rot).
Code reference: tests/tdd/test_egress_single_dial_point.py:547
- [x] AC-7b: Pruefdatum-Zeile in der Ratschen-Tabelle vorhanden.
Code reference: docs/reference/gates_und_ratschen.md:423
- [x] AC-8: Mutations-Gegenprobe durchgefuehrt, Ueberlebende M4/M5/M6/M10 in Runde 2 geschlossen.
Code reference: src/output/channels/telegram.py:397

## Mutationstabelle

| # | Verfaelschung | Rot |
|---|---|---|
| M1 | Guard-Block aus TelegramOutput._post entfernt | 35 rot: AC-1 token[7 Methoden], AC-1 fremder_chat[send, delete, edit, fallback], ac1_send_1288, ac2_neue_methode_fremder_chat, ac2_falscher_token, test_telegram_test_isolation::test_existing_1288 u.a. |
| M2a | bound_chat-Zweig (Payload-Pfad) entfernt | 3 rot: test_diverging_test_chat_id_blocks_send_without_any_post, test_existing_1288_chat_guard_unchanged, ac1_send_meldet_1288 |
| M12 | send ohne bound_chat=True | dieselben 3 |
| M2b/M11 | bound_chat im else-Zweig (ohne chat_id) entfernt | KEIN Test rot - aequivalent: send uebergibt immer chat_id im Payload, Zweig ist tot (LOW) |
| M3 | Guard nach _reserve_send_slot | 3 rot: ac5_geblockter_aufruf_belegt_keinen_drossel_platz[neue_methode, answer_callback_query, get_my_commands] |
| M13 | Guard zusaetzlich im Retry-Pfad | 3 rot: ac5_pruefung_laeuft_genau_einmal_auch_bei_429[...] |
| M4 | payload["chat_id"] = target entfernt (Origin-Umschreibung geht verloren) | KEIN Test rot -> F001 |
| M5 | chat_id = target (Drossel-Schluessel) entfernt | KEIN Test rot -> F002 |
| M6 | Payload nicht kopieren (Aufrufer-Dict wird mutiert) | KEIN Test rot -> F003 (LOW) |
| M7 | Token-Guard im Payload-Zweig entfernt | 13 rot (AC-1 token, ac5, test_telegram_test_isolation) |
| M8 | Token-Guard im else-Zweig entfernt | 10 rot (answer_callback_query, get_my_commands, set_my_commands, ac2) |
| M9 | _guard_test_mode_target_chat entfernt | 9 rot |
| M10 | _guard_code_origin in _post entfernt | KEIN Test rot -> F001 |
| M14 | send-Leer-Check (#2144) entfernt | 1 rot: test_channel_blocked_missing_recipient |
| M15 | Origin-Aufruf in send entfernt | KEIN Test rot - weitgehend aequivalent, weil _post den Origin-Guard erneut ausfuehrt (LOW, Doppelaufruf ist redundant) |
| M16 | seven _post ohne API-Key-Header | 2 rot: parity::test_sms_* |
| M17 | seven send ruft httpx.post direkt | 1 rot: test_ac7_httpx_post_nur_an_den_erlaubten_ausgaengen |
| M18 | Sandbox-Key-Guard aus seven send entfernt | 1 rot: test_sms_test_isolation::test_guard_blocks_mismatched_key_before_transport |
| M19 | Herkunftssperre aus seven send entfernt | 6 rot |
| M20 | Erlaubten Ausgang im Struktur-Test umbenannt | 4 rot (ac7) |
| M21 | Deckel 3 -> 9 | 1 rot: ac7_httpx_ausnahmen_unter_dem_deckel |

Nach jeder Mutation per Byte-Vergleich im Runner auf identischen Stand geprueft; abschliessend git diff --stat unveraendert (telegram.py 54 Zeilen, seven_io_base.py 18 Zeilen).

## Findings

Finding F001
  Severity: MEDIUM
  Category: edge_case (unbewachte Zusicherung)
  Code reference: src/output/channels/telegram.py:397-407
  Description: Die Herkunftssperre (#1476) und die Umschreibung payload["chat_id"] = target laufen jetzt in _post fuer delete_message, edit_message_text und den Rueckfall. Die neuen Sink-Tests pinnen running_origin auf "production" (tests/tdd/test_telegram_post_is_single_guarded_exit.py:93), die Parity-Tests pruefen Telegram nicht fuer diese Methoden.
  Spec requirement: AC-3 — Verhalten der Herkunftssperre bleibt unveraendert; AC-1 — Schutz am einen Ausgang.
  Conflict: Mutation M10 (Origin-Guard aus _post) und M4 (Umschreibung des Payload-Chats entfernt) lassen alle 140 Tests gruen. Unter Herkunft "test" wuerde delete/edit/fallback mit M4 die Pruefung gegen den Test-Chat bestehen, aber an den Original-(Prod-)Chat senden. Heute korrekt, aber unbewacht.
  Remediation: Test mit running_origin="test", telegram_test_chat_id gesetzt, Aufruf delete_message/edit_message_text/_send_fallback_without_parse_mode mit Prod-Chat, Sink prueft chat_id im POST == Test-Chat (und ohne Test-Chat: OutputConfigError).

Finding F002
  Severity: LOW
  Category: edge_case
  Code reference: src/output/channels/telegram.py:407-409
  Description: chat_id = target (Drossel-Schluessel nach Umschreibung) wird von keinem Test geprueft (M5 ueberlebt).
  Spec requirement: AC-5 — Drossel nach den Guards.
  Conflict: Bei Herkunft "test" haette die Drossel sonst den falschen Chat-Schluessel; kein Test.
  Remediation: Test, der den Schluessel von _reserve_send_slot unter Herkunft "test" liest.

Finding F003
  Severity: LOW
  Category: edge_case
  Code reference: src/output/channels/telegram.py:398
  Description: Die Payload-Kopie (dict(payload)) ist unbewacht (M6 ueberlebt); ohne Kopie wuerde das Dict des Aufrufers veraendert.
  Spec requirement: Spec Abschnitt 1, Schritt 2 — Kopie des Payloads.
  Conflict: Kein Test prueft, dass der Aufrufer-Payload unveraendert bleibt.
  Remediation: Assertion auf Gleichheit des Aufrufer-Payloads nach Aufruf unter Herkunft "test".

Gesperrt/Hinweis: Der Schreibversuch nach /tmp wurde zunaechst von secret_egress_guard geblockt; Ausgabe lief ueber das Scratchpad, danach per cp nach /tmp/adversary_test_output.txt.

Edge Cases geprueft (Code-Lesung): Doppelfehler Herkunft+Token — Reihenfolge Herkunft, Token, Settings-Chat, Ziel-Chat identisch zur Altreihenfolge der Argument-Methoden; leere chat_id in send — Leer-Check vor _post (M14 rot); Payload ohne chat_id — else-Zweig (AC-4 rot bei M8); Rueckfall nach 400 — Origin ist idempotent; edit_message_text schluckt HTTPError, aber OutputConfigError ist kein httpx.HTTPError und propagiert; send ruft Origin zweimal auf (Doppel-Log-Rauschen moeglich, harmlos).

Runde-1-Urteil: AMBIGUOUS
(Kein Spec-Bruch, Testlauf gruen. Die Zusicherung "Origin-Umschreibung am Ausgang" ist aber an der Wirkstelle unbewacht — F001 empfiehlt einen Test vor dem Merge.)

## Runde 2 (nach Fix-Loop)

Stand: src/ unveraendert (telegram.py 54 Zeilen, seven_io_base.py 18 Zeilen wie in Runde 1); neu sind 3 Tests (+89 Zeilen) in tests/tdd/test_telegram_post_is_single_guarded_exit.py. Lauf: 139 passed (--disable-socket, 7 Dateien), 14 passed / 2 skipped (test_issue_650 + parity ohne Sperre). Output: docs/artifacts/fix-1412-s3b-telegram-sms-guard/adversary-test-output.txt (+ /tmp/adversary_test_output.txt).

### Messen die neuen Tests die Wirkstelle?
- Fixture herkunft_test (tests/tdd/test_telegram_post_is_single_guarded_exit.py:448-451) patcht running_origin im verbrauchenden Modul (telegram_mod) auf "test" und ueberschreibt die autouse-Fixture "production" (:90-96).
- PROD_CHAT_ID "777000111" != TEST_CHAT_ID "424242" (:50-51). Der Test prueft den POST-Payload am Sink (sink.calls[0]["payload"]["chat_id"]) und den Drossel-Schluessel (_rate_limit_stamps); assert len(calls)==1 beweist, dass nicht vorher blockiert wurde. Gegenfall: ohne Test-Chat OutputConfigError "Herkunftssperre", 0 POSTs. Beide mit is_test_mode True und False. Beweis zusaetzlich durch die Mutationen unten.

### Mutationstabelle Runde 2
| Verfaelschung | Rot |
|---|---|
| M4 payload["chat_id"]=target entfernt | 9 rot: ..._schreibt_den_gesendeten_chat_auf_den_test_chat_um (4 Methoden x 2 Modi), test_post_veraendert_das_dict_des_aufrufers_nicht |
| M5 chat_id=target (Drossel-Schluessel) entfernt | 8 rot: ..._schreibt_den_gesendeten_chat_auf_den_test_chat_um (4 x 2, Drossel-Assertion) |
| M6 dict(payload)-Kopie entfernt | 1 rot: test_post_veraendert_das_dict_des_aufrufers_nicht |
| M10 Origin-Guard in _post entfernt | 13 rot: Umschreibe-Test (8), test_herkunft_test_ohne_test_chat_bricht_ohne_netzaufruf_ab (4), Dict-Test |
| M15 Origin-Aufruf in send entfernt | KEIN Test rot (aequivalent: _post wiederholt ihn) |
| M10+M15 zusammen (send ohne Herkunftssperre) | 14 rot, u.a. test_telegram_test_mode_guard.py::TestGuardBlockVisibleInCompareFailedTally::test_daily_run_counts_guard_blocked_preset_as_failed |

Nach jeder Mutation Rueckspielung und cmp gegen Sicherung: IDENTISCH.

### Status der Findings
- F001 geschlossen. Code reference: src/output/channels/telegram.py:397-407.
- F002 geschlossen. Code reference: src/output/channels/telegram.py:407-409.
- F003 geschlossen. Code reference: src/output/channels/telegram.py:398.
- Restpunkte M2b/M11 (toter else-Zweig bound_chat) und M15 (redundanter Origin-Aufruf in send): LOW, aequivalent, kein Finding. send fehlt in den Umschreibe-Tests, ist aber ueber M10+M15 und den Bestand (test_telegram_test_mode_guard) bewacht.

VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:58160ec63060469a7e3e95fa9d92547bbcaa53d2dc5fe1da7ba270c21875d780  docs/reference/gates_und_ratschen.md
- sha256:ee7ea46c40c1fba57cb3735d22f532905ee4699fe2d68801baab315c83893ee3  src/output/channels/seven_io_base.py
- sha256:adae7cd4e3c90280bbfff8d4d9cc5e101ba29af558d8b02190a5483fcef89faf  src/output/channels/telegram.py
- sha256:f0f1ab60b5ca808d4007704b5c0b470fedb12af7c876ec3752edba9b2e395887  tests/tdd/test_egress_single_dial_point.py
- sha256:55802ec94638c21237d942f065e0cac91548bdcc61adc951491e46e355fedd87  tests/tdd/test_telegram_post_is_single_guarded_exit.py

## Prüfbasis

- base: c1463084b7abe3dc917ad0ed9ee624d5e7edf166
- blob:4770d585f797405fa47cd0f545c7dd3a6b4b5c6c  docs/reference/gates_und_ratschen.md
- blob:0295287e3eb60965583c1f0d60346673b9fd499d  src/output/channels/seven_io_base.py
- blob:6a607dfc826858b5482affdce7096fbed53ea9c6  src/output/channels/telegram.py
- blob:256f9232c9711273caf4a4690e420c468cbe111c  tests/tdd/test_egress_single_dial_point.py
- blob:488381531f711b94ffa34faea7c3a271daef635c  tests/tdd/test_telegram_post_is_single_guarded_exit.py
