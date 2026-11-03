---
entity_id: fix_2774_staging_mailweg
type: module
created: 2026-11-03
updated: 2026-11-03
status: draft
version: "1.0"
tags: [tooling, staging, email, e2e-verify, validator, tests]
---

# Staging-Mailweg für die Mail-Verifikation in `/e2e-verify` (#2774)

## Approval

- [ ] Approved

## Purpose

Schritt 3b von `/e2e-verify` (Trip- und Compare-Mail auf Staging zustellen und per Validator prüfen) ist nicht mehr durchführbar: Das Rezept verlangt `gregor-test@henemm.com` als Empfänger eines Test-Trips, Go lehnt diese mehrdeutige Adresse aber als `email_taken` ab; der Python-Core (Port 8001) verlangt seit #2142 den Header `X-GZ-Core-Auth`, den das Rezept nicht nennt; ein frisch registriertes Wegwerf-Konto kommt ohne Bestätigung nicht über `email_not_verified`. Folge bei #1670: die Mails wurden nur lokal gerendert (`scripts/send_gate_test_mails.py`), nicht über Staging zugestellt, sodass nur der Health-Commit den Staging-Stand belegte.

Diese Spec liefert ein Prüfwerkzeug, das auf Staging **eine Trip-Mail und eine Compare-Mail wirklich zustellt** (Wegwerf-Nutzer mit eindeutiger Plus-Adresse `gregor-test+<tag>@henemm.com`, Bestätigung über das Helfer-Konto, Einzelversand mit Core-Auth) und den **pfadrichtigen, unveränderten Validator** gegen genau diese Mail laufen lässt. Dazu wird das Rezept in `/e2e-verify` ersetzt und der Weg in den Referenz-Dokumenten festgehalten. Es ändert **keinen Produktcode**, umgeht weder Absenderschutz noch Anmeldung und fasst keine Daten bestehender Nutzer an.

Ausdrücklich **nicht** gelöst, sondern als dokumentierte Grenze festgehalten: das Szenario „Ausblick ohne Winddaten" (AC-5 aus #1670, Wind-Zelle „–" statt „0"). Auf Staging liefern die echten Provider praktisch immer Wind, und der Seed-Endpoint (`staging_seed_endpoint`) setzt nur Tarif und SMS-Zähler, keine Wetterdaten. Dieser Fall bleibt per lokalem Render-Test belegt (abgedeckt in #1670); es gibt keinen Eingriff in Wetterdaten und keine Ersatzkonstruktion.

## Source

