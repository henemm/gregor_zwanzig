---
entity_id: fix_2541_telegram_live_messskript
type: module
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-2541-telegram-live-messskript
tags: [tooling, staging, telegram, e2e-verify, gate, tests]
---

# Telegram-Live-Messskript für /e2e-verify Schritt 3c (#2541)

## Approval

- [ ] Approved

## Purpose

Der Telegram-Live-Test in `/e2e-verify` (Schritt 3c) verlangt heute, dass der Agent Chat-ID und Bot-Token von Hand aus der Staging-`.env` kopiert; genau diesen Lesezugriff stoppt der Auto-Mode-Klassifikator. Diese Spec liefert ein geprüftes Mess-Skript im Repo, das die Live-Tests selbst im Staging-Checkout ausführt, nur Ergebnisse zurückgibt und bei Erfolg einen commit-gebundenen Nachweis schreibt. Das Telegram-Gate prüft künftig diesen Nachweis statt der bloßen Anwesenheit einer Umgebungsvariable (Verschärfung). Es entsteht kein Produktcode, der Klassifikator wird nicht gelockert und es gibt keine neue sudo-Regel.

## Source

- **Files:**
  - `.claude/tools/staging_telegram_live.py` (neu, Kommandozeilenwerkzeug)
  - `.claude/hooks/e2e_telegram_live.py` (Gate)
  - `.claude/hooks/staging_gate.py` (`_telegram_live_gate()`)
  - `tests/tdd/test_staging_telegram_live.py` (neu, Kern-Tests)
  - `.claude/commands/e2e-verify.md` (Schritt 3c)
- **Identifier:** `main()` im Werkzeug; reine Funktionen `baue_env`, `werte_junit_aus`, `maskiere`, `fingerabdruck`, `schreibe_nachweis`; `gate()` in `e2e_telegram_live.py`.

> Schicht-Hinweis: Reines Werkzeug-, Hook- und Test-Gebiet (`.claude/`, `tests/`, Doku). `src/`, `api/`, `internal/`, `frontend/` bleiben unverändert. Trip/Ortsvergleich-Teilung: nicht betroffen (kein Editor-Baustein). Kanäle: betrifft nur die Prüfung des Telegram-Kanals; Inhalte der vier Kanäle ändern sich nicht.

## Estimated Scope

- **LoC:** Werkzeug ca. +170, Gate ca. +40/-20, Kern-Tests ca. +130, Doku ca. +40 (`*.md` zählt nicht zum Limit). Gesamt ca. 300. Vor `/50` mit `workflow.py status` gegenlesen; bei Bedarf `loc_limit_override` setzen.
- **Files:** 7–8 (2 CREATE, 5 MODIFY, dazu .gitignore/Nachweis-Transport prüfen und ggf. MODIFY; siehe unten)
- **Effort:** medium (Gate-Code, Adversary-Stufe hoch; kein Produktcode)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `.claude/tools/staging_telegram_live.py` | CREATE | pytest `-m live` beider Dateien im Staging-Checkout, junit-Auswertung, Maskierung, Fingerabdruck, Nachweis |
| `.claude/hooks/e2e_telegram_live.py` | MODIFY | `gate()` prüft Nachweis-Datei statt Env-Präsenz |
| `.claude/hooks/staging_gate.py` | MODIFY | `_telegram_live_gate()` übergibt den verifizierten Commit |
| `.claude/commands/e2e-verify.md` | MODIFY | Schritt 3c = ein Aufruf (ersetzt Handrezeptur, Regel-Budget) |
| `tests/tdd/test_issue_686_telegram_functional_live.py` | MODIFY | AC-5-Gate-Tests auf Nachweis umstellen |
| `tests/tdd/test_staging_telegram_live.py` | CREATE | Kern-Tests (Auswertung, Maskierung, Gate, Isolation) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Beschreibung des neuen Telegram-Gates |
| `.gitignore` bzw. `scripts/e2e_nachweis_holen.py` | prüfen, ggf. MODIFY | Nachweis-Ordner und Transport |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `/home/hem/gregor_zwanzig_staging` (Checkout, `data/`, `.env`) | Upstream | Ausführungsort (CWD-`data`), Quelle der Zugangsdaten; `data/` hat ACL `user:hem:rwx`, kein sudo nötig |
| `tests/tdd/_telegram_live_fixture.py` (`load_staging_telegram_env`) | Upstream | liest `GZ_TELEGRAM_BOT_TOKEN`/`GZ_TELEGRAM_TEST_CHAT_ID` selbst aus der Staging-`.env`; abweichender Env-Wert führt zu RuntimeError |
| `tests/tdd/test_issue_686_telegram_functional_live.py`, `tests/tdd/test_telegram_live_zweisprachig.py` | Upstream | die auszuführenden Live-Tests (Marker `live`, Opt-in `GZ_TELEGRAM_LIVE=1`) |
| `uv`, Telegram-Bot-API (Staging-Bot) | Upstream | Testlauf und echte Zustellung |
| `.claude/tools/staging_befehl_pruefen.py` (`_lade_env`), `.claude/tools/staging_messlauf.py` | Vorbild | Muster: Staging-`.env` selbst lesen, nur Ergebnis und Exit-Code ausgeben |
| `.claude/hooks/staging_gate.py` (`--write-verdict`, `prune_old_attestations`) | Downstream | Verdict-Gate; Nachweis liegt bewusst in eigenem Ordner, damit das Aufräumen ihn nicht löscht |
| `/e2e-verify`, `/70-deploy` | Downstream | rufen das Werkzeug auf bzw. hängen am Verdict |

