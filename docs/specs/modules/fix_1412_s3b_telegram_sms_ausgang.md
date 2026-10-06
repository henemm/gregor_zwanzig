---
entity_id: fix_1412_s3b_telegram_sms_ausgang
type: module
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
tags: [telegram, sms, premium-sms, egress, struktur-test, 1412]
workflow: fix-1412-s3b-telegram-sms-guard
issue: 1412
---

# Fix #1412 Scheibe S3b — Telegram und SMS: ein geschützter Netzausgang je Kanal

## Approval

- [ ] Approved

## Purpose

Heute geht jede Telegram-Nachricht über sieben öffentliche Methoden an das
Netz, und jede Methode ruft ihre Schutzprüfungen (Herkunft, Test-Token,
Test-Chat) selbst auf — in drei verschiedenen Reihenfolgen, bei zwei Methoden
(`answer_callback_query`, `get_my_commands`) gar nicht. Wer eine achte Methode
ergänzt und die Prüfung vergisst, sendet ungeschützt. S3b verlegt die
Prüfungen in den **einen** Ausgang `TelegramOutput._post`, schafft für SMS und
Premium-SMS den einen Ausgang `SevenIoChannelBase._post` (reiner Transport)
und erweitert den bestehenden Struktur-Test um den `httpx`-Teil: kein
POST-Versand in `src/`+`api/` außer an den erlaubten Ausgängen und drei
begründeten localhost-Ausnahmen.

Die Scheibe ist **strukturell und verhaltensneutral**, mit genau einer
gewollten Verschärfung (AC-4).

## Was diese Scheibe NICHT tut (Klartext)

- **S3b schließt die Empfängerlücke in Produktion NICHT.** Die drei
  Telegram-Prüfungen für Test-Token und Test-Chat sind nur im Test-Modus
  aktiv. In Produktion und auf Staging läuft das System mit normalen
  Einstellungen (`is_test_mode` ist dort aus) — diese Prüfungen tun dort
  nichts. Das ist heute so und bleibt nach S3b so. Die Herkunftssperre
  (`_guard_code_origin`) wirkt dagegen immer; sie bleibt unverändert.
- Der **scharfe Empfängervertrag** — „es wird nur an die für diesen Nutzer
  hinterlegte und bestätigte Adresse gesendet", einschließlich Nutzerkennung
  in den Einstellungen und eines Zweck-Parameters für legitime Ausnahmen
  (Antwort an Absender, SMS-Bestätigungscode an eine noch unbestätigte
  Nummer) — kommt mit **Scheibe S4a/b** (PO-Entscheid 2026-07-29, eigene
  PO-Freigabe, 300–500 Zeilen). Nichts davon wird hier vorgezogen.
- Ein heute bestehender Rest-Umweg bleibt offen: Wer im Code per
  `model_copy(update={...})` die Empfängerdaten austauscht, umgeht die
  Profilprüfung. Das schließt erst S4.
- Warum trotzdem sinnvoll: S3b legt das Fundament, auf dem S4 genau **eine**
  Stelle schärfen muss statt sieben Methoden. Und es verhindert ab sofort,
  dass ein neuer Sendeweg unbemerkt am Ausgang vorbeigebaut wird.

## Source

