---
entity_id: fix_1412_s4a_empfaengervertrag_telegram
type: module
created: 2026-10-13
updated: 2026-10-13
status: draft
version: "1.0"
tags: [telegram, empfaengervertrag, mandantentrennung, egress, test-knopf, 1412]
workflow: feat-1412-s4a-empfaengervertrag-telegram
issue: 1412
---

# Fix #1412 Scheibe S4a — Empfängervertrag Telegram: Versand nur an belegte Chats

## Approval

- [ ] Approved

## Purpose

Heute greift der Telegram-Ausgang selbst nach `settings.telegram_chat_id`. Wer
die Einstellungen per `model_copy` mit dem Chat eines anderen Nutzers versieht,
oder wessen `user.json` fehlt (dann greift der globale `.env`-Chat), sendet
unbemerkt an den falschen Empfänger. Bei Befehlsantworten wird die übergebene
`chat_id` sogar verworfen (R7). S4a macht den Empfänger zu einem **expliziten,
belegten Objekt**: Der Transport `TelegramOutput._post` sendet nur an einen Chat,
dessen Herkunft belegt ist (Profil-Chat des Nutzers oder Absender des laufenden
Webhook-Updates). Ohne Beleg gilt der Default **Block**. Dazu kommt eine
bedingungslose Formprüfung der Chat-ID. Zusätzlich wird der nutzersichtbare
Defekt des Test-Knopfs („Telegram testen“ landet im Betreiber-Test-Chat, die
Oberfläche meldet Erfolg) in **diesem** Ticket behoben.

## Was diese Scheibe NICHT tut (Klartext)

- Kein Go-Nachzug und keine Härtung von `PUT /api/auth/profile` — das ist
  Scheibe S5 (siehe „Known Limitation“).
- Keine SMS-Seite und kein Zweck `verification` — das ist S4b.
- Kein neuer Struktur-Wächter (Regel-Budget): Der Default-Block **ist** die
  Struktur. Der bestehende `tests/tdd/test_egress_single_dial_point.py`
  bleibt unverändert gültig; es entsteht kein neuer Ausgang.

## Source

- **Identifier:** `TelegramOutput` (Konstruktor, `send`, `_send_fallback_without_parse_mode`, `delete_message`, `edit_message_text`, `_post`), neu `TelegramRecipient` / `RecipientPurpose`
- **File:** `src/output/channels/telegram.py` — `TelegramOutput` (Konstruktor,
  `send`, `_send_fallback_without_parse_mode`, `delete_message`,
  `edit_message_text`, `_post`)
- **File:** `src/output/channels/recipient.py` — neu; Ablage am Bestand geprüft
  (`ls src/output/channels/`: `base.py`, `console.py`, `email.py`,
  `premium_sms.py`, `seven_io_base.py`, `sms.py`, `telegram.py`; kein
  Namenskonflikt)
- **File:** `src/services/notification_service.py`,
  `src/services/inbound_telegram_reader.py`,
  `src/services/channel_test_service.py`, `src/output/channels/base.py`,
  `src/app/cli.py`

> **Schicht-Hinweis:** nur Python-Core (`src/`, `api/`). Kein Go-, kein
> Frontend-Anteil (ADR-0015: kein geteilter Go/Python-Code; der Go-Nachzug ist S5).

## Estimated Scope

- **Files:** produktiv 7 (telegram.py, neues recipient.py,
  notification_service.py, inbound_telegram_reader.py, channel_test_service.py,
  base.py, cli.py); Tests: neuer Helper, neue Testdatei(en), Migration von ca.
  25 Testdateien, die `TelegramOutput` direkt bauen.
- **LoC:** produktiv ca. +170 / −40. Das Workflow-Limit (250) zählt nur
  produktive Spec-Dateien — kein Override erwartet (vor Änderung
  `workflow.py status` fragen). Tests ca. +300, zählen nicht.