## Implementation Details

Ablauf eines Aufrufs `python3 .claude/tools/staging_telegram_live.py`:

```
1. Vorprüfung: Staging-Checkout, uv und lesbare .env vorhanden, sonst Exit 2
2. env = Aufrufer-Umgebung ohne alle GZ_TELEGRAM_*, plus GZ_TELEGRAM_LIVE=1
3. fp_vorher = fingerabdruck(Staging-data, zweiter Test-Nutzer)   # legt Nutzer bei Bedarf an
4. uv run pytest -m live <686-Datei> <zweisprachig-Datei> -p no:cacheprovider
     --junitxml=<mktemp>     (CWD = Staging-Checkout, Ausgabe nicht an den Aufrufer)
5. werte_junit_aus(xml): Soll-Tests passed, skipped=failures=errors=0
6. fp_nachher == fp_vorher, sonst Befund
7. maskiere() auf jede Textausgabe; bei Exit 0 Nachweis schreiben
```

**Soll-Live-Tests (alle live-gated Tests der beiden Dateien, Stand 2026-11-27):** aus `test_issue_686_telegram_functional_live.py`: `test_ac3_all_seven_commands_produce_meaningful_content`, `test_ac4_live_delivery_and_cleanup`, `test_ac25_live_menu_entspricht_der_vollstaendigen_ac21_liste`, `test_ac24_hilfe_bei_trip_und_vergleich_antwortet_sofort_live`, `test_heute_ohne_namen_bei_trip_und_vergleich_fragt_live_zurueck`; aus `test_telegram_live_zweisprachig.py`: `test_hilfe_englisch_dann_deutsch_live`. Die Liste steht als Konstante im Werkzeug; ein Kern-Test hält sie gegen die tatsächlich `live_telegram_enabled`-gegateten Tests der beiden Dateien synchron (neuer Live-Test ohne Listeneintrag ⇒ rot).

