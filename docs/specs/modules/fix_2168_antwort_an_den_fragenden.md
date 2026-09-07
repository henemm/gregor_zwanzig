---
entity_id: fix_2168_antwort_an_den_fragenden
type: module
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [bug, inbound, telegram, kanaltreue, issue-2168]
---

# Antwort an den Fragenden statt an den Betreiber (#2168)

## Approval

- [ ] Approved

## Purpose

Eine eingehende Telegram-Nachricht von einer Chat-ID, die keinem Nutzerprofil zugeordnet ist,
wird heute mit dem Registrierungshinweis beantwortet — aber die Antwort geht an die Chat-ID des
Basis-/Betreiberprofils, nicht an den Fragenden. Dieser Fix richtet die Antwort an den Absender
und nagelt zugleich das (korrekte) Schweigen des E-Mail-Pfads gegenüber unbekannten Absendern
fest, das heute von keinem Test bewacht ist.

## Source

- **File:** `src/services/inbound_telegram_reader.py`
- **Identifier:** `InboundTelegramReader._process_update`, Zweig `user_id == "default"`
  (`:181-191`, wirksame Zeile `:190`)

Schicht: **Python-Core / Domain-Backend** (`src/services/`). Kein Go-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** Produktivcode ~+2/-1, Tests ~+100…170
- **Files:** 3 (1 MODIFY, 2 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NotificationService.send_telegram_message` (`src/services/notification_service.py:1828-1845`) | unverändert | Naht zum Kanal; nimmt `chat_id` entgegen, nutzt sie nur im Fehler-Log |
| `TelegramOutput.send` (`src/output/channels/telegram.py:379-421`) | unverändert | liest die Zieladresse ausschließlich aus `settings.telegram_chat_id` (`:403`) |
| `TelegramOutput`-Wächter (`telegram.py:162-252`) | unverändert | `_guard_code_origin`, `_guard_test_mode_chat_id`, `_guard_test_mode_target_chat` — alle hängen an `settings.telegram_chat_id` |
| `Settings.with_user_profile` (`src/app/config.py:355-399`) | unverändert | übernimmt `profile["telegram_chat_id"]` 1:1 (`:387-388`); fällt für `"default"` auf die Basis zurück (`:376-377`) |
| `lookup_user_by_telegram_chat_id` (`src/app/loader.py:1244-1265`) | unverändert | findet den Nutzer exakt über den Treffer auf `telegram_chat_id` |
| `running_origin` (`src/app/origin_guard.py:30-41`) | unverändert | Herkunftssperre — bestimmt, wo ein Test messen kann |
| `InboundEmailReader._process_single` / `_authorize` (`src/services/inbound_email_reader.py:94-162`, `:188-202`) | unverändert | Prüfling für AC-2, **kein** Codeeingriff |

## Implementation Details

Der Aufruf im `default`-Zweig übergibt die richtige `chat_id` bereits — sie wird nur nirgends
verwendet. Gesendet wird an `settings.telegram_chat_id`. Der Fix setzt genau diese Größe:

```python
# src/services/inbound_telegram_reader.py, Zweig `user_id == "default"` (~:182-191)
mid = self._notification_service.send_telegram_message(
    chat_id=chat_id,
    subject="Registrierung erforderlich",
    body=(...),
    settings=settings.model_copy(update={"telegram_chat_id": chat_id}),
)
```

**Warum diese Form und nicht ein neuer `chat_id`-Parameter an `TelegramOutput.send()`:** Die
drei Telegram-Wächter (`telegram.py:162-252`) messen an `settings.telegram_chat_id`. Setzt der
Fix genau diese Größe, prüfen alle drei weiterhin die **tatsächlich verwendete** Adresse. Ein
zusätzlicher Parameter würde `_guard_test_mode_chat_id` (`:197-216`) an der falschen Größe
messen lassen — der Wächter würde still zum Stellvertreter. Das Muster existiert bereits im
selben Modul: `_process_start_command` (`:436`) baut genau dieses `model_copy`.

**Kein weiterer Eingriff.** Ausdrücklich unverändert bleiben:
`inbound_telegram_reader.py:305-317` (Callback-Pfad — reicht die `chat_id` bis in den Payload
durch, `telegram.py:550,561`, korrekt), `notification_service.py:1809-1845` (keine
Signaturänderung), `telegram.py:162-252`, und der gesamte Produktivcode von
`inbound_email_reader.py` (dort ist kein Defekt, nur eine Testlücke).

### Nachweisform — die Messstelle ist erzwungen, nicht frei gewählt

**Am Draht (`httpx.post`-Payload) ist der Empfänger nicht messbar.** `_guard_code_origin`
(`telegram.py:162-195`) hängt nicht an `is_test_mode`, sondern an der Herkunft des Codes
(`origin_guard.py:30-41`, exakter Pfadvergleich gegen die Prod-/Staging-Wurzel). Aus jedem
Worktree — also in jedem Testlauf — schaltet er die Ziel-Chat-ID auf `telegram_test_chat_id`
um oder bricht hart ab. Ein Payload-Test sähe immer nur die Test-Chat-ID und wäre ein blinder
Wächter.

**Höchste erreichbare Messstelle: die Konstruktor-Naht von `TelegramOutput`.** Muster im
Bestand: `Kanalmitschrift` / `_aufzeichner_installieren`
(`tests/tdd/test_kanaltreue_adhoc_antwort.py:115-192`, konkret `:178`) ersetzt
`notification_service.TelegramOutput` durch eine echte Klasse, die `settings.telegram_chat_id`
in `__init__` mitschneidet. `Mock()`-frei.

**Falle, die ein Test vermeiden MUSS:** Ein Aufzeichner, der am Notifier nur das
**`chat_id`-Argument** abgreift (Muster `_MitschnittNotifier`,
`tests/tdd/test_kommandoliste_einzelquelle.py:234-247`), ist **heute schon grün** — dieses
Argument wird bereits korrekt übergeben, es wird nur nicht benutzt. Gemessen werden muss die
**verwendete Adresse**, nicht das ignorierte Argument. Der Notifier-Aufzeichner darf nur als
Einstiegs-Blaupause dienen (`:250-272` zeigt den Aufruf über
`reader._process_update(update, settings)` mit gesetztem `reader._notification_service`).

**Einstieg für alle Telegram-Kriterien:** `InboundTelegramReader._process_update(update,
settings)` mit einer **nicht** registrierten `chat_id`. Der Einstieg über
`TripCommandProcessor().process(...)` (wie `test_kanaltreue_adhoc_antwort.py:255-261`) erreicht
den `default`-Zweig **nicht** — er überspringt den Reader.

## Expected Behavior

- **Input:** Ein Telegram-Update mit `message.chat.id`, zu dem kein `data/users/<id>/user.json`
  einen Treffer auf `telegram_chat_id` liefert.
- **Output:** Der Registrierungshinweis („Dieser Chat ist noch nicht mit einem
  Gregor-Zwanzig-Konto verknuepft. Sende /start …") geht an **diese** Chat-ID.
- **Side effects:** Keine Persistenz, keine Trip-/Wetterdaten (unverändert). Die Chat-ID des
  Basis-/Betreiberprofils erhält nichts mehr.

## Acceptance Criteria

- **AC-1:** Given eine Telegram-Nachricht von einer Chat-ID, zu der kein Nutzerprofil existiert
  / When das System mit dem Registrierungshinweis antwortet / Then ist die zum Versand
  verwendete Adresse genau diese Chat-ID und nicht die des Basis-/Betreiberprofils.
  - Test: `_process_update` mit einer nicht registrierten Chat-ID aufrufen, bei der die
    Basis-Einstellungen eine **abweichende** Chat-ID tragen; der Aufzeichner an der
    `TelegramOutput`-Konstruktor-Naht muss die Absender-Chat-ID sehen und die Basis-Chat-ID
    darf in keiner Aufzeichnung vorkommen.

- **AC-2:** Given eine E-Mail von einem Absender, zu dem kein Nutzerprofil existiert / When der
  Reader diese Nachricht verarbeitet / Then wird überhaupt keine Antwort versendet — weder an
  den Absender noch an das Basis-/Betreiberprofil.
  - Test: `_process_single` vollständig durchlaufen lassen (Fake-IMAP, das nur `fetch` und
    `store` bereitstellt) mit einem fremden `From:`; der Versand-Aufzeichner darf **keinen**
    Aufruf sehen. Das isolierte `_authorize(...) is False` genügt NICHT — es gibt es bereits
    (`tests/tdd/test_bug_inbound_email_loop.py:71-77`) und es misst nicht das Ausbleiben des
    Versands.

- **AC-3:** Given dieselbe Testanordnung wie in AC-2, aber mit einem bekannten Absender und
  einem existierenden Trip im Betreff / When der Reader diese Nachricht verarbeitet / Then wird
  sehr wohl eine Antwort versendet.
  - Test: Positivkontrolle zu AC-2 — ohne sie ist ein leeres Ergebnis in AC-2 genauso gut
    durch einen kaputten Testaufbau erklärbar wie durch korrektes Blocken.

- **AC-4:** Given ein Telegram-Absender, dessen Chat-ID einem Nutzerprofil zugeordnet ist /
  When er einen Befehl schickt / Then bleibt das Verhalten unverändert und die zum Versand
  verwendete Adresse ist die Chat-ID aus seinem Profil.
  - Test: registrierte Chat-ID über `_process_update` schicken; der Aufzeichner sieht die
    Profil-Chat-ID. Sichert, dass der Fix die sechs bereits korrekten Aufrufer nicht verschiebt.

- **AC-5:** Given die Zusicherung aus AC-1 / When die Adress-Auflösung im Produktivcode wieder
  auf die Basis-Adresse zurückfällt (Mutation: das `model_copy` durch die unveränderten
  Basis-Einstellungen ersetzen) / Then wird mindestens einer der Tests aus AC-1 rot.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie, Protokoll im
    Adversary-Dialog. Zusätzlich die Umkehrprobe zu AC-2: wird im E-Mail-Reader die
    Autorisierungsprüfung (`inbound_email_reader.py:107-109`) entfernt, muss der AC-2-Test rot
    werden — sonst bewacht er das Schweigen nicht.

## Known Limitations

- **Fail-Closed auf Staging (bewusst so entschieden):** Trägt die an `_process_update`
  übergebene Basis-`settings` bereits `is_test_mode=True`, prüft `_guard_test_mode_chat_id`
  (`telegram.py:206-216`) die neu gesetzte echte Absender-Chat-ID gegen `telegram_test_chat_id`
  und wirft `OutputConfigError`. Das `try/except` in `send_telegram_message`
  (`notification_service.py:1838-1845`) fängt sie ab — der Hinweis geht dann an **niemanden**
  statt (fehlerhaft) an den Betreiber. Das ist gewollt: Staging darf keine echten fremden
  Chats anschreiben. In Produktion ist `is_test_mode` nicht gesetzt, dort greift der Fix normal.
- **Nur Telegram.** E-Mail und SMS/Premium-SMS haben keinen wirksamen Defekt: der E-Mail-Pfad
  verwirft unbekannte Absender vor der Antwortstelle, der SMS-Eingangsweg antwortet überhaupt
  nicht (`src/services/inbound_sms_reader.py` lernt nur die Rückantwort-Adresse; bei
  uneindeutiger Zuordnung lehnt `internal/handler/premium_sms_connect.go:98-104` mit HTTP 409
  ab, ohne Fallback auf `default`).
- **Sentinel-Kollision bleibt offen (Nebenbefund, nicht Teil dieses Zuschnitts):**
  `user_id == "default"` dient als reiner String-Sentinel für „kein Profil-Treffer"
  (`inbound_telegram_reader.py:181`, `:305`, `:422`). Ein *echter* Nutzer mit
  `user_id == "default"` würde fälschlich in diesen Zweig fallen; kein Code-Invariant verbietet
  das. → Sammelstelle #1199.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche berührt. Kanäle, Datenmodell, Auth und
  Test-/Deploy-Strategie bleiben unverändert; der Fix wendet ein im selben Modul bereits
  etabliertes Muster (`inbound_telegram_reader.py:436`) an der ausgelassenen Stelle an. Die
  Produktvorgabe „jeder Kanal muss jede Frage beantworten können" wird nicht angetastet — im
  Gegenteil, die Adressierung wird für den Eingangskanal erst hergestellt.

## Changelog

- 2026-09-07: Initial spec created (Issue #2168, herausgelöst aus #2126 / Epic #2133)