- **Risiko:** MEDIUM-HIGH. Wegen des Default-Blocks verstummt jeder übersehene
  Aufrufer produktiv. Deshalb werden **alle** Aufrufer in einem Zug umgestellt,
  kein „Legacy erlaubt“-Übergang.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Settings` (`is_test_mode`, `telegram_test_chat_id`, `telegram_chat_id`) | Config | `for_user` liest im Testkontext den Test-Chat; `settings.telegram_chat_id` wird vom Transport nie mehr gelesen |
| `loader.get_data_dir` / Profil-Loader | Funktion | `for_user` liest `user.json` des Nutzers frisch |
| `contextvars.ContextVar` | stdlib | Herkunftsbeleg „Absender des laufenden Updates“ |
| `TelegramOutput._post` (S3b) | Methode | einziger geschützter Ausgang; Prüfung vor Drossel, genau einmal (auch bei 429) |
| `ChannelBlockedError` (mit `reason_code`) | Exception | Block-Signal |
| `api/routers/webhook.py:52-94` | Eingang | synchroner Handler; `_process_update` läuft vollständig im selben Thread (gemessen, keine Threads/Executor/asyncio im Reader) |
| `tests/tdd/test_telegram_poll_pfad_entfernt.py:53-80` | Wächter | Netz-Import-Verbot im Reader: dort nur `contextvars` und der Typ, kein `httpx` |
| `tests/tdd/test_egress_single_dial_point.py` | Wächter | bleibt unverändert |

## Implementation Details

### Kernregeln

1. **Empfänger an der Instanz, nicht an `send()`.** `TelegramOutput(settings, *, recipient=None)`.
   Passt zu ADR-0014 (frische Instanz je Bubble); die `send`-Signaturen bleiben gleich.
2. **`TelegramRecipient`** — unveränderlicher Typ, nur über zwei Fabriken
   erzeugbar:
   - `for_user(user_id, settings)` (Zweck `user_profile`): Ist
     `settings.is_test_mode` (bestehendes Signal, **kein** neuer Schalter), ist
     der Chat `telegram_test_chat_id`. Sonst wird die `user.json` des Nutzers
     **frisch** gelesen (`telegram_chat_id`); `settings.telegram_chat_id` wird
     **nie** gelesen. Fehlt der Chat oder ist das Profil nicht lesbar: Block
     mit `reason_code=telegram_no_chat_id`; das Log nennt die Nutzer-ID, nie die
     Chat-ID.
   - `inbound_reply(chat_id)` (Zweck `inbound_reply`): `_post` verlangt, dass die
     Chat-ID mit dem Absender des laufenden Webhook-Updates übereinstimmt
     (`ContextVar _current_inbound_sender`, gesetzt in `_process_update` /
     `_process_callback_query` nach dem Parsen, im `finally` zurückgesetzt).
     Außerhalb eines Updates ist die Variable leer ⇒ Block.
3. **Ohne `recipient`** ⇒ Default-Block (`ChannelBlockedError` mit `reason_code`).
4. **Formprüfung** `-?\d{1,20}` bedingungslos (auch Produktion) auf
   `payload["chat_id"]`; Chat-IDs werden vor dem Vergleich normalisiert
   (int aus dem Update ≙ str aus dem Profil).
5. **Reihenfolge in `_post`:** Form → Herkunft je Zweck (auf der **Original-ID**,
   vor jedem Umschreiben) → `_guard_code_origin` → Token-/Testmodus-Guards →
   Drossel. Der 429-Retry bleibt ohne Neuprüfung (genau einmal, S3b). Die
   `_post`-Signatur bleibt unverändert; die vier Test-Stubs bleiben heil.
6. `send`, `edit_message_text`, `delete_message` lesen nicht mehr
   `settings.telegram_chat_id`. Methoden ohne Chat (`answer_callback_query`,
   `set_my_commands`, `get_my_commands`) brauchen keinen Empfänger (nur
   Token-Guard).
7. `RecipientPurpose` (in `recipient.py`) ist **kanalübergreifend** angelegt:
   `user_profile`, `inbound_reply`. S4b ergänzt nur eine Konstante.

### Aufrufer → Zweck (Inventur abgeschlossen, gemessen per `grep TelegramOutput(|get_channel(` in `src/` und `api/`)

| Aufrufer | Stellen | Empfängerquelle → Zweck |
|---|---|---|
| `notification_service.py` (Briefing, Hinweise, Alarme, Vergleich, Amtswarnung) | :700, :722, :785, :858, :1200, :1205, :1336, :1547, :1558, :1882, :1918, :1946 | Helper `_telegram_output()` → `for_user(self._require_user(), self._settings)` — `user_profile` |
| `notification_service.py` `send_command_reply_telegram` / `send_telegram_message` / `edit_telegram_message_text` / `delete_telegram_message` | :2060, :2079, :2096, :2117 | übergebenes `chat_id`/Empfänger-Argument wird tatsächlich verwendet (R7), nicht mehr nur geloggt |
| `notification_service.py` `answer_callback_query` | :2132 | kein Chat, keine Empfängerprüfung |
| `inbound_telegram_reader.py` (Antworten, unbekannter Absender, Callback-Edit, Spinner, `/start` OK/409) | :190, :271, :306, :348, :360, :366, :375, :384, :424, :479, :502, :510, :591, :607 | `inbound_reply(chat_id)` (Absender des laufenden Updates); die `model_copy`-Umgehungen :200, :590, :606 entfallen |
| `channel_test_service.py` | :38 | Test-Knopf, siehe AC-11 (Befund M3) |
| `api/main.py` `set_my_commands` | :84 | kein Chat, unverändert, fail-soft |
| `src/output/channels/base.py` / `src/app/cli.py` (Debug-CLI, globale `.env`) | base.py:133; cli.py:258, :282 | Telegram wird mit klarer Meldung geblockt (kein Zweck `operator`) |
| `trip_command_processor.py` | — | erzeugt kein `TelegramOutput`, sendet nur über `NotificationService` ⇒ keine Änderung |

Hinweis: `settings.can_send_telegram()` (`config.py:478`) liest weiter
`telegram_chat_id` als Opt-in-Vorbedingung. Das bleibt; es ist keine
Empfängerquelle und kein Herkunftsbeleg.

### Messungen aus der Analyse

- **M2:** ContextVar trägt (synchroner Webhook-Handler, keine Threads im Reader).
- **M3:** `channel_test_service.py:25` baut `with_user_profile(uid).for_testing()`;
  `for_testing()` setzt Chat und Bot-Token auf die Test-Werte. Da
  `GZ_TELEGRAM_TEST_CHAT_ID` in Produktion gesetzt ist, geht „Telegram testen“
  an den Betreiber-Test-Chat; beim Nutzer kommt nichts an, die Oberfläche meldet
  Erfolg. Wird in diesem Ticket behoben.
- **M4:** Der globale `.env`-Chat greift heute nur, wenn `user.json` fehlt oder
  unlesbar ist; `for_user` ohne Rückfall lässt daher keinen heute belieferten
  Nutzer verstummen.

## Bewusste Abweichungen vom S4-Konzept

(Konzept: `docs/context/fix-1412-versandweg-basis.md:211-221`.)

- **Kein `Settings.user_id`.** Das Empfänger-Objekt trägt die `user_id`. Ein
  Settings-Feld öffnete über `model_copy` dieselbe Lücke wieder (alte `user_id`
  mit fremdem Chat).
- **Kein Zweck `operator`.** Für Telegram gibt es keinen Produktiv-Aufrufer;
  die Debug-CLI wird mit klarer Meldung geblockt. Eine Aufzählung ohne
  Verbraucher ist Fläche ohne Nutzen.
- **`verification` erst in S4b** (SMS-Code an unbestätigte Nummer). Telegram-
  `/start` antwortet dem Absender des Updates, ist also `inbound_reply`
  (kein Profil-Lesen, damit kein Rennen mit dem Go-Schreiben der Verknüpfung).
  Die Zweck-Aufzählung ist kanalübergreifend; S4b ergänzt sie nur.

## Expected Behavior

- **Input:** jeder Telegram-Sendeversuch (Briefing, Alarm, Befehlsantwort,
  Antwort an Absender, Test-Knopf).
- **Output:** Nachricht geht nur an den belegten Chat; sonst `ChannelBlockedError`
  mit `reason_code` und **kein** HTTP-Call. Legitime Wege (Briefings, Antworten
  auf Befehle, Registrierungshinweis, `/start`-Bestätigung) verstummen nicht.
- **Side effects:** Logs nennen Nutzer-ID, nie Chat-ID. Der Test-Knopf liefert
  bei fehlendem Profil-Chat eine Fehlermeldung statt einer Erfolgsmeldung.

## Acceptance Criteria

Nachweisform für alle ACs: Kern-Test mit Sink am `httpx`-Rand, `is_test_mode=False`,
**ohne** `_post`-Stub (Lehre #1288). Testdatei nach Verhalten benannt, z. B.
`tests/tdd/test_telegram_recipient_contract.py`.

- **AC-1:** Given ein `TelegramOutput`, das ohne Empfänger-Objekt gebaut wurde /
  When es eine Nachricht senden soll / Then wird der Versand mit
  `ChannelBlockedError` (mit `reason_code`) abgelehnt und es findet kein
  einziger HTTP-Call statt.
  - Test: echter `send`-Aufruf, Sink am `httpx.post`, 0 Aufrufe.

- **AC-2:** Given zwei Nutzer A und B, bei denen die Einstellungen per
  `model_copy` den Chat von Nutzer A tragen, der Empfänger aber `for_user(B)` ist
  / When gesendet wird / Then geht die Nachricht ausschließlich an den
  Profil-Chat von B (frisch aus B's `user.json` gelesen), nie an A; hat B keinen
  Chat, wird geblockt.
  - Test: zwei verschiedene Nutzer (CLAUDE.md-Pflicht), Sink prüft Ziel-Chat.

- **AC-3:** Given die `user.json` eines Nutzers fehlt, ist unlesbar oder enthält
  keinen Chat / When für ihn gesendet werden soll / Then wird mit
  `reason_code=telegram_no_chat_id` geblockt, auch wenn ein globaler
  `.env`-Chat gesetzt ist; das Log nennt die Nutzer-ID, nicht die Chat-ID.
  - Test: drei Profilzustände, `.env`-Chat gesetzt, Log-Inhalt geprüft.

- **AC-4:** Given ein Empfänger `inbound_reply(chat_id)` / When außerhalb eines
  Webhook-Updates gesendet wird / Then wird geblockt; innerhalb eines Updates
  geht die Antwort nur an den Absender-Chat, ein anderer Chat wird geblockt; und
  nach einer Exception im Update ist der Herkunftsbeleg wieder zurückgesetzt
  (eigener Testfall).
  - Test: echtes `_process_update`, Fälle: außerhalb, innerhalb gleicher Chat,
    innerhalb fremder Chat, nach Exception.

- **AC-5:** Given eine Chat-ID, die als Zahl (aus dem Update) bzw. als Text (aus
  dem Profil) vorliegt / When sie verglichen wird / Then werden beide
  normalisiert gleich behandelt — legitime Antworten werden nicht fälschlich
  geblockt und fremde Chats nicht durchgelassen.
  - Test: int/str-Kombinationen, je ein Gleich- und ein Fremdfall.

- **AC-6:** Given eine nicht-numerische Chat-ID (auch in Produktion, ohne
  Testmodus) / When gesendet werden soll / Then wird vor jedem HTTP-Call
  geblockt.
  - Test: z. B. `"abc"`, `"12; DROP"`, leer, zu lang; 0 Sink-Aufrufe.

- **AC-7:** Given ein Nutzer schickt einen Befehl (z. B. `heute`) über den echten
  Webhook-Pfad `_process_update` / When die Antwort gesendet wird / Then geht sie
  tatsächlich an die übergebene `chat_id` des Absenders (R7 geschlossen, vorher
  wurde die `chat_id` verworfen).
  - Test: echtes `_process_update`, Sink prüft Ziel-Chat der Antwort.

- **AC-8:** Given ein unbekannter Absender schreibt dem Bot / When die Antwort
  gesendet wird / Then erhält er weiterhin den Registrierungshinweis ohne
  Nutzerdaten; und `/start` (OK und 409) erreicht den Absender ohne Profil-Lesen
  (kein Rennen mit dem Go-Schreiben der Verknüpfung).
  - Test: echtes `_process_update` mit unbekanntem Absender und `/start`-Fällen.

- **AC-9:** Given der Versand schlägt zunächst mit HTML-400 oder 429 fehl bzw.
  eine Nachricht besteht aus mehreren Bubbles / When wiederholt bzw. weiter
  gesendet wird / Then geht der HTML-400-Rückfall an denselben Empfänger, bei 429
  wird genau einmal geprüft (kein Doppel-Log), und jede Bubble (frische
  Instanz) trägt den Empfänger.
  - Test: Sink liefert 400 bzw. 429; Zähler der Prüfungen und Ziel-Chat je Bubble.

- **AC-10:** Given das Bot-Menü (`set_my_commands`) und `answer_callback_query`
  / When sie aufgerufen werden / Then funktionieren sie unverändert ohne
  Empfänger (nur Token-Guard); das Bot-Menü bleibt fail-soft.
  - Test: beide ohne Empfänger gegen Sink; Bot-Menü-Fehler wirft nicht.

- **AC-11:** Given ein Nutzer mit Profil-Chat drückt „Telegram testen“ /
  When der Test-Knopf ausgelöst wird / Then geht die Testnachricht an den
  Profil-Chat dieses Nutzers über den Produktions-Bot und nicht an den
  Betreiber-Test-Chat; der Telegram-Zweig durchläuft `for_testing()` nicht.
  Hat der Nutzer keinen Profil-Chat, erhält er eine Fehlermeldung statt einer
  Erfolgsmeldung. Der E-Mail-Zweig des Test-Knopfs bleibt unverändert (#198).
  - Test: `GZ_TELEGRAM_TEST_CHAT_ID` gesetzt, `is_test_mode=False`; Sink
    prüft Ziel-Chat und Bot-Token; Fall ohne Profil-Chat; E-Mail-Zweig unverändert.

- **AC-12:** Given der Testkontext (`settings.is_test_mode`, bestehendes Signal,
  kein neuer Schalter) / When `for_user` einen Empfänger liefert / Then ist der
  Chat der `telegram_test_chat_id`, sodass Staging und Tests funktionsfähig
  bleiben.
  - Test: `is_test_mode=True` ⇒ Test-Chat; `False` ⇒ Profil-Chat.

- **AC-13:** Given die Debug-CLI ohne Nutzer (globale `.env`) / When sie den
  Telegram-Kanal anfordert / Then wird der Kanal mit klarer Meldung abgelehnt,
  nicht still ungeschützt gesendet.
  - Test: `get_channel("telegram")` bzw. CLI-Aufruf ⇒ klare Fehlermeldung, 0 HTTP-Calls.

## Known Limitations

Der Schutz gilt gegen Versehen und Regressionen — genau die Fehlerbilder aus
#1412: vergessene `model_copy`-Wege, `.env`-Rückfall, falscher Mandant, neue
Aufrufer mit nacktem `TelegramOutput(settings).send`. Gegen absichtlich
bösartigen Code im selben Prozess hilft er nicht (Python hat keine
Capability-Isolation).

~~`PUT /api/auth/profile` nimmt `telegram_chat_id` als Freitext.~~ Veraltet
(korrigiert mit #1412 S5): Seit #2141 übernimmt `PUT /api/auth/profile` für
`telegram_chat_id` nur noch den Leerstring („Telegram trennen“); gesetzt wird
die `chat_id` ausschließlich über den Einmal-Token-Flow `/start TOKEN` →
`PostTelegramConnectHandler` (`internal/handler/telegram_connect.go`). Damit ist
„Chat ∈ Profil“ ein Herkunftsbeleg. Festgehalten in ADR-0087 „Empfängerschutz“.

## Test Plan

- **Kern-Schicht (deterministisch, offline):** nur benannte Testdateien,
  `--disable-socket`. Neue Testdatei(en) für AC-1 bis AC-13 mit Sink am
  `httpx`-Rand. Gemeinsamer Test-Helper für Test-Empfänger; Migration der ca. 25
  Testdateien, die `TelegramOutput` direkt bauen. Die vier `_post`-Stub-Dateien
  (`tests/unit/test_briefing_cross_tenant_recipient_isolation.py`,
  `tests/unit/test_briefing_recipient_logging.py`,
  `tests/tdd/_befehl_e2e_fixtures.py`,
  `tests/tdd/test_egress_single_dial_point.py`) bleiben unberührt, da die
  `_post`-Signatur gleich bleibt. Mitzuziehen sind die Fakes von
  `send_telegram_message` / `send_command_reply_telegram`:
  `test_telegram_chat_id_ownership.py:136,143`,
  `test_issue_1009_1019_inbound_robustness.py:590,597`,
  `test_inbound_telegram_connect_rejection.py:46`,
  `test_kommandoliste_einzelquelle.py:244`,
  `tests/unit/test_pii_log_maskierung_kanaele.py:67,76`. Prüfling wird relativ
  zur Testdatei aufgelöst. Netz-Import-Verbot im Reader
  (`test_telegram_poll_pfad_entfernt.py:53-80`) bleibt eingehalten: nur
  `contextvars` und der Typ werden importiert.
- **Staging (ehrlich):** Staging läuft im Testmodus und kann den
  Produktiv-Block und den Test-Knopf-Defekt (AC-11) **nicht** belegen — das
  belegen allein die Kern-Tests. Staging belegt „nichts verstummt“, und zwar über
  den **echten Webhook-Eingang**: Antwort auf `heute`, `/start`-Verbindung,
  Hinweis an einen unbekannten Absender, Briefing an den Test-Nutzer kommt an.
  Das wird nicht als Blockbeweis verkauft.
- Mail-Validatoren entfallen (kein E-Mail-Pfad berührt).

## Randbedingungen

- **Multi-User:** Jeder datenbewegende Pfad wird mit zwei verschiedenen Nutzern
  getestet (AC-2); echte `user_id` aus dem Kontext, nie `"default"`.
- Blockaden bleiben sichtbar (Fehler/Log), nie still verschluckt; alle vier
  Kanäle bleiben gleichrangig.
- **Regel-Budget:** kein neues Gate, kein neuer Wächter.
- Schema-relevante Dateien werden nicht berührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue in S4a; der ADR „Empfängerschutz“ gehört zu S5.
- **Rationale:** Setzt ADR-0003 (Mandantentrennung), ADR-0012 (HTML-400-Rückfall
  an gleichen Empfänger) und ADR-0014 (frische Instanz je Bubble) um; ADR-0072
  (Testkonto nur über `is_test_user`) bleibt unberührt.

## Changelog

- 2026-10-13: Initial spec created (S4a, aus `docs/context/feat-1412-s4a-empfaengervertrag-telegram.md`)