**Auswertung (Exit-Codes):** 0 = alle Soll-Live-Tests `passed`, keine übersprungenen, fehlgeschlagenen oder fehlerhaften Tests. 1 = Befund: `0 selected`, jedes SKIPPED, Teardown-Error (Wächter #2226), Failure, fehlender Soll-Test oder veränderter Fingerabdruck (SKIPPED ist nie grün, #2813). 2 = Umgebungsfehler: Checkout fehlt, `uv` fehlt, `.env` nicht lesbar, pytest startet nicht, junit-Datei fehlt.

**Keine Zugangsdaten beim Aufrufer:** Das Werkzeug übergibt keine Secrets und entfernt `GZ_TELEGRAM_*` aus der Umgebung; die Fixture liest die `.env` selbst (Schutz gegen Prod-Zugangsdaten bleibt wirksam). Genutzt wird `GZ_TELEGRAM_BOT_TOKEN`, nicht der Test-Bot-Token.

**Keine Secrets in der Ausgabe:** Es gibt keine pytest-Rohausgabe. Ausgegeben werden nur Testnamen, Zähler und die Fehlerklasse. Erste Schicht: alle Werte aus der `.env` (Token, Chat-ID) werden maskiert. Zweite Schicht: Telegram-Token-Regex (`\d{6,}:[A-Za-z0-9_-]{30,}`) auf jede Ausgabe und den Nachweis.

**Nachweis:** Nur bei Exit 0 entsteht `.claude/e2e_telegram_live/<sha>.json` (sha = HEAD des Staging-Checkouts) mit `commit`, Zählern (passed, skipped, failures, errors), Testnamen und `finished_at`. Eigener Ordner, nicht der Ordner der Staging-Attestationen.

**Gate:** `staging_gate.py:_telegram_live_gate()` stellt weiterhin fest, ob HEAD~1..HEAD Telegram berührt. Bei Telegram-Scope verlangt `e2e_telegram_live.gate()` einen Nachweis für den verifizierten Commit (Sollnamen passed, skipped/failures/errors = 0). Die Chat-ID im Environment ist kein Ersatz mehr (sonst wäre die Verschärfung wirkungslos). Ohne Telegram-Scope bleibt das Verhalten unverändert.

**Zwei Nutzer:** Das Werkzeug nimmt vor dem Lauf einen Fingerabdruck (Dateiliste, Größen, Hashes) eines zweiten Test-Nutzers im Staging-`data` und prüft nach dem Lauf Byte-Gleichheit; der Lauf darf nur `tg-live-e2e` verändern. Zusätzlich deckt der zweisprachige Test DE und EN ab. Ein zweiter echter Telegram-Chat wurde verworfen (neue Secrets ohne zusätzliche Aussagekraft).

Begründung der Lesart: Die Projektregel „jeder datenbewegende Endpoint wird mit zwei verschiedenen Nutzern getestet“ (CLAUDE.md, Multi-User-Produkt) zielt auf die Mandantentrennung, also darauf, dass die Aktion eines Nutzers keine Daten eines anderen berührt. Genau das weist der Fingerabdruck nach. Das hier gebaute Werkzeug ist selbst kein Endpoint und bewegt keine Nutzerdaten; ein zweiter Nutzer, der dieselben Telegram-Befehle aktiv ausführt, prüfte nur ein zweites Mal denselben Befehlsweg und bräuchte einen zweiten Telegram-Chat samt neuer Zugangsdaten auf Staging.

## Scope

**In Scope:** neues Prüfwerkzeug für den Telegram-Live-Test auf Staging (Schritt 3c von `/e2e-verify`), Verschärfung des Telegram-Gates im Verdict auf einen commit-gebundenen Ergebnis-Nachweis, Kern-Tests, Nachzug von `/e2e-verify` und `gates_und_ratschen.md`.

**Out of Scope:** siehe Abschnitt „Out of Scope“ unten (kein Produktcode, keine Klassifikator-Lockerung, keine sudo-Regel, keine Änderung der Mail-Prüfwege, kein HMAC).

## Definition of Done

- AC-1 bis AC-10 erfüllt, Kern-Tests grün, Adversary-Verdict VERIFIED.
- Echter Lauf `python3 .claude/tools/staging_telegram_live.py` auf Staging mit Exit 0, Nachweis-Datei für den Staging-Commit vorhanden.
- `staging_gate.py --write-verdict` für eine Telegram-Änderung gelingt ohne Lesezugriff des Agenten auf die Staging-`.env` und verweigert ohne gültigen Nachweis.
- `/e2e-verify` Schritt 3c enthält nur noch den einen Aufruf (alte Handrezeptur entfernt).

## Expected Behavior

- **Input:** `python3 .claude/tools/staging_telegram_live.py` ohne Argumente und ohne Zugangsdaten.
- **Output:** je Soll-Test eine Zeile PASS/FAIL, Zähler, Exit 0/1/2; keine Secrets.
- **Side effects:** echte Telegram-Nachrichten an den Staging-Test-Chat, Änderungen nur unter `data/users/tg-live-e2e` im Staging-`data`, bei Erfolg eine Nachweis-Datei.

## Acceptance Criteria

- **AC-1:** Given ein Agent ohne Telegram-Zugangsdaten in seiner Umgebung (auch mit gesetzten `GZ_TELEGRAM_*`-Werten des Aufrufers) / When er `python3 .claude/tools/staging_telegram_live.py` aufruft / Then laufen die Live-Tests beider Dateien (`test_issue_686_telegram_functional_live.py`, `test_telegram_live_zweisprachig.py`) mit `-m live` und `GZ_TELEGRAM_LIVE=1` im Staging-Checkout `/home/hem/gregor_zwanzig_staging`, und die Aufrufer-Werte `GZ_TELEGRAM_*` erreichen pytest nicht.
  - Test: Kern, `test_env_ohne_telegram_werte_und_live_opt_in` (prüft die gebaute Umgebung und Befehlszeile ohne Netz); Live-Schicht: echter Lauf in `/e2e-verify`.

- **AC-2:** Given junit-XML-Ergebnisse eines pytest-Laufs / When das Werkzeug sie auswertet / Then ist der Exit-Code 0 nur, wenn alle Soll-Live-Tests `passed` sind und skipped, failures und errors je 0 sind; `0 selected`, jedes SKIPPED, ein Teardown-Error, ein Failure oder ein fehlender Soll-Test ergeben Exit 1.
  - Test: Kern, `test_junit_auswertung_gruen_und_alle_befundfaelle` (echte XML-Beispiele, je ein Positiv- und ein Negativfall pro Befundart).

- **AC-3:** Given der Staging-Checkout fehlt, `uv` ist nicht auffindbar oder die `.env` ist nicht lesbar / When das Werkzeug startet / Then endet es mit Exit 2 und einer klaren Meldung, ohne pytest zu starten und ohne einen Nachweis zu schreiben.
  - Test: Kern, `test_umgebungsfehler_ergeben_exit_2` (Aufruf mit nicht vorhandenen Pfaden in einem tmp-Verzeichnis).

- **AC-4:** Given ein Lauf, dessen pytest-Ausgabe, Fehlertexte und `.env` Chat-ID und Bot-Token enthalten / When das Werkzeug Ausgabe und Nachweis erzeugt / Then steht in stdout, stderr und Nachweis weder ein Wert aus der `.env` noch etwas, das dem Token-Muster entspricht, und es wird keine pytest-Rohausgabe weitergereicht.
  - Test: Kern, `test_maskierung_werte_und_token_regex`, `test_ausgabe_und_nachweis_ohne_geheimnisse` (Platzhalter-Secrets, Ausgabe wird nach diesen Werten durchsucht; je eine Probe nur mit Regel-Treffer ohne bekannten Wert).

- **AC-5:** Given ein Lauf endet mit Exit 0 / When das Werkzeug beendet wird / Then liegt `.claude/e2e_telegram_live/<sha>.json` vor (sha = HEAD des Staging-Checkouts) mit `commit`, Zählern, Testnamen und `finished_at`; bei Exit 1 oder 2 wird kein Nachweis geschrieben und ein vorhandener Nachweis eines früheren Laufs für denselben Commit nicht als neu ausgegeben.
  - Test: Kern, `test_nachweis_nur_bei_exit_0_mit_pflichtfeldern` (tmp-Ordner, echte Dateien).

- **AC-6:** Given ein Commit, der Telegram-Code berührt / When `staging_gate.py` das Verdict schreiben soll / Then verweigert es das Verdict, solange kein gültiger Nachweis für genau diesen Commit vorliegt; ein Nachweis für einen anderen Commit, ein Nachweis mit skipped oder failures größer 0, ein fehlender Soll-Test oder die bloße Anwesenheit von `GZ_TELEGRAM_TEST_CHAT_ID` im Environment genügen nicht.
  - Test: Kern, `test_gate_verlangt_nachweis_fuer_verifizierten_commit` (parametrisiert: gültig, anderer Commit, skipped>0, failures>0, fehlend, nur Env-Variable; tmp-Nachweisdateien, kein Mock-Theater).

- **AC-7:** Given ein Commit ohne Telegram-Scope / When `staging_gate.py` das Verdict schreibt / Then verhält sich das Gate unverändert und verlangt keinen Telegram-Nachweis.
  - Test: Kern, `test_gate_ohne_telegram_scope_laesst_durch`.

- **AC-8:** Given ein zweiter Test-Nutzer im Staging-`data` neben dem Live-Test-Nutzer `tg-live-e2e` / When der Live-Lauf durchgeführt wird / Then ist der Fingerabdruck des zweiten Nutzers vor und nach dem Lauf byte-identisch; eine Abweichung ergibt Exit 1, und der zweisprachige Test deckt `hilfe` in DE und EN ab.
  - Test: Kern, `test_fingerabdruck_erkennt_jede_aenderung_am_zweiten_nutzer` (Datei geändert, hinzugefügt, gelöscht, unverändert); Live-Schicht: DE/EN-Tests im echten Lauf.

- **AC-9:** Given ein Mitarbeiter führt `/e2e-verify` mit Telegram-Scope aus / When er Schritt 3c liest / Then findet er genau einen Aufruf (`python3 .claude/tools/staging_telegram_live.py`) mit Exit-Code-Bedeutung statt der Handrezeptur mit Token und Chat-ID, und `docs/reference/gates_und_ratschen.md` beschreibt das Nachweis-Gate samt Restrisiko.
  - Test: `# doc-compliance-test` `test_rezept_und_gate_doku_vorhanden` (Pflicht-Stichworte; ausdrücklich keine Verhaltensprüfung).

- **AC-10:** Given der echte Lauf auf Staging in `/e2e-verify` / When das Werkzeug gegen den verifizierten Commit läuft / Then endet es mit Exit 0, schreibt den Nachweis, und das Verdict kann danach ohne Handeingriff und ohne Lesezugriff des Agenten auf die `.env` geschrieben werden.
  - Test: Live-Schicht, echter Lauf des Werkzeugs auf Staging (nur in `/e2e-verify`, Telegram-Zustellung real).

## Test Plan

Alle neuen Tests in `tests/tdd/test_staging_telegram_live.py`; der Prüfling wird relativ zur Testdatei aufgelöst. Die AC-5-Gate-Tests in `test_issue_686_telegram_functional_live.py` werden auf den Nachweis umgestellt.

**Kern-Schicht (deterministisch, ohne Netz, Commit-Gate):**
- `test_env_ohne_telegram_werte_und_live_opt_in` → AC-1
- `test_junit_auswertung_gruen_und_alle_befundfaelle` → AC-2
- `test_umgebungsfehler_ergeben_exit_2` → AC-3
- `test_maskierung_werte_und_token_regex`, `test_ausgabe_und_nachweis_ohne_geheimnisse` → AC-4
- `test_nachweis_nur_bei_exit_0_mit_pflichtfeldern` → AC-5
- `test_gate_verlangt_nachweis_fuer_verifizierten_commit` → AC-6
- `test_gate_ohne_telegram_scope_laesst_durch` → AC-7
- `test_fingerabdruck_erkennt_jede_aenderung_am_zweiten_nutzer` → AC-8
- `test_rezept_und_gate_doku_vorhanden` (`# doc-compliance-test`) → AC-9

**Live-Schicht (nur `/e2e-verify`):** echter Lauf `python3 .claude/tools/staging_telegram_live.py` auf Staging → AC-1, AC-8 (DE/EN), AC-10.

**Review-Punkte (Adversary):** Produktcode im Diff unverändert; Mutations-Gegenprobe an Exit-Code-Ableitung (skipped als grün), Commit-Bindung im Gate, Maskierung, Fingerabdruck-Vergleich; Prüfung, dass der Nachweis-Ordner nicht von `prune_old_attestations` erfasst wird.

## Out of Scope

- Kein Produktcode, keine Lockerung des Auto-Mode-Klassifikators, keine breite sudo-Regel.
- Keine Änderung der Mail-Prüfwege (#2542, #2439).
- Zweiter echter Telegram-Chat (Variante B) wegen neuer Secrets ohne Mehrwert verworfen.
- HMAC-Härtung des Nachweises.

## Known Limitations

- Restrisiko: Die Nachweis-Datei ist wie jede Attestation theoretisch handschreibbar; HMAC-Härtung ist bewusst außerhalb des Scopes. Das Gate prüft Commit-Bindung, Zähler und Testnamen, nicht die Herkunft der Datei.
- Der Lauf sendet echte Nachrichten an den Staging-Test-Chat und braucht Netz zur Telegram-Bot-API.
- Der Staging-Checkout muss auf dem zu prüfenden Commit stehen (wie heute).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Prüfwerkzeug mit Verschärfung eines bestehenden Gates innerhalb der Test-/Deploy-Strategie (Staging-Verifikation vor Prod). Kanäle, Provider, Datenmodell, Auth und Editor-Paradigma bleiben unverändert.

## Changelog

- 2026-11-27: Initial spec created (Issue #2541). Ersetzt die Handrezeptur in `/e2e-verify` Schritt 3c (Regel-Budget) und verschärft das Telegram-Gate von Env-Präsenz auf commit-gebundenen Nachweis.