- **Files:**
  - `.claude/tools/staging_mail_pruefen.py` (neu, Kommandozeilenwerkzeug)
  - `tests/tdd/test_staging_mail_pruefweg.py` (neu, deterministische Kern-Tests)
  - `.claude/commands/e2e-verify.md` (Schritt 3b ersetzt, Z. ~83-106)
  - `docs/reference/mail_validators.md` (Zustellweg und Subject-Filter)
  - `docs/reference/operations_playbook.md` (Staging-Rezept, neuer Abschnitt neben „Staging-Messlauf auslösen")
- **Identifier:** `main()` im Werkzeug; reine Funktionen `baue_mail_tag`, `baue_trip_name`, `baue_preset`, `baue_validator_aufruf`, `waehle_validator`, `bestimme_exit`; HTTP-Rand `sende_einzelversand`, `lege_ort_an`, `lege_preset_an`.

> Schicht-Hinweis: Reines Werkzeug und Test-Schicht (`.claude/`, `tests/`, Doku). `src/`, `api/`, `internal/`, `frontend/` bleiben unverändert. Die Validatoren `.claude/hooks/briefing_mail_validator.py` und `.claude/hooks/email_spec_validator.py` bleiben **unverändert** (Gate-Dateien; das Renderer-Commit-Gate ist nicht betroffen, es sind keine Mail-Inhalts-Dateien).

## Estimated Scope

- **LoC:** Werkzeug ca. +190, Kern-Tests ca. +130, Doku (`e2e-verify.md`, `mail_validators.md`, `operations_playbook.md`) ca. +70. Gesamt ca. +390. Ob `.claude/tools/*.py` zum Limit von 250 zählt, ist nicht sicher (wie bei #2542); vor `/50` mit `workflow.py status` gegenlesen und bei Bedarf `workflow.py set-field loc_limit_override 500` setzen (`*.md` zählt nicht).
- **Files:** 5 (2 CREATE, 3 MODIFY)
  - CREATE `.claude/tools/staging_mail_pruefen.py` — Treiber (ca. +190)
  - CREATE `tests/tdd/test_staging_mail_pruefweg.py` — Kern-Tests (ca. +130)
  - MODIFY `.claude/commands/e2e-verify.md` — Schritt 3b neu (ca. +35)
  - MODIFY `docs/reference/mail_validators.md` — Zustellweg, Subject-Filter (ca. +15)
  - MODIFY `docs/reference/operations_playbook.md` — Rezept „Staging-Mail zustellen und prüfen" (ca. +25)
- **Effort:** medium-low (nur Test-Infrastruktur, kein Produktcode, Aufräumen im `finally`; Risiko: Staging-Versand langsam, geteiltes Postfach)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/tools/staging_befehl_pruefen.py` (#2542) | Upstream (importiert, nicht kopiert) | `StagingApi` (registriere mit Helfer-Bestätigung, `lege_trip_an`, `loesche_trip`, `loesche_nutzer`), `baue_tag`, `baue_plus_adresse`, `baue_trip`, `StagingFehler`, `http_transport`, `_lade_env`, `_imap_factory` |
| `.claude/tools/staging_messlauf.py` (#2439) | Vorbild für das Laden per `importlib` (`_lade_modul`, Z. ~25-50) | zweiter Staging-Treiber, gleiches Muster |
| Staging-Go-API: `/api/auth/register`, `/api/auth/login`, `/api/auth/verify-email(/staging-token)`, `POST /api/auth/account/delete`, `/api/trips`, `/api/locations`, `POST /api/compare/presets`, `DELETE`-Pendants | Upstream | Wegwerf-Nutzer, Trip, Orte, Preset anlegen und aufräumen |
| Staging-Kern Port 8001: `POST /api/scheduler/trips/{trip_id}/send?user_id=..&report_type=..`, `POST /api/scheduler/compare-presets/{preset_id}/send?user_id=..` mit Header `X-GZ-Core-Auth` | Upstream | Einzelversand (`api/routers/scheduler.py:310,321`, delegiert an `send_briefing`) |
| `.claude/hooks/briefing_mail_validator.py` | Upstream (unverändert) | Trip-Mails; CLI: `--mail-type`, `--subject-contains`, `--max-scan`, `--max-bytes`, `--eml` |
| `.claude/hooks/email_spec_validator.py` | Upstream (unverändert) | Compare-Mails; CLI: `--mail-type compare` (Default), `--subject-contains`, `--min-locations`, `--max-age-minutes`, `--ignore-mail-age`, `--eml` |
| Test-Postfach `gregor-test@henemm.com` (IMAP, `GZ_TEST_IMAP_*`) | Upstream | Beide Validatoren lesen das GANZE Postfach und filtern nur nach `X-GZ-Mail-Type` und `--subject-contains`, nicht nach Empfängeradresse; die Plus-Adresse landet im Basispostfach |
| `/home/hem/gregor_zwanzig_staging/.env` | Upstream | Staging-Adresse, Core-Secret, Helfer-Konto `GZ_AUTH_USER/PASS` (nie im Klartext ausgeben) |
| `docs/reference/api_contract.md` §16 (ComparePreset) | Upstream (nur lesen) | Feldschema des Presets |
| `fix_1670_mail_formatdetails.md` | Downstream | nutzt den Weg zur Staging-Verifikation; AC-5 dort bleibt per lokalem Render-Test belegt |
| `/e2e-verify` (Hard Gate für Prod-Deploy) | Downstream | ruft das Werkzeug in Schritt 3b auf |

## Implementation Details

Das Werkzeug lädt `staging_befehl_pruefen.py` per `importlib` (Muster `staging_messlauf._lade_modul`) und nutzt dessen `StagingApi`, `baue_tag`, `baue_plus_adresse`, `baue_trip` und die Env-/IMAP-Helfer. Es wird nichts kopiert; fehlt ein Helfer (Compare-Preset, Ort, Einzelversand), wird er im neuen Werkzeug ergänzt, nicht im Vorbild verändert.

Aufruf: `python3 .claude/tools/staging_mail_pruefen.py --typ trip|compare|beide [--report-type morning|evening] [--timeout 300] [--ohne-cleanup]`

Ablauf (ein Lauf, ein Wegwerf-Nutzer für beide Pfade):

```
1. tag          = baue_tag()                         # eindeutig je Lauf
2. plus_adresse = gregor-test+<tag>@henemm.com
3. Wegwerf-Nutzer registrieren (Helfer-Login -> register -> staging-token -> verify -> login);
   user_id = Server-ID u-<8hex> aus der Register-Antwort (nie "default")
4. Trip-Pfad:
   a. Trip anlegen (baue_trip; Trip-Name enthaelt den Tag, z. B. "GZ-Mailpruefung <tag> trip")
   b. POST http://127.0.0.1:8001/api/scheduler/trips/<trip_id>/send?user_id=<user_id>&report_type=<morning|evening>
      Header X-GZ-Core-Auth: <Core-Secret>, Timeout >= 300 s
   c. briefing_mail_validator.py --mail-type trip-briefing --subject-contains "<Trip-Name>"
5. Compare-Pfad:
   a. mindestens drei Orte per POST /api/locations anlegen (id, name, lat, lon; Namen enthalten den Tag)
   b. Compare-Preset per POST /api/compare/presets anlegen (Mindestfelder siehe unten;
      Name enthaelt den Tag)
   c. POST http://127.0.0.1:8001/api/scheduler/compare-presets/<preset_id>/send?user_id=<user_id>
      mit Core-Auth, Timeout >= 300 s (Compare-Versand dauert bis ueber 3 Minuten)
   d. email_spec_validator.py --mail-type compare --subject-contains "<Preset-Name>"
6. finally: Preset, Orte, Trip, dann Nutzer loeschen (account/delete). Gelingt etwas nicht,
   Befund mit der Nutzer-Kennung ausgeben (nie still).
```

**Warum die Plus-Adresse und kein `gregor-test@` als Empfänger:** Go lehnt `gregor-test@henemm.com` als `email_taken` ab (`internal/handler/auth.go:189,1278,1290`). Die Plus-Adresse `gregor-test+<tag>@henemm.com` ist je Lauf eindeutig und landet (Vorbild #2542) im selben Postfach, das die Validatoren ohnehin lesen. Die Eindeutigkeit gegenüber fremden und älteren Mails stellt **der Betreff** her: Trip-Name und Preset-Name enthalten den Tag, der Validator bekommt ihn per `--subject-contains`.

**Zuordnung Validator zu Mail-Typ** (Funktion `waehle_validator`):

| Pfad | `X-GZ-Mail-Type` | Validator | Pflicht-Argumente |
|---|---|---|---|
| Trip (`full`/`compact`) | `trip-briefing` | `briefing_mail_validator.py` | `--mail-type trip-briefing --subject-contains <Tag-Betreff>` |
| Compare | `compare` | `email_spec_validator.py` | `--mail-type compare --subject-contains <Tag-Betreff>` |

Der Validator-Aufruf ist ein Unterprozess; sein Exit-Code wird durchgereicht (Exit 0 = bestanden). Der Compare-Validator hat eine Altersschranke (`--max-age-minutes`); die frisch zugestellte Mail liegt innerhalb davon, `--ignore-mail-age` wird nicht benutzt.

**Compare-Preset, Mindestfelder** (aus `validateComparePreset` in `internal/handler/compare_preset.go` und DTO in `api_contract.md` §16; im Zuge von `/50` gegen den laufenden Staging-Endpunkt zu bestätigen): `name` (nicht leer), `schedule` (`daily|weekly|manual`; das Werkzeug nimmt `manual`, damit kein Cron zusätzlich versendet), `profil` (z. B. `ALLGEMEIN`), `forecast_hours` (24, 48 oder 72), `location_ids` (mindestens zwei, das Werkzeug nimmt drei, passend zum Validator-Default `--min-locations 3`), `hour_from`/`hour_to` (0 bis 23, `hour_to >= hour_from`). `id`, `user_id`, `created_at` setzt der Server. Der Empfänger kommt aus dem Nutzerprofil (`mail_to`), nicht aus dem Preset (`empfaenger` ist seit #1452 inert).

**Trip-Format:** Der Einzelversand liefert das konfigurierte Format (Standard `full`). Ob `compact` per Trip-Konfiguration über die Staging-API setzbar ist (`report_config.email_format`), ist beim Bau gegen das Trip-DTO zu bestätigen; ist es nicht setzbar, deckt das Werkzeug nur `full` ab und `compact` bleibt (wie AC-5 aus #1670) lokal belegt, was im Rezept ausdrücklich steht.

**Kontingent und Isolation:** Tarif `free` erlaubt drei Trips; das Werkzeug legt je Lauf genau einen Trip, drei Orte und ein Preset an und räumt alles wieder weg. Registrierung ist auf 5 Versuche pro IP und Stunde begrenzt (#117): ein Nutzer pro Lauf, 429 oder jede andere Ablehnung führt zu Exit 2 ohne Wiederholung. Alle Aufrufe tragen die echte Server-`user_id` des Wegwerf-Nutzers, nie `"default"`; Daten anderer Nutzer werden nie berührt, und der Versand geht ausschließlich an die Profil-Adresse dieses Wegwerf-Nutzers.

**Reine Funktionen getrennt vom HTTP-Rand:** Tag-/Betreff-Bau, Preset-Bau, Validator-Auswahl und -Argumentbau sowie die Exit-Code-Ableitung sind reine Funktionen ohne Netz; Registrierung, Anlegen, Einzelversand, Löschen und Validator-Unterprozess laufen über austauschbare Ränder (Transport-Funktionen wie im Vorbild), die in Tests durch echte, lokale Ersatz-Implementierungen (z. B. kleiner HTTP-Server auf Loopback) ersetzt werden, nicht durch `Mock()`.

**Dokumentierte Grenze „Ausblick ohne Winddaten":** Das Rezept in `e2e-verify.md` und `mail_validators.md` nennt: AC-5 aus #1670 (Wind-Zelle „–" bei fehlenden Winddaten) ist auf Staging nicht herstellbar (echte Provider liefern Wind, Seed-Endpoint setzt keine Wetterdaten); der Nachweis erfolgt per lokalem Render-Test (`tests/tdd/` zu #1670). Kein Eingriff in Wetterdaten, keine Sonderkonstruktion.

## Expected Behavior

- **Input:** `python3 .claude/tools/staging_mail_pruefen.py --typ trip|compare|beide` (optional `--report-type`, `--timeout`, `--ohne-cleanup` nur zur Fehlersuche).
- **Output:** je Pfad eine Zeile `PASS`/`FAIL` mit Betreff-Marker (Tag) und der Validator-Ausgabe; Gesamt-Exit 0 nur wenn alle gewählten Pfade bestehen. Exit 1 = Mail nicht zugestellt, Versand abgelehnt (z. B. `smtp_not_configured`, `send_failed`) oder Validator nicht Exit 0; Exit 2 = Aufruf-/Umgebungsfehler (fehlende Zugangsdaten oder Core-Secret, Registrierung abgelehnt, Aufräumen nicht möglich).
- **Side effects:** legt auf Staging einen Wegwerf-Nutzer samt Trip, Orten und Preset an, löst zwei Einzelversände aus, erzeugt zwei Mails im Test-Postfach (nur Lesezugriff durch die Validatoren), räumt im `finally` weg.

## Acceptance Criteria

- **AC-1:** Given ein Mitarbeiter führt `/e2e-verify` für eine Trip-Mail-Änderung aus und Staging läuft / When er `python3 .claude/tools/staging_mail_pruefen.py --typ trip` startet / Then wird ohne manuelle Zwischenschritte ein Wegwerf-Nutzer mit Plus-Adresse `gregor-test+<tag>@henemm.com` bestätigt angelegt, ein Trip mit dem Tag im Namen per Einzelversand mit Core-Auth zugestellt, `briefing_mail_validator.py --mail-type trip-briefing --subject-contains <Tag-Betreff>` auf genau diese Mail ausgeführt, und der Lauf endet mit Exit 0 nur, wenn der Validator Exit 0 meldet.
  - Test: live/staging-Marker, `test_staging_mail_pruefweg.py::test_gesamtlauf_trip_auf_staging` (nur in `/e2e-verify`, ohne Zugangsdaten übersprungen).

- **AC-2:** Given Staging läuft und der Wegwerf-Nutzer hat drei Orte und ein Compare-Preset / When der Mitarbeiter `--typ compare` startet / Then wird die Compare-Mail per Einzelversand mit Core-Auth zugestellt (Wartezeit bis mindestens 300 s toleriert), `email_spec_validator.py --mail-type compare --subject-contains <Tag-Betreff>` auf genau diese Mail ausgeführt und der Exit-Code des Validators als Exit-Code des Laufs ausgegeben.
  - Test: live/staging-Marker, `test_staging_mail_pruefweg.py::test_gesamtlauf_compare_auf_staging`.

- **AC-3:** Given ein Tag, ein Pfad (Trip oder Compare) und ein Report-Typ / When das Werkzeug Betreff-Marker, Plus-Adresse und Validator-Aufruf zusammenbaut / Then ist die Plus-Adresse `gregor-test+<tag>@henemm.com`, der Trip- bzw. Preset-Name enthält den Tag, für Trip wird `briefing_mail_validator.py` und für Compare `email_spec_validator.py` gewählt, beide mit `--mail-type` und `--subject-contains <Tag-Betreff>`, und zwei Läufe erzeugen nie denselben Tag.
  - Test: Kern, `test_betreff_tag_und_plus_adresse_werden_gebaut`, `test_validator_wahl_und_argumente_je_pfad`, `test_tags_sind_je_lauf_eindeutig` (reine Funktionen, ohne Netz).

- **AC-4:** Given der Einzelversand nennt die Core-Adresse / When das Werkzeug den Aufruf `POST /api/scheduler/trips/{id}/send` bzw. `/compare-presets/{id}/send` an den Core sendet / Then enthält jeder Aufruf den Header `X-GZ-Core-Auth` mit dem Secret aus der Staging-`.env`, die Query trägt die echte `user_id` des Wegwerf-Nutzers (Server-ID `u-<8hex>`, nie `default`), das Zeitlimit beträgt mindestens 300 s, und das Secret erscheint in keiner Ausgabe.
  - Test: Kern, `test_einzelversand_sendet_core_auth_und_echte_user_id`, `test_ausgaben_enthalten_keine_geheimnisse` (ein lokaler Loopback-Server zeichnet die tatsächlichen Anfragen auf; die Ausgabe wird nach den Platzhalter-Secrets durchsucht).

- **AC-5:** Given die Compare-Pfad-Vorbereitung / When das Werkzeug Orte und Preset zusammenbaut / Then enthält das Preset alle Mindestfelder (`name`, `schedule`, `profil`, `forecast_hours` in 24/48/72, `hour_from`/`hour_to` gültig, mindestens drei `location_ids` der angelegten Orte), `schedule` ist `manual` (kein zusätzlicher Cron-Versand), und alle Namen enthalten den Lauf-Tag.
  - Test: Kern, `test_preset_enthaelt_mindestfelder_und_tag` (prüft Feldmenge und Werte gegen die Validierungsregeln, ohne Netz).

- **AC-6:** Given ein Lauf endet erfolgreich, mit Fehler (z. B. Versand abgelehnt, Validator Exit 1) oder durch Abbruch mittendrin / When das Werkzeug beendet wird / Then wurden Preset, Orte, Trip und Wegwerf-Nutzer gelöscht (das Trip-Kontingent von 3 bleibt unbelastet); scheitert das Löschen, wird die Kennung des übrig gebliebenen Nutzers ausdrücklich ausgegeben und der Exit-Code ist ungleich 0.
  - Test: Kern, `test_cleanup_laeuft_auch_bei_fehler`, `test_cleanup_reihenfolge_und_befund_bei_fehlschlag` (Aufräumschritte werden bei ausgelöster Ausnahme in der erwarteten Reihenfolge ausgeführt, geprüft an der Aufrufreihenfolge der Ersatz-Staging-Schnittstelle am Netzrand).

- **AC-7:** Given verschiedene Ausgänge eines Laufs (Validator Exit 0, Validator Exit 1, Versand abgelehnt mit `smtp_not_configured`/`send_failed`, Core 401, fehlende Zugangsdaten, Registrierung 429) / When das Werkzeug den Exit-Code ableitet / Then ist Exit 0 nur bei Validator-Exit 0 aller gewählten Pfade, Exit 1 bei Mail-/Versand-/Validator-Befund, Exit 2 bei Umgebungs- oder Aufruffehlern (fehlende Zugangsdaten, 401, Registrierung abgelehnt); ein abgelehnter Versand gilt nie als Erfolg, auch wenn der Validator eine ältere, passende Mail fände.
  - Test: Kern, `test_exit_code_ableitung` (parametrisiert über alle Ausgänge, positiv und negativ).

- **AC-8:** Given die Validatoren `briefing_mail_validator.py` und `email_spec_validator.py` / When die Änderung an #2774 geprüft wird / Then sind beide Dateien (und `src/`, `api/`, `internal/`, `frontend/`) im Diff unverändert, und die Zuordnung Validator zu Mail-Typ im Werkzeug entspricht der Tabelle in `docs/reference/mail_validators.md`.
  - Test: Review-Punkt des Adversary (Diff-Prüfung); Kern, `test_validator_wahl_und_argumente_je_pfad` prüft die Zuordnung.

- **AC-9:** Given ein Mitarbeiter liest Schritt 3b in `.claude/commands/e2e-verify.md`, `docs/reference/mail_validators.md` und das Staging-Rezept in `docs/reference/operations_playbook.md` / When er die Mail-Verifikation durchführen will / Then findet er den Aufruf des Werkzeugs, die Exit-Code-Bedeutung, den Hinweis, dass `gregor-test@henemm.com` **nicht** als Empfänger eines Trips taugt (`email_taken`), den Hinweis auf `X-GZ-Core-Auth` für Aufrufe an Port 8001, die Plus-Adresse samt `--subject-contains`-Filter und die Zuordnung Validator zu Mail-Typ; der bisherige Wortlaut „Der Trip bekommt als einzigen Empfaenger die Test-Adresse `gregor-test@henemm.com`" steht nirgends mehr.
  - Test: `# doc-compliance-test` in `test_staging_mail_pruefweg.py::test_rezept_in_e2e_verify_und_referenz` (Pflicht-Stichworte vorhanden, alter Wortlaut fehlt; ausdrücklich keine Verhaltensprüfung).

- **AC-10:** Given das Szenario „Ausblick ohne Winddaten" aus #1670 AC-5 (Wind-Zelle „–" statt „0") / When ein Mitarbeiter im Rezept nach dem Staging-Weg dafür sucht / Then steht dort ausdrücklich, dass dieser Fall auf Staging nicht herstellbar ist (echte Provider liefern Wind, der Seed-Endpoint setzt keine Wetterdaten), dass er per lokalem Render-Test belegt und in #1670 abgedeckt ist, und dass es dafür keinen Eingriff in Wetterdaten gibt.
  - Test: `# doc-compliance-test` in `test_staging_mail_pruefweg.py::test_rezept_nennt_grenze_ohne_winddaten` (Pflicht-Stichworte „Winddaten", „lokal", „#1670" im Rezept).

- **AC-11:** Given die Mehr-Nutzer-Isolation / When zwei Läufe kurz nacheinander oder parallel starten / Then arbeitet jeder mit seinem eigenen Wegwerf-Nutzer, eigenem Tag und eigener `user_id`; der Lauf berührt nie das Konto `default` oder Daten bestehender Nutzer und löscht nur Objekte, deren Namen den eigenen Tag tragen.
  - Test: Kern, `test_zwei_laeufe_nutzen_getrennte_nutzer_und_loeschen_nur_eigenes` (zwei Läufe gegen eine lokale Ersatz-Staging-Schnittstelle mit zwei Nutzern; geprüft werden Anfragen und Löschungen je `user_id`).

## Test Plan

Alle Tests in `tests/tdd/test_staging_mail_pruefweg.py`; der Prüfling wird relativ zur Testdatei aufgelöst; kein `Mock()`/`patch()`, die Ränder werden durch einen lokalen Loopback-HTTP-Server bzw. Ersatzobjekte mit echtem Verhalten ersetzt.

**Kern (deterministisch, ohne Netz):**
- `test_betreff_tag_und_plus_adresse_werden_gebaut`, `test_validator_wahl_und_argumente_je_pfad`, `test_tags_sind_je_lauf_eindeutig` → AC-3, AC-8
- `test_einzelversand_sendet_core_auth_und_echte_user_id`, `test_ausgaben_enthalten_keine_geheimnisse` → AC-4
- `test_preset_enthaelt_mindestfelder_und_tag` → AC-5
- `test_cleanup_laeuft_auch_bei_fehler`, `test_cleanup_reihenfolge_und_befund_bei_fehlschlag` → AC-6
- `test_exit_code_ableitung` → AC-7
- `test_zwei_laeufe_nutzen_getrennte_nutzer_und_loeschen_nur_eigenes` → AC-11
- `test_rezept_in_e2e_verify_und_referenz`, `test_rezept_nennt_grenze_ohne_winddaten` (`# doc-compliance-test`) → AC-9, AC-10

**Live/Staging (Marker `live` + `staging`, nur in `/e2e-verify`, ohne Zugangsdaten übersprungen):**
- `test_gesamtlauf_trip_auf_staging` → AC-1
- `test_gesamtlauf_compare_auf_staging` → AC-2

**Review-Punkte (Adversary):** Validatoren und Produktcode im Diff unverändert (AC-8); Mutations-Gegenprobe an Exit-Code-Ableitung, Core-Auth-Header, `--subject-contains`-Bau und Cleanup-Reihenfolge.

## Out of Scope

- Änderungen an Produktcode, an den Validatoren, an der Absenderprüfung, am Konto `default` oder an der Profil-Validierung (`email_taken` bleibt bestehen).
- Ein Staging-Weg für „Ausblick ohne Winddaten" (AC-5 aus #1670): bewusst dokumentierte Grenze, kein Eingriff in Wetterdaten, keine Erweiterung des Seed-Endpoints.
- Radar-/Regen-Alarm-Mails, amtliche Warnmails und Befehls-Antworten (haben eigene Validatoren bzw. #2542).
- Heben der Hilfsfunktionen aus `staging_befehl_pruefen.py` in ein gemeinsames Modul (Sammel-Eintrag #1199); das Werkzeug importiert sie unverändert.
- Dauerhafter Cron-Lauf; das Werkzeug läuft nur im Rahmen von `/e2e-verify`.

## Known Limitations

- Der Staging-Versand ist langsam (DWD-Gewittersignal-Timeouts, Compare-Versand über 3 Minuten): großzügige Timeouts, ein voller Lauf `--typ beide` kann mehrere Minuten dauern.
- Das Postfach `gregor-test` bleibt geteilt; die Eindeutigkeit entsteht allein über den Tag im Betreff. Ein Validator ohne `--subject-contains` (z. B. der manuelle Altaufruf) kann eine fremde Mail prüfen.
- Registrierung ist auf 5 Versuche pro IP und Stunde begrenzt (#117): kein Wiederholungsversuch, mehrere Läufe in kurzer Folge können mit 429 abbrechen.
- `compact`-Format: nur abgedeckt, wenn es per Trip-Konfiguration über die Staging-API setzbar ist (beim Bau zu klären, siehe Implementation Details); sonst lokal belegt.
- „Ausblick ohne Winddaten" (#1670 AC-5) ist auf Staging nicht beobachtbar (siehe Out of Scope).
- Das Werkzeug prüft Inhalt und Zustellung bis zum Test-Postfach, nicht die Darstellung im Mail-Programm des Nutzers.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Prüfwerkzeug und Doku in der bestehenden Test-/Deploy-Strategie (Staging-Verifikation vor Prod, Muster #2542). Es wird weder ein Kanal noch ein Provider, das Datenmodell, die Authentifizierung noch das Editor-Paradigma geändert; Absenderschutz und Core-Auth bleiben wie beschlossen bestehen.

## Changelog

- 2026-11-03: Initial spec created (Issue #2774). Entscheidungen: neues Werkzeug nach Muster #2542 (importiert statt kopiert), Validatoren unverändert (Filter über `--subject-contains`), AC-5 aus #1670 als dokumentierte Grenze statt Staging-Eingriff.
