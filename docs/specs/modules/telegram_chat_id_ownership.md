---
entity_id: telegram_chat_id_ownership
type: module
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [security, multi-user, telegram, issue-2141, epic-2138]
---

# Telegram-Chat-ID: Besitz und Eindeutigkeit

## Approval

- [ ] Approved

## Purpose

Die Telegram-Chat-ID eines Nutzers ist eine Identitätszuordnung, keine Einstellung. Dieses Modul
legt fest, dass sie ausschließlich über den Einmal-Token-Flow gesetzt werden kann, nur einem echten
Konto gehören darf und bei Mehrdeutigkeit keine Zuordnung stattfindet. Es schließt Issue #2141
(Nachrichten- und Identitäts-Hijacking, `priority:critical`, Blocker aus Epic #2138).

## Source

- **File:** `internal/handler/auth.go` — **Identifier:** `UpdateProfileHandler`
- **File:** `internal/handler/telegram_connect.go` — **Identifier:** `PostTelegramConnectHandler`
- **File:** `internal/store/user.go` — **Identifier:** `FindUserByTelegramChatID` (neu)
- **File:** `src/app/loader.py` — **Identifier:** `lookup_user_by_telegram_chat_id`
- **File:** `src/services/inbound_telegram_reader.py` — **Identifier:** `_process_start_command`

## Estimated Scope

- **LoC:** ~280 (über dem 250er-Limit — `loc_limit_override 500` vor der Implementierung setzen)
- **Files:** 9 (davon 2 neue Testdateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/test_user.go` → `IsTestUserID` | Go-Prädikat | Test-Nutzer von Eindeutigkeit und Mehrdeutigkeit ausnehmen |
| `src/app/config.py` → `is_test_user_id` | Python-Prädikat | Dasselbe auf der Python-Seite |
| `internal/store/user.go` → `ListUserIDs`, `LoadUser` | Store | Iteration über alle Nutzer (Vorbild `FindUserByEmail`) |
| `docs/specs/modules/issue_1013_telegram_test_isolation.md` | Spec | Vorrang echter Nutzer vor Test-Nutzern darf nicht brechen |
| `internal/handler/localhost_guard.go` → `requireLocalOnly` | Guard | Schützt den Connect-Endpunkt bereits gegen externen Zugriff |

## Implementation Details

```
1) internal/handler/auth.go — UpdateProfileHandler (heute Zeile 717-719)
   Das Feld bleibt im Decode-Struct, damit "Telegram trennen" weiter funktioniert.
   Übernommen wird ausschließlich der Leerstring:

       if update.TelegramChatID != nil && *update.TelegramChatID == "" {
           user.TelegramChatID = ""
       }

   Kein else-Zweig, kein 400: ein nicht-leerer Wert fliesst nirgends ein. Die Antwort
   (toProfileResponse) liefert den unveraenderten gespeicherten Wert zurueck, der Aufrufer
   sieht die Nicht-Uebernahme also unmittelbar. Muster wie premium_sms_reply_to
   (api_contract.md:2984-2990).

2) internal/store/user.go — neu FindUserByTelegramChatID(chatID string) (*model.User, error)
   Vorbild FindUserByEmail (user.go:238-256): ListUserIDs -> LoadUser -> Vergleich.
   Exakter String-Vergleich (Chat-IDs sind numerisch, kein EqualFold).
   Nutzer mit model.IsTestUserID(uid) == true werden UEBERSPRUNGEN.
   Leerer chatID -> nil, nil (ein leeres Feld ist keine Verknuepfung).

3) internal/handler/telegram_connect.go — PostTelegramConnectHandler
   Zwischen LoadUser (192) und SaveUser (198), unter einem paketweiten sync.Mutex,
   der Pruefung UND Speichern umschliesst (TOCTOU bei gleichzeitigen Connects):

       existing, err := s.FindUserByTelegramChatID(body.ChatID)
       err != nil                              -> 500
       existing != nil && existing.ID != pt.UserID
           -> 409 {"error":"chat_id_already_linked"}, KEIN SaveUser
       sonst -> wie bisher

   Re-Connect desselben Nutzers ist bewusst kein Konflikt.

4) src/app/loader.py — lookup_user_by_telegram_chat_id
   Nicht mehr beim ersten Treffer abbrechen, sondern alle Treffer sammeln und in
   echte Nutzer / Test-Nutzer trennen (is_test_user_id):
     - genau ein echter Treffer          -> dessen user_id
     - kein echter, aber Test-Treffer    -> erster Test-Treffer (Verhalten wie bisher)
     - mehr als ein echter Treffer       -> None + logger.error mit allen kollidierenden IDs
     - gar kein Treffer                  -> None
   KEINE Exception: sie wuerde in poll_and_process (122-125) nur geloggt, der Mensch
   im Chat bliebe stumm. None laeuft in den bestehenden "kein Treffer"-Pfad, der den
   Registrierungs-Hinweis verschickt.

