# Context: fix-2141-telegram-chat-id-hijacking

Issue: [#2141](https://github.com/henemm/gregor_zwanzig/issues/2141) — `priority:critical`, `bug`, Teil von Epic #2138 (Multi-User-Readiness).

## Request Summary

`PUT /api/auth/profile` nimmt `telegram_chat_id` ungeprüft entgegen. Damit kann Nutzer B die
Chat-ID von Nutzer A eintragen und den localhost-gesperrten Einmal-Token-Flow vollständig
umgehen — Briefings/Alarme von B landen im Chat von A, und eingehende Kommandos von A werden
je nach Sortierreihenfolge dem Konto B zugeordnet.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/handler/auth.go:659–735` | `UpdateProfileHandler`. Read-Modify-Write über `LoadUser` (662) → Feld-Updates (684–719) → `SaveUser` (721). **Zeile 675** deklariert `TelegramChatID *string`, **717–719** schreibt ihn ohne jede Prüfung. |
| `internal/handler/telegram_connect.go:171–205` | `PostTelegramConnectHandler` — der saubere Weg. `requireLocalOnly` (173), `ResolveAndDelete` (186), **Zeile 197 setzt `user.TelegramChatID`**, `SaveUser` (198). **Keine Kollisionsprüfung.** |
| `internal/handler/telegram_connect.go:72–102` | `TelegramTokenStore`: Token = 16 Byte hex, TTL 24 h, Einmal-Verbrauch über `ResolveAndDelete`. |
| `internal/store/user.go:16–40, 48–85, 219–256` | `ListUserIDs`, `LoadUser`, `SaveUser`, `FindUserByOAuthSub`, `FindUserByEmail`. Letztere beide sind das vorhandene Muster „über alle Nutzer suchen". |
| `src/app/loader.py:1256–1277` | `lookup_user_by_telegram_chat_id` — String-toleranter Vergleich, **`return uid` beim ersten Treffer**, keine Mehrdeutigkeitsprüfung. |
| `src/app/loader.py:1202–1229` | `list_all_user_ids` — `sorted()`, echte Nutzer vor Test-Nutzern. Reihenfolge ist deterministisch alphabetisch, nicht zufällig. |
| `src/services/inbound_telegram_reader.py:406–423` | `_resolve_user_for_chat` — **Zeile 422: `… or "default"`**. Rückfall auf `"default"` im authentifizierten Pfad. |
| `src/services/inbound_telegram_reader.py:151–223` | Eingangskette: `chat_id` aus dem Update (165) → `_resolve_user_for_chat` (176) → bei `"default"` Registrierungs-Hinweis an die **ursprüngliche** `chat_id` (181–194) → sonst Kommando mit `user_settings` (202–223). |
| `src/services/inbound_telegram_reader.py:425–449` | `_process_start_command` — ruft `POST http://localhost:8090/api/internal/telegram-connect`. Bei Status ≠ 200 **nur ein Log-Warning**, der Nutzer erfährt nichts. `model_copy` in 436 ist reine In-Memory-Kopie für die Bestätigungsnachricht, **kein** Persistenzpfad. |
| `frontend/src/routes/account/+page.svelte:250–254` | `disconnectTelegram()` sendet `PUT /api/auth/profile { telegram_chat_id: '' }` — der **einzige** Schreibzugriff des Frontends auf das Feld. |
| `frontend/src/routes/account/+page.svelte:202–217` | `save()` sendet nur `display_name`, `mail_to`, `sms_to` — schreibt die Chat-ID nicht. |
| `docs/reference/api_contract.md:2963–2998` | Kontrakt für `PUT /api/auth/profile`. `telegram_chat_id` ist dort **gar nicht dokumentiert**, wird aber akzeptiert. |
| `internal/handler/profile_test.go` | Bestehende Handler-Tests, u. a. `TestUpdateProfileHandlerIgnoresPremiumSmsReplyFields` (Präzedenzfall) und `TestGetProfileTierTwoUsersNoCrossLeak:305–341` (Zwei-Nutzer-Muster). |

## Existing Patterns

**1. Der Präzedenzfall steht schon im Kontrakt** (`api_contract.md:2984–2990`, Issue #1717 S3, AC-7):
`premium_sms_reply_to` & Co. sind aus dem Decode-Struct **entfernt**, damit ein Nutzer keine fremde
Nummer eintragen und bezahlte Premium-SMS dorthin umleiten kann. Bewacht von
`TestUpdateProfileHandlerIgnoresPremiumSmsReplyFields`. Die Begründung dort ist wortgleich auf
`telegram_chat_id` übertragbar — die Regel existiert, sie wurde für Telegram nur nie gezogen.

**2. Eindeutigkeit über alle Nutzer** gibt es als Store-Muster: `FindUserByEmail`
(`internal/store/user.go:238–256`) iteriert `ListUserIDs` und vergleicht. Ein Pendant
`FindUserByTelegramChatID` fehlt.

**3. Konflikt-Statuscode:** 409 ist im Haus etabliert — Registrierung
(`internal/handler/auth.go:62–64`, `{"error":"user already exists"}`) und Metrik-Presets
(`api_contract.md:1895, 1947`, `{"error":"name_exists"}`).

**4. Zwei-Nutzer-Test:** `middleware.ContextWithUserID(req.Context(), userID)` + `req.WithContext(ctx)`
(`profile_test.go:35`, `display_name_642_test.go:46`). Helfer: `newTestStore`
(`trip_write_test.go:15`), `mustSaveUser` / `mustLoadUser` (`premium_sms_connect_test.go:49, 56`).

## Dependencies

- **Upstream:** `internal/store.Store` (Laden/Speichern, Iteration über alle Nutzer);
  `middleware.UserIDFromContext` als Identitätsquelle; `TelegramTokenStore` für den Einmal-Token.
- **Downstream:** Frontend `account/+page.svelte` (Verbinden/Trennen), Go-Endpunkte
  `/api/auth/telegram-link` und `/api/auth/telegram-status` (`internal/router/router.go:74–76`),
  Python-Inbound (`inbound_telegram_reader.py`), alle Telegram-Versandpfade, die
  `profile.telegram_chat_id` lesen.

## Existing Specs

- `docs/specs/modules/user_profile_channels.md:25–44` — Profil-Endpunkte und Kanal-Felder.
- `docs/specs/modules/telegram_webhook_inbound.md` — Inbound-Handler, Token-Setup.
- `docs/specs/modules/telegram_output.md`, `telegram_send_pacing.md` — Versandseite.
- **Nicht vorhanden:** eine Spec zum Connect-Token-Flow (`/api/internal/telegram-connect`) selbst.

## ADRs

| ADR | Aussage | Bezug |
|---|---|---|
| **ADR-0003** | Konsequente Mandantentrennung, **kein `"default"`-Fallback** im authentifizierten Pfad; Tests mit zwei Nutzern sind Pflicht. | Direkt verletzt durch `inbound_telegram_reader.py:422` |
| ADR-0060 | Dauerhafte Anmeldung mit dateibasierter Sperrliste; Session-Daten bewusst **getrennt** vom User-Datensatz, um RMW-Überschreiber zu vermeiden. | Erinnert daran, dass Schreibpfade auf `user.json` sparsam bleiben sollen |

## Risks & Considerations

1. **Löschen muss möglich bleiben.** Das Frontend trennt Telegram ausschließlich über
   `PUT /api/auth/profile { telegram_chat_id: '' }`. Ein ersatzloses Entfernen des Feldes aus dem
   Decode-Struct (wie bei `premium_sms_reply_to`) würde die Trennen-Funktion **still** kaputt
   machen — die Oberfläche meldete Erfolg, die Verknüpfung bliebe bestehen. Erlaubt sein darf
   also genau der Leerstring; jeder nicht-leere Wert muss abgewiesen werden.
2. **Bestandsdaten könnten bereits doppelt belegt sein.** Wenn der Python-Lookup künftig bei
   Mehrfachtreffern fehlschlägt, verlieren betroffene Nutzer den Inbound-Kanal. Verhalten dafür
   muss die Spec festlegen (Fehlschlag + Log ist die sichere Variante; „erster gewinnt" ist der
   Bug).
3. **Der `"default"`-Rückfall in Zeile 422 ist ein eigener ADR-0003-Verstoß.** Er ist nicht
   Wortlaut des Issues, hängt aber unmittelbar am selben Lookup. Entscheidung in der Analyse:
   mitfixen oder als eigenes Ticket abtrennen.
4. **Stiller 409 im `/start`-Pfad.** `_process_start_command` protokolliert einen
   Nicht-200-Status nur. Führt der Connect künftig 409 zurück, erfährt der Nutzer im Chat nichts —
   die Rückmeldung muss mitgedacht werden, sonst ist der Fix aus Nutzersicht ein Stillstand.
5. **Reihenfolge ist deterministisch, nicht zufällig.** `list_all_user_ids` sortiert alphabetisch.
   Ein Angreifer mit passender `user_id` gewinnt also verlässlich — der Angriff ist nicht auf
   Verzeichnisglück angewiesen. Der Issue-Text („je nach Verzeichnisreihenfolge") untertreibt.
6. **Nachweisform:** Ein Test, der nur den Handler mit einem Nutzer aufruft, beweist nichts. Der
   Nachweis muss zwei Nutzer anlegen und prüfen, dass B die Chat-ID von A weder über das Profil
   noch über den Connect-Endpunkt übernehmen kann, **und** dass A's `user.json` danach unverändert ist.

---

## Analysis

### Type

**Bug** — Sicherheitslücke, `priority:critical`, Blocker aus Epic #2138.

### Root Cause

`ddc41ea8` (F13 Phase 4a, #12) führte `telegram_chat_id` als frei beschreibbares Profil-Feld im
generischen Decoder ein. `c816d1c8` (#590) baute später den Einmal-Token-Flow **daneben**, ohne den
alten Schreibweg zu schließen. Es gab nie einen Fix an dieser Stelle (`git log -S"TelegramChatID"`).
Der Token-Flow ist damit keine Schranke, sondern nur eine bequemere Alternative zum offenen Feld.

### Geprüft und verworfen

| Vermutung | Befund |
|---|---|
| Weitere Go-Schreibwege | Keine. `TelegramChatID =` nur in `auth.go:718` und `telegram_connect.go:197`; alle 13 Body-Decoder in `internal/handler/` durchsucht, nur `auth.go` deklariert das JSON-Tag; kein `SaveUser`-Aufrufer setzt es nebenbei. |
| Python schreibt persistent | Nein. `inbound_telegram_reader.py:436` ist eine In-Memory-`model_copy` allein für die Bestätigungsnachricht; kein Python-Modul schreibt `user.json`. |
| `requireLocalOnly` umgehbar | Nein — `internal/handler/localhost_guard.go` prüft seit dem Team-Lead-Befund vom 2026-08-10 zusätzlich auf Abwesenheit von `X-Forwarded-For`/`X-Real-IP`/`X-Forwarded-Proto`. |
| Fremde Chat-ID auslesbar | Nein. `chat_id_suffix` (`telegram_connect.go:108, 145`) wird nur für die eigene `userID` aus dem Auth-Kontext gebildet. |
| Mehrere Chat-IDs je Nutzer | Nicht möglich — `model.User.TelegramChatID` ist ein einzelnes String-Feld (`internal/model/user.go:18`). |

### Der Konflikt mit Issue #1013 (entscheidend für die ACs)

Die Issue-Erwartung „Lookup schlägt bei Mehrfachtreffer fehl" kollidiert mit einer bestehenden,
getesteten Zusicherung: `tests/tdd/test_issue_1013_telegram_test_isolation.py:87–101` verlangt, dass
bei **identischer Chat-ID von echtem Nutzer und Test-Nutzern** deterministisch der echte Nutzer
gewinnt — genau dafür wurde die Vorrang-Sortierung in `list_all_user_ids` gebaut (sonst erhielt der
PO Test-Briefings über den Prod-Bot).

**Folge für die Regel:** Der Fehlerfall ist Mehrdeutigkeit **unter echten Nutzern**. Test-Nutzer
bleiben ausgenommen und verlieren gegen den echten Nutzer wie bisher. Dasselbe gilt für die
409-Prüfung beim Connect — sonst könnte der PO sich auf Staging nicht mehr verbinden, sobald die
Fixture `tg-live-e2e` seine Chat-ID trägt. Das Prädikat existiert auf beiden Seiten:
`app.config.is_test_user_id` (`src/app/config.py:56`) und `model.IsTestUserID`
(`internal/model/test_user.go:20`).

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `internal/handler/auth.go` | MODIFY | `UpdateProfileHandler`: nur noch der Leerstring wird übernommen, jeder nicht-leere Wert fließt nirgends ein. |
| `internal/store/user.go` | MODIFY | Neu `FindUserByTelegramChatID` nach Vorbild `FindUserByEmail:238–256`, Test-Nutzer übersprungen. |
| `internal/handler/telegram_connect.go` | MODIFY | Kollisionsprüfung vor `SaveUser` → 409 `chat_id_already_linked`; Re-Connect desselben Nutzers ist kein Konflikt; Prüfen-und-Schreiben unter einem paketweiten Mutex. |
| `src/app/loader.py` | MODIFY | `lookup_user_by_telegram_chat_id`: mehrere **echte** Treffer → `None` + `logger.error` statt erster Treffer. |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_process_start_command`: bei 409 eine verständliche Antwort in den Chat statt nur Log. |
| `internal/handler/profile_test.go` | MODIFY | `TestUpdateProfileHandler:105–107` fordert heute das verwundbare Verhalten ein — wird ersetzt, nicht gelöscht. |
| `internal/handler/telegram_connect_uniqueness_test.go` | CREATE | Zwei-Nutzer-Tests für 409, Re-Connect, Test-Nutzer-Ausnahme. |
| `tests/tdd/test_telegram_chat_id_ownership.py` | CREATE | Mehrfachtreffer-Verhalten inkl. Alt-Duplikaten und #1013-Regress. |
| `docs/reference/api_contract.md` | MODIFY | `PUT /api/auth/profile` + Connect-Konflikt dokumentieren (zählt nicht gegen das LoC-Limit). |

### Scope Assessment

- Dateien: 9 (2 neu)
- Geschätzte LoC: ~+280 — **über dem 250er-Limit**, `loc_limit_override 500` vor der Implementierung setzen.
- Risiko: **MEDIUM** — Angriffsfläche wird kleiner, aber Bestandsdaten mit Doppelbelegung ändern ihr Verhalten.

### Technical Approach

1. **Profil-Endpunkt:** Feld bleibt im Decode-Struct, aber nur `""` wird übernommen. Kein 400 — die
   Antwort liefert ohnehin den unveränderten Wert zurück, und kein legitimer Aufrufer sendet je einen
   nicht-leeren Wert. Konsistent mit dem `premium_sms_reply_to`-Präzedenzfall.
   *Verworfen:* eigener `DELETE /api/auth/telegram-link`-Endpunkt. Architektonisch sauberer (der
   generische Decoder bliebe frei von Sonderfällen), kostet aber einen neuen Endpunkt plus
   Frontend-Änderung auf einem kritischen Sicherheits-Hotfix. Die Sicherheitszusicherung ist in
   beiden Varianten identisch. → Nachfolge-Eintrag in #1199.
2. **Connect-Endpunkt:** `FindUserByTelegramChatID` (Test-Nutzer übersprungen) → gehört die ID einem
   **anderen echten** Nutzer, 409 und die bestehende Verknüpfung bleibt unangetastet. Prüfen und
   Speichern unter einem paketweiten `sync.Mutex` gegen die TOCTOU-Lücke bei gleichzeitigen Connects.
3. **Python-Lookup:** mehrere echte Treffer → `None` + `logger.error` mit den kollidierenden IDs.
   Kein Wurf: eine Exception würde in `poll_and_process:122–125` nur geloggt, der Mensch im Chat
   bliebe komplett stumm. `None` nutzt den vorhandenen „kein Treffer"-Pfad und liefert wenigstens den
   Registrierungs-Hinweis.
4. **409 im Chat beantworten:** `_process_start_command` bekommt für 409 eine eigene Antwort.

### Abgetrennt (eigenes Ticket)

Der `or "default"`-Rückfall (`inbound_telegram_reader.py:422`) bleibt. Die ursprüngliche Einschätzung
als ADR-0003-Verstoß war zu scharf: ADR-0003 verbietet den Rückfall im **authentifizierten** Pfad —
der Telegram-Inbound hat vor der Auflösung überhaupt keine Identität, und `_process_update:181` fängt
`"default"` sofort als Sentinel ab, ohne Daten eines etwaigen Nutzers `default` zu laden. Es bleibt ein
Namenskollisions-Randfall (ein echter Nutzer namens `default` bekäme fälschlich den
Registrierungs-Hinweis) — ein False Negative, kein Leck. Eigenes Issue, niedrigere Priorität.

### Nachweisformen, die trügen würden

- Ablehnungs-Test mit **einem** Nutzer — beweist nicht, dass A's `user.json` unangetastet bleibt.
- Kollisionsprüfung gegen einen gestubbten Store — eine fehlende Iteration über alle Nutzer bliebe unbemerkt.
- Nur der Go-Schreibweg getestet — **Alt-Duplikate** aus der Zeit vor dem Fix blieben wirkungslos abgedeckt.
- Kein No-Op-Fall geprüft — sendet ein Nutzer seine **eigene** aktuelle Chat-ID mit, darf das kein Fehler sein.

### Open Questions

Keine offenen Fragen an den PO. Alle Design-Abwägungen sind oben entschieden und begründet.
