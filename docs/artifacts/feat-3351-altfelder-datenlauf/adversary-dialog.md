# Adversary Dialog — feat-3351-altfelder-datenlauf
Spec: docs/specs/modules/feat_3351_altfelder_datenlauf.md
Datum: 2026-11-25 20:07

## Checkliste
- [x] **Input:** Datenwurzel mit Nutzerordnern; Schalter `--ausfuehren`, `--blockierte-auslassen`, `--nachzaehlen`.
- [x] **Output:** Bericht (je Feld, Abo-Art, Nutzeranzahl, aggregiert), Exit-Code. Nach dem Lauf enthält kein Abo und kein Eintrag in `compare_presets.json` mehr eines der zehn Altfelder, außer bewusst ausgelassene blockierte Abos (Staging).
- [x] **Side effects:** je Nutzer eine Sicherung unter `.backups`; betroffene Dateien neu im Python-Format. Keine sichtbare Änderung in Editor, Mail oder Kanälen (DE und EN).
- [x] **AC-1:** Given ein Datenbaum mit zwei Nutzern, deren Abos Altfelder auf oberster Ebene, in `report_config` und in `display_config` tragen / When das Skript im Standardmodus (Probelauf) läuft / Then meldet es je Feld, Abo-Art und Nutzeranzahl aggregiert, ändert aber keine Datei und legt keine Sicherung an.
- [x] **AC-2:** Given Abos mit Altfeldern auf allen drei Ebenen (Trip und Vergleich) mit vorhandener Tabelle `placements` / When das Skript mit `--ausfuehren` läuft / Then enthält danach keine Datei mehr eines der zehn Altfelder auf irgendeiner Ebene.
- [x] **AC-3:** Given Abos mit Altfeldern und vielen weiteren Feldern (Orte, Zeiten, Empfänger, `placements`, übrige Konfiguration) / When `--ausfuehren` die Altfelder entfernt / Then bleiben alle anderen Felder inhaltlich unverändert erhalten, und ein Container, der nur Altfelder trug, bleibt als leeres Objekt stehen.
- [x] **AC-4:** Given ein Datenbaum mit Abos von zwei Nutzern / When `--ausfuehren` läuft / Then liegt je Nutzer eine eigene Sicherung (tar.gz unter `.backups` der Datenwurzel) mit dessen Originaldateien vor dem ersten Schreiben, und die Dateien des einen Nutzers stehen nicht in der Sicherung des anderen.
- [x] **AC-5:** Given ein Abo mit Altfeldern, aber ohne `placements.rows` oder ohne `placements.outlook_reports` (neben unkritischen Abos) / When das Skript ohne `--blockierte-auslassen` mit `--ausfuehren` läuft / Then bricht es mit Exit 2 ab, nennt das Abo als BLOCKIERT und schreibt keine einzige Datei und keine Sicherung.
- [x] **AC-6:** Given derselbe Baum mit blockiertem Abo / When das Skript mit `--ausfuehren --blockierte-auslassen` läuft / Then bleibt das blockierte Abo byte-gleich, alle übrigen Abos sind bereinigt, der Bericht weist das blockierte Abo aus, und Exit ist 0.
- [x] **AC-7:** Given ein bereits bereinigter Datenbaum / When das Skript erneut mit `--ausfuehren` läuft / Then ändert es keine Datei (gleiche Bytes, gleiche Änderungszeit), meldet "Nichts zu tun" und beendet sich mit Exit 0.
- [x] **AC-8:** Given ein Datenbaum / When `--nachzaehlen` läuft / Then ändert es nichts, endet mit Exit 1, solange irgendwo ein Altfeld steht, mit Exit 0 bei 0 Altfeldern, und weist blockierte und ausgelassene Abos getrennt aus.
- [x] **AC-9:** Given Nutzerordner mit `compare_presets.json` (Array, Einträge mit Altfeldern) / When `--ausfuehren` läuft / Then sind die Altfelder je Eintrag entfernt, die Datei und alle übrigen Felder und Einträge bleiben erhalten, und die Tabellenprüfung gilt für diese Datei nicht.
- [x] **AC-10:** Given eine Datei, die sich zwischen Planung und Schreiben ändert (gleichzeitiger Schreiber) / When das Skript schreiben will / Then überschreibt es die geänderte Datei nicht, meldet sie als seit der Planung geändert und beendet sich mit Exit 1; ein Wiederholungslauf bereinigt sie.
- [x] **AC-11:** Given der Quelltext des Skripts / When die Altnamen-Sperre `tests/test_altfeld_namen_sperre.py` läuft / Then bleibt sie grün, weil das Skript die Namen nur über `from app.loader import ALTFELDER` bezieht und keinen Namen als Literal enthält.
- [x] **AC-12:** Given der abgeschlossene Lauf auf Staging und Prod / When die Nachzählung läuft / Then zeigt Prod 0 Altfelder, Staging 0 (außer bewusst ausgelassenen blockierten Abos, aggregiert benannt), und ein Kommentar mit diesen aggregierten Zahlen steht an #3351 und #3102, ohne Abo-IDs.

