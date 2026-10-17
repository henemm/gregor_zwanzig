---
entity_id: onboarding_willkommen_checkliste
type: module
created: 2026-10-16
updated: 2026-10-16
status: draft
version: "1.0"
workflow: feat-2521-s2-willkommen
tags: [frontend, go, python, onboarding, willkommen, checkliste, testmail, profil, adr, issue-2521, s2]
---

# Willkommens-Hinweis, Startklar-Checkliste und echte Testmail (Onboarding S2)

## Approval

- [ ] Approved (PO-Freigabe ausstehend: ACs auf Deutsch lesen, dann `approved` bzw. `freigabe`)

## Purpose

Ein neu eingeladener Nutzer soll vom ersten Login bis zum ersten planmäßig zugestellten Briefing geführt werden: Auf der Startseite erscheint ein Willkommens-Hinweis und eine Startklar-Checkliste. Er kann eine echte Testmail an seine bestätigte Adresse senden (heute scheitert der Knopf für Externe, oder die Mail ginge an den Betreiber). Außerdem führt „+ Neuer Vergleich" endlich auf `/compare/new`. Bestandsnutzer sehen von alledem nichts. Issue #2521, Scheibe S2; S1 (`begriff_erklaerung_infobox.md`) ist live. Der Gesamt-Entwurf `onboarding_hilfe_2521.md` bleibt Gesamtbild; S2 ist ausschließlich hier spezifiziert.

## Source

- **File:** `internal/model/user.go`, `internal/store/user.go`, `internal/handler/auth.go`, `internal/handler/notify.go` (neu), `internal/router/router.go`, `src/services/channel_test_service.py`, `src/services/first_briefing.py` (neu), `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/+page.svelte`, `frontend/src/routes/_home/EmptyKachel.svelte`, `frontend/src/routes/_home/StartklarCheckliste.svelte` (neu), `frontend/src/lib/i18n/messages/de.json`, `docs/adr/0092-nutzer-testmail-an-bestaetigte-profiladresse.md` (neu)
- **Identifier:** `User.OnboardingPending`, `User.OnboardingDismissed`, `User.ChecklistDismissed`, `User.TestMailSentAt`, `SetUserOnboardingFlags`, `SetUserTestMailSentAt`, `NotifyTestHandler`, `send_test_message`, `mark_first_briefing`, `StartklarCheckliste`

> **Schicht-Hinweis:** Full-Stack (Go, Python, SvelteKit). Mandantenfähig: jeder Endpoint und jeder Schreibweg arbeitet mit der `user_id` aus dem Auth-Kontext, nie mit `"default"`. Alle vier Kanäle bleiben gleichrangig; die Checkliste macht E-Mail zum Pflichtweg der Zustellung, ersetzt aber keinen anderen Kanal.

## Estimated Scope

- **Files:** ca. 14 produktiv (3 neu: `notify.go`, `first_briefing.py`, `StartklarCheckliste.svelte`; dazu 1 ADR) plus Tests
- **LoC (produktiv, ohne Tests/Katalog/docs):** ca. +430 bis +450 / −20. Über 250: `workflow.py set-field loc_limit_override 500` ist gesetzt. Der Scope wird nicht verengt (Epic-Regel).
- **Risiko:** MEDIUM (Versandentscheidung Testmail, `user.json`-Schema, Mandantentrennung)

### Betroffene Dateien

