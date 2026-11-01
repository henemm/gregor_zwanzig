---
entity_id: auth_haertung_python_2163
type: module
created: 2026-11-01
updated: 2026-11-01
status: draft
version: "1.0"
tags: [security, auth, python, epic-2138, issue-2163, scheibe-2, mandantentrennung, secrets]
workflow: fix-2163-auth-haertung-s1
---

# Auth-Härtung Python-Core (#2163, Scheibe 2 – letzte Scheibe)

> **Namenshinweis:** Der Workflow heißt aus der Intake-Bewertung heraus `fix-2163-auth-haertung-s1`. Inhaltlich ist dies **Scheibe 2** von #2163 (Scheibe 1 = Go, PR #2717; Scheibe 1b = Webhook-Secrets über die Config, #2715, PR #2719).

## Approval

- [ ] Approved

## Purpose

Der Python-Core baut Pfade unter `data/users/<user_id>/` künftig nur noch mit einer geprüften Kennung. Das ist die zweite Verteidigungslinie hinter der Go-Anmeldung und dem Core-Geheimnis (ADR-0062): Go lässt ungültige Kennungen nie durch, aber falls doch einmal eine ankommt (Fehler, neuer Eingang, Tippfehler), darf der Core damit keine fremden Dateien lesen oder schreiben. Zusätzlich wird die Secrets-Vorlage `.env.tpl` vervollständigt und durch einen Test davor geschützt, wieder unvollständig zu werden.

**Diese Scheibe schließt #2163.** Scheibe 1 hatte #2163 ausdrücklich „offen“ gelassen, weil genau diese beiden Punkte (Python-Pfadbauten, `.env.tpl`) fehlten. Mit dieser Scheibe ist die Issue-Checkliste vollständig abgearbeitet; `/70-deploy` schließt das Issue nach erfolgreichem Selftest (PR-Text „Refs #2163“, Close erst nach Selftest-Exit 0).

### Zuordnung Issue-Checkliste → Scheibe