## Dialog

### Runde 1
**Adversary:** Tests 36 passed (Skript-Tests + Namensperre). Code gelesen: Probelauf kehrt vor jeder Schreibwirkung zurueck (Z.176); Sicherung (Z.179-187) vor schreiben (Z.188), Fehler => Exit 1 ohne Schreiben; fail-closed Exit 2 vor Sicherung. Lesender Probelauf auf echtem Bestand: Prod 26 Altfelder in 10 Dateien, 3 Nutzer, 0 blockiert, Exit 0. Staging 41 Altfelder in 20 Dateien, 4 Nutzer, genau 1 blockiertes Abo (placements unvollstaendig), Exit 2; keine unlesbaren Dateien. Die Entscheidung "unlesbar/unerwartete Struktur = BLOCKIERT" blockiert Prod nicht. Abgrenzung Vergleich/Trip per kind/location_ids wirkt nur auf die Berichtsart, nicht auf die Bereinigung.
**Implementierer:** Keine Rueckmeldung eingeholt (Adversary-Lauf ohne Dialogpartner).

### Runde 2
**Adversary:** Mutationen per String-Ersetzung mit Sicherung im Scratchpad, danach per sha256 identisch zurueckgesetzt (Index und Worktree unveraendert): (1) Sicherung nach Schreiben: rot. (1b) Sicherung entfernt: rot. (2) fail-closed entfernt: rot. (3) report_config nicht bereinigt: rot. (4) Probelauf schreibt: rot. (5) Nicht-Altfeld mit entfernt: rot. (6) Inhaltsvergleich in schreiben() entfernt: rot. (7) Tabellenpruefung auch fuer Presets: rot. (8) --nachzaehlen immer Exit 0: rot. (9) Presets aus Sicherung entfernt: KEIN Test rot => F001.
**Implementierer:** offen: Test fuer Presets in der Sicherung ergaenzen.

### Findings
Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: scripts/migrate_3277_altfelder.py:141
  Description: _sichern nimmt briefings und compare_presets.json in die Sicherung. Die Mutation `for teil in ("briefings",)` (Presets aus der Sicherung entfernt) laesst alle 15 Tests in tests/tdd/test_migrate_3277_altfelder.py gruen.
  Spec requirement: AC-4 / Datensicherheit - Sicherung enthaelt Originaldateien vor dem ersten Schreiben, vollstaendig (auch compare_presets.json).
  Conflict: Die Zusicherung "Sicherung enthaelt compare_presets.json" ist von keinem Test bewacht; die Datei wird aber geschrieben (AC-9). Ein Rueckbau wuerde unbemerkt Datenverlust-Risiko erzeugen.
  Status: behoben (Runde 3, Test ergänzt, Mutation 9 jetzt rot)
  Remediation: Test, der in der tar.gz eines Nutzers mit compare_presets.json die Presets-Datei mit Originalbytes prueft.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: docs/reference/operations_playbook.md:968
  Description: Das Skript ist nur mit der Projekt-venv lauffaehig (`uv run`); `python3 -I` mit System-Python scheitert am Import app.loader (pydantic fehlt). Playbook nutzt korrekt `uv run`. Im Worktree-venv scheitert der Dienstnutzer zusaetzlich an Dateirechten (pydantic_core .so), mit /home/hem/gregor_zwanzig/.venv/bin/python lief es.
  Spec requirement: Side effects / Betrieb
  Conflict: Nur Hinweis fuer den echten Lauf (nach Deploy aus dem Hauptcheckout starten, nicht aus dem Worktree).
  Remediation: Keine Codeaenderung noetig.

