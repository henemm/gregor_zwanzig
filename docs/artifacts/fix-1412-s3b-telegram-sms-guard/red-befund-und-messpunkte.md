# RED-Befund und Messpunkte — fix-1412-s3b-telegram-sms-guard (Phase 5)

Stand 2026-10-06, gemessen im Worktree `epic-2138-triage`.

## RED-Lauf (`test-red-output.txt`): 13 rot, 58 grün

Nach Fast-Forward auf `origin/main` `c1463084b` erneut gemessen: unverändert
13 rot / 58 grün, einziger Struktur-Fund weiterhin `seven_io_base.py:171`.

**Heute ROT (müssen nach `/50` grün werden):**

| Test | AC | Warum rot |
|---|---|---|
| `test_ac1_ac4_falscher_bot_token_…[answer_callback_query]` / `[get_my_commands]` | AC-1/AC-4 | Methoden prüfen den Token nie |
| `test_ac2_neue_methode_mit_fremdem_chat_…` / `…_mit_falschem_token_…` | AC-2 | `_post` prüft nichts |
| `test_ac5_geblockter_aufruf_belegt_keinen_drossel_platz[3 Fälle]` | AC-5 | Slot wird reserviert und gepostet |
| `test_ac5_pruefung_laeuft_genau_einmal_auch_bei_429[answer_callback_query/get_my_commands]` | AC-5 | 0 statt 1 Token-Prüfung |
| `test_ac6_seven_io_basis_hat_einen_transport_post` | AC-6 | `SevenIoChannelBase._post` fehlt |
| `test_ac7_httpx_post_nur_an_den_erlaubten_ausgaengen` | AC-7 | meldet `seven_io_base.py:171 (httpx.post in SevenIoChannelBase.send)` |
| `test_ac7_beide_erlaubten_httpx_ausgaenge_existieren` | AC-7 | `SevenIoChannelBase._post` fehlt |
| `test_ac7_pruefdatum_steht_in_gates_und_ratschen` | AC-7 | Zeile in der Prüfdaten-Tabelle fehlt |

**Rohbeleg** (wörtlich aus `test-red-output.txt`, Kurzbericht und Summenzeile):

```
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac1_ac4_falscher_bot_token_blockt_jede_methode_ohne_netzaufruf[answer_callback_query]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac1_ac4_falscher_bot_token_blockt_jede_methode_ohne_netzaufruf[get_my_commands]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac2_neue_methode_mit_fremdem_chat_wird_am_ausgang_geblockt
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac2_neue_methode_mit_falschem_token_wird_am_ausgang_geblockt
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac5_geblockter_aufruf_belegt_keinen_drossel_platz[answer_callback_query]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac5_geblockter_aufruf_belegt_keinen_drossel_platz[get_my_commands]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac5_geblockter_aufruf_belegt_keinen_drossel_platz[neue_methode]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac5_pruefung_laeuft_genau_einmal_auch_bei_429[answer_callback_query-<lambda>-0]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac5_pruefung_laeuft_genau_einmal_auch_bei_429[get_my_commands-<lambda>-0]
FAILED tests/tdd/test_telegram_post_is_single_guarded_exit.py::test_ac6_seven_io_basis_hat_einen_transport_post
FAILED tests/tdd/test_egress_single_dial_point.py::test_ac7_httpx_post_nur_an_den_erlaubten_ausgaengen
FAILED tests/tdd/test_egress_single_dial_point.py::test_ac7_beide_erlaubten_httpx_ausgaenge_existieren
FAILED tests/tdd/test_egress_single_dial_point.py::test_ac7_pruefdatum_steht_in_gates_und_ratschen
======================== 13 failed, 58 passed in 3.48s =========================
```

**Heute bewusst GRÜN (Regressionsschutz, dürfen nicht kippen):** `send`,
Rückfall, `delete_message`, `edit_message_text` in Token- und Chat-Fall;
`set_my_commands` im Token-Fall; alle Gegenfälle ohne Test-Modus und mit
korrekter Konfiguration; `test_ac1_send_meldet_weiter_die_settings_chat_pruefung_1288`
(bewacht den Schalter `bound_chat`); `delete_message` „genau einmal bei 429“
(wird rot, wenn die Prüfung in `delete_message` stehen bleibt UND in `_post`
dazukommt → 2×); alle Struktur-Selbstnachweise.

**Fallstrick für `/50`:** `delete_message` & Co. müssen ihre eigenen
Guard-Aufrufe tatsächlich abgeben — sonst läuft die Ziel-Chat-Prüfung
doppelt und `test_ac5_…[delete_message]` wird rot.

## Herkunft festgenagelt

Alle neuen Telegram-Tests setzen `telegram_mod.running_origin` auf
`"production"` (Vorbild `test_telegram_test_isolation.py:226`) und prüfen im
Fehlertext, welche Prüfung gegriffen hat. Sonst hinge das Ergebnis vom
Checkout-Ort ab.

## Bestandstests-Baseline (AC-3)

- `bestand-baseline.txt` (mit `--disable-socket`): 62 grün, 1 rot + 6 Fehler
  — **alle** sind `SocketBlockedError` in Testaufbauten mit lokalem
  Stub-Server (`test_issue_650_telegram_foundation.py`,
  `test_channel_origin_guard_parity.py`), keine Code-Befunde.
- `bestand-baseline-mit-socket.txt`: genau diese beiden Dateien ohne
  Socket-Sperre → 14 grün, 2 übersprungen (Live, opt-in).
- ⇒ Ausgangslage vollständig grün. Nach dem Umbau dieselben Dateien in
  derselben Aufteilung erneut fahren.

## Offene Messpunkte der Spec

1. **Reihenfolge Token vs. Herkunft bei Doppelfehler:** Kein Bestandstest
   sichert einen Fehlertext für den Doppelfehler zu (grep nach
   `#1476`/Herkunftssperre in Verbindung mit Token: 0 Treffer). Die
   Reihenfolge ist also frei. **Empfehlung:** in `_post` Herkunft vor Token
   (wie die bisherigen Argument-Methoden) — risikoärmste Variante, `send`
   bleibt idempotent, weil seine eigene Herkunftsprüfung den Test-Chat
   liefert.
2. **`get_my_commands`-Tests im Test-Modus?** Nein.
   `test_issue_650_telegram_foundation.py:113` (`_LOCAL_SETTINGS`) setzt kein
   `is_test_mode` (Default False); `test_issue_671_bot_menu_autoset.py` und
   die übrigen Treffer-Dateien haben 0 Test-Modus-Bezüge;
   `test_pii_log_maskierung_kanaele.py:246` setzt ausdrücklich
   `is_test_mode=False`. AC-4 färbt keinen Bestandstest rot — kein Finding.