| Punkt im Issue | Erledigt in |
|---|---|
| Enumeration 409 / Timing | Scheibe 1 (PR #2717): Timing angeglichen, 409 bewusst belassen (Spec `auth_haertung_go_2163.md`) |
| Webhook-Secret konstantzeitig | Scheibe 1 / #2159 |
| `Secure`-Flag am Cookie | Scheibe 1 |
| `os.Getenv` Telegram | Scheibe 1b (#2715, PR #2719) |
| `ProxyHandler` ohne `appendUserID` | Scheibe 1 |
| `scheduler.go` Log hartkodiert | Scheibe 1 |
| **Python-Pfadbauten ohne `VALID_USER_ID_RE`** | **diese Scheibe (AC-1 bis AC-12)** |
| **`.env.tpl` unvollständig** | **diese Scheibe (AC-13 bis AC-15)** |

## Source

- **File:** `src/app/loader.py`, `src/app/config.py`, `src/services/scheduler_dispatch_service.py`, `src/services/forecast_budget.py`, `src/services/alert_input_capture.py`, `api/routers/gpx.py`, `api/routers/briefings_send.py`, `api/main.py`, `.env.tpl`
- **Identifier:** `VALID_USER_ID_RE`, `get_data_dir`, `load_compare_presets`, `is_test_user_id`, `is_user_disabled`, `with_user_profile`, `send_compare_preset`, `_briefings_dir_for`, `load_trip`

> **Schicht-Hinweis:** ausschließlich Python-Core und die Vorlagedatei `.env.tpl`. Kein Go-Code, kein Frontend.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Es entsteht kein Pendant-Code. Der Helfer `user_dir` wird von Trip- und Vergleichs-Pfaden gemeinsam genutzt (`load_trip`, `load_compare_presets`, `_briefings_dir_for`); `send_briefing` bleibt der eine geteilte Eingang für beide Arten.
> - **Mandantentrennung (ADR-0003):** Kern des Auftrags. Zwei-Nutzer-Tests (Alice/Bob) gegen echte Dateien (AC-1 bis AC-8, AC-12). `user_id` kommt weiter nur aus dem Auth-Kontext (Go-Proxy), nie ein Fallback auf `"default"`.
> - **Kanäle:** Inhalt und Versand aller vier Kanäle sind nicht berührt; nur die Kennungsprüfung vor dem Dateizugriff ändert sich. Der Handversand (Trip und Ortsvergleich) muss für gültige Kennungen unverändert funktionieren (AC-12, AC-16).
> - **Mail-Renderer / Validatoren:** nicht berührt (keine Mail-Inhalts-Datei wird geändert), Renderer-Commit-Gate greift nicht.
> - **Persistenz (ADR-0031):** Ablageort `data/users/<user_id>/` unverändert; es gibt keine Schemaänderung und keine Migration.

## Abdeckung: alle Stellen mit `users`-Pfad

Quelle der Wahrheit für die `.match`-Stellen: `grep -rn "VALID_USER_ID_RE" src api` (Stand 2026-11-01). Die Spec nennt Funktionsnamen, die Zeilen sind Orientierung.

| Stelle (Funktion) | Herkunft der `user_id` | Entscheidung |
|---|---|---|
| `loader.load_compare_presets` (baut `data_root/users/<id>/briefings`, ca. Z. 342) | extern (Router → `send_compare_preset`) | `user_dir`, wirft `InvalidUserIdError` |
| `loader.load_trip` mit `data_dir` (ca. Z. 458; in Produktion kein Aufrufer, toter Zweig) | Parameter | `user_dir` |
| `loader.is_user_disabled` (ca. Z. 1385, Inbound-Leser) | Parameter | fail-soft bleibt: ungültig ⇒ `False`, keine Datei gelesen |
| `loader._briefings_dir_for` mit `data_dir` (ca. Z. 2004, **schreibt**, `mkdir`) | Parameter | `user_dir` |
| `loader.get_data_dir` (ca. Z. 1309–1323) | Parameter | delegiert an `user_dir(get_data_root(), …)` |
| `config.is_test_user_id` (ca. Z. 82; läuft **vor** `get_data_dir`) | Parameter | fail-soft bleibt: ungültig ⇒ `False`, keine Datei gelesen |
| `config.Settings.with_user_profile` (ca. Z. 400–430) | extern (Router, Inbound) | Kennung als **erste Handlung** prüfen, dann erst `_is_test_user` |
| `scheduler_dispatch_service._load_presets_for_dispatch` (Z. 65) | Parameter | `user_dir` |
| `scheduler_dispatch_service.save_compare_preset_status` / `save_compare_preset_pause` / `resume_compare_preset` (Z. 516/551/589, **schreiben**, Read-Modify-Write) | Parameter | `user_dir` (Kennungsprüfung vor der Entitäts-ID-Prüfung) |
| `scheduler_dispatch_service.send_compare_preset` (Z. 1064ff.) | extern (Router) | Kennung als **erste Handlung** vor dem ersten Dateizugriff prüfen |
| `forecast_budget` (ca. Z. 105), `alert_input_capture` (ca. Z. 109), `api/routers/gpx.py` (ca. Z. 33) | Parameter | `.match` ⇒ `is_valid_user_id` (fullmatch) |
| `i18n/lang.py` (Z. 41) | Parameter | prüft schon mit `fullmatch`, auf `is_valid_user_id` angleichen (verhaltensgleich) |
| `loader.lookup_user_by_email`, `lookup_user_by_telegram_chat_id`, `loader` Verzeichnis-Iteration (ca. Z. 1363), `channels/email.py` Profil-Sammler (ca. Z. 269/276) | Name stammt aus dem Verzeichnis, kein Eingang von außen | unverändert, hier dokumentiert |

**Alle Anwendungen von `VALID_USER_ID_RE`** (vollständig, aus dem grep): `loader.py` (Definition Z. 1294, `get_data_dir` Z. 1321), `forecast_budget.py` (Z. 104–105), `alert_input_capture.py` (Import Z. 30, Prüfung Z. 109), `i18n/lang.py` (Z. 39–41, `fullmatch`), `api/routers/gpx.py` (Import Z. 29, Prüfung Z. 33). Nach der Änderung wird `VALID_USER_ID_RE.match` nirgends mehr benutzt. Das **Muster-Literal `^[a-zA-Z0-9_-]+$` bleibt textuell unverändert**, weil `tests/unit/test_user_id_pattern_parity.py` es als Text gegen `internal/store/pathsafe.go` vergleicht; nur die Anwendung wechselt von `.match` auf `fullmatch`.

**Warum `fullmatch`:** Das `$` im Muster akzeptiert einen Zeilenumbruch am Ende. Damit galt `"alice\n"` in Python als gültig, in Go (`pathsafe.go`) nicht. Ein Pfad-Ausbruch ist damit nicht möglich, aber es ist eine Paritätslücke. Bestandsordner können keinen Zeilenumbruch tragen (Go legt sie an), das Risiko ist gering.

### Externe Eingänge (Kennung aus dem Request)

| Eingang | Aufrufer in der Kette | Festlegung |
|---|---|---|
| `POST /api/briefings/{id}/send` (`briefings_send.send_briefing_endpoint`) | Go-Proxy | `send_briefing` fängt `InvalidUserIdError` **zuerst**; Antwort 404 `not_found` (AC-9) |
| `POST /api/scheduler/trips/{id}/send`, `POST /api/scheduler/compare-presets/{id}/send` (`scheduler.py`, ca. Z. 311 und 322, Kennung aus der Query) | Delegation an `send_briefing` | erben AC-9 ohne eigenen Code (AC-10) |
| `GET /api/preview/{trip_id}/sms` (`preview._build_service` ⇒ `with_user_profile`) | Go-Proxy | zentraler Handler (unten) ⇒ 404 `not_found` (AC-11) |
| `POST /api/_internal/sms/verification-code` (`internal.py`, `with_user_profile(req.user_id)`) | Go-Prozess | zentraler Handler ⇒ 404 `not_found` (AC-11) |
| Scheduler-Auslöser mit `user_id` aus der Query (`/trip-reports`, `/alert-checks`, `/compare-alert-checks`, `/compare-presets` täglich, Radar), `notify.py`, `debug.py`, `compare.py`, `validator.py` | Go-Scheduler bzw. Go-Proxy | zentraler Handler ⇒ 404 `not_found`; vorher unbehandelte 500 (AC-11) |
| Inbound-Leser (E-Mail, Telegram, SMS, `trip_command_processor`) | Kennung kommt aus der Verzeichnis-Iteration bzw. dem Adress-/Chat-Treffer, nicht aus freier Eingabe | kein Handler nötig; `send_compare_preset`/`with_user_profile` lehnen trotzdem hart ab (AC-5, AC-6) |

**Fehlerbehandlung konkret:**

1. `src/app/loader.py` definiert `class InvalidUserIdError(ValueError)`. Sie erbt von `ValueError`, damit alle bestehenden `except ValueError` rückwärtskompatibel bleiben.
2. `api/routers/briefings_send.py`: In `_send_vergleich` steht `except InvalidUserIdError` **vor** `except InvalidPresetError` und vor `except ValueError` (beide Typen erben von `ValueError`; ohne die Reihenfolge würde die Kennung als „ungültiges Preset“ gemeldet und über `reason=str(e)` im Antworttext gespiegelt). In `_send_trip` wird `InvalidUserIdError` ebenfalls vor dem allgemeinen Pfad gefangen (heute würde `send_briefing` sie als 500 `send_failed` melden). Beide Zweige antworten `_error("not_found", …)` mit der **Entitäts-ID** als Wert, nie mit der Nutzerkennung.
3. `api/main.py` registriert **einen** zentralen `exception_handler(InvalidUserIdError)`: Status 404, Body `{"detail": "not_found", "code": "not_found"}`, ohne Kennung im Text, Log nur als Warnung ohne Traceback-Spam. Er deckt alle übrigen Router ab, die `with_user_profile` oder die Loader-Funktionen mit einer Kennung aus dem Request aufrufen.
4. Das Fehlerbild ist bewusst `not_found` und kein neuer Code `invalid_user_id`: Ein neuer Code bräuchte Vokabular in allen Sprachen und würde eine Existenz-Aussage machen; Go lässt ungültige Kennungen ohnehin nie durch. `api/routers/gpx.py` behält sein bestehendes 400 `invalid_user_id` (nicht Teil dieser Änderung außer dem Wechsel auf `fullmatch`).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/loader.py` | MODIFY | Neu: `InvalidUserIdError(ValueError)`, `is_valid_user_id(s)` (str + `fullmatch`), `user_dir(root, user_id)`. `get_data_dir` delegiert. `load_compare_presets`, `load_trip(data_dir=…)`, `is_user_disabled`, `_briefings_dir_for` über `user_dir`. Muster-Literal unverändert |
| `src/app/config.py` | MODIFY | `is_test_user_id` über `user_dir` (im `try`: ungültig ⇒ `False`). `with_user_profile` prüft die Kennung als erste Handlung |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `_load_presets_for_dispatch`, `save_compare_preset_status`, `save_compare_preset_pause`, `resume_compare_preset` über `user_dir`. `send_compare_preset` prüft vor dem ersten Dateizugriff |
| `src/services/forecast_budget.py`, `src/services/alert_input_capture.py`, `api/routers/gpx.py`, `src/i18n/lang.py` | MODIFY | `.match` bzw. `fullmatch` ⇒ `is_valid_user_id` |
| `api/routers/briefings_send.py` | MODIFY | `InvalidUserIdError` vor `InvalidPresetError`/`ValueError` ⇒ 404 `not_found` (Vergleich und Trip) |
| `api/main.py` | MODIFY | zentraler Handler für `InvalidUserIdError` ⇒ 404 `not_found` |
| `.env.tpl` | MODIFY | fehlende Secrets als Kommentarzeilen (siehe unten) |
| `docs/specs/modules/auth_haertung_go_2163.md` | MODIFY | Status `draft` ⇒ `implemented`; Known-Limitations-Satz „#2163 bleibt offen“ auf „geschlossen mit Scheibe 2 (`auth_haertung_python_2163.md`)“ aktualisieren |
| `tests/unit/test_user_dir_guard_zwei_nutzer.py` | CREATE | Zwei-Nutzer-Tests gegen echte Dateien in `tmp_path` (Pfadbauten) |
| `tests/unit/test_user_id_haertung_router.py` | CREATE | Router-Tests über echten FastAPI-`TestClient` (AC-9 bis AC-11) |
| `tests/unit/test_env_tpl_secret_drift.py` | CREATE | Drift-Ratsche, `# doc-compliance-test` |
| `tests/unit/test_user_id_pattern_parity.py` | MODIFY (falls nötig) | ergänzt um `"alice\n"`-Fall; Muster-Textvergleich bleibt grün |

## `.env.tpl`: endgültige Secret-Liste und Ratsche

**Befund:** Die Datei hat 7 Zeilen (`GZ_SMTP_*`, `GZ_MAIL_FROM`, `GZ_MAIL_TO`, `GZ_PO_EMAIL`). Nichts im Repo verarbeitet sie (kein `op inject`), die echten 1Password-Einträge sind unbekannt. Deshalb: **keine erfundenen `op://`-Pfade.** Fehlende Einträge kommen als Kommentarzeile `# NAME=  (1Password-Eintrag noch anzulegen)`. Die 7 vorhandenen Zeilen bleiben byte-gleich.

**Wie die Namen abgeleitet sind:** Go liest per `envconfig.Process("GZ", &cfg)` je Feld zuerst `GZ_<Tag>`, dann unpräfixiert `<Tag>` (envconfig-Standardverhalten, in Scheibe 1b für die Webhook-Namen genutzt; Prod/Staging setzen diese Webhook-Namen heute **unpräfixiert**). Python liest per `env_prefix="GZ_"` ausschließlich `GZ_<FELDNAME>` (kein Alias). Die Vorlage führt deshalb **einheitlich den `GZ_`-Namen**, der in beiden Welten funktioniert; zur Dokumentation steht hinter den fünf Webhook-Namen der Zusatz „(Go liest auch unpräfixiert)“. Die Namen stammen aus den Struct-Tags (`internal/config/config.go`) und den Feldnamen (`src/app/config.py`), nicht aus CamelCase-Raten.

| Env-Name in der Vorlage | Herkunft | Vorlage heute |
|---|---|---|
| `GZ_SESSION_SECRET` | Go `SessionSecret`, Tag `SESSION_SECRET` (Default `dev-secret-change-me`, in Produktion zwingend setzen) | fehlt ⇒ Kommentar |
| `GZ_CORE_SHARED_SECRET` | Go `CoreSharedSecret` (Tag `CORE_SHARED_SECRET`) und Python `core_shared_secret` (ADR-0062) | fehlt ⇒ Kommentar |
| `GZ_AUTH_PASS` | Go `AuthPass`, Tag `AUTH_PASS` | fehlt ⇒ Kommentar |
| `GZ_SMTP_PASS` | Go `SMTPPass` und Python `smtp_pass` | **vorhanden** (Wertzeile) |
| `GZ_GOOGLE_SMTP_PASS` | Go `GoogleSMTPPass` | fehlt ⇒ Kommentar |
| `GZ_FALLBACK_SMTP_PASS` | Go `FallbackSMTPPass` | fehlt ⇒ Kommentar |
| `GZ_GOOGLE_CLIENT_SECRET` | Go `GoogleClientSecret` | fehlt ⇒ Kommentar |
| `GZ_TELEGRAM_WEBHOOK_SECRET` | Go `TelegramWebhookSecret`, Tag `TELEGRAM_WEBHOOK_SECRET` (#2715) | fehlt ⇒ Kommentar |
| `GZ_SEVEN_WEBHOOK_PATH_SECRET` | Go `SevenWebhookPathSecret` (#2715) | fehlt ⇒ Kommentar |
| `GZ_SEVEN_WEBHOOK_SIGNING_KEY` | Go `SevenWebhookSigningKey` (#2715) | fehlt ⇒ Kommentar |
| `GZ_STALWART_WEBHOOK_PATH_SECRET` | Go `StalwartWebhookPathSecret` (#2715) | fehlt ⇒ Kommentar |
| `GZ_STALWART_WEBHOOK_SECRET` | Go `StalwartWebhookSecret` (#2715) | fehlt ⇒ Kommentar |
| `GZ_STATUS_TOKEN` | Go `StatusToken`, Tag `STATUS_TOKEN` (ADR-0079) | fehlt ⇒ Kommentar |
| `GZ_IMAP_PASS` | Python `imap_pass` | fehlt ⇒ Kommentar |
| `GZ_TEST_SMTP_PASS`, `GZ_TEST_IMAP_PASS` | Python `test_smtp_pass`, `test_imap_pass` | fehlen ⇒ Kommentare |
| `GZ_SEVEN_API_KEY`, `GZ_SEVEN_SANDBOX_KEY` | Python `seven_api_key`, `seven_sandbox_key` | fehlen ⇒ Kommentare |
| `GZ_TELEGRAM_BOT_TOKEN`, `GZ_TELEGRAM_TEST_BOT_TOKEN` | Python `telegram_bot_token`, `telegram_test_bot_token` | fehlen ⇒ Kommentare |
| `GZ_METEOFRANCE_APIKEY` | Python, direkt per `os.environ.get("GZ_METEOFRANCE_APIKEY")` (`providers/meteofrance.py`, `official_alerts/vigilance.py`, `official_alerts/meteo_forets.py`) | fehlt ⇒ Kommentar |

Das sind 20 Namen, davon 1 schon vorhanden (`GZ_SMTP_PASS`) und 19 neu als Kommentarzeilen. Nicht aufgenommen: `TELEGRAM_BOT_USERNAME` (öffentlicher Name, kein Geheimnis), `GZ_WEBAUTHN_*` (öffentliche Konfiguration), Sendernamen und Adressen.

**Drift-Ratsche (`tests/unit/test_env_tpl_secret_drift.py`, `# doc-compliance-test`).** Sie liest Quelltext als Daten und leitet die Soll-Liste selbst ab:

- **Go:** Jede Zeile in `internal/config/config.go` der Form `<Feld> <Typ> \`envconfig:"<TAG>" …\``; der Env-Name ist `GZ_` + `<TAG>` (Tag lesen, nicht CamelCase raten; ein Feld ohne `envconfig`-Tag wird nicht geraten, sondern lässt den Test mit klarer Meldung scheitern).
- **Python:** Jedes Feld von `Settings.model_fields`; der Env-Name ist `GZ_` + `FELDNAME.upper()` (`env_prefix`, kein Alias; die Ratsche prüft, dass kein Alias vorkommt).
- **Python direkt per `os.environ`:** jede Zeichenkette `os.environ.get("GZ_…")` bzw. `os.environ["GZ_…"]` unter `src/`.
- **Kriterium „Secret“:** Der Env-Name endet auf `_SECRET`, `_KEY`, `_PASS`, `_TOKEN` oder `_APIKEY`.
- **Soll:** Jeder so gefundene Name steht in `.env.tpl` entweder als Wertzeile (`NAME=`) oder als Kommentarzeile (`# NAME=`). Fehlt einer, nennt die Meldung den Namen und die Quelle.
- **Zusatzprüfungen:** Alle `op://`-Verweise der Datei stehen nur in den 7 ursprünglichen Wertzeilen (kein erfundener Pfad); jede neue Kommentarzeile trägt den Vermerk „1Password-Eintrag noch anzulegen“.

Wer künftig ein Secret-Feld ergänzt, ohne die Vorlage zu pflegen, bekommt einen roten Test.

## Estimated Scope

- Files: 9 Produktion/Vorlage + 1 Spec-Status, 3 neue Testdateien (+1 kleine Ergänzung)
- LoC: Produktion ca. +180/-40 (Obergrenze ≈ 250 geänderte Zeilen), Tests ca. +350 (Obergrenze ≈ 450 geänderte Zeilen)
- Effort: medium
- Risk: LOW–MEDIUM. `with_user_profile` wird sehr breit genutzt, sein Verhalten ändert sich aber ausschließlich für ungültige Kennungen.

**Abtrennregel (vorab festgelegt):** Überschreitet die Umsetzung das LoC-Budget, wird der Block `.env.tpl` + Drift-Ratsche (AC-13 bis AC-15) als eigene Teilscheibe abgetrennt und in einem Folge-Workflow geliefert; er ist vom Pfad-Härten unabhängig. Pfad-Härtung (AC-1 bis AC-12) wird dann trotzdem ausgeliefert. **#2163 bleibt in diesem Fall offen** und wird erst mit der abgetrennten Teilscheibe geschlossen (sonst: Close nach Selftest dieser Scheibe).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_root` | Funktion | Wurzel `_DATA_ROOT` > `GZ_DATA_DIR` > `data` |
| `app.loader.VALID_USER_ID_RE` | Konstante | Muster, textuell paritätsgeprüft gegen `internal/store/pathsafe.go` |
| `services.send_outcomes.InvalidPresetError` | Klasse | erbt von `ValueError`; Reihenfolge der `except`-Zweige beachten |
| `forecast_budget` (`user_root`-Prüfung) | Muster | Vorbild für `user_dir(root, user_id)` |
| ADR-0003 | ADR | Mandantentrennung, Zwei-Nutzer-Test, kein `"default"` |
| ADR-0031 | ADR | Ablage `data/users/<user_id>/` |
| ADR-0062 | ADR | Core-Geheimnis: erste Linie, diese Scheibe ist die zweite |
| `fix_2140_pfad_traversal_nutzer_kennung.md`, `fix_2140_entitaets_id_pfadsperre.md` | Spec | Vorläufer (Go-Seite bzw. Entitäts-IDs) |

## Implementation Details

- `is_valid_user_id(s)` gibt `True` nur für `str`, das `VALID_USER_ID_RE.fullmatch` besteht. Nicht-Strings und `"alice\n"` ⇒ `False`.
- `user_dir(root, user_id)` wirft `InvalidUserIdError(f"invalid user_id")` (ohne Kennung im Text, um Spiegelung zu vermeiden) bzw. liefert `Path(root) / "users" / user_id`.
- `get_data_dir(user_id)` = `user_dir(get_data_root(), user_id)`; die bisherige Meldung `invalid user_id` und der Typ `ValueError` bleiben (Unterklasse).
- `is_test_user_id` und `is_user_disabled` bleiben **fail-soft**: Ungültig ⇒ `False`, und es wird keine Datei gelesen. Die harte Ablehnung steckt in `with_user_profile` (erste Handlung, vor `_is_test_user`) und `send_compare_preset` (vor `load_compare_presets`). So wird eine Kennung nie „zuerst nachgesehen und dann abgelehnt“.
- Schreibpfade (`save_compare_preset_status`, `save_compare_preset_pause`, `resume_compare_preset`, `_briefings_dir_for`) prüfen die Kennung vor dem Pfadbau. Bei den drei Preset-Funktionen gilt die bestehende Fail-soft-Semantik (stilles Zurück statt neuer Fehlerausgang) weiter; die Prüfung darf einen Versandfehler nicht überdecken. `_briefings_dir_for` wirft (kein stiller `mkdir` unter fremdem Pfad).
- Die Mutationsprobe des Adversary arbeitet per String-Ersetzung mit externer Sicherung, nie per `git checkout/stash/reset`.

**RED-Befunde (2026-11-01, für `/50-implement` und Adversary):**
- `_load_presets_for_dispatch` muss bei ungültiger Kennung künftig `InvalidUserIdError` werfen (der AC-1-Test verlangt das; bisher fail-soft `None`). Aufrufer `dispatch_orchestrator.collect_due` hat kein eigenes try/except. Das Risiko ist gering, weil ein ungültig benannter Ordner heute schon bei `load_all_locations` über `get_data_dir` abbricht. Trotzdem prüfen, dass die Verzeichnis-Iteration nur gültige Namen weiterreicht oder der Fehler je Nutzer isoliert wird.
- Drei Kopfprüfungen sind nach dem Fix durch die tieferen Prüfungen beobachtbar verdeckt, Mutationen dort sind ohne Wirkung und **kein Testloch**:
  - `with_user_profile`: `is_test_user_id` liest nichts mehr, `get_data_dir` wirft ohnehin.
  - `send_compare_preset`: `load_compare_presets` wirft vor jedem Lesen und vor der Sperre.
  - `_load_presets_for_dispatch`: `exists()` ist nur ein stat, danach wirft der Loader.
- Der Nachweis „Datei nicht geöffnet" (AC-2/3/5/6) läuft über `sys.addaudithook` (Ereignis `open`) statt über eine Datei mit Rechten 000. Das ist ein stärkerer Nachweis.
- Bei AC-6 wird die Sende-Sperre im Test vorab belegt (Netzsicherung). Der heutige Pfad endet dort mit `already_in_progress`.
- Router-Tests: `tests/conftest.py` setzt das Core-Geheimnis. Die Netzsperre läuft über `pytest_socket.disable_socket(allow_unix_socket=True)` in der Fixture, weil `mark.disable_socket` den TestClient-Event-Loop bricht.

## Expected Behavior

- **Input:** Aufrufe mit ungültiger Kennung (`../users/bob`, `alice/../bob`, `"alice\n"`, leer, Nicht-String) an Loader, Config und Router; Aufrufe mit gültiger Kennung wie bisher.
- **Output:** ungültig ⇒ `InvalidUserIdError` (harte Pfade) bzw. `False` (fail-soft-Leser) bzw. 404 `not_found` am Router; gültig ⇒ unverändert.
- **Side effects:** Bei ungültiger Kennung wird keine Datei gelesen, geschrieben oder angelegt (kein neues Verzeichnis). Die Kennung steht nie im Antworttext.

## Test Plan

Kern-Schicht (deterministisch, ohne Netz). **Kein Mock-Theater** (kein `Mock`, `patch`, `MagicMock`); echte Dateien in `tmp_path`, Router über echten FastAPI-`TestClient`. Nur die Ratsche ist `# doc-compliance-test`.

**Angriffskennung (Pflicht, Advisor-Befund):** `../users/bob` bzw. `alice/../bob`. **Nicht** `../bob`: `users/../bob` zeigt auf `root/bob`, das Verzeichnis existiert nicht, der Test wäre schon heute grün und damit blind.

**Testdaten:** Bob bekommt echte Dateien: ein Vergleichs-Preset unter `users/bob/briefings/` und eine `user.json` mit `is_test_user: true` und `disabled: true`. Alice bekommt eigene, andere Daten.

### Automated Tests (TDD RED)

- [ ] `load_compare_presets("../users/bob", root)` liefert heute Bobs Preset (rot); danach `InvalidUserIdError` (AC-1)
- [ ] `is_test_user_id("../users/bob", root)` liefert heute `True` (rot); danach `False` (AC-2). `is_user_disabled` analog (AC-3)
- [ ] Schreibpfade: Aufruf mit Angriffskennung, danach ist Bobs Datei **byte-gleich**, es gibt kein neues Verzeichnis (AC-4)
- [ ] `with_user_profile` und `send_compare_preset` mit Angriffskennung: `InvalidUserIdError`, vorher keine Dateizugriffe (AC-5, AC-6)
- [ ] `"alice\n"` wird überall abgelehnt (heute angenommen) (AC-7)
- [ ] Zwei-Nutzer-Gegenprobe: Alice mit gültiger Kennung liest weiter nur ihre eigenen Daten, nie Bobs (AC-8)
- [ ] Router über `TestClient`: `POST /api/briefings/<id>/send?kind=vergleich&user_id=../users/bob` ⇒ 404 `not_found`, Antworttext enthält `bob` und `users` nicht (AC-9); Trip-Zweig und die beiden `scheduler.py`-Routen ebenso (AC-10); Preview, interne SMS-Route und ein Scheduler-Auslöser ⇒ 404 `not_found` statt 500 (AC-11)
- [ ] Paritätstest bleibt grün, Muster-Literal unverändert (AC-12)
- [ ] Ratsche `.env.tpl` (AC-13 bis AC-15), mit Gegenprobe: Ein künftig zusätzlich in der Go-Config angelegtes Secret-Feld lässt den Test rot werden (Test erzeugt dazu eine Kopie der Quelle in `tmp_path`)

### Staging-Nachweis (AC-16)

Go lässt ungültige Kennungen nie durch, deshalb gibt es auf Staging **keinen Angriffsversuch**. Der Nachweis ist ein Regressionsnachweis: Nach dem Push gegen `https://staging.gregor20.henemm.com` funktionieren für einen echten Testnutzer der Handversand eines Trip-Briefings und eines Ortsvergleichs weiter (Mail kommt im Stalwart-Test-Postfach an), Health und Login sind in Ordnung.

## Acceptance Criteria

**Pfadbauten mit eigener Wurzel (Mandantentrennung)**

- **AC-1:** Given Bob hat ein Vergleichs-Preset unter `users/bob/briefings/` / When `load_compare_presets` mit der Kennung `../users/bob` oder `alice/../bob` aufgerufen wird / Then wirft sie `InvalidUserIdError` und liefert keines von Bobs Presets.
  - Test: echte Dateien in `tmp_path`; vor der Änderung liefert der Aufruf Bobs Preset (rot).
- **AC-2:** Given Bob hat eine `user.json` mit `is_test_user: true` / When `is_test_user_id` mit `../users/bob` aufgerufen wird / Then ist das Ergebnis `False`, und Bobs `user.json` wird nicht gelesen.
  - Test: Aufruf mit Angriffskennung; vor der Änderung `True` (rot). Dazu der Nachweis, dass keine Datei geöffnet wurde (Datei in `tmp_path` mit Rechten 000 ändert das Ergebnis nicht).
- **AC-3:** Given Bob hat eine `user.json` mit `disabled: true` / When `is_user_disabled` mit der Angriffskennung aufgerufen wird / Then ist das Ergebnis `False` (fail-soft bleibt) und Bobs Datei wird nicht gelesen.
  - Test: wie AC-2; Gegenprobe: `is_user_disabled("bob", root)` liefert `True`.
- **AC-4:** Given Bobs Preset-Datei und Bobs `user.json` liegen in `tmp_path` / When `save_compare_preset_status`, `save_compare_preset_pause`, `resume_compare_preset` oder `_briefings_dir_for` mit der Angriffskennung aufgerufen werden / Then bleibt Bobs Datei byte-gleich, es entsteht kein neues Verzeichnis, und ein Fehler beim Vermerk-Schreiben überdeckt keinen Versandfehler.
  - Test: Hash der Dateien und Verzeichnisliste von `tmp_path` vor und nach dem Aufruf sind gleich; `_briefings_dir_for` wirft `InvalidUserIdError`.
- **AC-5:** Given eine ungültige Kennung / When `Settings().with_user_profile(<ungültig>)` aufgerufen wird / Then wirft es `InvalidUserIdError` als erste Handlung, bevor `_is_test_user` oder `get_data_dir` etwas lesen.
  - Test: Bobs `user.json` mit `is_test_user: true`; Angriffskennung wirft, ohne dass Bobs Datei in das Ergebnis eingeht.
- **AC-6:** Given eine ungültige Kennung / When `send_compare_preset(<ungültig>, preset_id)` aufgerufen wird / Then wirft es `InvalidUserIdError`, bevor eine Datei gelesen wird und bevor der Sende-Sperre-Schlüssel gebildet wird.
  - Test: Bobs Preset existiert; Aufruf wirft; kein Versandversuch.
- **AC-7:** Given die Kennung `"alice\n"` (Zeilenumbruch am Ende) / When sie an `is_valid_user_id`, `get_data_dir`, `user_dir`, die `forecast_budget`-Prüfung, die `alert_input_capture`-Prüfung oder den GPX-Endpoint geht / Then wird sie überall abgelehnt, genau wie in Go.
  - Test: parametrisiert über alle Anwendungsstellen aus der Abdeckungstabelle; vor der Änderung nehmen `get_data_dir`, `forecast_budget`, `alert_input_capture` und GPX sie an (rot). `i18n/lang.py` lehnt schon heute ab (bleibt so).
- **AC-8:** Given Alice und Bob haben je eigene Presets, Trips und Profile / When Alice mit ihrer gültigen Kennung `load_compare_presets`, `load_trip`, `is_test_user_id` und `with_user_profile` benutzt / Then bekommt sie ausschließlich ihre eigenen Daten, nie Bobs, und alle bestehenden Aufrufe mit gültiger Kennung verhalten sich unverändert.
  - Test: Zwei-Nutzer-Test mit gültigen Kennungen `alice` und `bob`; Ergebnisse enthalten nur die jeweils eigenen Daten.

**Externe Eingänge (Fehlerbild)**

- **AC-9:** Given ein Handversand für einen Ortsvergleich oder Trip mit einer ungültigen Kennung in der Query (`../users/bob`) / When der Endpoint `POST /api/briefings/{id}/send` aufgerufen wird / Then antwortet er 404 mit dem Code `not_found`, die Kennung steht nicht im Antworttext, und es gibt weder 500 noch `invalid_preset` noch `send_failed`.
  - Test: `TestClient` gegen die echte App; Antworttext enthält weder `bob` noch `users` noch die Kennung. In `_send_vergleich` steht `except InvalidUserIdError` vor `InvalidPresetError` und `ValueError`.
- **AC-10:** Given die Alt-Routen `POST /api/scheduler/trips/{id}/send` und `POST /api/scheduler/compare-presets/{id}/send` mit ungültiger Kennung in der Query / When sie aufgerufen werden / Then antworten sie genau wie der neue Endpoint mit 404 `not_found` ohne Kennung im Text.
  - Test: `TestClient`, beide Routen; Antwort gleicht der von AC-9 (Status, Code).
- **AC-11:** Given ein Router, der die Kennung aus dem Request an `with_user_profile` oder die Loader gibt (Vorschau `GET /api/preview/{trip_id}/sms`, `POST /api/_internal/sms/verification-code`, die Scheduler-Auslöser mit `user_id` in der Query) / When die Kennung ungültig ist / Then antwortet der zentrale Handler in `api/main.py` mit 404 `not_found` ohne Kennung im Text, statt mit einer unbehandelten 500.
  - Test: `TestClient`, je ein Aufruf pro genannter Gruppe; bestehendes 400 `invalid_user_id` am GPX-Endpoint bleibt unverändert.
- **AC-12:** Given der Paritätstest gegen `internal/store/pathsafe.go` / When er nach der Änderung läuft / Then ist er grün, weil das Muster-Literal `^[a-zA-Z0-9_-]+$` textuell unverändert bleibt, und `VALID_USER_ID_RE.match` kommt im Code nirgends mehr vor.
  - Test: `tests/unit/test_user_id_pattern_parity.py` unverändert grün; ein Strukturtest bestätigt per Quelltext-Suche, dass `VALID_USER_ID_RE.match(` nicht mehr vorkommt (`# doc-compliance-test`).

**`.env.tpl` und Drift-Ratsche**

- **AC-13:** Given die Liste der Secrets aus Go-Config (Struct-Tags), Python-Settings (Feldnamen) und `os.environ`-Zugriffen unter `src/` / When die Ratsche `tests/unit/test_env_tpl_secret_drift.py` läuft / Then steht jeder Name, der auf `_SECRET`, `_KEY`, `_PASS`, `_TOKEN` oder `_APIKEY` endet, in `.env.tpl` (als Wertzeile oder als Kommentarzeile), und der Test ist grün.
  - Test: `# doc-compliance-test`; Soll-Liste ist die Tabelle „endgültige Secret-Liste“ (21 Namen).
- **AC-14:** Given ein neues Secret-Feld wird künftig in der Go-Config oder den Python-Settings ergänzt, ohne `.env.tpl` zu pflegen / When die Ratsche läuft / Then wird sie rot und nennt den fehlenden Namen samt Quelle.
  - Test: Gegenprobe in `tmp_path` mit einer Kopie von `config.go` plus einem zusätzlichen `envconfig:"NEUES_GEHEIMNIS_KEY"`-Feld; die Ratsche scheitert mit dem Namen `GZ_NEUES_GEHEIMNIS_KEY`.
- **AC-15:** Given die 1Password-Einträge sind nicht bekannt / When `.env.tpl` ergänzt wird / Then bleiben die 7 vorhandenen Wertzeilen byte-gleich, alle neuen Einträge sind Kommentarzeilen mit dem Vermerk „1Password-Eintrag noch anzulegen“, und es steht kein neuer `op://`-Pfad in der Datei.
  - Test: Die Ratsche vergleicht die Wertzeilen mit den 7 ursprünglichen und zählt `op://`-Vorkommen (nur in diesen 7).

**Nachweis auf Staging**

- **AC-16:** Given die Änderung ist auf Staging ausgerollt / When für einen echten Testnutzer ein Trip-Briefing und ein Ortsvergleich von Hand versendet werden und Health sowie Login geprüft werden / Then kommen beide Mails im Stalwart-Test-Postfach an, und Health und Login funktionieren wie vorher.
  - Test: `/e2e-verify` gegen `https://staging.gregor20.henemm.com` mit Staging-`.env`; kein Angriffsversuch (Go lässt ungültige Kennungen nie durch), Mail-Zustellung und Status werden protokolliert.

## Known Limitations

- Die Prüfung ist **Verteidigung in der Tiefe**: Alle Stellen liegen hinter Go-Auth und Core-Geheimnis (ADR-0062), die praktische Ausnutzbarkeit war schon vorher niedrig.
- Inbound-Leser und Verzeichnis-Iterationen (`lookup_user_by_email`, `lookup_user_by_telegram_chat_id`, Profil-Sammler in `channels/email.py`) bekommen ihre Kennungen aus dem Dateisystem, nicht aus freier Eingabe; sie bleiben bewusst ohne eigenen Handler.
- Es gibt keinen neuen Fehlercode `invalid_user_id`; ungültige Kennungen erscheinen als `not_found` (siehe Fehlerbehandlung, Punkt 4).
- Die Vorlage `.env.tpl` bleibt eine Dokumentationsvorlage ohne Einspielwerkzeug; die echten 1Password-Einträge für die 20 neuen Namen sind weiterhin anzulegen (kein Teil dieser Scheibe).
- Die Registrierung verrät weiter vergebene Namen (409), bewusst belassen laut Scheibe 1 (#2147 B1).
- **Nebenbefund (Triage #1199, nicht in dieser Scheibe gebaut):** `.env.example` nutzt `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_TO` **ohne** `GZ_`-Präfix. Gelesen werden aber `GZ_SMTP_*` (Go `envconfig.Process("GZ")`, Python `env_prefix="GZ_"`); die Beispieldatei ist veraltet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; bestätigt ADR-0003 (Mandantentrennung), ADR-0031 (Ablage `data/users`) und ADR-0062 (Core-Geheimnis als erste Linie)
- **Rationale:** Reine Härtung innerhalb bestehender Entscheidungen. Verworfen: Muster auf `\Z` ändern (bräche den textuellen Go-Paritätstest); neuer Fehlercode `invalid_user_id` (Vokabular in allen Sprachen, Existenz-Aussage); nur die drei im Issue genannten Stellen fixen (Zeilennummern im Issue veraltet, bei Teilabdeckung bliebe ein Schreibpfad fail-open).

## Changelog

- 2026-11-01: Initial spec created (Scheibe 2 von #2163, schließt das Issue). Abweichungen von der Analyse: zentraler Exception-Handler in `api/main.py` zusätzlich zur Behandlung in `briefings_send.py`; `.env.tpl`-Liste aus den tatsächlichen Quellen auf 21 Namen erweitert (Zählung in RED von 20 auf 21 korrigiert, Liste selbst unverändert); `i18n/lang.py` und `api/routers/gpx.py` in die Umstellung aufgenommen.
