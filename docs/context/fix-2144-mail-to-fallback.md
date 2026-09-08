# Context: fix-2144-mail-to-fallback

## Request Summary
Neue Nutzer, die bei der Registrierung kein explizites `mail_to` im Profil bekommen,
erhalten ihre Briefings über den globalen `.env`-Fallback (`GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/
`GZ_SMS_TO`) — die landen beim Betreiber. Cross-Tenant-Zustellung, Blocker, Teil von Epic #2138.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:96-109` | `RegisterHandler` (Passwort-Weg) — setzt `model.User{Email: req.Email}`, **kein** `MailTo`. Feld existiert bereits im Modell (`internal/model/user.go:16 json:"mail_to"`). |
| `internal/handler/auth_magic.go:205-213` | Magic-Link-Registrierung — analoges `model.User{}`-Literal, ebenfalls ohne `MailTo`. |
| `internal/handler/auth_oauth.go:201-211` | OAuth-Registrierung — dito. |
| `internal/handler/passkey.go:477,528,536,554` | Passkey-Registrierung — `newUser := model.User{...}` bei `passkey.go:536`, ebenfalls ohne `MailTo`. |
| `internal/store/user.go:52,84` | `SaveUser` schreibt das komplette `User`-Struct nach `<DataDir>/users/<id>/user.json` — Neuanlage, kein Read-Modify-Write nötig (Datei existiert noch nicht). |
| `src/app/config.py:365-410` (`with_user_profile`) | Liest **dieselbe** `user.json` (`get_data_dir(user_id)/"user.json"`, gleicher Pfad wie Go's `DataDir/users/<id>/user.json` — bestätigt über `GZ_DATA_DIR`/systemd-Drop-in). Überschreibt `mail_to`/`telegram_chat_id`/`sms_to` in `overrides` **nur wenn im Profil vorhanden** (`if profile.get("mail_to"): overrides["mail_to"] = ...`) — sonst bleibt der globale `.env`-Wert aus `base` (bzw. `self`) stehen. Das ist die Kernursache. |
| `src/output/channels/base.py:66` | `ChannelBlockedError(OutputConfigError)` — bestehende Exception-Klasse für „Kanal technisch/fachlich nicht sendefähig", trägt `reason_code`. |
| `src/output/channels/premium_sms.py:41-91` (`_resolve_recipient`) | **Referenzmuster** für „kein Empfänger bekannt": wirft `ChannelBlockedError` mit eigenem `reason_code` (`BLOCK_REASON_NO_REPLY_ADDRESS`) statt zu senden oder zu crashen. Wird von `notification_service.py` als `blocked_channels`/`blocked_reason_codes` sauber protokolliert (kein `briefing_log`-Eintrag, aber unterscheidbare Log-Zeile — vgl. #1007/#1403). |
| `src/output/channels/email.py:431,648-650` | `self._to = settings.mail_to`; `send()` baut `recipients = [to] if to else [self._to]` — bei leerem `self._to` **kein** Skip, sondern Versand an `[None]`/`[""]`. Braucht dieselbe Resolve-mit-`ChannelBlockedError`-Behandlung wie Premium-SMS. |
| `src/output/channels/telegram.py:209,403` | `chat_id = self._settings.telegram_chat_id` — analog ungeprüft. |
| `src/output/channels/sms.py:42` | `return self._settings.sms_to` — analog ungeprüft. |
| `src/services/scheduler_dispatch_service.py:412-431` | Compare-Preset-Versand: **hat bereits** einen expliziten Check (`if not default_to: raise ValueError(...)`), Issue #1452, „Fehlerverhalten bewusst unveraendert" — dieser Pfad ist NICHT Teil des Bugs, sollte aber nicht durch die config.py-Änderung in seinem Verhalten kippen. |
| `src/services/trip_report_scheduler.py:1616-1641` | Trip-Briefing-Versand — nutzt `settings.mail_to` nur für Logging (`mail_empfaenger = self._settings.mail_to if "email" in result.sent_channels ...`), der eigentliche Versand läuft über `notification_service.py` → `email.py`. Kein eigener Fix nötig, profitiert von der Channel-Fix. |
| `docs/reference/operations_playbook.md:616-621` | Beschreibt aktuell nur den Override-Fall (`user.json.mail_to` überschreibt `GZ_MAIL_TO`), **nicht** den Fallback-bei-Fehlen-Fall aus dem Issue — Zeilennummern im Issue (531-533) sind durch spätere Doc-Edits verschoben, inhaltlich aber dieselbe Passage. Braucht nach dem Fix eine Ergänzung: kein Fallback mehr, sondern Skip. |

## Existing Patterns

- **`ChannelBlockedError` + `reason_code`** (`premium_sms.py`) ist das etablierte Muster für „technisch/fachlich nicht sendefähig, kein Crash, sauberes Log" — sollte für Email/Telegram/SMS bei fehlendem Empfänger wiederverwendet werden, nicht neu erfunden.
- **Zwei getrennte Fallback-Fragen** existieren im Code: (a) `with_user_profile()` — Profil fehlt Feld → globaler Fallback (BUG), (b) Compare-Preset-Pfad — hat schon einen expliziten `ValueError`-Guard (kein Bug, aber inkonsistentes Fehlerverhalten ggü. dem Kanal-Skip-Muster; aus Scope-Gründen vermutlich unangetastet lassen, siehe Risiken).
- **`data/users/<id>/user.json` ist eine geteilte Datei** zwischen Go-API und Python-Core (gleicher Pfad über `DataDir`/`GZ_DATA_DIR`) — kein Sync-Mechanismus nötig, Go schreibt direkt das Feld, das Python liest.

## Dependencies

- Upstream: Go `RegisterHandler`-Familie (4 Wege) schreibt `user.json`; Python `with_user_profile()` liest sie.
- Downstream: `notification_service.py` orchestriert die drei Kanal-Klassen (`email.py`, `telegram.py`, `sms.py`), wertet `blocked_channels`/`blocked_reason_codes` aus für Cockpit/Log (#393, #1007, #1403).

## Existing Specs

- `docs/specs/modules/user_auth_endpoints.md` — RegisterHandler-Spec, kennt bisher kein `MailTo`-AC.
- `docs/specs/modules/scheduler_multi_user.md` — Mandanten-Dispatch, relevant für „Zwei-Nutzer-Test"-AC.
- `docs/specs/modules/passkey_webauthn.md` — vierter Registrierungsweg.

## Risks & Considerations

- **Scope-Grenze:** Das Issue fordert explizit alle drei Felder (`mail_to`/`telegram_chat_id`/`sms_to`) UND alle vier Registrierungswege UND den Zwei-Nutzer-Test. Das ist mehr als eine Ein-Zeilen-Änderung — bestätigt die Standard-Track-Einstufung (nicht Fast Track).
- **Nicht anfassen:** Der Compare-Preset-`ValueError`-Pfad (#1452) hat bewusst anderes Fehlerverhalten (hart failen statt skip) — Spec sollte klarstellen, dass dieser Pfad unverändert bleibt, sonst bricht ein bestehender Test.
- **Telegram-Sonderfall:** `telegram_chat_id` wird beim Onboarding typischerweise erst durch eine Bot-Interaktion gelernt (nicht bei Registrierung), d.h. „explizit auf `None` setzen, wenn Profil-Feld fehlt" ist für Telegram vermutlich schon der Ist-Zustand oder nahe dran — separat verifizieren, um keinen Regressions-Fix für ein bereits korrektes Verhalten zu bauen.
- **Bestandsnutzer:** Bereits registrierte Nutzer ohne `mail_to` im Profil sind vom Fix nicht rückwirkend betroffen (nur `with_user_profile()`-Verhalten ändert sich) — das ist erwünscht (kein Daten-Backfill nötig, das Verhalten korrigiert sich beim nächsten Versandversuch selbst: Skip statt Fehlversand).
- **Doku:** `operations_playbook.md` braucht eine Ergänzung nach dem Fix (Fallback-Fall ist dann „Skip mit Log", nicht mehr "globaler Fallback").

## Analysis

### Type
Bug (Cross-Tenant-Zustellung durch stillen globalen Fallback).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | `model.User{...}` um `MailTo: req.Email` ergänzen (Passwort-Registrierung). |
| `internal/handler/auth_magic.go` | MODIFY | dito für Magic-Link-Registrierung. |
| `internal/handler/auth_oauth.go` | MODIFY | dito für OAuth-Registrierung. |
| `internal/handler/passkey.go` | MODIFY | dito für `newUser` bei Passkey-Registrierung (Zeile ~536) — `PasskeyRegisterPublicBeginHandler` validiert `req.Email` (`@`-Pflicht, Zeile ~468) und legt sie in `ChallengeEntry.Email` ab; `Finish` liest `entry.Email` bereits für `newUser.Email` (Zeile ~537) → `MailTo: entry.Email` verfügbar, keine offene Frage. |
| `src/app/config.py` (`with_user_profile`) | MODIFY | `overrides["mail_to"] = profile.get("mail_to")` (auch wenn falsy → explizit `None`), analog für `telegram_chat_id`/`sms_to`. `GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/`GZ_SMS_TO` bleiben nur noch für Legacy-CLI ohne `with_user_profile()`-Aufruf wirksam. |
| `src/output/channels/email.py` | MODIFY | `_resolve_recipient()`-artige Prüfung vor Versand: fehlendes `self._to` → `ChannelBlockedError("email", "...", reason_code=BLOCK_REASON_NO_RECIPIENT)` statt Versand an `[None]`. |
| `src/output/channels/telegram.py` | MODIFY | analoge Prüfung für `chat_id`. |
| `src/output/channels/sms.py` | MODIFY | analoge Prüfung für `sms_to`. |
| `docs/reference/operations_playbook.md` | MODIFY (Doku, zählt nicht gegen LoC-Limit) | Fallback-Passage um den Skip-statt-Fallback-Fall ergänzen. |
| Tests (neu, je Bereich) | CREATE | Zwei-Nutzer-Test je Registrierungsweg (mind. 1 repräsentativ + Parametrisierung möglich) + Skip-Test je Kanal + `with_user_profile()`-Unit-Test für alle drei Felder. |

### Scope Assessment
- Files: ~8 Produktionsdateien + Doku + neue/erweiterte Testdateien
- Estimated LoC: +70/-5 Produktionscode (grobe Schätzung: 4×1 Go-Zeilen, ~20 config.py, ~45 auf 3 Kanalklassen), Tests zusätzlich ~100-150 LoC — Summe wahrscheinlich unter, aber nahe am 250-LoC-Workflow-Limit; ggf. `loc_limit_override` nötig.
- Risk Level: HIGH (Auth + Versand-Kernpfad, alle Nutzer, alle drei Kanäle) bei niedriger technischer Unsicherheit (bestehendes Muster wiederverwendbar).

### Technical Approach
1. Go: an allen vier Registrierungs-Stellen `MailTo` mit der bekannten E-Mail-Adresse setzen (dort wo eine E-Mail vorliegt).
2. Python `with_user_profile()`: von „nur überschreiben wenn vorhanden" auf „immer setzen, auch auf `None`" umstellen — das entfernt den stillen Fallback strukturell an der Quelle.
3. Kanal-Klassen (`email.py`/`telegram.py`/`sms.py`): defensive Prüfung ergänzen, die bei fehlendem Empfänger sauber mit `ChannelBlockedError` abbricht (Muster aus `premium_sms.py`) statt an eine leere Adresse zu senden — nötig, weil Schritt 2 sonst bestehende Trips mit `send_email=True` aber ohne `mail_to` hart brechen lassen würde statt sauber zu skippen.
4. Compare-Preset-Pfad (`scheduler_dispatch_service.py:412-431`) bewusst **nicht anfassen** — hat bereits sein eigenes, dokumentiert-unverändertes `ValueError`-Verhalten (#1452).
5. Zwei-Nutzer-Test wie im Issue gefordert: Nutzer A mit `mail_to`, Nutzer B ohne → B wird übersprungen mit erkennbarer Meldung/`reason_code`, nichts geht an Nutzer A oder den Betreiber.

### Dependencies
Siehe „Dependencies" oben (Context-Sektion) — unverändert.

### Open Questions
- [x] **Geklärt:** `telegram_chat_id` wird bei **keinem** der vier Registrierungswege gesetzt (nur nachträglich über den Settings-Endpoint, `auth.go:675`). Ein frisches `user.json` hat das Feld leer → `with_user_profile()` überschreibt nicht → derselbe globale Fallback auf `GZ_TELEGRAM_CHAT_ID` (Betreiber-Chat) wie bei `mail_to`. Kein Sonderfall, sondern dieselbe Bug-Klasse — bestätigt den Scope aus dem Issue (alle drei Felder).

## Track & Nächster Schritt

Standard Track (Score 3) bestätigt durch Kontext-Recherche — Scope trifft 4 Go-Handler + 3 Python-Kanalklassen + `config.py` + Doku, Blast Radius bleibt hoch (Auth + alle drei Kanäle für alle Nutzer), Unsicherheit bleibt niedrig (bekanntes `ChannelBlockedError`-Muster wiederverwendbar).

Weiter mit `/30-write-spec`.
