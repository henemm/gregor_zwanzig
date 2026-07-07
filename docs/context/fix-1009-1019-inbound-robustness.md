# Context: Inbound-Reader Robustheit (#1009, #1019)

## Request Summary

Zwei gebündelte Robustheits-/Sicherheitsbefunde im Inbound-Verarbeitungspfad:
(#1009) eine Exception während der Kommando-Verarbeitung lässt die E-Mail UNSEEN,
was bei anhaltendem SMTP-Ausfall zu einer Dauer-Reprocessing-Schleife führt;
(#1019) beide Inbound-Handler (E-Mail, Telegram) fallen bei unbekanntem Absender
auf `user_id = "default"` zurück — zu prüfen ist, ob das ein Datenleck an Unbekannte
darstellt.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/inbound_email_reader.py` | `_process_single` (Z.94-159): `processor.process()` (Z.149) hat kein eigenes try/except; `imap.store(...,"\\Seen")` (Z.158) danach wird bei Exception nie erreicht. `_authorize` (Z.185-199) ist der bestehende Autorisierungs-Gate für E-Mail. `_resolve_settings_for_sender` (Z.216-231) löst `user_id` via `lookup_user_by_email(...) or "default"` auf (Z.230). |
| `src/services/inbound_telegram_reader.py` | `_process_update` (Z.141-259) hat **keinen** zu `_authorize` analogen Gate — nach `_resolve_user_for_chat` (Z.341-356, Fallback `"default"` Z.355) wird direkt der aktive Trip geladen und Befehle verarbeitet, unabhängig davon ob der Chat bekannt ist. `poll_and_process` (Z.91-118) hat bereits try/except pro Update (Z.111-115) — Offset wird VOR dem try fortgeschrieben (Z.106-110), analog zum email-Pattern von #1009 aber hier bereits korrekt (kein Reprocessing-Risiko bei Telegram). |
| `src/app/loader.py` | `lookup_user_by_email` (Z.807), `lookup_user_by_telegram_chat_id` (Z.829) — iterieren `list_all_user_ids()`, matchen gegen `user.json`. `"default"` selbst hat i.d.R. **kein** `user.json` (bestätigt: `data/users/default/` enthält keine `user.json`), daher kann kein echter Absender via Lookup auf `"default"` matchen — der Fallback greift ausschließlich bei Nicht-Match. |
| `src/app/config.py` | `Settings.with_user_profile(user_id)` (Z.197-233): existiert kein `user.json` für `user_id`, wird `base` (die **globalen** Settings, real konfiguriertes `mail_to`/`telegram_chat_id` des Betreibers) unverändert zurückgegeben. D.h. `user_id="default"` ohne Profil-Datei liefert die **echten globalen Empfänger-Settings**, nicht neutrale Platzhalter. |
| `data/users/default/trips/gr221-mallorca.json` | Es existieren reale Trip-Daten unter `default` (Altbestand vor Multi-Tenancy) — kein leerer Dummy-Account. |
| `tests/tdd/test_bug_inbound_email_loop.py` | Bestehende Testsuite für `_authorize` (Bugfix Feedback-Loop, anderes Issue). Zeigt: E-Mail hat bereits einen granular getesteten Autorisierungs-Gate. |
| `tests/tdd/test_inbound_telegram_reader.py` | Keine Tests zu unbekannter/nicht-registrierter `chat_id` — Lücke bestätigt. |
| `docs/adr/0003-multi-tenant-isolation.md` | Verbietet `"default"`-Fallback explizit nur in **authentifizierten** Pfaden. Inbound-Reader sind formal nicht "authentifiziert" (kein Login), daher kein direkter ADR-Verstoß — aber die Grundmotivation (Cross-User-Datenleck) trifft strukturell zu, wenn Fremde echte Betreiber-Daten erhalten. |
| `docs/specs/modules/issue_572_multi_user_inbound_routing.md` | **Wichtig:** Der `"default"`-Fallback wurde 2026-06-03 (nach ADR-0003 vom 2026-04-12) bewusst spezifiziert und freigegeben (AC-3, AC-4: "unbekannter Absender → user_id='default', kein Fehler"). Kein Versehen, sondern eine damalige Design-Entscheidung — die jetzt (#1019) auf ihre Sicherheits-Konsequenz hin geprüft wird, weil sich seither reale Trip-Daten unter `default` angesammelt haben. |
| `src/services/trip_command_processor.py` | `process()` (Z.259ff) — die Methode, deren unbehandelte Exception #1009 auslöst. Kann bei Fehlern in Wetter-/Datenzugriff werfen. |

## Existing Patterns

- **E-Mail hat einen Autorisierungs-Gate, Telegram nicht:** `_authorize()` in `inbound_email_reader.py` prüft den Absender explizit gegen `settings.mail_to`/`inbound_address` der aufgelösten (ggf. globalen) Settings, BEVOR verarbeitet wird. Für Telegram existiert keine äquivalente Prüfung — jede eingehende `chat_id` wird verarbeitet, sobald `_resolve_user_for_chat` einen (ggf. Fallback-)User zurückgibt.
- **"Mark as seen" nach Verarbeitung, nicht davor:** E-Mail-Pfad markiert erst nach erfolgreicher (oder früh abgebrochener) Verarbeitung als gelesen — das ist der Webfehler-Pfad in #1009, weil zwischen `process()` und `imap.store()` keine Fehlerbehandlung liegt.
- **Telegram-Offset-Pattern ist bereits robust:** `poll_and_process()` schreibt `max_update_id`/`self._offset` VOR dem try/except pro Update fort (Z.106-110) — ein Fehler in einem Update blockiert nicht die nächste Poll-Runde. Das ist das Zielmuster, das #1009 für den IMAP-"Seen"-Flag nachbilden soll (funktional analog, nicht identisch: bei IMAP gibt es kein globales "Offset", sondern pro-UID-Flags).
- **`/start TOKEN`-Onboarding existiert bereits:** Telegram hat einen dedizierten Registrierungsweg (`_process_start_command`, Z.358-382), der `chat_id` über ein Token mit einem echten User verknüpft (via Go-Backend `/api/internal/telegram-connect`). Ein "unbekannter Absender bekommt neutrale Ablehnung"-Fix für #1019 könnte auf diesen Mechanismus verweisen (z.B. Hinweis "sende /start mit deinem Token").

## Dependencies

- **Upstream:** `TripCommandProcessor.process()`, `NotificationService` (SMTP/Telegram-Versand), `Settings.with_user_profile()`, `loader.lookup_user_by_email`/`lookup_user_by_telegram_chat_id`.
- **Downstream:** Scheduler-Cronjob ruft `poll_and_process()` beider Reader periodisch auf (5-Min-Takt lt. Issue #1009). Keine bekannten weiteren Konsumenten von `_process_single`/`_process_update`.

## Existing Specs

- `docs/specs/modules/inbound_command_channels.md` (E-Mail-Kanal, v1.1) — "Autorisierungsfehler (unbekannter Absender) bleiben stumm" ist bereits dokumentiertes Verhalten für E-Mail.
- `docs/specs/modules/inbound_telegram_reader.md` (v1.0) — keine Autorisierungs-Sektion.
- `docs/specs/modules/issue_572_multi_user_inbound_routing.md` — Ursprungs-Spec des `"default"`-Fallbacks (s.o.).
- `docs/specs/modules/bug_inbound_email_loop.md` — verwandter, aber unterschiedlicher Bug (Stalwart-Feedback-Loop via `mail_from`).
- `docs/adr/0003-multi-tenant-isolation.md` — Grundsatzentscheidung gegen `"default"`-Fallback in authentifizierten Pfaden.

## Risks & Considerations

- **#1019 ist der signifikantere Befund:** Code-Analyse zeigt bereits jetzt (ohne Staging-Reproduktion), dass ein unbekannter Telegram-Absender strukturell echte Betreiber-Trip-Daten (`data/users/default/trips/gr221-mallorca.json`) über Befehle wie `status`/`heute` erhalten könnte, weil (a) kein Autorisierungs-Gate existiert und (b) `with_user_profile("default")` mangels `user.json` die globalen (echten) Settings durchreicht. Staging-Reproduktion (AC aus #1019) sollte das dennoch verifizieren, bevor als Faktum behandelt.
- **E-Mail-Pfad ist wahrscheinlich bereits sicher**, weil `_authorize` einen unbekannten Absender vor Erreichen von `TripCommandProcessor` abfängt — muss in der Analyse-Phase bestätigt werden, nicht nur angenommen.
- **#1009-Fix-Scope:** Die Aufgabenbeschreibung nennt nur `processor.process()`; der nachfolgende `send_command_reply_email`-Call (Z.154-155) kann bei SMTP-Ausfall ebenso werfen und würde `imap.store` (Z.158) genauso verhindern. Die Analyse-Phase sollte klären, ob der try/except-Block beide Schritte (Verarbeitung + Antwortversand) umschließen soll, damit "Seen" in jedem Fall gesetzt wird.
- **Vorherige Design-Entscheidung nicht leichtfertig umwerfen:** #1019 verändert eine 2026-06-03 explizit freigegebene Spec (`issue_572...`) — Spec-Änderung und ggf. Anpassung der dortigen AC-3/AC-4 gehört zum Umfang, nicht nur Code-Fix.
- **Kein Konflikt mit ADR-0003 im engeren Sinne** (Inbound-Reader sind unauthentifiziert), aber die Schutzintention des ADR ist thematisch einschlägig — sollte in der Spec referenziert werden.

## Analysis

### Type

Bug (beide: #1009 Reprocessing-Loop, #1019 Datenleck via default-Fallback).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_email_reader.py` | MODIFY | `_process_single`: try/except/finally um Schritt 5 (`processor.process()`) + Schritt 6 (`send_command_reply_email`) zusammen; `imap.store(uid,"+FLAGS","\\Seen")` ins `finally` statt ans Blockende (#1009). |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_process_update`: Autorisierungs-Gate NACH `_resolve_user_for_chat`, VOR `_find_active_trip`/Kommando-Verarbeitung (#1019, siehe korrigierter Ansatz unten). |
| `tests/tdd/test_bug_inbound_email_loop.py` oder neue Datei | MODIFY/CREATE | Test: provozierte Exception in `process()`/Versand → Mail trotzdem `\Seen`, kein Endlos-Reprocessing (#1009). |
| `tests/tdd/test_inbound_telegram_reader.py` | MODIFY | Test: unbekannte chat_id → neutrale Antwort statt Trip-Daten; Betreiber-eigene chat_id (== globales `GZ_TELEGRAM_CHAT_ID`) → weiterhin normal verarbeitet, KEINE Regression (#1019). |
| `docs/specs/modules/issue_572_multi_user_inbound_routing.md` | MODIFY (Doku) | AC-3/AC-4 anpassen: `"default"`-Fallback bleibt für Trip-Lookup bestehen, aber Telegram-Verarbeitung erhält zusätzlichen Autorisierungs-Gate. |
| `docs/specs/modules/inbound_telegram_reader.md` | MODIFY (Doku) | Neue Autorisierungs-Sektion ergänzen, analog `inbound_command_channels.md`. |

### Scope Assessment

- Files: 2 Produktion + 2 Test + 2 Doku
- Estimated LoC: Produktion ~30-40 (deutlich unter 250-LoC-Limit), Tests ~60-100
- Risk Level: MEDIUM — #1009 niedrig, #1019 mittel (siehe Korrektur unten)

### Technical Approach

**Korrektur (2026-07-07):** Die erste Fassung dieser Sektion beruhte auf einer unvollständigen Datenbasis — dieser Worktree hat `data/users/henning/` (gitignored, s. `.gitignore` Z.52) nicht gespiegelt. Gegen das Hauptrepo (`/home/hem/gregor_zwanzig/data/users/henning/user.json`) verifiziert: Der Betreiber HAT ein reguläres, vollständiges Profil (`mail_to`, `telegram_chat_id`, `sms_to` alle gesetzt). `lookup_user_by_email("henning.emmrich@gmail.com")` und `lookup_user_by_telegram_chat_id(<seine chat_id>)` matchen beide korrekt auf `user_id="henning"` — er durchläuft für **beide** Kanäle den regulären Multi-Tenant-Pfad, **nicht** den `"default"`-Fallback. Die ursprüngliche Plan-Bewertung (`if user_id == "default": ablehnen`) war also von Anfang an korrekt; meine „Korrektur" in der Vorversion dieses Dokuments war falsch und ist hiermit zurückgezogen.

**#1009:** try/except/finally in `_process_single`, `\Seen`-Flag im `finally`-Zweig — analog zum bereits korrekten Offset-Pattern des Telegram-Readers (`poll_and_process`, Z.106-110). Scope-Korrektur nach PO-Rückfrage: `_send_trip_report_outcome` (trip_report_scheduler.py) fängt Wetterdienst-Ausfälle bereits fail-soft ab (Z.607-630: `_fetch_weather` liefert `has_error`-Platzhalter statt zu werfen, bei Totalausfall wird `send_no_data_hint` gesendet, kein Raise) — ebenso Wind-Exposition (Z.595-604), Weather-Pattern (Z.640-646), Daylight (Z.680-699) und Vortag-Vergleich (Z.710-719), alle einzeln try/except-geschützt. Der E-Mail-Versand selbst hat bereits eine 4-Versuche-Kaskade mit Backoff plus Fallback auf den eigenen Mailserver (`src/output/channels/email.py` Z.196-302). Die verbleibende reale Auslöse-Bedingung für #1009 ist also schmaler als ursprünglich angenommen: nur wenn **beide** Mailwege gleichzeitig ausfallen, oder ein unerwarteter Fehler im finalen Render-/Versand-Schritt (`NotificationService`-Aufruf ab Z.721, oder SMS/Telegram-Versand) auftritt. Der Fix bleibt als defensiver Backstop sinnvoll (verhindert Dauerschleife bei diesem selteneren Restfehler), ist aber kein Schutz gegen alltägliche Ausfälle — die sind bereits anderweitig abgefangen.

**#1019:** Gate direkt nach `_resolve_user_for_chat` (Telegram) bzw. bereits vorhanden über `_authorize` (E-Mail): wenn `user_id == "default"`, neutrale Antwort mit Hinweis auf Registrierung (`/start TOKEN`) statt Verarbeitung — PO-Entscheidung bereits getroffen (s. Open Questions, erledigt). Kein Sonderfall für den Betreiber nötig, da er nie in den `"default"`-Zweig fällt.

### Dependencies

Siehe Kontext-Dokument oben (`TripCommandProcessor.process()`, `NotificationService`, `Settings.with_user_profile()`, `loader.lookup_user_by_*`). Keine harte Reihenfolge zwischen #1009/#1019 (unterschiedliche Dateien/Methoden) — beide in einem Workflow/einer Spec, Implementierungsreihenfolge #1019 zuerst (sicherheitsrelevanter, PO-Freigabe zum Wortlaut könnte länger dauern).

### Open Questions — GEKLÄRT (2026-07-07)

- [x] #1019 — Antwortverhalten bei abgelehntem Fremden: **Hinweis auf Registrierung** (`/start TOKEN`-Hinweis), PO-entschieden.
- [x] #1019 — Betreiber-Profil: **hinfällig**, `henning` ist bereits vollständig registriert (mail_to, telegram_chat_id, sms_to) — kein Sonderfall nötig, kein Folge-Issue.
- [x] #1009 — Trade-off: **akzeptiert** als defensiver Backstop, mit korrigiertem (schmalerem) Anwendungsfall — s. Technical Approach oben.
- [ ] #1019 — exakter deutscher Wortlaut der Registrierungs-Hinweis-Antwort — wird in der Spec formuliert und dem PO zur Freigabe vorgelegt.
