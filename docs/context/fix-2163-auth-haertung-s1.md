# Context: fix-2163-auth-haertung-s1

> **Namenshinweis:** Der Workflow heißt aus der Intake-Bewertung heraus „s1". Inhaltlich ist er **Scheibe 2** von #2163.
> Scheibe 1 (Go, PR #2717) und Scheibe 1b (#2715, Webhook-Secrets über `config.Config`, PR #2719) sind gemergt
> (`git log --grep=2163`: e6965e21e, 108ec73da, 3c386ae8e). Die Spec dazu: `docs/specs/modules/auth_haertung_go_2163.md`.
> Sie steht noch auf `status: draft`, obwohl die Scheibe gemergt ist (Nebenbefund). Laut Spec Z. 27 und Known Limitations gehören zu Scheibe 2
> „Python-Pfadbauten ohne `VALID_USER_ID_RE`, `.env.tpl`".

## Request Summary
Die offenen Restpunkte von #2163 schließen: Der Python-Core baut Pfade unter `data/users/<user_id>/` nur noch mit geprüfter
Kennung (zweite Verteidigungslinie hinter Go-Auth und Core-Geheimnis, ADR-0062). Außerdem die Lücke in der Secrets-Vorlage `.env.tpl`.

## Stand Go-Seite (erledigt, kein Bau)
- Login/Forgot: Dummy-Hash und Timing-Angleichung (`internal/handler/auth.go:29-57, 347-404, 502-623`), Tests `auth_timing_test.go`, `auth_dummy_hash_test.go`.
- Die 409 bei der Registrierung bleibt bewusst stehen (Spec-Abschnitt „Bewusst nicht geändert", #2147 B1, Rate-Limit 5/h). **Nicht neu aufrollen.**
- Webhook-Secret konstantzeitig (#2159), `Secure`-Flag (`middleware/auth.go:156`), In-Memory-Wachstum, Proxy-`user_id`-Strip, Scheduler-Log: erledigt.
- Magic-Link ohne Enumeration (`auth_magic.go:76-140`).

## Related Files (Python, Scheibe 2)
Zentrale Prüfung: `src/app/loader.py:1294` `VALID_USER_ID_RE = ^[a-zA-Z0-9_-]+$`; `get_data_dir` (1309-1323) wirft `ValueError("invalid user_id")`, nimmt aber nur die globale Wurzel. Es gibt keinen Helfer für Aufrufe mit eigenem `data_root`/`data_dir`.

| Stelle | Funktion | ID vorher geprüft? | Mit fremder ID erreichbar (hinter Go + Geheimnis) |
|---|---|---|---|
| `src/app/loader.py:342` | `load_compare_presets` | **nein** auf dem Pfad `send_compare_preset` (`scheduler_dispatch_service.py:1093` liest vor `with_user_profile` 1107; Eingang `api/routers/briefings_send.py:63`, `api/routers/scheduler.py:322` Query) | ja, nur lesend (exists/glob) |
| `src/app/config.py:82` | `is_test_user_id` | **nein**: `with_user_profile._is_test_user` (`config.py:414`) läuft **vor** `get_data_dir` (422) | ja, nur lesend (`user.json`) |
| `src/app/loader.py:458` | `load_trip(data_dir=…)` | in Produktion kein Aufrufer mit `data_dir` | nein (toter Zweig) |
| `src/app/loader.py:2004` | `_briefings_dir_for(data_dir≠None)` | nur in Tests erreichbar; **schreibt mit mkdir** | nein |
| `src/app/loader.py:1385, 1423, 1482` | `is_user_disabled`, `lookup_user_by_email`, `lookup_user_by_telegram_chat_id` | implizit (ID aus Verzeichnis-Iteration) | nein |
| `src/services/scheduler_dispatch_service.py:65, 516, 551, 589` | Preset-Laden/-Status/-Pause/-Resume (516/551/589 **schreiben**, RMW) | indirekt über `with_user_profile` bzw. Inbound-Suche | nein |
| `src/output/channels/email.py:276` | Profil-Sammler | implizit (Iteration) | nein |
| `src/services/forecast_budget.py:105`, `src/i18n/lang.py:41` | prüfen selbst | ja | – |

**Randbefund `.match` und `fullmatch`:** `get_data_dir` (1321), `forecast_budget.py:105` und `alert_input_capture.py:109` prüfen mit `.match` und `$`. Damit gilt `"alice\n"` als gültig, mit `fullmatch` wäre es ungültig. Ein Pfad-Ausbruch ist damit nicht möglich (es entsteht kein Trenner), aber Go (`internal/store/pathsafe.go:20`) lehnt die Kennung ab, Python nimmt sie an: eine Paritätslücke. `src/i18n/lang.py:41` nutzt schon `fullmatch`.

`.env.tpl` (7 Zeilen, 1Password-Referenzen): enthält nur `GZ_SMTP_*`, `GZ_MAIL_FROM`, `GZ_MAIL_TO`, `GZ_PO_EMAIL`. Es fehlen `SESSION_SECRET`, `GZ_SEVEN_API_KEY`, die Telegram-Token, das Core-Geheimnis (ADR-0062) und die Webhook-Secrets. Wie die Vorlage befüllt wird, ist in keinem Repo-Doc beschrieben. Die 1Password-Item-Namen sind unbekannt und dürfen nicht erfunden werden.

## Existing Patterns
- Eigenprüfung mit eigener Wurzel: `forecast_budget.py:103-107`. Das ist das Vorbild für einen Helfer `user_dir(root, user_id)`.
- `VALID_ENTITY_ID_RE` für Preset-/Trip-IDs (`scheduler_dispatch_service.py:513`, Spec `fix_2140_entitaets_id_pfadsperre.md`).
- Python/Go-Paritätstest: `tests/unit/test_user_id_pattern_parity.py`.

## Dependencies
- Upstream: `get_data_root()` (`_DATA_ROOT` > `GZ_DATA_DIR` > `data`), `VALID_USER_ID_RE`.
- Downstream: Router `briefings_send`, `scheduler`, `internal`; Dispatch-Orchestrator; Inbound-Leser (E-Mail/Telegram/SMS); `trip_command_processor`; `with_user_profile` (sehr breit genutzt).

## Existing Specs / ADRs
- `docs/specs/modules/auth_haertung_go_2163.md`: Scheibe 1 (Go), definiert den Umfang von Scheibe 2.
- `docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md`, `fix_2140_entitaets_id_pfadsperre.md`
- ADR-0003 (Mandantentrennung), ADR-0062 (Core-Geheimnis), ADR-0031 (Ablage `data/users`)

## Existing Tests
`tests/unit/test_user_data_dir_isolation.py`, `tests/unit/test_user_id_pattern_parity.py`, `tests/unit/test_entity_id_path_guard.py`, `tests/tdd/test_gpx_upload_user_isolation.py`, `tests/test_user_language_resolution.py`, `tests/test_loader_requires_user_id.py`. **Kein** Test für die Stellen der Tabelle mit ungültiger `user_id`.

## Risks & Considerations
- `with_user_profile` ist zentral: Wird die Prüfung dort vorgezogen (vor `_is_test_user`), wirft der Dienst für ungültige IDs früher. Fehlerbild prüfen (500 statt 4xx?). Das Fehlerverhalten des Routers muss gleich bleiben oder besser werden.
- Wechsel `.match` → `fullmatch`: Es ändert sich nur der Fall mit `\n` am Ende. Bestandsordner können keinen Zeilenumbruch im Namen tragen (Go legt sie an). Risiko gering, Paritätstest spiegeln.
- Die Schreibpfade (516/551/589, 2004) bekommen dieselbe Prüfung, damit keiner fail-open bleibt. Die Fail-soft-Semantik (Vermerk-Schreiben) darf einen Versandfehler nicht überdecken.
- Tests: kein Mock-Theater. Zwei-Nutzer-Test (alice/bob plus `../bob`) gegen echte Dateien in `tmp_path`.
- `.env.tpl`: keine erfundenen 1Password-Pfade. In der Analyse entscheiden: Platzhalter mit Kommentar oder als offener Punkt dokumentieren.
- Der Inhalt ist nicht mail-relevant: Das Renderer-Gate und die Mail-Validatoren sind nicht berührt.

## Analysis

### Type
Bugfix (Sicherheits-Härtung, zweite Verteidigungslinie). Letzte Scheibe von #2163.

### Zuordnung Issue-Checkliste → Scheibe
| Punkt im Issue | Erledigt in |
|---|---|
| Enumeration 409 / Timing | Scheibe 1 (PR #2717): Timing angeglichen, 409 bewusst belassen (Spec `auth_haertung_go_2163.md`) |
| Webhook-Secret konstantzeitig | Scheibe 1 / #2159 |
| `Secure`-Flag | Scheibe 1 |
| `os.Getenv` Telegram | Scheibe 1b (#2715, PR #2719) |
| `ProxyHandler` ohne `appendUserID` | Scheibe 1 |
| `scheduler.go` Log hartkodiert | Scheibe 1 |
| **Python-Pfadbauten ohne `VALID_USER_ID_RE`** | **diese Scheibe** |
| **`.env.tpl` unvollständig** | **diese Scheibe** |

Nach dieser Scheibe kann `/70-deploy` #2163 schließen (PR-Text „Refs #2163", Close erst nach Selftest).

### Vollständige Abdeckung
Breite Suche `grep -rn '"users"' src api`, dazu f-Strings `users/{` und `os.path.join`: Die beiden letzten treffen nur Docstrings.

| Stelle | Herkunft `user_id` | Entscheidung |
|---|---|---|
| `loader.py:342` `load_compare_presets` | extern (Router → `send_compare_preset`) | **Helfer** |
| `loader.py:458` `load_trip(data_dir=…)` | Parameter | **Helfer** |
| `loader.py:1385` `is_user_disabled` | Parameter (Inbound-Leser) | **Helfer** (fail-soft bleibt: ungültig ⇒ `False`, keine Datei gelesen) |
| `loader.py:2004` `_briefings_dir_for` (schreibt, mkdir) | Parameter | **Helfer** |
| `config.py:82` `is_test_user_id` | Parameter, läuft vor `get_data_dir` | **Helfer** (im `try`: ungültig ⇒ `False`, nichts gelesen) |
| `scheduler_dispatch_service.py:65, 516, 551, 589` (516/551/589 schreiben) | Parameter | **Helfer** |
| `loader.py:1323` `get_data_dir` | – | nutzt künftig den Helfer |
| `i18n/lang.py:44` | prüft selbst mit `fullmatch` | unverändert |
| `forecast_budget.py:93/105` | prüft selbst | auf `is_valid_user_id` (fullmatch) umstellen |
| `loader.py:1363, 1423, 1482`, `email.py:269` | Verzeichnis-Iteration (kein Eingang von außen) | unverändert, dokumentiert |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/loader.py` | MODIFY | Neue Helfer `is_valid_user_id(s)` (str + `fullmatch`) und `user_dir(root, user_id)` (wirft `InvalidUserIdError`, Unterklasse von `ValueError`). `get_data_dir` delegiert. Stellen 342/458/1385/2004 auf `user_dir` |
| `src/app/config.py` | MODIFY | `is_test_user_id` über `user_dir`. `with_user_profile` prüft die Kennung als erste Handlung |
| `src/services/scheduler_dispatch_service.py` | MODIFY | 65/516/551/589 auf `user_dir`. `send_compare_preset` prüft die Kennung vor dem ersten Dateizugriff |
| `src/services/forecast_budget.py`, `src/services/alert_input_capture.py`, `api/routers/gpx.py` | MODIFY | `.match` → `is_valid_user_id` (fullmatch), schließt die Paritätslücke `"alice\n"` |
| `api/routers/briefings_send.py` | MODIFY | `InvalidUserIdError` **vor** den Zweigen `InvalidPresetError`/`ValueError` fangen (beide erben von `ValueError`) ⇒ `not_found` (404), Kennung nicht im Antworttext. Trip-Zweig gleich behandeln |
| `.env.tpl` | MODIFY | fehlende Secrets als Kommentarzeilen ergänzen, kein erfundener `op://`-Pfad |
| `tests/unit/test_user_dir_guard_zwei_nutzer.py` | CREATE | Zwei-Nutzer-Tests gegen echte Dateien in `tmp_path` |
| `tests/unit/test_env_tpl_secret_drift.py` | CREATE | Drift-Ratsche (`# doc-compliance-test`): Jedes Secret-Feld der Go-Config (`*SECRET*`, `*_KEY`, `*PASS`, `*TOKEN`) steht in `.env.tpl` (als Wert oder Kommentar) |
| `docs/specs/modules/auth_haertung_go_2163.md` | MODIFY | Status `draft` → `implemented` (Nebenbefund) |

### Scope Assessment
- Files: ~11 (6 Quellcode, 1 Vorlage, 2 neue Tests, 1 Spec-Status)
- Estimated LoC: +~180 / -~25 (davon ~120 Tests)
- Risk Level: LOW–MEDIUM. `with_user_profile` wird sehr breit genutzt, das Verhalten ändert sich aber nur für ungültige Kennungen.

### Technical Approach
1. **Ein Helfer für alle Pfadbauten mit eigener Wurzel** (`user_dir(root, user_id)`), Vorbild `forecast_budget.py:103-107`. Die Prüfung läuft per `fullmatch`. Das **Muster-Literal bleibt unverändert**, weil `tests/unit/test_user_id_pattern_parity.py` den Text mit Go `internal/store/pathsafe.go` vergleicht. Nur die Anwendung wechselt von `.match` auf `fullmatch`.
2. **Fehlertyp `InvalidUserIdError(ValueError)`**: rückwärtskompatibel zu allen bestehenden `except ValueError`, aber gezielt fangbar. So meldet der Router eine ungültige Kennung nicht mehr als „ungültiges Preset" und spiegelt sie nicht im Text (heute `reason=str(e)`).
3. **Fail-soft-Leser** (`is_test_user_id`, `is_user_disabled`) bleiben fail-soft (ungültig ⇒ `False`), lesen aber keine Datei außerhalb des eigenen Ordners mehr. Die harte Ablehnung erfolgt in `with_user_profile` (erste Zeile) bzw. in `send_compare_preset` (vor dem Laden).
4. **Fehlervertrag:** Eine ungültige Kennung beim Handversand ergibt 404 `not_found` (wie „nicht gefunden"). Das ist keine Existenz-Aussage und braucht kein neues Fehlervokabular. Heute ergibt sie beim Ortsvergleich 4xx `invalid_preset` mit gespiegelter Kennung, beim Trip 500 `send_failed`.
5. **`.env.tpl`**: Nichts im Repo und nichts in `henemm-infra` verarbeitet die Datei (kein `op inject`), letzte Änderung 2026-07-07 (#1071). Die echten 1Password-Pfade sind unbekannt und werden **nicht erfunden**. Deshalb kommen die fehlenden Schlüssel als Kommentarzeilen mit dem Vermerk „1Password-Eintrag noch anzulegen" hinein, das stört ein späteres `op inject` nicht:
   - Kandidaten: `GZ_SESSION_SECRET`, `GZ_CORE_SHARED_SECRET`, `GZ_SEVEN_API_KEY`, `GZ_SEVEN_SANDBOX_KEY`, `GZ_TELEGRAM_BOT_TOKEN`, `GZ_TELEGRAM_TEST_BOT_TOKEN`, `GZ_TELEGRAM_WEBHOOK_SECRET`, `GZ_SEVEN_WEBHOOK_PATH_SECRET`, `GZ_SEVEN_WEBHOOK_SIGNING_KEY`, `GZ_STALWART_WEBHOOK_PATH_SECRET`, `GZ_STALWART_WEBHOOK_SECRET`, `GZ_STATUS_TOKEN`.
   - Die endgültige Liste legt die Spec gegen `internal/config/config.go` (Präfix `GZ` via `envconfig.Process`) und `src/app/config.py` (`env_prefix="GZ_"`) fest.
   - Eine Drift-Ratsche verhindert, dass neue Secrets wieder fehlen.

### Test-Design (Pflicht für RED, Advisor-Befund)
- Die **Angriffskennung muss wirken**: `../users/bob` bzw. `alice/../bob`. **Nicht** `../bob`, denn `users/../bob` zeigt auf `root/bob`. Das Verzeichnis existiert nicht, der Test wäre schon heute grün und damit blind.
- Bob bekommt **echte Daten** in `tmp_path`: ein Vergleichs-Preset unter `users/bob/briefings/`, dazu `user.json` mit `is_test_user: true` und `disabled: true`.
- RED heute: `load_compare_presets("../users/bob", root)` liefert Bobs Preset, `is_test_user_id("../users/bob", root)` liefert `True`. Nach dem Fix: `InvalidUserIdError` bzw. `False`.
- Schreibpfade (516/551/589, `_briefings_dir_for`): Nach einem Aufruf mit der Angriffskennung ist Bobs Datei byte-gleich, und es gibt kein neues Verzeichnis.
- `"alice\n"` wird abgelehnt (heute angenommen).
- Router: `send_briefing("vergleich", …, user_id="../users/bob")` ergibt 404 `not_found`, der Antworttext enthält die Kennung nicht.
- Gegenprobe: Alice mit gültiger Kennung liest weiter nur ihre eigenen Daten.

### Befunde gegen den Plan
Keine, die den Ansatz kippen. Abgewogen:
- „Nur die drei Stellen aus dem Issue fixen": verworfen. Die Zeilennummern im Issue sind veraltet, die breite Suche ergibt neun Stellen, und bei Teilabdeckung bliebe ein Schreibpfad fail-open.
- „Muster auf `\Z` ändern": verworfen, das bricht den textuellen Go-Paritätstest.
- „Neuer Fehlercode `invalid_user_id`": verworfen. Er bräuchte i18n-Vokabular in allen Sprachen und macht eine Existenz-Aussage. `not_found` genügt, weil Go solche Kennungen nie durchlässt.
- Alle Stellen liegen hinter Go-Auth und Core-Geheimnis (ADR-0062). Die praktische Ausnutzbarkeit ist niedrig, es geht bewusst um Verteidigung in der Tiefe.

### Nebenbefunde (Triage #1199)
- `.env.example` nutzt `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASS`/`MAIL_TO` **ohne** `GZ_`-Präfix. Gelesen wird aber `GZ_SMTP_*` (Go `envconfig.Process("GZ")`, Python `env_prefix="GZ_"`), die Beispieldatei ist also veraltet. Außerhalb des Scopes, nur melden.
- Spec `auth_haertung_go_2163.md` steht noch auf `draft` und wird in dieser Scheibe mitgezogen.

### Open Questions
- Keine an den PO. Alle Punkte sind technisch und oben entschieden.