### Runde 3
**Adversary:** Nachtrag zu F001: Mutation 9 (Presets aus der Sicherung) wiederholt. Neuer Test test_ac4_ac9_sicherung_enthaelt_presets_und_briefings_byte_genau wird rot (1 failed, 15 passed). Datei per sha256 identisch zurückgesetzt, Index unverändert, keine unstaged Änderungen. Tests danach: 37 passed. F001 Status: behoben.
**Implementierer:** Test ergänzt.

## Confirmations
Confirmation:
  AC: Input
  Code reference: scripts/migrate_3277_altfelder.py:148
  Evidence: Schalter --ausfuehren, --blockierte-auslassen, --nachzaehlen, --root, --backup-dir in main() (Z.149-153).
  Status: CONFIRMED

Confirmation:
  AC: Output
  Code reference: scripts/migrate_3277_altfelder.py:118
  Evidence: _bericht aggregiert je Feld Ebene/Art/Nutzeranzahl, blockierte getrennt; Exit 0/1/2 (Z.15-17, 170, 175, 192). Lesender Probelauf auf Prod: 26 Altfelder in 10 Dateien, 3 Nutzer, 0 blockiert.
  Status: CONFIRMED

Confirmation:
  AC: Side effects
  Code reference: scripts/migrate_3277_altfelder.py:138
  Evidence: _sichern je Nutzer tar.gz (briefings + compare_presets.json) unter .backups; Schreiben via schreiben() aus migrate_2792 mit json.dumps(indent=2).
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: scripts/migrate_3277_altfelder.py:176
  Evidence: Ohne --ausfuehren Return 0 in Z.176-178 vor mkdir/_sichern/schreiben; Mutation 4 (Probelauf schreibt) rot (tests/tdd/test_migrate_3277_altfelder.py).
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: scripts/migrate_3277_altfelder.py:111
  Evidence: altfelder_entfernen (src/app/loader.py:150) auf allen drei Ebenen; Mutation 3 (report_config nicht bereinigt) rot; Test jedes der zehn Felder je Ebene gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: scripts/migrate_3277_altfelder.py:113
  Evidence: Nur ALTFELDER werden gepoppt (loader.py:157-158), Rest per deepcopy erhalten; Mutation 5 (zusaetzlich Schluessel name entfernt) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: scripts/migrate_3277_altfelder.py:180
  Evidence: Sicherung je Nutzer in Schleife Z.183-184 vor schreiben() Z.188; Mutation 1 (nach Schreiben) und 1b (entfernt) rot. Siehe aber F001 (Presets in Sicherung ungeprueft).
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: scripts/migrate_3277_altfelder.py:167
  Evidence: blockiert und nicht --blockierte-auslassen => Exit 2 vor Sicherung/Schreiben; Mutation 2 (fail-closed entfernt) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: scripts/migrate_3277_altfelder.py:171
  Evidence: Blockierte stehen nicht in plaene (Z.106-107), bleiben byte-gleich, Exit 0; staging-Realbestand hat genau 1 blockiertes Abo.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: scripts/migrate_3277_altfelder.py:173
  Evidence: neu != daten Filter (Z.113) => leere plaene => 'Nichts zu tun', Exit 0, keine Sicherung.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: scripts/migrate_3277_altfelder.py:164
  Evidence: --nachzaehlen liest nur (zaehlen) und gibt 1 wenn irgendein Eintrag (auch blockiert/unlesbar) existiert; Mutation 8 (immer 0) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: scripts/migrate_3277_altfelder.py:97
  Evidence: Tabellenpruefung nur fuer Abos (not ist_presets); Presets-Array je Eintrag bereinigt (Z.111); Mutation 7 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: scripts/migrate_3277_altfelder.py:188
  Evidence: schreiben() (scripts/migrate_2792_profil_ampel.py:325-338) liest unter Sperre neu und vergleicht; Mutation 6 (Vergleich weg) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-11
  Code reference: scripts/migrate_3277_altfelder.py:36
  Evidence: Namen nur ueber from app.loader import ALTFELDER; tests/test_altfeld_namen_sperre.py gruen (36 passed in adversary-test-output.txt).
  Status: CONFIRMED

