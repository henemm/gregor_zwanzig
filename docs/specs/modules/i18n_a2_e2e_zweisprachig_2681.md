---
entity_id: i18n_a2_e2e_zweisprachig_2681
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2681, e2e, model-sonnet]
---

# i18n A2: E2E zweisprachig, zweiter Staging-Nutzer, Marker `X-GZ-Lang` verpflichtend

**Issue:** #2681 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 6, 1

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Das letzte Paket des Epics beweist aus Nutzersicht, dass beide Sprachen auf Staging wirklich ankommen: ein zweiter Staging-Nutzer mit `language=en` erhält Briefing-, Vergleichs-, Alarm-Mails und die Telegram-Antwort auf Englisch, der bisherige Testnutzer unverändert auf Deutsch. Danach wird der Marker `X-GZ-Lang` zur Pflicht (die Übergangsregel aus PV #2663 endet), und der Nachweis `.claude/e2e_verified/<sha>.json` trägt `langs: ["de","en"]`, sodass der Prod-Deploy ohne zweisprachigen Lauf nicht mehr durchgeht.

## Source

- **File:** `scripts/staging_e2e_user_en.py` (neu), `.claude/hooks/_e2e_paths.py`, `.claude/hooks/staging_gate.py`, `.claude/hooks/e2e_browser_test.py`, `.claude/hooks/e2e_telegram_live.py`, `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py`, `.claude/hooks/official_alert_mail_validator.py`, `.claude/hooks/radar_alert_mail_validator.py`, `scripts/send_gate_test_mails.py`, `tests/tdd/_telegram_live_fixture.py`
- **Identifier:** `write_verdict` (staging_gate.py Z. 336), `gate_check` (Z. 501), `main` (Z. 710); `_nearest_verified_ancestor` (`_e2e_paths.py` Z. 360, bleibt unverändert); `_scope_touches_telegram` (`e2e_telegram_live.py` Z. 48), `gate` (Z. 17); `run_browser_test` (`e2e_browser_test.py` Z. 42), `run_email_test` (Z. 112); `validate_message` (briefing Z. 613, official Z. 198, radar Z. 94), `fetch_latest_message` (briefing Z. 690, official Z. 371, radar Z. 192), `_message_matches` (briefing Z. 667, `email_spec_validator.py` Z. 241), `_fetch_latest_message` (`email_spec_validator.py` Z. 371), `main` der Validatoren; `main` (`send_gate_test_mails.py` Z. 364); `ensure_test_user_with_active_trip` (`_telegram_live_fixture.py` Z. 207), `TEST_USER_ID = "tg-live-e2e"` (Z. 24)

> **Schicht-Hinweis:** Entwicklungs- und Prüfwerkzeug (`.claude/hooks/`, `.claude/tools/`, `scripts/`, `tests/`), kein ausgelieferter Produktcode. Der Python-Core, die Go-API und das Frontend werden **nicht** geändert; A2 prüft sie live. Staging ist `https://staging.gregor20.henemm.com`, nie Produktion (`/e2e-verify`-Regeln, kein Eingriff in laufende Systemd-Prozesse).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Mail-Pfade werden in beiden Sprachen geprüft, je mit dem zuständigen Validator (`email_spec_validator.py` für den Ortsvergleich `X-GZ-Mail-Type: compare`, `briefing_mail_validator.py` für `trip-briefing`); es entsteht kein neuer geteilter Baustein und keine einseitige Neuanlage.
> - **Mandantentrennung:** Es existieren **zwei verschiedene** Staging-Nutzer (Standard-Testnutzer `de`, neuer Nutzer `en`) mit getrennten Konten und getrennter Zustellung (Basis-Postfach bzw. Subadresse `+en`). Die Registrierung geht über die echte API mit echter Anmeldung; die `user_id` kommt aus der Sitzung, nie `"default"`. Ein Test beweist, dass eine Mail für den einen Nutzer den Lauf für den anderen nicht erfüllt (AC-6).
> - **Kanäle:** E-Mail (live, beide Sprachen, vier Validatoren) und Telegram (live, Sprachwechsel des Test-Nutzers) werden auf Staging geprüft. SMS und Premium-SMS haben keinen Staging-Livepfad (kostenpflichtig, Satellit); ihr zweisprachiger Nachweis liegt in den Kern-Tests von P8 (#2670) und P10 (#2673) und im Handy-Nachtest nach dem Prod-Deploy. Alle vier Kanäle sind damit benannt (ADR-0095).

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `scripts/staging_e2e_user_en.py` | CREATE | idempotentes Anlegen/Absichern des Staging-Nutzers `en` über die Register-API; Subadresse `+en`; `language=en` sicherstellen |
| `docs/runbooks/staging_e2e_nutzer_en.md` | CREATE | Runbook: Zweck, Aufruf, Secrets `GZ_E2E_EN_*`, Rate-Limit, Wiederherstellung |
| `.claude/hooks/_e2e_paths.py` | MODIFY | `ERFORDERLICHE_SPRACHEN`, `parse_langs`, `langs_vollstaendig`, `mail_sprache`, `mail_passt_zu_sprache` (gemeinsame Stelle für Validatoren und Gate) |
| `.claude/hooks/staging_gate.py` | MODIFY | `--langs`, `write_verdict(..., langs=…)` schreibt `langs` und verweigert ohne beide Sprachen; `gate_check` blockt Nachweise ohne `langs` (außer Scope `docs-only`) |
| `.claude/hooks/e2e_browser_test.py` | MODIFY | `--lang {de,en}` für `browser` und `email`: Cookie `gz_lang`, Mail nach `X-GZ-Lang` und Zieladresse filtern |
| `.claude/hooks/e2e_telegram_live.py` | MODIFY | `_scope_touches_telegram` zählt Änderungen unter `src/i18n/` als Telegram-Scope (Texte kommen aus den Katalogen) |
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | fehlender `X-GZ-Lang` → Fehler (Exit 1) statt Warnung; `--lang`, `--to-contains`; Auswahl der Mail über `mail_passt_zu_sprache` |
| `.claude/hooks/email_spec_validator.py` | MODIFY | dito |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | dito |
| `.claude/hooks/radar_alert_mail_validator.py` | MODIFY | dito |
| `scripts/send_gate_test_mails.py` | MODIFY | `--lang {de,en}`: Empfänger Subadresse, Sprachkonto in temporärem `GZ_DATA_DIR`; Mail-Typen official, briefing, compare, radar |
| `tests/tdd/_telegram_live_fixture.py` | MODIFY | `set_test_user_language(lang, data_dir="data")` (Read-Modify-Write auf `user.json` des Test-Nutzers) und Kontextmanager `test_user_language(lang)` mit Rücksetzen in `finally` |
| `tests/tdd/test_telegram_live_zweisprachig.py` | CREATE | Live-Prüfung (Opt-in `GZ_TELEGRAM_LIVE=1`): `hilfe` auf Deutsch und auf Englisch, Rücksetzen (AC-3) |
| `tests/tdd/test_staging_gate_sprachen.py` | CREATE | Nachweis-Feld `langs`, Schreib- und Leseseite (AC-5) |
| `tests/tdd/test_validatoren_lang_pflicht.py` | CREATE | alle vier Validatoren: Pflicht-Header, Sprach-/Adressfilter (AC-2, AC-6) |
| `tests/tdd/test_staging_e2e_nutzer_en.py` | CREATE | Idempotenz und Secret-Hygiene des Skripts (AC-4) |
| `tests/tdd/test_gate_testmails_zweisprachig.py` | CREATE | `send_gate_test_mails.py --lang en` erzeugt Mails mit `X-GZ-Lang: en` an die Subadresse (AC-1, Kern-Teil) |
| `frontend/playwright.sprachwechsel.staging.config.ts` | CREATE | Staging-Konfiguration für `frontend/e2e/sprachwechsel.spec.ts` (F12), Muster der vorhandenen `playwright.*.staging.config.ts` (AC-8) |
| `.claude/commands/e2e-verify.md` | MODIFY | Schritt 3a/3b/3c/5 zweisprachig: je Pfad beide Nutzer, `--langs de,en` |
| `.claude/agents/staging-validator.md` | MODIFY | der Aufruf `staging_gate.py --write-verdict` (Z. 90-91) bekommt `--langs de,en` |
| `docs/reference/mail_validators.md`, `docs/reference/gates_und_ratschen.md`, `docs/reference/i18n_konventionen.md` | MODIFY | Übergangsregel durch „Pflicht" ersetzen; Zugangsdaten-Tabelle um `GZ_E2E_EN_*`; Nachweis-Feld `langs` |
| `.claude/hooks/prod_selftest.py` | **unverändert** | bleibt deutsch, kein `en`-Check (siehe Known Limitations) |

## Estimated Scope

- **LoC:** ca. 470 Code ohne Tests (Skript ca. 150, Validatoren ca. 100, `staging_gate.py` ca. 40, `e2e_browser_test.py` ca. 45, `_e2e_paths.py` ca. 35, `send_gate_test_mails.py` ca. 60, Telegram-Fixture ca. 35, Rest ca. 5) — über dem Workflow-Limit von 250 LoC: `workflow.py set-field loc_limit_override 500` einplanen. Wird auch 500 erreicht, geht Teil B (Telegram-Live und `send_gate_test_mails.py`) als zweiter Commit im selben Workflow in die Lieferung.
- **Files:** 21 Dateien (Code, Doku, Konfiguration), 5 neue Testdateien.
- **Effort:** high (Hard-Gate-Pfad für Staging und Prod).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2680 A1 | Paket | Doku-Stand (Übergangsregel `X-GZ-Lang`), den A2 auf „Pflicht" umstellt |
| #2663 PV | Paket | Validatoren lesen `X-GZ-Lang` bereits (fehlt → `de` + Warnung); A2 macht daraus einen Fehler |
| #2661 F12 | Paket | `frontend/e2e/sprachwechsel.spec.ts` und der Sprachumschalter; A2 nimmt die Spec in den Staging-Lauf |
| #2646 S1, #2675 G1, #2676 G2 | Pakete | `language` bei Register und Profil-Update, Cookie `gz_lang` |
| #2678 G4 | Paket | Konto-Mails tragen `X-GZ-Lang` |
| `.claude/tools/staging_befehl_pruefen.py` (`StagingApi.registriere`, `http_transport`) | Modul | Vorbild und Wiederverwendung des Registrierungsablaufs (Helfer-Konto, `staging-token`, `verify-email`) |
| `GZ_AUTH_USER`/`GZ_AUTH_PASS`, `GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` (`/home/hem/gregor_zwanzig_staging/.env`) | Umgebung | Helfer-Konto für die Bestätigung; Test-Postfach (Stalwart, `mail.henemm.com`) |
| `tests/tdd/_telegram_live_fixture.py`, `GZ_TELEGRAM_TEST_CHAT_ID`, `GZ_TELEGRAM_BOT_TOKEN`, `GZ_TELEGRAM_LIVE=1` | Test | Live-Telegram-Aufbau (#686, #1014) |
| `secret_in_repo_gate.py`, `secret_output_gate.py` | Hooks | Secrets `GZ_E2E_EN_*` dürfen nie im Repo oder in Ausgaben stehen |
| ADR-0104 Nr. 8, ADR-0095 | ADR | Marker `X-GZ-Lang` verpflichtend; Kanal-Parität |

## Implementation Details

### 1. Zweiter Staging-Nutzer `en` (Subadressierung, keine neue Infrastruktur)

- **Postfach:** `<Lokalteil von GZ_TEST_IMAP_USER>+en@<Domain>`, heute `gregor-test+en@henemm.com`. Stalwart liefert `user+tag` ins Basispostfach (Muster des Werkzeugs `staging_befehl_pruefen.py`, dort `baue_plus_adresse`). Das Skript leitet die Adresse aus `GZ_TEST_IMAP_USER` ab; der Standard-Testnutzer `de` behält das Basispostfach.
- **Skript** `scripts/staging_e2e_user_en.py`, Aufruf `python3 scripts/staging_e2e_user_en.py [--basis-url URL]`. Exit 0 = Nutzer vorhanden, `language=en`, E-Mail bestätigt; Exit 1 = Zustand nicht herstellbar; Exit 2 = Aufruf-/Umgebungsfehler (fehlende Zugangsdaten, Registrierung abgelehnt, 429 bei mehr als 5 Registrierungen je IP und Stunde).

```python
def adresse_en(test_imap_user: str) -> str                       # 'gregor-test@henemm.com' -> 'gregor-test+en@henemm.com'
def lade_env(pfad: Path) -> dict[str, str]                        # Staging-.env lesen
def schreibe_fehlende_schluessel(pfad: Path, werte: dict) -> None # nur ANHÄNGEN, nie überschreiben
def sichere_nutzer_en(api: StagingApi, env: dict) -> str          # 'vorhanden' | 'angelegt' | 'korrigiert'
def main(argv=None, *, transport=None, helfer_transport=None) -> int
```

- **Ablauf von `sichere_nutzer_en` (idempotent):** (1) Sind `GZ_E2E_EN_USER`, `GZ_E2E_EN_PASS`, `GZ_E2E_EN_MAIL` gesetzt, Anmeldung mit diesen Werten; gelingt sie, `GET /api/auth/profile` lesen und bei `language != "en"` per `PUT /api/auth/profile {"language": "en"}` korrigieren (Ergebnis `vorhanden` bzw. `korrigiert`). (2) Fehlt ein Schlüssel oder scheitert die Anmeldung mit 401: Helfer-Konto (`GZ_AUTH_USER`/`GZ_AUTH_PASS`) anmelden, `POST /api/auth/register` mit `language: "en"`, Name `gzp-e2e-en`, E-Mail `adresse_en(...)`, Passwort `secrets.token_urlsafe(24)`, dann `staging-token` und `verify-email`, dann Anmeldung (Ergebnis `angelegt`); die drei Schlüssel werden mit `schreibe_fehlende_schluessel` an `/home/hem/gregor_zwanzig_staging/.env` angehängt. Es wird höchstens **eine** Registrierung je Lauf versucht, nie gelöscht, nie ein zweites Konto angelegt, wenn das erste existiert.
- **Secrets:** `GZ_E2E_EN_USER`, `GZ_E2E_EN_PASS`, `GZ_E2E_EN_MAIL` liegen nur in der Staging-Umgebung, nicht im Repo. Das Skript gibt das Passwort nie aus (Klartext würde `secret_output_gate.py` maskieren, `secret_in_repo_gate.py` blockt jeden Commit damit). Die Tabelle „Zugangsdaten" in `gates_und_ratschen.md` bekommt die Zeile „zweiter Staging-Nutzer (en) | `GZ_E2E_EN_*` | Staging-`.env`".

### 2. Nachweis-Feld `langs` (Hard Gate)

```python
# .claude/hooks/_e2e_paths.py  (Pure Funktionen, wie der Rest der Datei)
ERFORDERLICHE_SPRACHEN = ("de", "en")
def parse_langs(text: str) -> list[str]            # "de,en" -> ["de","en"]; unbekannte Sprache -> ValueError
def langs_vollstaendig(data: dict) -> bool         # alle ERFORDERLICHE_SPRACHEN in data.get("langs") (Liste)
EN_SUBADRESSE = "+en@"
def mail_sprache(headers) -> str | None            # Wert von X-GZ-Lang oder None
def mail_passt_zu_sprache(headers, lang: str) -> bool
    # X-GZ-Lang == lang UND To-Regel: lang=="en" -> To enthält "+en@"; lang=="de" -> To enthält "+en@" NICHT
```

- **Schreibseite** (`staging_gate.py::write_verdict`): neues `--langs de,en` (Default leer). Nach der Scope-Berechnung (Z. 401): ist der Scope nicht `docs-only` und `langs_vollstaendig({"langs": langs})` falsch, wird mit Fehlermeldung „beide Sprachen müssen geprüft sein (`--langs de,en`)" abgebrochen, **ohne** Artefakt (Exit 1, Muster #1327/#1689). Sonst steht `"langs": ["de","en"]` im Payload (Z. 407-414). Der Merge zweier Workflows (Z. 431-487) behält `langs` des schreibenden Workflows.
- **Leseseite** (`gate_check`): nach der VERIFIED- und Staleness-Prüfung des Exakt-Treffers (vor Z. 702) und bei der Ancestor-Relaxierung (mit `_cdata`, Z. 627-634) wird `langs_vollstaendig(data)` verlangt; fehlt das Feld oder ist es unvollständig, meldet das Gate „Nachweis ohne zweisprachigen Lauf — `/e2e-verify` mit beiden Nutzern ausführen" und gibt Exit 1. Scope `docs-only` bleibt davon unberührt. `_nearest_verified_ancestor` und `prod_selftest.py` bleiben unverändert.
- **Folge:** Nachweise, die vor A2 geschrieben wurden, haben kein `langs` und blocken den Deploy bis zum nächsten `/e2e-verify` (ohnehin nach 24 h veraltet).

### 3. Validatoren: `X-GZ-Lang` Pflicht, Sprach- und Adressfilter

- In allen vier Dateien die von PV eingeführte Übergangsstelle finden (`grep -n "X-GZ-Lang"`): Header fehlt → bisher `de` + Warnung, **neu** Fehler mit dem Text „Marker-Header X-GZ-Lang fehlt — Mail nicht vom sprachfähigen Renderer" (Exit 1 aus `main`, `validate_message` liefert `(False, [..])`).
- Neue Optionen in jeder `main`: `--lang {de,en}` (Default `de`) und `--to-contains TEXT`. Die Mail-Auswahl (`fetch_latest_message`, `_fetch_latest_message`, `_message_matches`) nimmt nur Mails, für die `mail_passt_zu_sprache(headers, lang)` wahr ist (und, falls gesetzt, deren `To` den Text enthält). Erwartungen (Überschriften, Legendenzeile, Hinweise) bildet der Validator aus `src/i18n` mit der gewählten Sprache (Stand PV, nicht neu entscheiden).
- **Beispiel-Umstellung** (Muster, in jeder Datei an der PV-Stelle): vorher `if lang_header is None: warnungen.append("X-GZ-Lang fehlt, nehme de an"); lang = "de"` → nachher `if lang_header is None: return False, ["Marker-Header X-GZ-Lang fehlt — Mail nicht vom sprachfähigen Renderer"]`.

### 4. `/e2e-verify` zweisprachig

- **Schritt 3b** läuft **zweimal**: Sitzung des Standard-Testnutzers (`de`, Empfänger `gregor-test@henemm.com`) und Sitzung des Nutzers `en` (Anmeldung mit `GZ_E2E_EN_*`, Empfänger die Subadresse). Je Mail-Pfad der zuständige Validator mit `--lang`:
  - `uv run python3 .claude/hooks/briefing_mail_validator.py --lang en --to-contains "+en@"`
  - `uv run python3 .claude/hooks/email_spec_validator.py --lang en --to-contains "+en@"`
  - Alarm-Pfade (`official-alert`, `radar-alert`, Abweichungs-Alarm) über `uv run python3 scripts/send_gate_test_mails.py --lang en --only <official|briefing|compare|radar>` und die Validatoren `official_alert_mail_validator.py` / `radar_alert_mail_validator.py` mit `--lang en`.
- **`send_gate_test_mails.py --lang en`:** Empfänger `adresse_en(TEST_RECIPIENT)`; für die vom Lauf genutzten `user_id`s (`gate-1233-official-<token>` usw.) legt eine Hilfsfunktion `_temp_sprachkonto(lang, user_ids)` in einem `tempfile.TemporaryDirectory()` (gesetzt als `GZ_DATA_DIR`, `get_data_root` honoriert das) je eine `user.json` mit `language` an, damit `resolve_user_lang` die Sprache findet; Default `de` unverändert.
- **Schritt 3a (frontend):** `python3 .claude/hooks/e2e_browser_test.py browser --check "<Text>" --url "/" --lang en` setzt den Cookie `gz_lang` (`context.add_cookies([{"name": "gz_lang", "value": lang, "url": _base_url()}])`) und prüft den Text in der jeweiligen Sprache; zusätzlich `cd frontend && npx playwright test --config playwright.sprachwechsel.staging.config.ts` für `e2e/sprachwechsel.spec.ts`.
- **Schritt 3c (Telegram):** `GZ_TELEGRAM_LIVE=1 … uv run pytest tests/tdd/test_telegram_live_zweisprachig.py -v` zusätzlich zum bisherigen Live-Test. `_scope_touches_telegram` ergänzt das Muster `src/i18n/`; ein SKIPPED zählt weiterhin nicht als grün.
- **Schritt 5:** `staging_gate.py --write-verdict "VERIFIED: …" --findings-json … --langs de,en`.

### 5. Telegram: Sprache des bestehenden Test-Nutzers umschalten

Der Telegram-Live-Test läuft im Prozess gegen das lokale `data/` der Staging-Installation mit Nutzer `tg-live-e2e` (`TEST_USER_ID`); ein Chat gehört genau einem Nutzer (`address_owner.go`), ein zweiter Chat ist nicht nötig.

```python
# tests/tdd/_telegram_live_fixture.py
def set_test_user_language(lang: str | None, data_dir: str = "data") -> str | None
    # Read-Modify-Write auf data/users/tg-live-e2e/user.json: nur das Feld "language";
    # lang=None entfernt das Feld. Rückgabe: vorheriger Wert (None, wenn das Feld fehlte).
@contextmanager
def test_user_language(lang: str, data_dir: str = "data")
    # vorher = set_test_user_language(lang); try: yield; finally: set_test_user_language(vorher)
```

`test_telegram_live_zweisprachig.py` ruft `ensure_test_user_with_active_trip(chat_id=…)`, dann unter `test_user_language("en")` den Befehl `hilfe` (über `run_command_through_pipeline`) und prüft: englische Langform (`Available commands`), englische Befehlswörter, Kürzel unverändert; danach (Rücksetzen) `hilfe` auf Deutsch (`Verfügbare Befehle`). Ein erzwungener Fehler im `with`-Block lässt den Nutzer trotzdem auf dem vorherigen Wert (`finally`).

### 6. Doku und Nacharbeit

`docs/reference/mail_validators.md` und `docs/reference/i18n_konventionen.md`: „Header fehlt → `de` + Warnung" wird „Pflicht, Exit ≠ 0"; `gates_und_ratschen.md`: Abschnitt „E2E-Nachweis-Ablage" nennt `langs`, die Zugangsdaten-Tabelle `GZ_E2E_EN_*`. Das Runbook `docs/runbooks/staging_e2e_nutzer_en.md` beschreibt Zweck, Aufruf, Rate-Limit, Wiederherstellung (Konto fehlt → Skript erneut laufen lassen).

### 7. Mutations-Gegenproben (Adversary)

(a) `langs_vollstaendig` immer `True` → AC-5 rot; (b) Validator-Fehlerzweig für fehlenden Header wieder auf Warnung → AC-2 rot; (c) `mail_passt_zu_sprache` ohne To-Regel → AC-6 rot; (d) `finally` im Kontextmanager entfernen → AC-3-Teilprobe rot; (e) Skript legt bei vorhandenem Konto ein zweites an → AC-4 rot.

## Expected Behavior

- **Input:** `/e2e-verify` nach dem Merge, mit den Zugangsdaten beider Staging-Nutzer.
- **Output:** pro Mail-Pfad zwei bestandene Validatorläufe (`de`, `en`), eine englische und eine deutsche Telegram-Antwort, ein Nachweis mit `"langs": ["de","en"]`; ohne beides verweigert das Gate Schreiben und Deploy.
- **Side effects:** höchstens eine einmalige Registrierung des Nutzers `en` auf Staging (und Anhängen der drei Schlüssel an die Staging-`.env`); `language` des Telegram-Test-Nutzers wird zeitweise geändert und immer zurückgesetzt; Testmails an Basispostfach und Subadresse. Keine Mail an echte Nutzer, kein Eingriff in Produktion.

## Acceptance Criteria

- **AC-1:** Given beide Staging-Nutzer (`de` im Basispostfach, `en` an der Subadresse `+en`) / When `/e2e-verify` auf Staging läuft / Then bestehen alle vier Validatoren (`briefing_mail_validator.py`, `email_spec_validator.py`, `official_alert_mail_validator.py`, `radar_alert_mail_validator.py`) mit Exit 0, einmal für die deutsche und einmal für die englische Mail, und die englischen Mails tragen `X-GZ-Lang: en`.
  - Test: Live-Lauf `/e2e-verify` gegen Staging mit echt zugestellten Mails im Stalwart-Test-Postfach (Marker `staging`, kein Mock); Kern-Teil: tests/tdd/test_gate_testmails_zweisprachig.py — `send_gate_test_mails.py --lang en` baut Mails mit englischer Sprache an die Subadresse, `--lang de` bleibt byte-gleich zum bisherigen Verhalten.

- **AC-2:** Given eine Mail ohne den Header `X-GZ-Lang` / When jeder der vier Validatoren sie prüft / Then endet er mit Exit ungleich 0 und nennt den fehlenden Header in der Meldung, statt wie in der Übergangsphase mit Deutsch und Warnung zu bestehen.
  - Test: tests/tdd/test_validatoren_lang_pflicht.py — je Validator eine echt gerenderte Mail (Typ `trip-briefing`, `compare`, `official-alert`, `radar-alert`) mit und ohne Header; mit Header Exit 0, ohne Exit 1.

- **AC-3:** Given der bestehende Telegram-Test-Nutzer mit Opt-in `GZ_TELEGRAM_LIVE=1` / When der Live-Test seine Sprache auf `en` setzt und `hilfe` sendet / Then ist die Antwort englisch (Langform, englische Befehlswörter) mit unveränderten Kürzeln, danach antwortet `hilfe` wieder deutsch, und die Sprache des Nutzers steht nach dem Test, auch bei einem Fehler im Test, wieder auf dem Wert vor dem Test.
  - Test: tests/tdd/test_telegram_live_zweisprachig.py — echter Webhook-Eintritt gegen den Test-Chat; Teilprobe mit absichtlich ausgelöstem Fehler im `with`-Block prüft das Rücksetzen in `finally`.

- **AC-4:** Given der Staging-Nutzer `en` existiert bereits / When `scripts/staging_e2e_user_en.py` erneut läuft / Then legt es kein zweites Konto an, bestätigt `language=en`, korrigiert eine abweichende Sprache per Profil-Update, endet mit Exit 0, und kein Passwort steht im Repo, in der Ausgabe oder im Log.
  - Test: tests/tdd/test_staging_e2e_nutzer_en.py — Skript gegen einen Transport, der den beobachtbaren Vertrag der Register-/Profil-Endpunkte nachbildet (Muster `staging_befehl_pruefen.py`): zweiter Lauf = null Registrierungen; abweichende Sprache wird korrigiert; die Ausgabe enthält das Passwort nicht; `schreibe_fehlende_schluessel` überschreibt nie vorhandene Werte.

- **AC-5:** Given ein `/e2e-verify`-Ergebnis für einen Backend- oder Frontend-Change / When der Nachweis geschrieben und das Deploy-Gate geprüft wird / Then verweigert `staging_gate.py --write-verdict` ohne `--langs de,en` das Artefakt (Exit 1), der Nachweis mit beiden Sprachen enthält `"langs": ["de","en"]`, `--check` blockt einen Nachweis ohne dieses Feld, und für Scope `docs-only` bleibt das Gate unverändert offen.
  - Test: tests/tdd/test_staging_gate_sprachen.py — `write_verdict` und `gate_check` mit echten Dateien in `tmp_path` für die Scopes `backend`, `frontend-only` und `docs-only`; bestehende Gate-Tests (`test_staging_gate.py`, `test_staging_gate_verdict_merge.py`, `test_staging_gate_ancestor_scope.py`) bleiben grün, ihre Fixtures tragen `langs`.

- **AC-6:** Given eine englische Mail an die Subadresse `+en` und eine deutsche Mail an das Basispostfach liegen im selben Postfach / When ein Validator mit `--lang de` bzw. `--lang en` läuft / Then wählt er nur die Mail seiner Sprache und seines Empfängers, eine Mail der anderen Sprache oder an die andere Adresse erfüllt den Lauf nie.
  - Test: tests/tdd/test_validatoren_lang_pflicht.py — Auswahlprädikat `mail_passt_zu_sprache` und die vier Auswahlfunktionen über ein Postfach mit beiden Mails (zwei Nutzer); Gegenprobe: korrekter Header, falsche Adresse wird abgelehnt.

- **AC-7:** Given der Prod-Selftest nach dem Deploy / When `prod_selftest.py` läuft / Then prüft er weiterhin nur deutsche Prod-Daten, braucht keinerlei `GZ_E2E_EN_*`-Werte und gibt für einen vollständigen Nachweis (mit `langs`) Exit 0.
  - Test: tests/tdd/test_prod_selftest_564.py (bestehend) bleibt grün; ergänzend in tests/tdd/test_staging_gate_sprachen.py — Selftest-Lauf mit Nachweis, in dessen Umgebung keine `GZ_E2E_EN_*` gesetzt sind.

- **AC-8:** Given die Staging-Seite im Browser / When `e2e_browser_test.py browser --lang en --url "/"` (und `--lang de`) läuft und die Playwright-Spec `sprachwechsel.spec.ts` gegen Staging ausgeführt wird / Then zeigt die Seite bei `gz_lang=en` die englischen und bei `gz_lang=de` die deutschen Texte, beide Läufe enden mit Exit 0.
  - Test: Live-Lauf gegen Staging (Marker `staging`): `e2e_browser_test.py browser` mit `--lang` je Sprache und `npx playwright test --config playwright.sprachwechsel.staging.config.ts`; Kern-Teil in tests/tdd/test_staging_gate_sprachen.py prüft, dass `run_browser_test(…, lang="en")` den Cookie `gz_lang=en` setzt.

## Known Limitations

- **Annahme 1 (Postfach):** Die Subadresse leitet sich aus `GZ_TEST_IMAP_USER` ab (das Test-Postfach der Validatoren, #972), nicht aus `GZ_IMAP_USER`; beide zeigen auf dasselbe Stalwart-Basispostfach `gregor-test@henemm.com`. Stalwart liefert `user+tag` dorthin (Beleg: `staging_befehl_pruefen.py`).
- **Annahme 2 (Secrets):** Das Skript legt die Schlüssel `GZ_E2E_EN_*` bei der Erstanlage selbst an (anhängend, nie überschreibend) statt auf einen manuellen Schritt zu warten; sie bleiben außerhalb des Repos.
- **Annahme 3 (`prod_selftest.py`):** bleibt unverändert deutsch, ohne optionalen `en`-Check (PO-Entscheid der Spec laut Issue: kein Prod-Nutzer `en` als Voraussetzung).
- **Annahme 4 (Scope von `langs`):** `langs` ist für jeden Scope außer `docs-only` Pflicht, auch für `frontend-only` (der Sprachumschalter wird dort mitgeprüft).
- **Annahme 5 (F12-Spec):** `frontend/e2e/sprachwechsel.spec.ts` ist über `GZ_SVELTE_BASE` und Staging-Zugang parametrisierbar; falls nicht, deckt `e2e_browser_test.py --lang` die Sprachumschaltung allein ab und die zusätzliche Playwright-Konfiguration bleibt ungenutzt.
- Konto- und Transaktions-Mails (Go) werden auf Staging nur bei der Erstanlage des Nutzers `en` durch die Bestätigungsmail sichtbar; ihr Marker `X-GZ-Lang` ist durch die Go-Tests von G4 (#2678) gedeckt. Ein Live-Nachweis jeder weiteren Konto-Mail entfällt.
- SMS und Premium-SMS haben keinen Staging-Livepfad (siehe Kanal-Prüfpunkt); der Handy-Nachtest nach dem Prod-Deploy bleibt manuell.
- Nachweise vor A2 haben kein `langs` und blocken den Deploy bis zum nächsten `/e2e-verify`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** ADR-0104 Nr. 8 verlangt, dass die Mail-Validatoren den Marker `X-GZ-Lang` lesen und er nach Abschluss Pflicht ist; diese Spec setzt das zusammen mit dem zweisprachigen Nachweis (`langs`) und dem zweiten Staging-Nutzer um.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