- **File:** `src/output/channels/telegram.py` — Klasse `TelegramOutput`,
  `_post` (:372-409, zwei `httpx.post` :391/:409, Docstring :377-382
  „KEINE Guards"); Guards `_guard_code_origin` (:194-227),
  `_guard_test_mode_chat_id` (:229), `_guard_test_mode_bot_token` (:250),
  `_guard_test_mode_target_chat` (:268)
- **File:** `src/output/channels/seven_io_base.py` — `SevenIoChannelBase.send`
  (:155-187), `httpx.post` direkt in `send` (:171-176); Guards :108-149
  (Sandbox-Key, Herkunftssperre)
- **File:** `tests/tdd/test_egress_single_dial_point.py` — Struktur-Test
  (`smtplib`-Teil aus S3a), `EXPIRY = 2026-10-28` (:57), Deckel 0 (:70)

> **Schicht-Hinweis:** nur Python-Core. Kein Go-, kein Frontend-Anteil.

## Estimated Scope

- **Files:** 5 (2 produktiv, 2 Test, 1 Doku)
- **LoC:** produktiv ca. +30 netto (Telegram ca. +20, SMS ca. +10); Test ca.
  +300. Das Workflow-Limit (250) zählt nur produktive Spec-Dateien — kein
  Override erwartet (vorher `workflow.py status` fragen).
- **Risiko:** MEDIUM — Sicherheitspfad aller Telegram-Sendungen, aber
  verhaltensneutral bis auf AC-4; alle Produktivwirkungen sind No-Op.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Settings` (`is_test_mode`, `telegram_chat_id`, `telegram_test_chat_id`, `sms_to`, `premium_sms_reply_to`) | Config | Eingabe der Guards; `is_test_mode` default False (`config.py:178`), gesetzt nur über `for_testing()` / Testnutzer-Profil (`config.py:366/:382`) |
| `running_origin` / `_guard_code_origin` | Funktion | Herkunftssperre, schreibt bei Herkunft „test" auf `telegram_test_chat_id` um |
| `TelegramOutput._reserve_send_slot` | Methode | Drossel; Guards müssen **davor** laufen |
| `tests/tdd/test_egress_single_dial_point.py` | Test | Vorlage und Ziel des erweiterten Struktur-Tests (Alias-Auflösung, Ausnahmen-Klasse, Selbstnachweise) |
| `tests/tdd/test_telegram_test_mode_guard.py:121` | Bestandstest | `test_diverging_test_chat_id_blocks_send_without_any_post` — muss ohne Edit grün bleiben |
| `tests/tdd/test_telegram_test_isolation.py:392-430` | Bestandstest | `test_existing_1288_chat_guard_unchanged` — erwartet exakten Text `chat_id='<PROD>'` |
| `tests/unit/test_channel_blocked_missing_recipient.py:70-101` | Bestandstest | #2144-Leer-Check in `send` |
| `tests/tdd/test_channel_origin_guard_parity.py` | Bestandstest | Herkunftsparität je Kanalklasse |
| `src/app/egress_guard.py` (#1337) | Fremd-Mechanik | patcht `HTTPTransport.handle_request` (:153-159), nur Test/Staging — keine Kollision |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/channels/telegram.py` | MODIFY | Guard-Sequenz in `_post` vor `_reserve_send_slot`, genau einmal (nicht beim 429-Retry :409); Guard-Aufrufe aus `_send_fallback_without_parse_mode`, `delete_message`, `edit_message_text`, `set_my_commands` entfernen; Docstring :377-382 („KEINE Guards") neu |
| `src/output/channels/seven_io_base.py` | MODIFY | `httpx.post` :171-176 → `_post(url, api_key, payload)` als **reiner Transport**; Guards bleiben in `send` :162-165 |
| `tests/tdd/test_egress_single_dial_point.py` | MODIFY | httpx-Teil: eigene Erlaubt-Menge + `AUSNAHMEN_HTTPX` (3, Deckel 3); Kommentar :68-69 („zwei Ausnahmen") korrigieren; `EXPIRY` → 2027-01-04 (:55-57, Assertion :505) |
| `tests/tdd/test_telegram_post_is_single_guarded_exit.py` | CREATE | Sink-Test über alle 7 öffentlichen Telegram-Methoden + Test-Unterklasse mit Methode ohne eigene Guards |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Zeile in der Prüfdaten-Tabelle (ab :390) für `test_egress_single_dial_point` (fehlt heute) |

**Nicht in dieser Scheibe:** scharfer Empfängervertrag (S4a/b),
`getUpdates`-GET (#1369), `notification_service.py`/`inbound_*`-Aufrufer.

## Implementation Details

### 1. Telegram `_post`: Guard-Sequenz (der Kernpunkt)

**Befund (gelesen):** Die heutigen Sequenzen sind nicht gleich:

| Methode | Sequenz heute | Chat-Prüfung prüft |
|---|---|---|
| `send` (:435-448) | Herkunft(Settings-Chat) → Leer-Check `ChannelBlockedError` (:440) → Token → `_guard_test_mode_chat_id()` | Settings-Wert, **vor** dem Umschreiben |
| `_send_fallback_without_parse_mode` (:511-513), `delete_message` (:555-557), `edit_message_text` (:593-595) | Herkunft(Argument) → Token → `_guard_test_mode_target_chat(c)` | den **umgeschriebenen** Wert |
| `set_my_commands` (:649) | nur Token | — |
| `answer_callback_query` (:632), `get_my_commands` (:677) | keine | — |

Ein naiver Payload-Check in `_post` **nach** dem Umschreiben würde `send`
schwächen (Settings-Chat-Prüfung sähe nur noch den umgeschriebenen Wert) und
zwei Bestandstests rot färben (`test_diverging_test_chat_id_blocks_send_without_any_post`,
`test_existing_1288_chat_guard_unchanged`). Deshalb die Schalter-Lösung:

Neue Sequenz in `_post`, **vor** `_reserve_send_slot`, **einmal** pro
`_post`-Aufruf (nicht erneut beim 429-Wiederholungsversuch :409):

1. `_guard_test_mode_bot_token()` für **alle** Endpunkte.
2. Enthält der Payload `"chat_id"`: Kopie des Payloads;
   `c = _guard_code_origin(payload["chat_id"])` (idempotent: Test-Chat bleibt
   Test-Chat, der 400-Rückfall ohne `parse_mode` bleibt ok).
3. Nur bei `bound_chat=True` (wird **nur von `send`** übergeben):
   zusätzlich `_guard_test_mode_chat_id()` — Settings-Wert, alter
   Fehlertext, unverändert.
4. `_guard_test_mode_target_chat(c)`; danach `payload["chat_id"] = c`.

`send` behält seinen eigenen Origin-Aufruf und den Leer-Check (sonst kippt
`tests/unit/test_channel_blocked_missing_recipient.py:70-101`) und übergibt
`bound_chat=True`. Eine künftige Methode ohne Schalter bekommt mindestens das
Niveau der heutigen Argument-Methoden (Schritte 1, 2, 4).

### 2. SMS / Premium-SMS: `_post` als reiner Transport

`SevenIoChannelBase._post(url, api_key, payload)` wird der **einzige**
`httpx.post` der Basisklasse. Die Guards (Sandbox-Key :108-125,
Herkunftssperre :127-149, Leer-Check `_resolve_recipient`) **bleiben in
`send`**. Begründung nach dem S3a-Kriterium („Prüfung in den gemeinsamen Weg
nur, wenn die Aufruferzahl es rechtfertigt"): `_post` hat genau **einen**
Aufrufer (`send`), und `send` ist selbst bereits der gemeinsame Pfad für SMS
und Premium-SMS; keine Unterklasse überschreibt `send`. Telegram dagegen hat
sieben Aufrufer — dort lohnt die Verlagerung. Optionaler Zusatztest: keine
Unterklasse überschreibt `send`.

### 3. Struktur-Test `httpx`-Teil (Erweiterung des bestehenden Wächters)

- **Erfasste Formen (AST, mit Alias-Auflösung):** `httpx.post(...)`,
  Modul-Alias (`import httpx as h`), `from httpx import post [as p]`,
  `httpx.request("POST", …)`, `httpx.stream("POST", …)`,
  `httpx.Client(...).post(...)` und `httpx.AsyncClient(...).post(...)`
  (direkt verkettet). **Nur POST**, nicht `httpx.get` (Datenabruf per GET in
  20+ Provider-Dateien; eine Ausnahmeliste in Dutzendgröße würde sich selbst
  erodieren).
- **Erlaubt-Menge (eigene Menge für httpx):** `TelegramOutput._post`,
  `SevenIoChannelBase._post`.
- **`AUSNAHMEN_HTTPX` (Deckel 3), je Eintrag Fundstelle, Begründung
  ≥15 sinnvolle Zeichen, Frist:**
  - `src/lib/mq_notify.py:45` — localhost-Benachrichtigung an die Claude-MQ,
    kein Endnutzer-Empfänger
  - `src/services/inbound_telegram_reader.py:635` — localhost-Aufruf an den
    eigenen Dienst, kein Endnutzer-Empfänger
  - `src/services/inbound_sms_reader.py:251` — localhost-Aufruf
    (premium-sms-learn), kein Endnutzer-Empfänger
- **Vor dem Bau gemessen** (Datenabruf-Clients): `.post` an
  `radar_service.py:1019`, `validation/ground_truth.py:41`,
  `validation/geosphere_validator.py:51` per grep ausschließen; sind es
  nur GET, bleiben sie außen vor.
- **Selbstnachweis je erfasster Form:** künstliche Attrappe mit je einer
  Form außerhalb der Erlaubt-Menge wird namentlich gemeldet; Deckel-Überschreitung
  und abgelaufene Frist schlagen fehl.
- **Repo-Wurzel** weiterhin relativ zur Testdatei (`Path(__file__).resolve().parents[N]`).

### 4. Prüfdatum (Regel-Budget)

`EXPIRY` in `test_egress_single_dial_point.py` wird von `2026-10-28` auf
**`2027-01-04`** (+90 Tage) gesetzt — Konstante **und** maschinell auffindbarer
Text (Selbstnachweis :505 mitziehen). `EXPIRY` wird nirgends gegen
`date.today()` geprüft (:502-507 nur Konstante/Text), daher entsteht am
29.10. kein CI-Rot. Zusätzlich wird in der Prüfdaten-Tabelle von
`docs/reference/gates_und_ratschen.md` (ab :390) eine Zeile mit diesem Datum
ergänzt. Am Prüfdatum gilt: kein nachweisbarer Fang → Rückbau.

## Expected Behavior

- **Input:** jeder Sendeversuch über eine der sieben Telegram-Methoden bzw.
  über `SmsOutput`/`PremiumSmsOutput.send`.
- **Output:** identisch zu heute (gleiche Nachricht, gleiche Fehlertexte,
  gleiche Blockaden) — ausgenommen AC-4.
- **Side effects:** Guards laufen künftig an genau einer Stelle je Kanal.
  Prod/Staging mit normalen `Settings()` merken nichts. Der Struktur-Test
  schlägt an, sobald ein neuer POST-Weg am Ausgang vorbei entsteht.

## Acceptance Criteria

- **AC-1:** Given der Test-Modus mit falscher Konfiguration (z. B. abweichender
  Test-Chat oder abweichender Bot-Token) / When jede der **sieben**
  öffentlichen Telegram-Methoden (`send`, Rückfall ohne Formatierung,
  `delete_message`, `edit_message_text`, `answer_callback_query`,
  `set_my_commands`, `get_my_commands`) tatsächlich zum Senden aufgerufen wird
  / Then wird mit `OutputConfigError` abgelehnt und es findet **kein einziger**
  Netzaufruf statt (0 Aufrufe an `httpx.post`).
  - Test: echter Sendeaufruf der öffentlichen Methode mit Sink am Transport
    (`httpx.post`); kein isolierter Guard-Aufruf, kein Mock-Theater.
    Ausnahme je Methode: wo AC-4 gilt, ist der Token-Fall der Prüffall.

- **AC-2:** Given eine neue Methode (Test-Unterklasse von `TelegramOutput`),
  die `_post` aufruft und **keine eigenen** Prüfungen mitbringt / When sie in
  falscher Test-Konfiguration sendet / Then wird sie trotzdem blockiert, mit 0
  Netzaufrufen — die Prüfung hängt am Ausgang, nicht an der einzelnen Methode.
  - Test: Unterklasse in der Testdatei, Sink am `httpx.post`.

- **AC-3:** Given die bestehenden Telegram-Schutztests (#1288 Chat-Guard,
  #1363 Test-Isolation, #1476 Herkunft, #2144 Leer-Check) und die bestehenden
  SMS-Sink-Tests / When sie nach dem Umbau laufen / Then sind alle grün
  **ohne Änderung an den Tests**, und die Fehlertexte sind wortgleich
  (insbesondere `chat_id='<PROD>'`).
  - Test: Bestandstests aus der Abhängigkeitstabelle, unverändert.

- **AC-4:** Given der Test-Modus mit abweichendem Bot-Token / When
  `answer_callback_query` oder `get_my_commands` senden / Then werden sie
  blockiert (0 Netzaufrufe) — **gewollte Verschärfung**; sie hatten bisher
  keine Token-Prüfung. In Produktion und auf Staging (`Settings()`, Test-Modus
  aus) ändert sich nichts; der einzige Produktivaufrufer
  (`notification_service.py:2095`) ist fail-soft.
  - Test: Sink am `httpx.post`, Fall mit abweichendem Token je Methode; ein
    Gegenfall ohne Test-Modus bleibt unberührt.

- **AC-5:** Given ein Sendeaufruf, der über den Drossel-Mechanismus läuft /
  When `_post` aufgerufen wird (auch mit Wiederholung nach HTTP 429) / Then
  laufen die Prüfungen **vor** `_reserve_send_slot` und **genau einmal** pro
  `_post`-Aufruf, nicht erneut beim Wiederholungsversuch.
  - Test: Reihenfolge (Guard vor Slot-Reservierung) und Zähler am Sink für
    einen 429-Fall.

- **AC-6:** Given SMS und Premium-SMS / When der Code geprüft und gesendet
  wird / Then liegt `httpx.post` nur noch in `SevenIoChannelBase._post`
  (reiner Transport), die Guards laufen weiterhin in `send`, und die
  bestehenden SMS-Sink-Tests sind ohne Edit grün.
  - Test: Bestandstests + Struktur-Test (AC-7) + optional „keine Unterklasse
    überschreibt `send`".

- **AC-7:** Given der erweiterte Struktur-Test läuft gegen `src/` und `api/` /
  When er POST-Wege per `httpx` sucht / Then findet er ausschließlich die zwei
  erlaubten Ausgänge und die drei dokumentierten localhost-Ausnahmen, meldet
  jeden anderen POST **namentlich**, hält den Deckel von 3 Ausnahmen ein und
  weist für **jede** erfasste Form (siehe Abschnitt 3) per Selbstnachweis
  nach, dass er sie fängt.
  - Test: `tests/tdd/test_egress_single_dial_point.py` (httpx-Teil +
    Selbstnachweise). `EXPIRY = 2027-01-04` als Text auffindbar; Zeile in
    `gates_und_ratschen.md` vorhanden.

- **AC-8:** Given die fertige Umsetzung / When der Guard-Block testweise aus
  `TelegramOutput._post` entfernt wird (Mutations-Gegenprobe, per
  String-Ersetzung mit externer Sicherungskopie) / Then werden die
  AC-1- und AC-2-Fälle rot — und es wird dokumentiert, **welcher** Test rot
  wurde; wird keiner rot, ist das ein Finding.
  - Test: Adversary-Phase, Mutationen nur per String-Ersetzung, nie
    `git checkout/stash/reset`. Zusätzlich: Schalter `bound_chat` entfernt →
    `test_diverging_test_chat_id_blocks_send_without_any_post` rot.

## Offene Messpunkte (in /40 zu messen)

1. **Reihenfolge Token-vor-Origin bei Doppelfehler:** In `_post` läuft der
   Token-Guard zuerst, die Argument-Methoden riefen bisher Origin zuerst.
   Bei einem Doppelfehler könnte sich der gemeldete Fehlertext ändern.
   **Default:** Origin-vor-Token **beibehalten**, falls auch nur ein Test die
   Reihenfolge zusichert; sonst darf die Reihenfolge laut Abschnitt 1 gelten.
2. **`get_my_commands`-Tests im Test-Modus?** Zwei Telegram-
   `get_my_commands`-Tests (Zeilen 671/686 der jeweiligen Datei) — prüfen, ob
   sie im Test-Modus laufen und AC-4 sie rot färbt. **Default:** läuft ein
   Test im Test-Modus mit abweichendem Token, ist das ein Finding gegen AC-4
   und wird in /40 benannt, nicht stillschweigend am Test angepasst.

## Known Limitations (ehrliche Grenzen)

- Wird ein `httpx`-Client in einer Variablen gebunden und erst danach
  `.post` gerufen, erkennt der Struktur-Test das **nicht** (nur direkt
  verkettete Formen).
- Die Telegram-Bot-API akzeptiert `sendMessage` auch per GET; der
  POST-Scan lässt diesen Weg offen.
- `inbound_telegram_reader.py:198` (`getUpdates`-GET mit Bot-Token) ist
  #1369, nicht Scope.
- **Nachweis nur in der Kern-Schicht** (Offline-Sink, `--disable-socket`).
  Auf Staging sind die Guards No-Ops: Staging ist hier **nur Smoke** (Dienste
  gesund, Briefing-Telegram kommt an) und liefert **keinen Blockbeweis**. Das
  wird nicht als PASS verkauft.
- Die produktive Empfängerlücke bleibt bis S4a/b offen (siehe „Was diese
  Scheibe NICHT tut").

## Test-Plan

- **Kern-Schicht (deterministisch, offline):** nur benannte Testdateien,
  `--disable-socket`: `tests/tdd/test_telegram_post_is_single_guarded_exit.py`,
  `tests/tdd/test_egress_single_dial_point.py`, die Bestandstests der
  Abhängigkeitstabelle, die bestehenden SMS-Sink-Tests. Nachweis über echte
  Sendeaufrufe mit Sink am `httpx.post`. Testdateien werden nach Verhalten
  benannt, nicht nach Issue-Nummer; der Prüfling wird relativ zur Testdatei
  aufgelöst (Pfadregel #1409). Gezielte Regression, keine Vollsuite.
- **Staging (nach PR-Merge und Auto-Deploy):** Smoke — `/api/health` 200,
  ein Briefing an den Test-Trip, Telegram-Nachricht kommt an. Kein
  Blockbeweis (Guards dort No-Op). Verdict nicht als Blockade-PASS formulieren.
- Mail-Validatoren entfallen (kein E-Mail-Pfad berührt).

## Randbedingungen

- **Regel-Budget:** Der erweiterte Struktur-Test trägt das Prüfdatum
  **2027-01-04**; kein nachweisbarer Fang bis dahin → Rückbau. Er ersetzt
  das bisherige Datum 2026-10-28 (keine zusätzliche Regel).
- **Multi-User:** Die Guards laufen gegen die `Settings` des sendenden
  Nutzers; es werden keine neuen nutzerbezogenen Endpunkte eingeführt.
- Blockaden bleiben sichtbar (Fehler/Log wie heute), nie still verschluckt;
  alle vier Kanäle bleiben gleichrangig.
- Schema-relevante Dateien werden nicht berührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Strukturelle Verlagerung bestehender Prüfungen in einen
  gemeinsamen Ausgang, keine neue Entscheidungsfläche. Bestätigt die
  S3a-Leitentscheidung (Prüfung im gemeinsamen Weg nur bei mehreren
  unabhängigen Aufrufern) und ADR-0006 (Sink statt Mock).

## Changelog

- 2026-10-06: Initial spec created (S3b, aus `docs/context/fix-1412-s3b-telegram-sms-guard.md`)