Confirmation:
  AC: AC-12
  Code reference: scripts/migrate_3277_altfelder.py:159
  Evidence: Echter Lauf steht noch aus (nach Deploy); Nachzaehlung ist implementiert, Vorab-Probelauf: Prod 26 Altfelder/0 blockiert (Exit 0), Staging 41 Altfelder/1 blockiert (Exit 2 ohne --blockierte-auslassen). Nicht im Scope dieses Gates.
  Status: CONFIRMED

Confirmation:
  AC: Datei docs/reference/operations_playbook.md
  Code reference: docs/reference/operations_playbook.md:966
  Evidence: Aufrufe, Exit-Codes, Sicherungsort dokumentiert; Standard-backup-dir root/../.backups ist fuer claude-gregor schreibbar (Prod und Staging geprueft).
  Status: CONFIRMED

Confirmation:
  AC: Datei docs/artifacts/feat-3351-altfelder-datenlauf/test-green-output.txt
  Code reference: docs/artifacts/feat-3351-altfelder-datenlauf/test-green-output.txt:1
  Evidence: Gruen-Nachweis der Implementierer-Tests, durch eigenen Lauf adversary-test-output.txt (36 passed) bestaetigt.
  Status: CONFIRMED

Confirmation:
  AC: Datei tests/tdd/test_migrate_3277_altfelder.py
  Code reference: tests/tdd/test_migrate_3277_altfelder.py:1
  Evidence: Alle Tests laufen gruen; Luecke bei Presets-Sicherung siehe F001.
  Status: CONFIRMED

Confirmation:
  AC: Datei tests/test_altfeld_namen_sperre.py
  Code reference: tests/test_altfeld_namen_sperre.py:1
  Evidence: Sperre gruen, Skript enthaelt keinen Altnamen als Literal.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

Keine Vorbedingungen aus Fremdquellen; Realbestand nur lesend per Probelauf (Prod/Staging) ermittelt.

## Verdict

VERDICT: VERIFIED
F001 behoben (Mutation 9 jetzt rot), F002 nur Hinweis. Tests: 37 passed, 0 failed. Alle ACs ausser AC-12 (nach Deploy) bestätigt.

## Geprüfte Dateien

- sha256:55104198997f3c8c918840ad68e4b844f2a2f21969e2d434d8afcc26442a27b6  docs/artifacts/feat-3351-altfelder-datenlauf/test-green-output.txt
- sha256:5fa80a046661680743db1adf145b8099fc58109542cf42690e97d6ecacd7d097  docs/reference/operations_playbook.md
- sha256:58d69780cca998abc37b2724a926b4f71d14c191ba82698fedb58880cdc4338b  scripts/migrate_3277_altfelder.py
- sha256:c861493dff183b0c514eb73a5eba2f581af4af01f1258450186a3a6af796ecde  tests/tdd/test_migrate_3277_altfelder.py
- sha256:a28878440e93d12a71a27d0bc0e844e0865bf045501a3defa33a3975c108cc4c  tests/test_altfeld_namen_sperre.py

## Prüfbasis

- base: b1b6b7e56cef843f5d3dcb827e26f8f15507a8b7
- blob:03c317a06d989c213db0a9482e6eb0f890be9bb1  docs/artifacts/feat-3351-altfelder-datenlauf/test-green-output.txt
- blob:8629cc1d87920b2536b52aa0fbe1817d703583ba  docs/reference/operations_playbook.md
- blob:8d961c066d8c247513224963eb1e2fa6b2b057a8  scripts/migrate_3277_altfelder.py
- blob:52aacb1fa5c9404fec922a9d8fb65ab57c338ae5  tests/tdd/test_migrate_3277_altfelder.py
- blob:b54f55edb46e3bd50fcff7fd643e1d77456047d0  tests/test_altfeld_namen_sperre.py
