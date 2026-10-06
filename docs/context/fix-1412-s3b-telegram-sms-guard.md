# Context: fix-1412-s3b-telegram-sms-guard

## Request Summary
#1412 Scheibe S3b: Die Empfängerprüfung für Telegram und SMS/Premium-SMS in den jeweils
gemeinsamen Netzausgang verlegen (Telegram `_post`, SMS neu `SevenIoChannelBase._post`) und per
AST-Struktur-Test (httpx-Teil) absichern, dass kein Sendeweg am Ausgang vorbeigeht. PO-Entscheid
29.07.: Telegram und SMS sollen eine **produktiv** wirksame Empfängerprüfung bekommen, Fehltreffer
werden **blockiert**.

Stand origin/main `709b2c506`, gemessen 2026-10-06. Vorgänger-Kontext:
`docs/context/fix-1412-versandweg-basis.md`, `docs/context/fix-1412-s3-transport-kapselung.md`.

## 🔴 Zuschnitt-Spannung (für /20-analyse zu entscheiden)

Der Plan aus der Bestandsaufnahme (`fix-1412-versandweg-basis.md:249-251`, S3a-Spec :217-233,
`fix-1412-s3-transport-kapselung.md:358`) teilt so:

| Scheibe | Inhalt | Größe |
|---|---|---|
| **S3b** | Bestehende (Test-Modus-)Guards in den Ausgang verlegen, Struktur-Test httpx | ~111 LoC |
| **S4a/b** | Scharfer Empfängervertrag produktiv (`Settings.user_id`, Zweck-Parameter) | 300–500 LoC, PO-Freigabe |

Die produktive Schärfe war also **S4** zugeordnet, nicht S3b. Im Intake wurde S3b als „schließt
die Produktionslücke" beschrieben — das ist am Plan gemessen ungenau und muss in der Analyse
richtiggestellt werden.

Gleichzeitig ist die Produktionslücke seit Juli **kleiner geworden** (gemessen):