5) src/services/inbound_telegram_reader.py — _process_start_command (425-449)
   Der else-Zweig (445-446) unterscheidet 409 von anderen Fehlern und schickt bei 409
   eine verstaendliche Nachricht an die eingehende chat_id, analog zum
   Bestaetigungs-Muster in 437-442. Andere Statuscodes bleiben still geloggt.
```

## Expected Behavior

- **Input:** (a) `PUT /api/auth/profile` mit `telegram_chat_id`; (b) `POST /api/internal/telegram-connect` mit Token und Chat-ID; (c) eingehende Telegram-Nachricht mit einer Chat-ID.
- **Output:** (a) Profil ohne übernommene Chat-ID, außer beim Leerstring; (b) 200 bei freier oder eigener Chat-ID, 409 `chat_id_already_linked` bei fremder; (c) genau ein zuständiges Konto oder gar keins.
- **Side effects:** `data/users/<user_id>/user.json` wird nur noch über den Token-Flow oder das Löschen verändert. Bei 409 bleibt die bestehende Verknüpfung des anderen Kontos unangetastet. Mehrdeutige Bestandsdaten erzeugen einen `logger.error`-Eintrag mit den kollidierenden Nutzer-IDs.

## Acceptance Criteria

- **AC-1:** Given Nutzer A hat die Telegram-Chat-ID `55501` und Nutzer B ist angemeldet / When B `PUT /api/auth/profile` mit `{"telegram_chat_id":"55501"}` sendet / Then bleibt B's gespeicherte Chat-ID leer, A's `user.json` trägt unverändert `55501`, und die Antwort an B zeigt nicht `55501`.
  - Test: Go-Handler-Test mit zwei über `SaveUser` persistierten Nutzern; nach dem Request werden **beide** Profile über `LoadUser` neu gelesen und geprüft.

- **AC-2:** Given Nutzer B hat bereits die Chat-ID `77702` verknüpft / When B `PUT /api/auth/profile` mit `{"telegram_chat_id":""}` sendet / Then ist B's Chat-ID danach leer und die Antwort zeigt sie als leer — das Trennen im Konto-Bereich funktioniert weiter.
  - Test: Go-Handler-Test, der nach dem Request `LoadUser` liest; deckt den Aufruf ab, den `account/+page.svelte:251` tatsächlich absetzt.

- **AC-3:** Given Nutzer B hat bereits die Chat-ID `77702` verknüpft / When B `PUT /api/auth/profile` mit genau seiner eigenen `{"telegram_chat_id":"77702"}` sendet / Then antwortet der Endpunkt mit 200, B's Chat-ID bleibt `77702` und die übrigen gesendeten Felder werden normal übernommen.
  - Test: Go-Handler-Test, der zusätzlich ein zweites Feld (`mail_to`) mitsendet und dessen Übernahme prüft — ein wiederholtes Speichern des unveränderten Profils darf nichts kaputtmachen.

- **AC-4:** Given Nutzer A hat die Chat-ID `55501` und Nutzer B besitzt einen gültigen Einmal-Token / When `POST /api/internal/telegram-connect` mit B's Token und Chat-ID `55501` aufgerufen wird / Then antwortet der Endpunkt mit 409 und `{"error":"chat_id_already_linked"}`, B's Chat-ID bleibt leer und A's Verknüpfung bleibt `55501`.
  - Test: Go-Handler-Test mit zwei persistierten Nutzern über den echten `store.Store`; beide Profile werden nach dem Request von der Platte gelesen.

- **AC-5:** Given Nutzer B hat die Chat-ID `77702` bereits verknüpft und löst einen neuen Einmal-Token aus / When `POST /api/internal/telegram-connect` mit diesem Token und derselben Chat-ID `77702` aufgerufen wird / Then antwortet der Endpunkt mit 200 und B's Chat-ID bleibt `77702` — ein erneutes Verbinden desselben Kontos ist kein Konflikt.
  - Test: Go-Handler-Test; verhindert, dass die Eindeutigkeitsprüfung den legitimen Re-Connect blockiert.

- **AC-6:** Given der Test-Nutzer `tg-live-e2e` trägt die Chat-ID `55501` und der echte Nutzer A besitzt einen gültigen Einmal-Token / When `POST /api/internal/telegram-connect` mit A's Token und `55501` aufgerufen wird / Then antwortet der Endpunkt mit 200 und A's Chat-ID ist `55501` — Test-Nutzer blockieren echte Nutzer nicht.
  - Test: Go-Handler-Test mit einem Test-Nutzer und einem echten Nutzer; hält die Zusicherung aus Issue #1013 auf der Go-Seite offen.

- **AC-7:** Given zwei echte Nutzer `anna` und `bertram` tragen beide die Chat-ID `55501` in ihrer `user.json` (Bestandsdaten aus der Zeit vor dem Fix) / When `lookup_user_by_telegram_chat_id("55501")` aufgerufen wird / Then liefert die Funktion `None` statt einer der beiden IDs.
  - Test: Python-Test auf echtem Dateisystem (`tmp_path`), zwei echte Nutzerprofile geschrieben; prüft den Rückgabewert, nicht den Quelltext.

- **AC-8:** Given der echte Nutzer `henning` und die Test-Nutzer `tg-live-e2e`, `test_aaa`, `tdd-zzz` tragen alle die Chat-ID `999888` / When `lookup_user_by_telegram_chat_id("999888")` aufgerufen wird / Then liefert die Funktion `henning` — der Vorrang des echten Nutzers vor Test-Nutzern aus Issue #1013 bleibt erhalten.
  - Test: Python-Test auf echtem Dateisystem; entspricht dem Aufbau von `test_issue_1013_telegram_test_isolation.py:87-101` und ist der Regressionsschutz für diese Zusicherung.

- **AC-9:** Given zwei echte Nutzer teilen sich die Chat-ID `55501` / When von dieser Chat-ID eine Telegram-Nachricht eingeht / Then wird kein Trip und keine Einstellung eines der beiden Konten geladen, der Absender erhält stattdessen den bestehenden Registrierungs-Hinweis, und im Log steht ein `error`-Eintrag, der beide kollidierenden Nutzer-IDs nennt.
  - Test: Python-Test, der eine eingehende Nachricht durch `_process_update` schickt und die tatsächlich versendete Antwort sowie den Log-Eintrag prüft.

- **AC-10:** Given die Chat-ID `55501` gehört bereits einem anderen echten Konto / When ein Nutzer im Telegram-Chat `/start <token>` sendet und die Go-API mit 409 antwortet / Then erhält er in seinem Chat eine verständliche Nachricht, dass diese Chat-Verbindung bereits mit einem anderen Konto verknüpft ist — statt wie bisher gar keiner Rückmeldung.
  - Test: Python-Test, der `_process_start_command` gegen eine 409-Antwort laufen lässt und prüft, dass eine Nachricht an die eingehende Chat-ID hinausgeht.

## Known Limitations

- **Bestandsdaten mit Doppelbelegung** werden nicht automatisch bereinigt. Betroffene Nutzer verlieren
  den Inbound-Kanal (AC-9) statt fälschlich einem Konto zugeordnet zu werden. Das ist der gewollte
  sichere Zustand, aber ein Verhaltenssprung — nach dem Deploy einmal gegen den Prod-Bestand unter
  `/var/lib/gregor` prüfen, ob es solche Duplikate überhaupt gibt.
- **Der `or "default"`-Rückfall** in `inbound_telegram_reader.py:422` bleibt bestehen. Ein echter
  Nutzer mit der ID `default` bekäme fälschlich den Registrierungs-Hinweis. Kein Datenleck, sondern
  ein Namenskollisions-Randfall → eigenes Issue.
- **Kein dedizierter Trenn-Endpunkt.** Das Löschen bleibt ein Sonderfall im Profil-Decoder. Ein
  `DELETE /api/auth/telegram-link` wäre sauberer, kostet aber Endpunkt plus Frontend-Änderung auf
  einem kritischen Hotfix → Nachfolge-Eintrag in #1199.
- **Der Mutex wirkt prozessintern.** Bei mehreren `gregor-api`-Prozessen auf denselben Daten wäre die
  TOCTOU-Lücke wieder offen. Je Umgebung läuft genau ein Prozess, deshalb ausreichend.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (bestätigt ADR-0003)
- **Rationale:** Es wird keine neue Grundsatzentscheidung getroffen, sondern eine bestehende
  durchgesetzt: ADR-0003 verlangt konsequente Mandantentrennung. Die Regel „Identitätszuordnungen
  sind nicht über den generischen Profil-Decoder schreibbar" existiert bereits als Präzedenzfall für
  `premium_sms_reply_to` (#1717 S3, AC-7) und wird hier nur auf `telegram_chat_id` angewandt. Die
  Ausnahme für Test-Nutzer folgt der bestehenden Entscheidung aus Issue #1013.

## Changelog

- 2026-09-07: Initial spec created (Issue #2141)