| Datei (Stelle) | Änderung | Beschreibung |
|---|---|---|
| `internal/model/user.go:10-77` (Muster `PasskeyPromptDismissed :47`, `EmailVerifiedAt :36`) | MODIFY | Felder `OnboardingPending`, `OnboardingDismissed`, `ChecklistDismissed` (bool) und `TestMailSentAt *time.Time`, alle `omitempty`, typisiert; Kommentar nach Muster `Disabled`. Löst Pre-Snapshot-Hook aus. Gemeinsamer Helfer „neues Konto markieren" |
| `internal/store/user.go:76-90, :120, :144` | MODIFY | Neue öffentliche Merge-Setter `SetUserOnboardingFlags` und `SetUserTestMailSentAt` nach Muster `SetUserDisabled`, über privates `mergeUserJSON` |
| `internal/handler/auth.go:46, :134, :178` | MODIFY | `RegisterHandlerWithInvites` ruft den Helfer vor `SaveUser` |
| `internal/handler/auth_magic.go:285` | MODIFY | `createMagicLinkUser` ruft den Helfer |
| `internal/handler/auth_oauth.go:383` | MODIFY | `createOAuthUser` ruft den Helfer |
| `internal/handler/passkey.go:517, :572` | MODIFY | `PasskeyRegisterPublicFinishHandler` ruft den Helfer |
| `internal/handler/auth.go:844-912, :928-978` | MODIFY | `profileResponse` und `toProfileResponse`: drei Bools immer, `test_mail_sent_at` nur wenn gesetzt, `first_briefing_at` aus `first_briefing.json` (fail-soft) |
| `internal/handler/auth.go:1021, :1041, :1304-1306, :1339` | MODIFY | `UpdateProfileHandler`: Decoder um `onboarding_dismissed`/`checklist_dismissed` (`*bool`); Schreiben über den Merge-Setter |
| `internal/handler/notify.go` | CREATE | `NotifyTestHandler`: Proxy zu Python mit `user_id` aus Auth-Kontext, setzt `TestMailSentAt` nur bei Kanal `email` und `status=="ok"` (Muster `sms_daily_usage.go:17-37`) |
| `internal/router/router.go:256` | MODIFY | `POST /api/notify/test` von `ProxyPostHandler` auf `NotifyTestHandler` |
| `src/services/channel_test_service.py:12-46` (E-Mail-Zweig `:26-31`) | MODIFY | Kein `.for_testing()` für echte Nutzer; Sperren im Dienst (A3) |
| `src/services/first_briefing.py` | CREATE | Geteilter, einmaliger, fail-soft Schreiber von `first_briefing.json` |
| `src/services/trip_report_scheduler.py:1787` | MODIFY | Aufruf neben `_append_briefing_log`, nur wenn `not angefordert` |
| `src/services/scheduler_dispatch_service.py:455, :716` | MODIFY | Aufruf in `send_one_compare_preset` bei `send_result.sent and not on_demand` |
| `frontend/src/routes/+layout.server.ts:5-33` | MODIFY | Profilfelder durchreichen (Muster `passkeyPromptDismissed :22/30`) |
| `frontend/src/routes/+page.svelte:104, :162, :167` | MODIFY | Willkommen/Checkliste einbinden; Link-Fix `buildCompareCtaHref` und Kopfzeilen-Link auf `/compare/new` |
| `frontend/src/routes/_home/EmptyKachel.svelte:9` | MODIFY | Willkommens-Inhalt, Link-Fix |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | CREATE | Checkliste mit „Ausblenden" |
| `frontend/src/lib/i18n/messages/de.json` | MODIFY | Alle neuen Texte (`onboarding.*`) |
| `docs/adr/0092-nutzer-testmail-an-bestaetigte-profiladresse.md`, `docs/adr/README.md` | CREATE/MODIFY | Neues ADR und Indexeintrag (`tests/test_adr_index_drift.py`) |
| `docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md:247-248` | MODIFY | Vermerk „abgelöst durch #2521 S2 / ADR-0092" |
| `docs/specs/modules/onboarding_hilfe_2521.md` | MODIFY | Verweis „S2 spezifiziert in onboarding_willkommen_checkliste.md" |
| `tests/tdd/test_telegram_inbound_reply_contract.py:414`, `tests/tdd/test_channel_test_button.py:81-101`, `tests/test_success_status_guard.py:~2144` | MODIFY | An die neue Testmail-Regel angepasst (siehe „Abgelöste Zusicherungen") |
| Neue Tests: Go, pytest, `node --test`, Staging-Playwright | CREATE | zu den ACs |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `PasskeyPromptDismissed` (`user.go:47`, `profile_passkey_prompt_test.go:52`) | Muster | Profil-Flag: omitempty, Antwort immer, Decoder `*bool`, Test „PUT nur mit Flag" |
| `mergeUserJSON` / `SetUserDisabled` (`store/user.go:120, :144`) | function | Fremdfeld-erhaltender Schreibweg (Daten-Schema-Regel Read-Modify-Write) |
| `GET/PUT /api/auth/profile` | endpoint | Quelle und Ziel der Flags |
| `POST /api/notify/test` → Python `send_test_message` | endpoint | Testmail; Fehler kommen als HTTP 200 mit `{"error": …}`, nur `status=="ok"` heißt gesendet |
| `Settings.with_user_profile`, `force_test` (`src/app/config.py:400, :414, :444`) | function | Empfänger aus dem Profil; Testnutzer/Staging bleiben auf Stalwart |
| Resend-Allowlist (`src/outputs/email.py:239-300`), ADR-0087 (Empfängerschutz), ADR-0066 (E-Mail-Bestätigung) | adr/module | Fremdadressen nur bestätigt und über Resend |
| `trip_report_scheduler.py` (`angefordert`), `scheduler_dispatch_service.py` (`on_demand`, `send_result.sent`) | module | Unterscheidung planmäßig / angefordert |
| `model.SmsAllowed(tier)`, `premium_sms_allowed` | function | Tarif-Hinweise (keine Profilfelder) |
| `t(key)` / `de.json` (#2520, S1) | module | Einziger Ort für Texte |
| Stalwart-Test-Postfach `gregor-test@henemm.com` (`GZ_IMAP_*`) | Infrastruktur | Staging-Beleg der echten Mail über Wegwerf-Nutzer `gregor-test+…@henemm.com` |

## Implementation Details

### Go

1. **Profilfelder (typisiert).** `internal/model/user.go` bekommt `OnboardingPending`, `OnboardingDismissed`, `ChecklistDismissed` (je `bool`, `omitempty`) und `TestMailSentAt *time.Time`. Typisiert, damit sie jeden übrigen `SaveUser`-Schreiber überstehen. `profileResponse` liefert die drei Bools immer (kein „Feld fehlt"), `test_mail_sent_at` nur wenn gesetzt, dazu `first_briefing_at`. `onboarding_pending`, `test_mail_sent_at` und `first_briefing_at` werden vom Client **nie** gelesen; der Update-Decoder kennt nur `onboarding_dismissed` und `checklist_dismissed` als `*bool`.
2. **„Nur neu Eingeladene" ohne Backfill.** `OnboardingPending=true` wird bei **jeder** Kontoanlage über einen gemeinsamen Helfer gesetzt, den alle vier nutzerseitigen Anlagewege aufrufen: `RegisterHandlerWithInvites` (auth.go:46; Registrierung ist nicht auf Einladungen beschränkt), `createMagicLinkUser` (auth_magic.go:285), `createOAuthUser` (auth_oauth.go:383), `PasskeyRegisterPublicFinishHandler` (passkey.go:517/:572). **Nicht** `seedAdminUser` (cmd/server/main.go:141). Testkonten (`IsTestUser`) bekommen das Merkmal ebenfalls (Staging-E2E). Bestandskonten haben das Feld nicht, es liest als `false`, nichts wird sichtbar.
3. **Merge-Setter.** `SaveUser` schreibt das typisierte Struct komplett; unbekannte JSON-Felder gehen verloren, `mergeUserJSON` erhält sie. Deshalb gibt es `SetUserOnboardingFlags` (je Flag, nur gesetzte) und `SetUserTestMailSentAt` nach Muster `SetUserDisabled`. `UpdateProfileHandler` schreibt die Dismiss-Flags darüber. Enthält der PUT **nur** Dismiss-Flags, findet kein `SaveUser` statt; Fremdfeld und alle Nachbarfelder bleiben erhalten. Grenze: PUTs mit anderen Profilfeldern laufen weiter über `SaveUser` (Bestandsverhalten, siehe Known Limitations).
4. **`NotifyTestHandler`** (neu, `notify.go`) ersetzt `ProxyPostHandler` an `router.go:256`: liest `user_id` aus dem Auth-Kontext (401 ohne), reicht Anfrage unverändert an den Python-Core, setzt `TestMailSentAt = now` per Merge-Setter **nur** bei Kanal `email` **und** Antwort `status=="ok"`; die Python-Antwort geht unverändert zurück.
5. **`first_briefing_at`.** `toProfileResponse` liest `data/users/<id>/first_briefing.json` (`{"first_briefing_at": "<ISO>"}`) über `s.WithUser(<user_id>)`, fail-soft (fehlend oder kaputt = Feld fehlt).

### Python

1. **Testmail (Variante A3).** Der E-Mail-Zweig von `send_test_message` (`channel_test_service.py:26-31`) nutzt heute `.for_testing()` und damit den Stalwart-Host; der Lokal-Guard (`src/output/channels/email.py:~810-850`) lässt dort nur `@henemm.com` durch, externe Nutzer bekommen einen Fehler. Fehlt `user.json`, fällt `with_user_profile` auf die globale Betreiber-`mail_to` zurück, die Mail ginge an den Betreiber. Neu: für echte Nutzer **kein** `.for_testing()`, es gilt die normale Versandkette (Resend, Allowlist, ADR-0087); Testnutzer und Staging bleiben über `force_test` (`config.py:~414`) auf Stalwart. Der Dienst sperrt **selbst** und sendet nichts, mit deutschem Fehlertext, wenn: `user_id` leer oder `"default"`, `user.json` fehlt, `email_verified_at` fehlt oder die Profil-`mail_to` leer ist. Es wird nie an die Betreiber-Adresse gesendet. Der Telegram-Zweig bleibt unverändert.
2. **`first_briefing.py`** (neu): `mark_first_briefing(user_id)` schreibt `first_briefing.json` nur, wenn die Datei fehlt (einmalig), fail-soft (nie eine Ausnahme nach außen). Python schreibt `user.json` nirgends und tut das auch hier nicht (kein zweiter Schreiber, kein Race mit `mergeUserJSON`).
3. **Aufrufstellen (nur planmäßig).**
   - Trip: `trip_report_scheduler.py` im Erfolgs-`else` bei `:1787` neben `_append_briefing_log`, nur wenn `not angefordert`. (Test-Versand, „report"-Befehl und SMS heute/morgen setzen `angefordert=True` und zählen nicht.)
   - Ortsvergleich: `scheduler_dispatch_service.py`, `send_one_compare_preset` (`:455`), an der Stelle `if send_result.sent and not on_demand:` (`:716`). Manueller Versand (`send_compare_preset` `:741` → `on_demand=True`) und Fehlschlag zählen nicht.
   - **Nicht** `letzter_versand`/`save_compare_preset_status` (`:732`, läuft auch bei Fehlschlag) und **nicht** `briefing_log.json` als Quelle. Deren Leser (`cockpit.go:21`, `BriefingCountByTrip` `log.go:103`, `briefing_history.go:25`, `briefing_slots.py:365`) bleiben unberührt.

### Frontend

1. `+layout.server.ts` reicht `onboarding_pending`, `onboarding_dismissed`, `checklist_dismissed`, `test_mail_sent_at`, `first_briefing_at`, `email_verified`, `telegram_chat_id`, `sms_allowed`, `premium_sms_allowed` aus dem einen vorhandenen Profilabruf durch (kein zweiter Abruf).
2. **Willkommens-Hinweis** (ersetzt/ergänzt `EmptyKachel.svelte`): sichtbar nur wenn `onboarding_pending && !onboarding_dismissed` **und** der Nutzer weder Trips noch Ortsvergleiche hat. Inhalt: was Gregor macht (Briefing morgens/abends, Alarme), Testmail senden, ersten Trip oder Ortsvergleich anlegen. „Verstanden" setzt `onboarding_dismissed` per `PUT /api/auth/profile` (nur dieses Feld).
3. **Startklar-Checkliste** (`StartklarCheckliste.svelte`): sichtbar wenn `onboarding_pending && !checklist_dismissed` und mindestens ein Pflichtpunkt offen. **Pflichtpunkte:** E-Mail bestätigt · mindestens ein Trip oder Ortsvergleich · erstes Briefing erhalten. **Info-Punkte (blockieren nicht):** „Testmail gesendet am <Datum>" (ohne Datum: Knopf „Testmail senden") · „Telegram verknüpft" (optional, nie Pflicht). SMS-/Premium-SMS-Hinweis nur bei `sms_allowed`/`premium_sms_allowed`. „Ausblenden" setzt `checklist_dismissed`. Kein Hilfelink (`/hilfe` existiert nicht, spätere Scheibe).
4. **Link-Fix:** `+page.svelte:104` (`buildCompareCtaHref`), `:162` und `EmptyKachel.svelte:9` auf `/compare/new`; Listen-Links auf `/compare` bleiben.
5. **Texte** ausschließlich über `t(key)` aus `de.json` (Präfix `onboarding.*`), durchgehend „Trip", Kontrast mindestens 4,5:1, nie `--g-ink-4`. Texte erklären und zeigen Stand, sie geben keine Handlungsempfehlung. Tests mit `node --test`, nicht Vitest.

### ADR-0092

`docs/adr/0092-nutzer-testmail-an-bestaetigte-profiladresse.md`: „Nutzer-Testmail geht an die bestätigte Profiladresse über den echten Versandweg". Löst die #198-Regel „Testmail nie über Resend" (Quelle: `docs/specs/_archive/bugfix/bug_198_notify_test_resend.md:20-22`) **für echte Nutzer** ab; Bezug ADR-0087. Eintrag in `docs/adr/README.md`.

### Abgelöste Zusicherungen (ausdrücklich, nicht still)

- Freigegebene AC in `docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md:247-248` („E-Mail-Zweig des Test-Knopfs bleibt unverändert (#198)") samt Test `tests/tdd/test_telegram_inbound_reply_contract.py:414` (`verbindungen == [TEST_SMTP_HOST]`). Dort Vermerk „abgelöst durch #2521 S2 / ADR-0092"; der Test wird auf die neue Regel umgestellt (echter Nutzer: normale Kette; Testnutzer: weiter Stalwart).
- `tests/tdd/test_channel_test_button.py:81-101` (echte Mail mit `user_id="default"`): wird auf die neue Sperre umgestellt, `"default"` sendet nichts mehr.
- `tests/test_success_status_guard.py:~2144` (Zeilenzitate aus `channel_test_service`): Zitate nachgezogen.
- Der Konto-Testknopf (`frontend/src/routes/account/+page.svelte:275-290`) nutzt denselben Pfad und profitiert mit.

## Expected Behavior

- **Input:** erster Login eines neu angelegten Nutzers; Klick auf „Testmail senden", „Verstanden", „Ausblenden"; Anlegen eines Trips/Ortsvergleichs; erstes planmäßiges Briefing.
- **Output:** Willkommen und Checkliste auf `/`; Testmail im Postfach der bestätigten Adresse mit Datum in der Checkliste; Checkliste verschwindet, wenn die drei Pflichtpunkte erledigt sind.
- **Side effects:** `onboarding_pending` (bei Anlage), `onboarding_dismissed`, `checklist_dismissed`, `test_mail_sent_at` in `user.json` (nur über Merge-Setter bzw. `SaveUser` bei Anlage); `first_briefing.json` je Nutzer (einmalig); eine echte Mail pro Testmail-Klick. Keine Änderung an anderen Bestandsdaten.

## Acceptance Criteria

- **AC-1:** Given ein Konto wird über Registrierung (mit Einladung), Magic-Link, OAuth-Anmeldung oder Passkey-Registrierung neu angelegt / When ich das gespeicherte Nutzerprofil lese / Then ist das Merkmal „neu eingeladen" (`onboarding_pending`) gesetzt, bei allen vier Wegen gleich, und der Admin-Startnutzer aus dem Serverstart trägt es nicht.
  - Prüfung: Go-Test je Anlageweg bzw. ein Test, der alle vier Wege durch den gemeinsamen Helfer führt; Gegenprobe: den Aufruf in einem Weg auslassen macht genau diesen Test rot.
- **AC-2:** Given ein Nutzer, dessen Konto vor S2 angelegt wurde (ohne Merkmal), mit offenen Pflichtpunkten / When er die Startseite öffnet / Then sieht er weder den Willkommens-Hinweis noch die Startklar-Checkliste, während ein frisch angelegter Nutzer beides sieht.
  - Prüfung: `node --test` mit Layout-Daten beider Fälle; Staging-Playwright mit Altkonto und neuem Wegwerf-Nutzer.
- **AC-3:** Given ein neu angelegter Nutzer ohne Trips und ohne Ortsvergleiche / When er `/` öffnet / Then sieht er den Willkommens-Hinweis (was Gregor macht, Testmail senden, ersten Trip oder Ortsvergleich anlegen); hat er mindestens einen Trip oder Ortsvergleich, erscheint der Hinweis nicht.
  - Prüfung: `node --test` Render-Test mit beiden Zuständen; Staging-Playwright.
- **AC-4:** Given der Willkommens-Hinweis / When ich „Verstanden" klicke und die Seite auf einem anderen Gerät neu lade / Then bleibt der Hinweis weg, und E-Mail, Telegram, Tarif, Passkey-Flag und ein unbekanntes Fremdfeld meiner Profildatei sind unverändert.
  - Prüfung: Go-Test `PUT /api/auth/profile` mit nur `onboarding_dismissed`, Fixture-Altdatei mit Fremdfeld, Nachbarfelder auf der Platte byte-gleich (Muster `profile_passkey_prompt_test.go:52`); es findet kein `SaveUser` statt.
- **AC-5:** Given die sichtbare Checkliste mit offenen Pflichtpunkten / When ich „Ausblenden" klicke und später auf einem anderen Gerät `/` öffne / Then bleibt die Checkliste weg, obwohl Pflichtpunkte offen sind, und alle Nachbarfelder meines Profils sind unverändert.
  - Prüfung: Go-Test `PUT` mit nur `checklist_dismissed` (Fremdfeld und Nachbarfelder erhalten); `node --test`: dismissed schlägt offene Pflichtpunkte.
- **AC-6:** Given zwei Nutzer A und B / When A „Verstanden" oder „Ausblenden" klickt / Then ändert sich nur das Profil von A, B sieht Willkommen und Checkliste unverändert; ein vom Client per `PUT` mitgeschicktes `onboarding_pending`, `test_mail_sent_at` oder `first_briefing_at` bleibt wirkungslos.
  - Prüfung: Go-Zwei-Nutzer-Test, PUT mit gefälschten Feldern, Platten-Vergleich.
- **AC-7:** Given eine bestehende `user.json` ohne die neuen Felder, aber mit einem unbekannten Fremdfeld / When `GET /api/auth/profile` gelesen und danach ein Dismiss-Flag gesetzt wird / Then liefert das Profil die drei Bools immer (`false`), `test_mail_sent_at` nur wenn gesetzt, und weder Fremdfeld noch bestehende Felder gehen verloren, auch nicht nach `SetUserTestMailSentAt`.
  - Prüfung: Go-Roundtrip-Test mit Altdatei inkl. Fremdfeld, je Merge-Setter einzeln und zusammen.
- **AC-8:** Given ein Nutzer mit bestätigter E-Mail-Adresse / When er „Testmail senden" klickt / Then kommt innerhalb weniger Minuten eine echte Mail im Postfach genau dieser Adresse an, ohne dass ein Trip existiert, und die Checkliste zeigt „Testmail gesendet am" mit dem heutigen Datum.
  - Prüfung: pytest `send_test_message("email", uid)` mit aufgezeichnetem SMTP-Gegenstück (Verbindungshost stammt aus der normalen Versandkette, nicht aus `test_smtp_host`; Testnutzer weiter Stalwart); Staging-E2E über Wegwerf-Nutzer `gregor-test+…@henemm.com` und IMAP-Abruf (`GZ_IMAP_*`).
- **AC-9:** Given zwei Nutzer A und B mit verschiedenen bestätigten Adressen / When A die Testmail auslöst / Then geht sie nur an As Adresse, nie an B, nie an die Betreiber-Adresse und nie unter der `user_id` `"default"`.
  - Prüfung: pytest mit zwei Profilen (`get_data_dir`-Isolation), Empfänger je Nutzer geprüft; Go-Handlertest übergibt die `user_id` aus dem Auth-Kontext.
- **AC-10:** Given ein Nutzer ohne bestätigte Adresse, ohne Profil-Adresse, ohne vorhandene `user.json` oder mit leerer bzw. „default"-Kennung / When die Testmail ausgelöst wird / Then wird nichts gesendet, der Nutzer sieht einen klaren deutschen Fehlertext, und es geht auch keine Mail an die Betreiber-Adresse.
  - Prüfung: pytest je Sperrfall (Verbindungs-Aufzeichnung leer); Gegenprobe: Sperre „user.json fehlt" entfernen macht den Test rot.
- **AC-11:** Given ein Testmail-Aufruf / When er mit Kanal E-Mail und Antwort `status` = `ok` endet / Then steht `test_mail_sent_at` im Profil des aufrufenden Nutzers und nur dort; bei Fehlerantwort (`error` bei HTTP 200), bei Kanal Telegram und bei fehlender Anmeldung bleibt das Feld unverändert.
  - Prüfung: Go-Handlertest mit HTTP-Stub als Python-Gegenstück (Antworten `ok`, `error`, Telegram); Zwei-Nutzer-Test; Mutation „HTTP 200 genügt statt `status=="ok"`" muss rot werden.
- **AC-12:** Given Nutzer A hat ein planmäßiges Briefing (Trip oder Ortsvergleich) erhalten und Nutzer B nicht / When beide `/` öffnen / Then zeigt A „Erstes Briefing erhalten" als erledigt (`first_briefing_at` im Profil), B sieht den Punkt offen; ein zweites Briefing ändert das Datum von A nicht.
  - Prüfung: pytest `mark_first_briefing` (einmalig, fail-soft bei Schreibfehler) und Go-Test `toProfileResponse` mit zwei Nutzerverzeichnissen, fehlende/kaputte Datei = Feld fehlt.
- **AC-13:** Given ein angefordertes oder fehlgeschlagenes Briefing (Test-Versand, „report"-Befehl, SMS heute/morgen, manueller Ortsvergleich-Versand, fehlgeschlagener Versand) / When der Versand endet / Then bleibt „Erstes Briefing erhalten" offen; erst ein planmäßig zugestellter Trip- oder Ortsvergleich-Versand hakt ab.
  - Prüfung: pytest je Aufrufstelle (`angefordert=True`, `on_demand=True`, `send_result.sent=False` schreibt keine Datei; planmäßiger Erfolg schreibt sie); Mutation „`letzter_versand` oder `briefing_log.json` als Signal" muss rot werden.
- **AC-14:** Given ein Nutzer mit bestätigter E-Mail, mindestens einem Trip oder Ortsvergleich und einem planmäßig erhaltenen Briefing / When er `/` öffnet / Then ist die Checkliste verschwunden; solange einer dieser drei Pflichtpunkte offen ist, bleibt sie sichtbar, und „Testmail gesendet" und „Telegram verknüpft" blockieren das Verschwinden nicht.
  - Prüfung: `node --test` Zustandsmatrix; Mutation „Testmail oder Telegram als Pflichtpunkt" bzw. „Briefing nicht als Pflicht" muss rot werden.
- **AC-15:** Given ein Nutzer mit Tarif ohne SMS bzw. mit `sms_allowed` oder `premium_sms_allowed` / When Willkommen und Checkliste angezeigt werden / Then erscheinen SMS und Premium-SMS nur beim passenden Tarif, Telegram nur als optionaler Hinweis ohne Blockade, und kein Text sagt, ein Kanal ersetze einen anderen.
  - Prüfung: `node --test` Render-Tests je Tarifstand und Katalogtest.
- **AC-16:** Given die Startseite eines Nutzers ohne Trips und Ortsvergleiche / When ich „+ Neuer Vergleich" klicke (Kopfzeile, Leerzustand oder Aufruf-Knopf) / Then lande ich auf `/compare/new`, während die Listen-Links weiter auf `/compare` führen.
  - Prüfung: `node --test` Render-Test aller Links inkl. `buildCompareCtaHref`; Staging-Playwright.
- **AC-17:** Given Willkommen und Checkliste / When ich die Texte lese / Then stehen sie vollständig im Textkatalog (nicht leer, durchgehend „Trip", keine Handlungsempfehlung), haben Kontrast mindestens 4,5:1 und nutzen nie `--g-ink-4`; die Seite wirft keinen Konsolenfehler.
  - Prüfung: Katalogtest mit Gegenprobe, Kontrast-Test der Token, Staging-Playwright mit Konsolen-Listener.
- **AC-18:** Given das neue ADR und die abgelösten Zusicherungen / When die Test-Suite läuft / Then enthält `docs/adr/README.md` das ADR-0092, die abgelöste AC in `fix_1412_s4a_empfaengervertrag_telegram.md` trägt den Vermerk „abgelöst durch #2521 S2 / ADR-0092", und die drei angepassten Bestandstests sind grün.
  - Prüfung: `tests/test_adr_index_drift.py`; benannte Testdateien `test_telegram_inbound_reply_contract.py`, `test_channel_test_button.py`, `test_success_status_guard.py`.

## Test Plan

### Kern (deterministisch, 100 % grün)

- Go: `internal/handler/` Tests für Anlagewege (AC-1), Dismiss-PUT mit Fremdfeld und Zwei-Nutzer (AC-4/5/6/7), `NotifyTestHandler` mit HTTP-Stub (AC-11), `toProfileResponse` mit `first_briefing.json` (AC-12); `internal/store/` Merge-Setter-Roundtrip.
- pytest (benannte Dateien): Testmail-Dienst mit aufgezeichnetem SMTP-Gegenstück, Sperrfälle, Zwei-Nutzer (AC-8/9/10); `first_briefing`-Helfer und beide Aufrufstellen (AC-12/13); ADR-Index (AC-18). Kein Mock-Theater, nur aufgezeichnete Verbindungen und echte Dateien in der Test-Datenablage.
- `node --test`: Sichtbarkeitsmatrix Willkommen/Checkliste, Tarif-Hinweise, Link-Fix, Katalog und Kontrast (AC-2/3/14/15/16/17).

### Live-E2E (nur `/e2e-verify`)

- Staging-Playwright: Wegwerf-Nutzer `gregor-test+…@henemm.com` anlegen, Willkommen sehen, Testmail senden, Zustellung per IMAP (Stalwart `gregor-test@henemm.com`) prüfen, Datum in der Checkliste; Altkonto sieht nichts (AC-2/8). Trip-Mail-Validator ist für diese Testmail nicht einschlägig (keine Briefing-Mail).
- „Erstes Briefing erhalten" auf Staging nur messbar, soweit ein planmäßiger Lauf stattfindet; sonst als `NOT_MEASURABLE_ON_STAGING` ausweisen, nie PASS erfinden.

## Known Limitations

- `test_mail_sent_at` belegt, dass der Versand angenommen wurde, nicht die Zustellung im Postfach.
- „Erstes Briefing erhalten" zählt nur planmäßige Briefings (PO-Entscheidung 2026-10-16); ein Nutzer, der nur Test-Versände auslöst, sieht den Punkt offen.
- Bestandsnutzer (Konto vor S2) sehen Willkommen und Checkliste nie; es gibt bewusst keinen Backfill (PO-Entscheidung).
- PUTs auf `/api/auth/profile` mit anderen Profilfeldern laufen weiter über `SaveUser` und können unbekannte Fremdfelder verlieren (Bestandsverhalten); der Umbau des ganzen Handlers ist nicht Teil von S2. Die neuen Felder überstehen das, weil sie typisiert sind.
- `first_briefing.json` ist eine zweite kleine Datei neben `user.json`; sie wird nicht über das Admin-DTO ausgegeben (S5).
- Kein Hilfelink in der Checkliste; die Hilfeseite ist eine spätere Scheibe.
- Telegram-Verknüpfung bleibt außerhalb dieser Scheibe (Token-Flow, #2141); die Checkliste zeigt nur den Stand.
- Nur Deutsch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0092 (neu)
- **Rationale:** Die Testmail für echte Nutzer geht über den echten Versandweg an die bestätigte Profiladresse. Das löst die Regel aus #198 („Testmail nie über Resend") für echte Nutzer ab und berührt die Kanal-/Versandentscheidung (ADR-0087). Testnutzer und Staging bleiben unverändert auf Stalwart.

## Changelog

- 2026-10-16: Initial spec created (Issue #2521, Scheibe S2); Varianten A3 (Testmail), B3' (`first_briefing.json`), PO-Entscheidungen „nur planmäßige Briefings zählen" und „nur neu Eingeladene"
- 2026-10-17: ADR-Nummer 0091 → 0092 (Kollision mit ADR-0091 SLF-Lawinenquelle aus #1441 S3, zuerst in main); Inhalt unverändert, PO-Zustimmung 2026-10-17