- **SMS:** `config.py:433-437 with_user_profile` übernimmt `sms_to` nur, wenn es der
  verifizierten Nummer entspricht (#2406: `SmsVerifiedNumber`/`SmsVerifiedAt`, `internal/model/user.go:65-67`).
  Rest-Vektor: jedes `model_copy(update={"sms_to": …})` umgeht das.
- **Telegram:** `TelegramChatID` (`user.go:18`) wird nur im localhost-gesperrten Einmal-Token-Flow
  gesetzt (`internal/handler/telegram_connect.go:270-322`, Eindeutigkeit :305); PUT-Härtung erledigt
  (`auth.go:1220-1230`, #2141). Praktisch „verifiziert per Konstruktion". Rest-Vektor: `model_copy`.

## Related Files

| File | Relevance |
|---|---|
| `src/output/channels/telegram.py` | `_post` :372-409 (2× `httpx.post` :391/:409, Docstring „KEINE Guards" :377-382). Guards: `_guard_code_origin` :194-227 (wirkt immer), `_guard_test_mode_chat_id` :229, `_guard_test_mode_bot_token` :250, `_guard_test_mode_target_chat` :268 (alle drei aus bei `is_test_mode==False`) |
| `src/output/channels/seven_io_base.py` | `SevenIoChannelBase.send` :155-187; Sandbox-Key-Guard :108-125 (aus bei Prod :115), Herkunftssperre :127-149, **`httpx.post` direkt in `send` :171** → neues `_post` gehört hierhin |
| `src/output/channels/sms.py` | 50 Zeilen, erbt von `SevenIoChannelBase`; `_resolve_recipient` :41-50 blockt nur leeres `sms_to` |
| `src/output/channels/premium_sms.py` | gleicher Ausgang; Empfänger nur gelernte `premium_sms_reply_to` (TTL 30 T, Zukunftssperre :64-103) |
| `src/app/config.py` | `with_user_profile` :433-441 — SMS-Verifikationssperre, Telegram-Chat-ID aus Profil |
| `src/services/notification_service.py` | baut fast alle Kanal-Instanzen; `send_command_reply_telegram`/`send_telegram_message` :2009-2042 verwerfen `chat_id` (R7), Aufrufer weichen per `model_copy` aus |
| `src/services/inbound_telegram_reader.py` | legitime Sendungen an Chats **ohne/mit fremdem** Profil: :243-253, :477-487, :643, :659 (409: Chat gehört anderem Konto); `answer_callback_query` :463/:498; `httpx.get` getUpdates :198 (#1369); localhost-`httpx.post` :635 |
| `api/routers/internal.py` | :176-201 SMS-Bestätigungscode an **unverifizierte** Nummer per `model_copy(update={"sms_to": req.to})` |
| `api/routers/webhook.py` | :86-90 Telegram-Webhook mit nacktem `Settings()` |
| `src/services/inbound_sms_reader.py` | :386/:408 Premium-SMS-Antworten; :251 localhost-`httpx.post` (premium-sms-learn) |
| `src/services/channel_test_service.py` | :25,:38 `.for_testing()` |
| `api/main.py` | :84 `set_my_commands` |
| `tests/tdd/test_egress_single_dial_point.py` | Vorlage Struktur-Test (smtplib); `EXPIRY = 2026-10-28` :57 — **22 Tage**; Deckel 0 :70 |
| `src/app/egress_guard.py` | #1337, patcht `HTTPTransport.handle_request` (:153-159), nur Test/Staging (:142) — keine Kollision |

## Existing Patterns

- **E-Mail (Vorbild):** `email.py:239 _load_resend_allowlist` — Profile mit `email_verified_at`
  (:294), Prüfung **einmal vor** der Sendeschleife (:455-460, :705-733). `_dial_and_send` bleibt
  reiner Transport (S3a-Leitentscheidung: Prüfung in den gemeinsamen Weg nur, wenn die
  Aufruferzahl es rechtfertigt — Telegram hat 7 Aufrufer → ja).
- **Vorentscheid aus S3-Kontext** (`fix-1412-s3-transport-kapselung.md:361-389`): Prüfung **in**
  `_post`, Nachrichten-Endpunkte erkannt an `"chat_id" in payload`; `answer_callback_query`/
  `get_my_commands` bekommen den Token-Guard (:391-407).
- **Struktur-Test:** nur `httpx.post` / Client-`.post`, nicht `httpx.get` (:409-437). AST mit
  Alias-Auflösung, `Ausnahme`-Klasse mit Begründung ≥15 Zeichen + Frist.
- **Parität je Klasse:** `tests/tdd/test_channel_origin_guard_parity.py`.

## `_post`-Aufrufer Telegram (heute)

| Methode | Zeile | Guards heute |
|---|---|---|
| `send` | :465 | origin + Token + chat_id (:435/447/448), leer → `ChannelBlockedError` :440 |
| `_send_fallback_without_parse_mode` | :521 | :511-513 |
| `delete_message` | :563 | :555-557 |
| `edit_message_text` | :609 | :593-595 |
| `answer_callback_query` | :632 | **keine** |
| `set_my_commands` | :655 | nur Token :649 |
| `get_my_commands` | :677 | keine |

## httpx.post-Fundstellen (Struktur-Test-Inventar)

- Erlaubt: `telegram.py:391/409` (`_post`), `seven_io_base.py:171` (wird `_post`).
- Ausnahmen (alle localhost): `lib/mq_notify.py:45`, `inbound_telegram_reader.py:635`,
  `inbound_sms_reader.py:251` — **drei**, nicht zwei wie im Vorgänger-Kontext.
- `httpx.Client` in `validation/ground_truth.py:41`, `geosphere_validator.py:51`,
  `radar_service.py:1019` (Datenabruf) — vor Erfassung von Client-Formen auf `.post` prüfen.

## Dependencies

- Upstream: `Settings` (`is_test_mode`, `telegram_chat_id`, `sms_to`, `premium_sms_reply_to`),
  Nutzerprofil (`data/users/<id>/user.json`, Go schreibt), `httpx`.
- Downstream: NotificationService (alle Briefings/Alarme), Inbound-Befehle Telegram/Premium-SMS,
  SMS-Verifikation (#2406), Kanal-Test, Bot-Befehlsmenü.

## Existing Specs

- `docs/specs/modules/fix_1412_s1_*`, `*_s2a_*`, `*_s2b_*`, `fix_1412_s3a_transport_kapselung_mail.md`
  (S3b additiv, :77, :114-115, :217-233). **Keine S3b-Spec.**

## Risks & Considerations

1. **Aussperr-Risiko (hoch):** Ein produktiver Abgleich „Empfänger == Profilwert" blockiert vier
   legitime Wege: Telegram-Antworten an unregistrierte/fremde Chats (Registrierungshinweis,
   `/start`-Race, 409-Konflikt, edit an unbekannten Chat) und den SMS-Bestätigungscode an die noch
   unverifizierte Nummer. → braucht einen **Zweck** (z. B. Antwort-an-Absender / Verifikation)
   oder eine andere Regel.
2. **Testmasse:** 58 Teststellen setzen erfundene `telegram_chat_id`, 12 `sms_to`
   (`fix-1412-versandweg-basis.md:264`) — produktive Schärfe kann breit rot machen.
3. **Prüfdatum `test_egress_single_dial_point.py` = 2026-10-28:** läuft während/kurz nach dieser
   Scheibe ab; Fang-Nachweis oder Verlängerung mitentscheiden (Regel-Budget).
4. **Multi-User:** Prüfung muss gegen das Profil **des sendenden Nutzers** laufen, nicht gegen
   „irgendein" Profil (sonst Cross-User-Zustellung erlaubt).
5. **Alle vier Kanäle gleichrangig:** Blockade darf Alarme nicht still verschlucken — Blockade muss
   sichtbar sein (Log/Fehler), wie bei E-Mail.
6. **Nachweis laut Ticket:** echter Versandversuch an gesperrten Empfänger wird geblockt — nicht
   nur isolierter Guard-Aufruf (Lehre #1288).

## Analysis

### Type
Bug (Strukturdefekt im Sicherheitspfad, Issue-Label `bug`) — umgesetzt als verhaltensneutraler
Struktur-Umbau mit einer gewollten Verschärfung (AC-Kandidat 4).

### Zuschnitt-Korrektur (Tech-Lead-Festlegung)
S3b ist **strukturell**: die heute bestehenden Telegram-Guards (Herkunft, Test-Token, Test-Chat)
wandern in den gemeinsamen Ausgang `TelegramOutput._post`; SMS bekommt `SevenIoChannelBase._post`;
der AST-Struktur-Test wird um den httpx-Teil erweitert. **S3b schließt die Produktionslücke NICHT** —
die Guards sind bei normalen `Settings()` in Prod und Staging No-Ops (`is_test_mode` default False,
`config.py:178`, gesetzt nur über `for_testing()`/Testnutzer-Profil `:366/:382`). Der produktiv
scharfe Empfängervertrag (`Settings.user_id`, Zweck-Parameter) bleibt **S4a/b** (PO-Entscheid
2026-07-29 gilt für das Issue als Ganzes, zugeordnet S4). Keine S4-Bausteine in S3b ziehen.

### Kernbefund: die Telegram-Guard-Sequenzen sind NICHT gleich (gelesen, telegram.py)
| Methode | Sequenz heute | Chat-Prüfung prüft |
|---|---|---|
| `send` :435-448 | origin(Settings-Chat) → Leer-Check `ChannelBlockedError` :440 → token → `_guard_test_mode_chat_id()` | **Settings-Wert, UNGEÄNDERT** (vor Umschreiben) |
| `_send_fallback_without_parse_mode` :511-513, `delete_message` :555-557, `edit_message_text` :593-595 | origin(arg) → token → `_guard_test_mode_target_chat(c)` | **umgeschriebenen** Wert |
| `set_my_commands` :649 | nur token | — |
| `answer_callback_query` :632, `get_my_commands` :677 | keine | — |

`_guard_code_origin` (:194-227) schreibt bei Herkunft „test" auf `telegram_test_chat_id` um.
Ein naiver Payload-Check in `_post` NACH dem Umschreiben schwächt `send`: rot würden ohne Testedit
`test_diverging_test_chat_id_blocks_send_without_any_post` (`tests/tdd/test_telegram_test_mode_guard.py:121`)
und AC-7 `test_existing_1288_chat_guard_unchanged` (`tests/tdd/test_telegram_test_isolation.py:392-430`,
erwartet exakten Text `chat_id='<PROD>'`). Der `chat_id=`-Keyword von `_post` (:372) ist heute nur
Drossel-Schlüssel (:389).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/channels/telegram.py` | MODIFY | Guards in `_post` vor `_reserve_send_slot`, genau einmal (nicht beim 429-Retry :409); Guard-Aufrufe aus `_send_fallback`/`delete`/`edit`/`set_my_commands` entfernen; Docstring :377-382 („KEINE Guards") neu |
| `src/output/channels/seven_io_base.py` | MODIFY | `httpx.post` :171-176 → `_post(url, api_key, payload)` als **reiner Transport**; Guards bleiben in `send` :162-165 |
| `tests/tdd/test_egress_single_dial_point.py` | MODIFY | httpx-Teil: eigene Erlaubt-Menge + `AUSNAHMEN_HTTPX` (3, Deckel 3); Kommentar :68-69 („zwei Ausnahmen") korrigieren; `EXPIRY` → 2027-01-04 (:55-57, Assertion :505) |
| `tests/tdd/test_<verhalten>.py` (z.B. `test_telegram_post_is_single_guarded_exit.py`) | CREATE | Sink-Test über alle 7 öffentlichen Methoden + Unterklassen-Methode ohne eigene Guards |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Prüfdaten-Zeile für `test_egress_single_dial_point` (fehlt heute, grep ohne Treffer) |

### Scope Assessment
- Files: 5 (2 produktiv, 2 Test, 1 Doku)
- Estimated LoC: produktiv ~+30 netto (telegram ~+20, seven_io ~+10); Test ~+300 → unter Limit 250 (zählt nur produktive Spec-Dateien)
- Risk Level: MEDIUM — Sicherheitspfad aller Telegram-Sendungen, aber verhaltensneutral bis auf AC-Kandidat 4; alle Prod-Wirkungen No-Op

### Technical Approach (Empfehlung)
1. **Telegram `_post`-Sequenz** (vor Drossel-Slot, einmal):
   `_guard_test_mode_bot_token()` für alle Endpunkte → wenn `"chat_id" in payload`: Kopie,
   `c = _guard_code_origin(payload["chat_id"])` (idempotent: Test-Chat→Test-Chat, 400-Fallback ok),
   bei Schalter `bound_chat=True` (nur `send`) zusätzlich `_guard_test_mode_chat_id()` (Settings-Wert,
   alter Fehlertext), dann `_guard_test_mode_target_chat(c)`; `payload["chat_id"] = c`.
   `send` behält Origin-Aufruf + Leer-Check (sonst kippt `tests/unit/test_channel_blocked_missing_recipient.py:70-101`)
   und übergibt `bound_chat=True`. Eine künftige Methode ohne Schalter bekommt mindestens das Niveau der
   heutigen Argument-Methoden.
2. **SMS:** `_post` reiner Transport; Guards bleiben in `send`. Begründung S3a-Kriterium: einziger
   Aufrufer, `send` ist bereits gemeinsamer Pfad für SMS + Premium-SMS (keine Unterklasse überschreibt
   `send`). Optional: Test, dass keine Unterklasse `send` überschreibt.
3. **Struktur-Test httpx** im bestehenden Wächter: Formen `httpx.post`, Modul-Alias,
   `from httpx import post [as p]`, `httpx.request("POST", …)`, `httpx.stream("POST", …)`,
   `httpx.Client(...).post`/`AsyncClient(...).post` (direkt verkettet). Erlaubt: `TelegramOutput._post`,
   `SevenIoChannelBase._post`. Ausnahmen (localhost, Begründung ≥15 Zeichen, Frist):
   `src/lib/mq_notify.py:45`, `src/services/inbound_telegram_reader.py:635`, `src/services/inbound_sms_reader.py:251`.
   Vor dem Bau: `.post` an Datenabruf-Clients (`radar_service.py:1019`, `validation/`) per grep ausschließen.
4. **Prüfdatum:** `EXPIRY` wird nirgends gegen `date.today()` geprüft (`:502-507` nur Konstante/Text) —
   kein CI-Rot am 29.10. Gemeinsames neues Datum 2027-01-04 (+90 T) für die erweiterte Datei + Zeile in
   der Prüfdaten-Tabelle `gates_und_ratschen.md` (ab :390).

### AC-Kandidaten (für /30-write-spec)
1. Jede der 7 öffentlichen Telegram-Methoden: falsche Test-Konfig ⇒ `OutputConfigError`, **0** Transportaufrufe (Sink am `httpx.post`).
2. Eine neue (Test-Unterklassen-)Methode, die `_post` ohne eigene Guards ruft, wird trotzdem geblockt — die eigentliche Struktur-Zusicherung.
3. Bestandstests der Telegram-Guards (#1288, #1363, Herkunft #1476, #2144-Leer-Check) bleiben **ohne Testedit** grün; Fehlertexte unverändert.
4. **Gewollte Verschärfung:** `answer_callback_query` und `get_my_commands` bekommen den Test-Token-Guard (im Test-Modus mit abweichendem Token geblockt). Prod/Staging mit `Settings()` unberührt; einziger Produktivaufrufer `notification_service.py:2095` ist fail-soft.
5. Guards laufen vor `_reserve_send_slot` und genau einmal pro `_post`-Aufruf (nicht beim 429-Retry).
6. SMS/Premium-SMS: `httpx.post` nur noch in `SevenIoChannelBase._post`; bestehende SMS-Sink-Tests ohne Edit grün.
7. Struktur-Test meldet jeden POST außerhalb der zwei erlaubten Orte und der drei Ausnahmen namentlich; Deckel 3; Selbstnachweis je erfasster Form.
8. Mutation: Guard-Block aus `_post` entfernt ⇒ AC-1/AC-2-Fälle rot.

### Ehrliche Grenzen (in Spec übernehmen)
- Client in Variable gebunden, danach `.post` → nicht erkannt.
- Bot-API akzeptiert `sendMessage` auch per GET → POST-Scan lässt das offen.
- `inbound_telegram_reader.py:198` (getUpdates-GET mit Bot-Token) → #1369, nicht Scope.
- Nachweis ist Kern-Schicht (Offline-Sink, `--disable-socket`); auf Staging sind die Guards No-Ops — Staging = Smoke (Dienste gesund, Briefing-Telegram kommt an), kein Blockbeweis. Das ist ehrlich so zu benennen, nicht als PASS zu verkaufen.

### Dependencies
- Upstream: `Settings` (`is_test_mode`, `telegram_*`, `seven_*`), `running_origin`, `httpx`.
- Downstream: NotificationService (alle Briefings/Alarme), Inbound-Telegram-Befehle/Callbacks, Bot-Menü (`api/main.py:84`), SMS-Verifikation, Kanal-Test.

### Open Questions
- [x] Zuschnitt S3b vs. S4 → entschieden: S3b strukturell, Schärfe S4 (Plan-konform, keine PO-Frage)
- [x] Prüfdatum 2026-10-28 → kein hartes Rot; neues Datum 2027-01-04 + Tabellenzeile
- [ ] Reihenfolgewechsel Token-vor-Origin bei Argument-Methoden: prüfen, ob ein Test die Fehlertext-Reihenfolge bei Doppelfehler zusichert (in /40 messen; sonst Origin-vor-Token beibehalten)
- [ ] Zwei Telegram-`get_my_commands`-Tests (Zeilen 671/686 der jeweiligen Datei) im Test-Modus? — in /40 messen
