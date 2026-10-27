# Context: feat-1412-s4a-empfaengervertrag-telegram

Issue #1412, Scheibe **S4a** (Telegram). Vorgänger live: S1, S2a, S2b, S3a, S3b (`045c7bb2b`, PR #2523).
Danach offen: S4b (SMS), S5 (Go-Nachzug D1/R2, PUT-Härtung `telegram_chat_id`, ADR „Empfängerschutz").
Stand der Erhebung: HEAD `cdbd935da` (inkl. #2555 — Telegram-Poll-Pfad entfernt).

## Request Summary

Telegram-Versand darf nur noch an einen Chat gehen, dessen **Herkunft belegt** ist. Der Transport
(`TelegramOutput._post`) bekommt Empfänger und Zweck explizit und prüft bedingungslos — auch produktiv.
Konzept aus `docs/context/fix-1412-versandweg-basis.md:211-221, :250`:

1. **Empfänger explizit übergeben** — Transport greift nicht mehr selbst nach `settings.telegram_chat_id`. Macht R7 unbaubar.
2. **Herkunftsbindung über Zweck** (geschlossene Aufzählung, Default = Block): `user_profile` · `inbound_reply` · `operator` · `verification`. Voraussetzung: `Settings` trägt `user_id` (heute nicht), `with_user_profile()` schreibt es mit.
3. **Formprüfung bedingungslos** (Telegram: numerische ID).
4. Gemeinsamer Test-Helper Pflicht; LoC-Override (~300–500) braucht PO-Freigabe.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/channels/telegram.py` | `TelegramOutput`: Konstruktor `:185` (nur `settings`), `send` `:433` (Empfänger = `self._settings.telegram_chat_id` `:457`), `_send_fallback_without_parse_mode` `:522`, `delete_message`/`edit_message_text` `:559/:599` (chat_id als Argument), `answer_callback_query`/`set_my_commands`/`get_my_commands` `:630/:653/:677` (ohne Chat), `_post` `:372-431` (zentrale Prüfungen seit S3b; 429-Retry ohne Neuprüfung `:431`), `_guard_code_origin` `:194`, Test-Modus-Guards `:229/:238/:257/:275` |
| `src/app/config.py` | `Settings`: `telegram_chat_id` `:251`, Test-Felder `:252-253`; **kein `user_id`-Feld**. `for_testing()` `:362`. `with_user_profile` `:400` (`force_test` `:414`; Profil fehlt/kaputt ⇒ Basis unverändert inkl. globaler `.env`-Chat `:421-427`; Prod-Zweig `:447`). `can_send_telegram` `:478` |
| `src/services/notification_service.py` | Alle Briefing-/Alarm-/Hinweis-Versände: `:692-739, :785, :856, :1194-1205, :1331, :1480-1558, :1869-1946` via `TelegramOutput(self._settings).send`. Befehlsantworten `:2046-2136`: `send_telegram_message`/`send_command_reply_telegram` **verwerfen `chat_id`** (R7 offen) |
| `src/services/inbound_telegram_reader.py` | `_process_update` (nach #2555 nur noch Webhook-gespeist). Unbekannter Absender `:190-201` (`model_copy(chat_id)`), Antworten an bekannte Nutzer `:271, :306, :348-390, :445, :479-510`, Callback unbekannt `:424-433`, Spinner bei gesperrtem Konto `:410`, `/start` OK/409 `:590/:606` (`model_copy`), `_resolve_user_for_chat` `:555` |
| `api/routers/webhook.py:52-94` | Telegram-Eingang; Basis `Settings()` ohne Nutzer (`:86`) |
| `src/services/channel_test_service.py:25-39` | `/api/notify/test`: `with_user_profile(uid).for_testing()` ⇒ faktisch Test-Chat; Prod-Verhalten unklar (eventuell bereits defekt) |
| `api/main.py:84` | `_init_telegram_bot_menu` → `set_my_commands` (kein Chat) |
| `src/app/cli.py:258`, `src/output/channels/base.py:131` | Debug-CLI über `get_channel` mit globalen Settings |
| `src/app/loader.py:1446` | `lookup_user_by_telegram_chat_id` (Mehrdeutigkeit ⇒ `None`, #2141) |
| `internal/handler/telegram_connect.go:269` | Go schreibt Chat-Verknüpfung beim `/start`-Token |
| `internal/handler/auth.go:544, :587-589` | PUT-Profil nimmt `telegram_chat_id` als Freitext (Restlücke, S5) |

## Aufrufer → Empfängerquelle → Zweck

| Aufrufer | Empfängerquelle | Zweck |
|---|---|---|
| NotificationService (Briefing, Hinweise, Alarme, Vergleich, Amtswarnung) | `with_user_profile(user_id).telegram_chat_id` | `user_profile` |
| `trip_command_processor.py:935/1547/2478` (`heute`/`morgen`) | Profil über `TripReportSchedulerService(user_id)` | `user_profile` |
| Reader, bekannter Nutzer | `user_settings` (= Absender per Rückwärtssuche) | `inbound_reply` (zugleich Profil-Chat) |
| Reader, unbekannter Absender / Callback unbekannt | Absender-`chat_id` | `inbound_reply` ohne Nutzer |
| Reader `/start` OK/409 | Absender-`chat_id` | `verification` |
| `answer_callback_query`, `set/get_my_commands` | kein Chat | keine Empfängerprüfung (nur Token-Guard) |
| `channel_test_service` | Profil → `for_testing()` | `user_profile` — zu klären |
| CLI `get_channel` | globale `.env` | `operator` |
| Betreiber-Telegram-Meldungen | existieren nicht | `operator` ohne Produktiv-Aufrufer |

## Existing Patterns

- S3b: `_post` als einziger geschützter Ausgang, Prüfung **vor** Drossel-Reservierung, genau einmal (auch bei 429).
- Struktur-Wächter `tests/tdd/test_egress_single_dial_point.py` (Prüfdatum 2027-01-04).
- Nachweisform: Sink am Transport-Rand (`tests/tdd/test_telegram_test_isolation.py`, `test_telegram_post_is_single_guarded_exit.py`), kein isolierter Guard-Aufruf (Lehre #1288).
- Mail-Seite: Prüfung „bestätigte Profil-Adresse **oder** lokal zustellbar" (S1/S2b) — Vorbild für „Profil-Chat oder belegter Sonderzweck".

## Dependencies

- Upstream: `Settings`/`with_user_profile`, Profil-Loader, `running_origin`, Drossel (Klassenebene, prozessweit).
- Downstream: alle Telegram-Aufrufer oben; Tests, die `_post` mit fester Signatur (`bound_chat=False`) stubben: `tests/unit/test_briefing_cross_tenant_recipient_isolation.py`, `tests/unit/test_briefing_recipient_logging.py`, `tests/tdd/_befehl_e2e_fixtures.py`, `tests/tdd/test_egress_single_dial_point.py`.

## Existing Specs

- `docs/specs/modules/fix_1412_s1_*`, `fix_1412_s2a_*`, `fix_1412_s2b_*`, `fix_1412_s3a_transport_kapselung_mail.md`, `fix_1412_s3b_telegram_sms_ausgang.md` (`:43-53`: `model_copy`-Umgehung bleibt bis S4 offen, S4 schärft nur noch **eine** Stelle)
- Kontext: `docs/context/fix-1412-versandweg-basis.md` (Konzept S4 `:211-221, :250, :263`), `fix-1412-s3b-telegram-sms-guard.md:103-111` (Risiken)
- ADR-0003 (Mandantentrennung, kein `default`), ADR-0012 (HTML-400-Rückfall, gleicher Empfänger), ADR-0014 (Multi-Bubble: frische Instanz je Bubble ⇒ Zweck/user_id über Settings/Konstruktor), ADR-0072 (Testkonto nur via `is_test_user`, Ausnahme `tg-live-e2e`), ADR-0015 (kein geteilter Go/Python-Code)

## Risks & Considerations

1. **R7 offen:** `chat_id` in `send_telegram_message`/`send_command_reply_telegram` ist nur Log-Wert; alle `model_copy`-Ausweichstellen (`reader :200, :590, :606`) mitziehen.
2. **`model_copy` trägt alte `user_id` mit fremdem Chat weiter** — der Transport muss den Chat gegen das Profil **neu** abgleichen, nicht `Settings.telegram_chat_id` vertrauen.
3. **`/start`-Rennen:** Go schreibt, Python sendet sofort — Bestätigung über `verification`, nicht über Profil-Lesen.
4. **Test/Staging:** bei `force_test` ist der Chat die Test-Chat-ID ⇒ „Chat ∈ Profil" schlägt fehl. Regel „Test-Chat im Testkontext zulässig" oder Prüfung vor dem Umschreiben.
5. **Profil fehlt/kaputt** ⇒ globaler `.env`-Chat mit `user_id` — muss blockieren.
6. **`channel_test_service`** in Prod vermutlich schon heute falsch (Test-Chat bzw. `OutputConfigError`) — vor Umbau messen.
7. **Methoden ohne Chat** dürfen nicht brechen (Bot-Menü fail-soft, `test_issue_671_bot_menu_autoset.py`).
8. **Antworten an Unbekannte** (Registrierungshinweis, Callback-Edit, Spinner) dürfen nicht verstummen und keine Nutzerdaten tragen.
9. **400-Rückfall / 429-Retry:** Prüfung nicht verlieren, nicht doppelt protokollieren.
10. **Multi-Bubble:** Zweck + `user_id` je frischer Instanz verfügbar.
11. **Testmasse:** 188 Treffer `telegram_chat_id` in 109 Testdateien (129 kwarg/Zuweisung, 52 Profil-Dict); Zahl 58 aus 07/2026 veraltet. Gemeinsamer Test-Helper Pflicht, LoC-Override nötig.
12. **Wächter `test_telegram_poll_pfad_entfernt.py:53-80`** verbietet Netz-Imports in `inbound_telegram_reader.py`.
13. **Regel-Budget:** neuer Wächter ⇒ Prüfdatum oder Ersatz einer bestehenden Regel.
14. **Mehrdeutige Rückwärtssuche** ⇒ Zweig „unbekannt" — keine Nutzerdaten.
15. **Bekannte Restlücke:** `PUT /api/auth/profile` setzt `telegram_chat_id` als Freitext ⇒ „Chat ∈ Profil" ist bis S5 kein voller Herkunftsbeleg. In der Spec als Known Limitation führen.
16. **Operator-Zweck** hat für Telegram keinen Produktiv-Aufrufer außer der Debug-CLI — prüfen, ob er in S4a überhaupt gebraucht wird (YAGNI vs. geschlossene Aufzählung aus dem Konzept).

## Analysis

### Type
Feature (Härtung im produktiven Sicherheitspfad) mit einem mitbehobenen, nutzersichtbaren Defekt (Test-Knopf, Befund M3).

### Messungen dieser Phase (gelesen/gemessen, nicht abgeleitet)

| # | Befund | Beleg |
|---|---|---|
| M1 | **LoC-Zähler zählt nur produktive Spec-Dateien**, Tests nicht ⇒ geschätzt ~160–200 produktive Zeilen passen **ohne Teilung** unter 250. Override erst nach `workflow.py status` in /50 anfassen. | Memory `reference_loc_limit_zaehlt_nur_produktive_spec_dateien` (#1761 gemessen) |
| M2 | **ContextVar trägt:** `api/routers/webhook.py` ist ein synchroner Handler, `_reader._process_update(update, settings)` läuft vollständig im selben Thread. Im Reader keine Threads/Executor/asyncio/BackgroundTasks (grep leer). | `webhook.py:90`, grep `inbound_telegram_reader.py` |
| M3 | **Test-Knopf in Prod defekt (nutzersichtbar):** `channel_test_service.py:25` baut `with_user_profile(uid).for_testing()`; `for_testing()` (`config.py:375-376`) setzt `telegram_chat_id = telegram_test_chat_id` und `telegram_bot_token = telegram_test_bot_token`. `GZ_TELEGRAM_TEST_CHAT_ID` ist in der Prod-`.env` **gesetzt** (nur das Vorhandensein geprüft). ⇒ Drückt ein Nutzer „Telegram testen“, schickt der Test-Bot an den **Betreiber-Test-Chat**; beim Nutzer kommt nichts an, die Oberfläche meldet Erfolg. Wird **in diesem Ticket** behoben, nicht abgespalten. | `channel_test_service.py:22-39`, `config.py:362-393`, `.env` |
| M4 | **`.env`-Rückfall-Risiko kleiner als befürchtet:** Liegt ein Profil vor und läuft kein Testmodus, setzt `with_user_profile` schon heute `telegram_chat_id = profile or None` (`config.py:446-447`). Der globale `.env`-Chat greift **nur**, wenn `user.json` fehlt oder unlesbar ist (`:421-427`); ein Nutzer ohne `user.json` hat keine Trips. Dass `for_user` ohne Rückfall arbeitet, lässt also keinen heute belieferten Nutzer verstummen. | `config.py:400-458` |
| M5 | `NotificationService._require_user()` bricht fail-closed ab, wenn `user_id` fehlt (`notification_service.py:484-491`); die 12 `.send`-Stellen laufen in nutzergebundenen Diensten. | `notification_service.py:475-491` |
| M6 | Produktivprofile (`/var/lib/gregor/users`) ließen sich nicht auszählen, der Zugriff wurde aus Datenschutzgründen verweigert. Ersatz: der Code-Beleg M4. | — |

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/channels/telegram.py` | MODIFY | Neuer Typ `TelegramRecipient` (unveränderlich, nur über Fabriken `for_user(user_id, settings)` und `inbound_reply(chat_id)`). `TelegramOutput(settings, *, recipient=None)`. In `_post`: Formprüfung (numerische ID, bedingungslos) → Herkunftsprüfung je Zweck auf der **Original-ID** → bestehende Guards → Drossel. `send`/`edit_message_text`/`delete_message` lesen **nicht** mehr `settings.telegram_chat_id` (`:457`, `:403`, `:241`). Ohne `recipient` Default-Block (`ChannelBlockedError`, reason_code). `_post`-Signatur bleibt unverändert, damit die 4 Test-Stubs heil bleiben. |
| `src/output/channels/recipient.py` (o. ä.) | CREATE | Kanalübergreifende Zweck-Aufzählung `RecipientPurpose` (`user_profile`, `inbound_reply`). S4b ergänzt `verification` (SMS-Bestätigungscode): nur eine weitere Konstante, kein Umbau. Ablageort vor Anlage per `ls src/output/channels/` am Bestand prüfen. |
| `src/services/notification_service.py` | MODIFY | Helper `_telegram_output()` → `TelegramOutput(self._settings, recipient=TelegramRecipient.for_user(self._require_user(), self._settings))` an allen 12 Stellen (`:700,722,785,858,1200,1205,1336,1547,1558,1882,1918,1946`). `send_telegram_message`/`send_command_reply_telegram` (`:2046-2080`) reichen den Empfänger tatsächlich durch (R7). Ebenso `edit_/delete_telegram_message` (`:2096/:2117`). |
| `src/services/inbound_telegram_reader.py` | MODIFY | `ContextVar` `_current_inbound_sender`: in `_process_update`/`_process_callback_query` nach dem Parsen setzen, im `finally` zurücksetzen. Die 3 `model_copy`-Umgehungen (`:200, :590, :606`) entfallen. Die 9 `send_*`-Aufrufe bekommen `inbound_reply(chat_id)` bzw. bei bekanntem Nutzer `for_user`. Netz-Import-Verbot aus `test_telegram_poll_pfad_entfernt.py:53-80` einhalten: nur `contextvars` und den Typ importieren, kein `httpx`. |
| `src/services/channel_test_service.py` | MODIFY | M3 beheben: Der Telegram-Zweig sendet über `for_user(uid, …)` an den echten Profil-Chat mit dem Produktions-Bot. Der E-Mail-Zweig behält das Test-Routing (#198), das ist nicht S4a. Fehlt der Profil-Chat, klare Fehlermeldung statt Erfolg. |
| `src/trip_command_processor.py` (`:935/1547/2478`) | MODIFY (prüfen) | Läuft der Versand über den NotificationService, ist keine Änderung nötig. In /40 verifizieren. |
| `src/app/cli.py:258`, `src/output/channels/base.py:131` | MODIFY | Debug-CLI ohne Nutzer wird mit klarer Meldung geblockt. Kein Zweck `operator` (YAGNI, kein Produktiv-Aufrufer). |
| `tests/…` gemeinsamer Helper | CREATE | Fabrik für Test-Empfänger plus Migration der 25 Testdateien, die `TelegramOutput(` direkt bauen. |
| neue Tests | CREATE | Zweck×Kontext-Matrix mit Sink am `httpx`-Rand bei `is_test_mode=False`, **ohne** `_post`-Stub. Dazu R7 durch das echte `_process_update`, Test-Knopf (M3), 429-Einmaligkeit, 400-Rückfall mit demselben Empfänger, Multi-Bubble. |
| `docs/specs/modules/fix_1412_s4a_*.md` | CREATE | Spec (Phase 3) |

### Scope Assessment
- Produktive Dateien: ~6 (telegram.py, Recipient-Modul, notification_service.py, inbound_telegram_reader.py, channel_test_service.py, cli/base)
- Estimated LoC (produktiv, Schätzung): +170 / -40. Tests zusätzlich ~+300, zählen nicht ins Limit (M1)
- Risk Level: **MEDIUM-HIGH**. Wegen des Default-Blocks verstummt jeder übersehene Aufrufer **produktiv**. Deshalb werden alle Aufrufer in einem Zug umgestellt, ohne „Legacy erlaubt“-Übergang.

### Technical Approach (Tech-Lead-Entscheidung)

**Variante B ungeteilt:** Empfänger-Objekt mit Fabriken plus ContextVar-Herkunftsbeleg für Antworten.

| Variante | Prod-LoC | Schutz | Bewertung |
|---|---|---|---|
| A: `Settings.user_id` + Chat-Abgleich, Aufrufer unverändert | ~80 | schwach: `model_copy` umgeht weiter, Selbstauskunft | verworfen, schließt R7/`model_copy` nicht |
| **B: `TelegramRecipient` + Fabriken + ContextVar** | ~170 | Profil frisch gelesen, Absender belegt, Default-Block | **gewählt** |
| C: B + `Settings.user_id` + 4 Zwecke inkl. `operator`/`verification` | ~230 | wie B | mehr Fläche ohne Nutzen |
| D: B geteilt in S4a1/S4a2 | 100+80 | S4a1 nur halb | unnötig, weil Tests nicht zählen (M1) |

Kernregeln:
1. **Empfänger an der Instanz**, nicht an `send()`. Passt zu ADR-0014 (frische Instanz je Bubble), die 12 `send`-Signaturen bleiben gleich.
2. **`for_user(user_id, settings)`**: Im Testkontext (`settings.is_test_mode`) ist der Chat `telegram_test_chat_id`. Sonst wird die `user.json` des Nutzers **frisch** gelesen (`telegram_chat_id`); `settings.telegram_chat_id` wird nie gelesen. Fehlt der Chat oder ist das Profil unlesbar: Block (`telegram_no_chat_id`) plus Log mit Nutzer-ID, ohne Chat-ID. Schließt Risiko 2 (`model_copy`) und Risiko 5 (`.env`-Rückfall) konstruktiv.
3. **`inbound_reply(chat_id)`**: `_post` verlangt `chat_id == _current_inbound_sender.get()`. Außerhalb eines Webhook-Updates ist die Variable leer, also Block. Deckt unbekannte Absender, `/start` OK/409 und Callback-Edit ab, ohne Profil-Lesen; das `/start`-Rennen (Risiko 3) entfällt.
4. **Formprüfung** `-?\d{1,20}` bedingungslos auf `payload["chat_id"]`.
5. **Reihenfolge in `_post`:** Form → Zweck/Herkunft (Original-ID) → `_guard_code_origin` → Token-/Testmodus-Guards → Drossel. Der 429-Retry bleibt ohne Neuprüfung (S3b).

**Bewusste Abweichungen vom S4-Konzept** (Issue-Kommentar, `fix-1412-versandweg-basis.md:218`), für das Spec-Gate sichtbar:
- **Kein `Settings.user_id`.** Das Empfänger-Objekt trägt die `user_id`; ein Settings-Feld öffnete über `model_copy` dieselbe Lücke wieder.
- **Kein `operator`.** Für Telegram gibt es keinen Produktiv-Aufrufer; die Debug-CLI wird mit klarer Meldung geblockt.
- **`verification` erst in S4b** (SMS-Code an unbestätigte Nummer). Telegram-`/start` antwortet dem Absender des Updates, also `inbound_reply`. Die Aufzählung ist kanalübergreifend, S4b ergänzt sie nur.

**Ehrliches Schutzniveau (Known Limitation):** Schützt gegen Versehen und Regressionen, also genau die Fehlerbilder aus #1412: vergessene `model_copy`-Wege, `.env`-Rückfall, falscher Mandant, neue Aufrufer mit nacktem `TelegramOutput(settings).send`. Gegen absichtlich bösartigen Code im selben Prozess hilft es nicht, Python hat keine Capability-Isolation. Dazu kommt die Restlücke `PUT /api/auth/profile` (`telegram_chat_id` als Freitext): bis S5 ist „Chat ∈ Profil“ kein voller Herkunftsbeleg.

**Nachweisform (ehrlich formuliert):**
- **Produktiv-Block:** Kern-Tests mit Sink am `httpx`-Rand bei `is_test_mode=False`, ohne `_post`-Stub (Lehre #1288). Auf Staging ist alles im Testmodus; ein „fremder Chat geblockt“ dort bewiese nur das Umschreiben auf den Test-Chat, nicht die neue Prüfung.
- **Staging belegt „nichts verstummt“:** Briefing an Test-Nutzer kommt an. Über den **echten Webhook-Eingang** (Lehre #2417) kommen an: Antwort auf `heute`, `/start`-Verbindung, Hinweis an einen unbekannten Absender.
- **Test-Knopf (M3):** Kern-Test „Test-Knopf → Profil-Chat über Produktions-Bot, nicht Test-Chat“.

### Dependencies
- Upstream: `Settings.for_testing`/`with_user_profile` (unverändert), `loader.get_data_dir`, ContextVar (stdlib), Drossel (Klassenebene).
- Downstream:
  - 12 Stellen in notification_service, 9 im Reader, channel_test_service, CLI-Factory.
  - 25 Testdateien bauen `TelegramOutput` direkt.
  - 4 Testdateien stubben `_post`; die Signatur bleibt, sie sind also nicht betroffen.
  - Test-Fakes von `send_telegram_message`/`send_command_reply_telegram`: `test_telegram_chat_id_ownership.py:136,143`, `test_issue_1009_1019_inbound_robustness.py:590,597`, `test_inbound_telegram_connect_rejection.py:46`, `test_kommandoliste_einzelquelle.py:244`, `tests/unit/test_pii_log_maskierung_kanaele.py:67,76`.
- Wächter `test_egress_single_dial_point.py` (Prüfdatum 2027-01-04) bleibt gültig, es entsteht kein neuer Ausgang. Ein zusätzlicher Struktur-Wächter wäre nur mit Prüfdatum zulässig (Regel-Budget). Vorzug: **kein** neuer Wächter, denn der Default-Block **ist** die Struktur.

### Open Questions
- Keine an den PO. Zuschnitt und Zwecke sind oben als Tech-Lead-Entscheidungen mit Begründung festgehalten und werden mit der Spec freigegeben.
- Technisch in /40 verifizieren: Laufen `trip_command_processor.py:935/1547/2478` über den NotificationService? Geht der Callback-Edit an Unbekannte (`reader :421-432`) über `edit_telegram_message_text` mit expliziter chat_id?
