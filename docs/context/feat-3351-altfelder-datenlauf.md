# Context + Analyse: #3351 Altfelder-Datenlauf (Was steht wo B6b-5)

Workflow `feat-3351-altfelder-datenlauf`, Epic #3122, Stand origin/main `99e52b2d3` (#3277, #3297, #3298, #3301 live). Erstellt 2026-11-25.

## Request Summary

Einmal-Skript `scripts/migrate_3277_altfelder.py` entfernt je Nutzer die zehn Altfelder (`ALTFELDER` in `src/app/loader.py:142`) aus `<root>/<uid>/briefings/*.json` (Trip und Ortsvergleich) und aus der Altdatei `compare_presets.json`. Muster `migrate_2792_profil_ampel.py`: Probelauf mit Bericht je Feld, Sicherung je Nutzer, Sperre, Read-Modify-Write (ADR-0101), atomar, idempotent, fail-closed (Abo ohne `placements.rows`/`outlook_reports` wird nie umgeschrieben). Lauf Staging, dann Prod, danach Nachzählung (0 Altfelder) und Abschluss von #3102 als Nachweis. Voraussetzungen #3277, #3297, #3298 sind live. Kommentar im Issue: Nachzählung nach einigen Tagen Betrieb wiederholen.

## Related Files

| Datei:Zeile | Relevanz |
|---|---|
| `src/app/loader.py:142` `ALTFELDER` (10 Namen) | Einzige Namensliste im Backend; Skript importiert sie (kein Namens-Literal im Skript). |
| `src/app/loader.py:150` `altfelder_entfernen(daten)` | Entfernt in-place aus oberster Ebene, `display_config`, `report_config`; fertig wiederverwendbar im Skript. |
| `src/app/loader.py:2102` (save_trip), `src/services/scheduler_dispatch_service.py:573` (Vergleich) | Python-Schreibwege verwerfen Altfelder schon beim Speichern; der Lauf macht dasselbe für Dateien, die niemand speichert. |
| `scripts/migrate_2792_profil_ampel.py:375` | Vorbild. Wiederverwendbar: `schreiben(plaene)` (Z. ~330: Sperre `exclusive_lock`, Inhaltsvergleich seit Planung, `_atomar` mit Rechte-Erhalt, Liste offener Dateien), `main`-Gerüst (`--root`, `--backup-dir`, `--execute`), `planen`-Schleife über Nutzerordner (`.`/`_`-Ordner übersprungen). |
| `scripts/migrate_2794_preset_horizons.py:120` | Jüngstes, kürzestes Muster: importiert `schreiben` aus 2792 (`sys.path` auf `scripts`), eigenes `_sichern` (tar.gz je Nutzer, `migrate-<nr>-<uid>-<stempel>.tar.gz`), Exit 0/1. Strukturvorlage fürs neue Skript. |
| `scripts/migrate_1250_briefings.py:205` | Einzige Stelle, die `compare_presets.json` (Array-Datei) noch liest, einmalig zur Überführung nach `briefings/`. |
| `tests/tdd/test_migration_2792_profil_ampel.py` (539 Z.), `tests/tdd/test_migration_vorlagen_horizonte.py` (164 Z.) | Testvorbild: echter Datenbaum in `tmp_path`, Skript als Subprozess, Probelauf schreibt nichts, Sicherung je Nutzer, Idempotenz, Rechte, Sperre. |
| `tests/tdd/test_3277_altfelder_entfernen.py:25-120` | Fixtures mit allen zehn Namen je Ebene (`DC_ALT`, `RC_ALT`, `TOP_ALT`, `TABELLE`); direkt für die Skript-Tests nutzbar. |
| `tests/test_altfeld_namen_sperre.py:72` (`ERLAUBT`, `_ABLAUF = 2027-02-23`) | Wächter scannt auch `scripts/`: ein Namens-Literal im neuen Skript wäre rot. Lösung: Namen nur über `from app.loader import ALTFELDER`, kein `ERLAUBT`-Eintrag. |
| `internal/model/trip.go:124-125`, `internal/model/compare_preset.go:48` | `DisplayConfig`/`ReportConfig` sind `map[string]interface{}`: Go reicht unbekannte Schlüssel durch. |
| `internal/handler/trip.go:449,512` (`mergeConfigMap`) | Go-Trip-Update mergt `report_config` aus dem Request in den Bestand; Altfelder aus dem Bestand blieben stehen, aus dem Request kämen neu hinzu. |
| `.claude/hooks/prod_selftest.py:893` `check_dead_trips_guard` | Präzedenz für dauerhafte Zählwächter im Prod-Selftest (PASS/FAIL/SKIPPED, `sudo -n find`). |
| `docs/reference/operations_playbook.md:~913-957` | Skript-Rezepte je Migration (Staging Probelauf, Staging `--execute`, Prod Probelauf, Prod `--execute`); hier kommt ein Abschnitt "Altfelder entfernen (#3351)" dazu. |
| `docs/specs/modules/feat_3122_was_steht_wo.md` Teil A Nr. 8 (Z. 366-369) | Fachliche Quelle: "Bestand folgt #3351". |

## Existing Patterns

- **Zweiphasiger Ablauf** (2792/2794): (1) planen, nichts schreiben, Bericht je Nutzer/Datei; (2) erst alle Sicherungen je Nutzer (tar.gz nach `<root>/../.backups`, Standard `root.parent/.backups`), Fehler dort ⇒ nichts geschrieben, Exit 1; (3) schreiben je Datei unter `exclusive_lock` (flock auf `<id>.json.lock`, dieselbe Sperre wie Go, ADR-0083), nur wenn der Inhalt seit der Planung gleich blieb, sonst "seit der Planung geändert" ⇒ `Error:`-Zeile, Exit 1, Lauf wiederholen.
- **Atomar**: Temp-Datei im selben Ordner (`.<name>.<uuid>.tmp`, kein `*.json`), `fsync`, `chmod` wie Original, `os.replace`.
- **Idempotent**: unveränderte Dateien werden nicht geschrieben; zweiter Lauf meldet "Nichts zu tun".
- **Format-Hinweis**: neu geschriebene Dateien tragen Python-Format (`indent=2`, `ensure_ascii=False`); Go-Escapes werden zu Zeichen, JSON-semantisch gleich (steht im Playbook).
- **Lauf-Rezept**: Staging zuerst, `uv run python3 scripts/<skript> --root /var/lib/gregor-staging/users [--execute]`, dann Prod `--root /var/lib/gregor/users`. Der Dienstnutzer `claude-gregor` (Gruppe von `users/`, 2770; Staging per ACL `gregor-staging-data`) darf lesen und schreiben, Backup-Ordner `.backups` ist für `claude-gregor` beschreibbar (geprüft per `stat`). Aus einem Worktree: direkte sudo-uv-Form (Memory `reference_prod_skript_als_dienstnutzer_aus_worktree`).
- **Sperre gegen Schreiber**: nur Dateisperre (flock) plus Inhaltsvergleich, kein Dienststopp (2792, 3196). Nur 2794 verlangte `gregor-api` gestoppt (Vorlagen-Datei hat keine Sperrdatei). Briefings haben Sperrdateien (Prod 71 `.lock`, Staging 30), also reicht flock.
- **Dauerwächter**: `check_dead_trips_guard` im Prod-Selftest (additiver Check, FAIL bei Fund, SKIPPED bei Nicht-Prüfbarkeit).

## Dependencies

- Vorgänger live: #3277 (Core/Go lesen+serialisieren keine Altfelder, Python-Speichern verwirft sie), #3297 (Trip-Frontend), #3298 (Vergleich-Frontend, Typ-Sperre `frontend/src/lib/altfeld_namen_sperre.test.ts`), #3301.
- Skript braucht nur `app.loader.ALTFELDER`/`altfelder_entfernen` und `services.file_lock` (`exclusive_lock`, `LockTimeout`), plus `schreiben` aus `migrate_2792_profil_ampel`.
- Folgt aus dem Lauf: #3102 (siehe unten), Epic #3122 Abschluss.

## Existing Specs

- `docs/specs/modules/feat_3122_was_steht_wo.md` (Teil A Nr. 8, Nachtrag 21.11./25.11.), ADR-0124 Nr. 6/8, ADR-0101 (RMW mit Merge).
- `docs/specs/modules/feat_3277_altfelder_entfernen.md` (Altfelder-Liste, Wächter AC-7). Eine eigene Spec für #3351 fehlt noch (Spec ab 2026-05-11 braucht `## Acceptance Criteria`, Given/When/Then, Deutsch).
- Vorbild-Specs: `feat_2792_s1_profil_ampel.md` §4, `feat_2794_s3a_reiter_wetter.md` §6, `feat_3157_migration_placements.md` (Probelauf-Muster mit Freigabe).

## Befund 2: Wo die Altfelder in gespeicherten Daten liegen (belegt)

Ebenen laut Code (`altfelder_entfernen`) und Fixtures (`test_3277`, `test_3237`): alle zehn kommen in `display_config` vor; `show_outlook` und `multi_day_trend_reports` zusätzlich in `report_config` (Trip); `outlook_enabled`, `multi_day_trend_reports`, `show_outlook` auch top-level (Vergleich). Lesender Zähllauf (Prod, nur Zahlen) bestätigt die Ebenen: Prod `display_config.*` (channel_active_metrics, channel_layouts, hourly_metric_formats, hourly_metrics, multi_day_trend_reports, outlook_metric_formats, outlook_metrics), `report_config.multi_day_trend_reports`, `report_config.show_outlook`, top-level `outlook_enabled`. Staging: `display_config.*` und `report_config.show_outlook`/`multi_day_trend_reports`, `display_config.outlook_enabled` (einmal; also auch dort möglich). Das Skript muss daher wie `altfelder_entfernen` alle drei Ebenen prüfen. Hinweis: das Testfixture nennt zusätzlich einen Tippfehler-Namen `outlook_metrics_formats` (Orte-Fixture in `test_3237`); er steht nicht in `ALTFELDER` und kommt in keinem Bestand vor (in der Zählung nicht gesucht, nur die zehn Namen). Orte (`locations/*.json`, `display_config`) tragen laut Zählung keine Altfelder (0 von 37 Prod, 0 von 22 Staging).

## Befund 4: Bestandszählung (nur lesend, aggregiert, 25.11. gegen 17:30 UTC)

| | Prod (`/var/lib/gregor/users`) | Staging (`/var/lib/gregor-staging/users`) |
|---|---|---|
| Nutzerordner | 4 | 117 |
| Briefing-Dateien (Trip+Vergleich) | 21 | 31 |
| Abos mit Altfeldern | **9** (6 Trip, 3 Vergleich), bei 3 Nutzern | **20** (16 Trip, 4 Vergleich), bei 4 Nutzern |
| davon ohne `placements.rows` | 0 | **1** |
| davon ohne `placements.outlook_reports` | 0 | **1** |
| Abos ganz ohne `placements` (mit oder ohne Altfeld) | 0 | 6 |
| `outlook_enabled` vorhanden | 3, alle `true` | 1, `true` |
| `compare_presets.json` vorhanden | 2 Dateien, 1 Eintrag mit Altfeldern | 3 Dateien, 1 Eintrag mit Altfeldern |
| Orte mit Altfeldern / `trips/`-Ordner | 0 / 0 | 0 / 0 |
| unlesbare Dateien | 0 | 0 |

Das Issue nennt 10 Abos auf Prod (Stand Morgen); jetzt sind es 9. Differenz erklärt: ein Abo wurde inzwischen gespeichert (Python/Go-Speichern verwirft Altfelder bzw. #3297/#3298-Frontend), konsistent mit dem Rückgang. Heißt: Bestand schrumpft von selbst, ist aber nicht null. Zählskript: Scratchpad `zaehl3351.py` (liest nur, gibt nur Zahlen aus).

`compare_presets.json`: wird von keinem Laufzeit-Code mehr gelesen (`load_compare_presets` liest `briefings/*.json`, Cutover #1250 S7b). Die Altdatei ist toter Bestand; die Einträge dort sind kein Betriebsrisiko, das Issue verlangt sie aber ausdrücklich bereinigt.

## Befund 5: Issue #3102

"Einstellung = Mail, Phase 3g: Abschluss" (Teil von Epic #3058): Bestandsdaten per RMW mit Merge auf die kanonische Form migrieren (Pre-Snapshot, ADR-0101), Differenztest-Orakel und überflüssige Lese-Adapter löschen, Import-Sperre (Test) gegen die gelöschten Altfunktionen. Abschlusskriterium: Prüfkatalog aller vier Kanäle grün, keine `offen_feature`-Fälle mehr aus Phase 3. Der Datenlauf liefert nur den Teil "Bestandsdaten migriert + Nachzählung 0" als Nachweis; Orakel-Löschung und Import-Sperre (Namenssperre existiert seit #3277/#3298) sind Anteile anderer Scheiben. Vor dem Schließen von #3102 prüfen, ob die übrigen Punkte erledigt sind (Orakel gelöscht? Prüfkatalog grün?); sonst Nachweis ins Issue kommentieren, nicht schließen (Memory: Sammel-/Epic-Issues nie mit Teil-Workflow schließen).

## Befund 6: Go-Echo-Risiko

- Go hält `report_config`/`display_config` als `map[string]interface{}`; beim Trip-Update (`internal/handler/trip.go:512`, `mergeConfigMap`) wird der Request-Inhalt in den Bestand gemergt, beim Anlegen (`trip.go:270`) unverändert gespeichert. Go entfernt keine Altfelder selbst. Neu entstehen sie also nur, wenn ein Client sie mitsendet; Bestandsfelder bleiben bei Go-Speichern stehen, bis Python speichert.
- Frontend nach #3297/#3298: keine Treffer mit Schreibwirkung (nur Kommentare in `compareEditorSave.ts`, `weatherMetricsCompareSave.ts`, `subscriptionHelpers.ts`, `alarmeDeliveryPayload.ts`, `cockpitHelpers568.ts`); Typ-Sperre `altfeld_namen_sperre.test.ts` (#3298) verhindert Rückkehr im Frontend, `tests/test_altfeld_namen_sperre.py` im Backend. Offene Restrisiken: (a) im Browser offene, alte Seitenstände (vor Deploy geladen) und alte Tabs speichern noch alte Felder; (b) externe API-Clients; (c) beim Trip-Update spiegelt Go ggf. Bestandsfelder zurück (unschädlich, solange sie weg sind).
- Empfehlung: nach dem Lauf einen dauerhaften Wächter, weil die Wiederkehr still wäre (Felder wirkungslos, aber Datenmüll und Verstoß gegen die Zielzahl 0): neuer additiver Check im Prod-Selftest (Muster `check_dead_trips_guard`, nur Zählung, FAIL bei Fund, SKIPPED wenn nicht prüfbar), plus einmalige Nachzählung nach ca. 3 bis 7 Tagen Betrieb (Issue-Kommentar vom 25.11.). Alternative ohne Selftest-Anbindung: Teil-Check in `henemm-infra/scripts/monitor.sh` (Warnung statt Alarm); schwerer, da Datenwurzel nur als `claude-gregor` lesbar. Empfohlen: Selftest-Check.

## Risks & Considerations

1. **Fail-closed im Bestand real**: Staging hat 1 Abo mit Altfeldern ohne `rows`/`outlook_reports` (Testdaten). Prod hat keins. Wird das Altfeld bei fehlender Tabelle entfernt, gehen Metrik-Wahl und Ausblick verloren (die Tabelle ist seit #3277 einzige Quelle, ein Abo ohne Tabelle fällt auf Vorlage zurück). Darum: Abo nicht schreiben, im Bericht als BLOCKIERT mit Dateiname, Feldliste und Grund führen.
2. **Verlust von Information**: Altfelder sind wirkungslos (nach #3277 nicht mehr gelesen), daher keine Ausgabeänderung. Prod: alle `outlook_enabled = true`, das Ausblick-Verhalten kommt aus `placements.outlook_reports`.
3. **Wettlauf mit Schreibern**: Go und Python können dieselbe Datei speichern; Absicherung per flock plus Inhaltsvergleich, ggf. Exit 1 und Wiederholung. Kein Dienststopp nötig.
4. **Wiederkehr nach Lauf** (alter Tab, API-Client): Nachzählung nach einigen Tagen und Dauerwächter (siehe Befund 6).
5. **Nur-Altfeld-Container**: ein Objekt `display_config`/`report_config`, das nach der Entfernung leer wäre: bleibt als leeres Objekt stehen (nicht löschen, Merge-Prinzip).
6. **Wächter `test_altfeld_namen_sperre.py`**: Namens-Literale im Skript wären rot; über `ALTFELDER` importieren (kein Literal, kein `ERLAUBT`). Skript-Tests dürfen Namen in Fixtures nennen (Tests werden nicht gescannt, `test_3277` macht es auch).
7. **Format-Änderung**: Dateien werden in Python-Format neu geschrieben (Go-Escapes, Einrückung); semantisch gleich.
8. **Datenschutz im Chat/Bericht**: der Bericht nennt Abo-IDs und Dateinamen; im Issue/PR nur aggregierte Zahlen (öffentliches Repo).
9. **Isolations-Test** (Multi-User): Skript über mehrere Nutzer, Test mit zwei Nutzern, Sicherung getrennt je Nutzer, kein Fallback auf `"default"` (Nutzerordner kommt aus dem Verzeichnis, nicht aus dem Auth-Kontext).

## Analysis

**Ansatz.** Neues Skript `scripts/migrate_3277_altfelder.py` (nach Issue-Name, auch wenn Workflow #3351 heißt) im Gerüst von `migrate_2794_preset_horizons.py`:
1. `planen(root)`: je Nutzerordner `briefings/*.json` (alle `.json`, `.lock` ignorieren) und `compare_presets.json` (Array). Je Datei: JSON laden (unlesbar ⇒ BLOCKIERT/übersprungen, berichtet, Exit 1, nie stumm), Altfelder je Ebene (`top`, `display_config`, `report_config`) mit `ALTFELDER` suchen, im Bericht je Feld zählen (`Feld  Ebene  Anzahl Abos`) plus Gesamtzahlen je Nutzer. Neues Objekt per `altfelder_entfernen(copy.deepcopy(obj))`; geändert nur, wenn sich etwas ändert.
2. **Fail-closed für `briefings/*.json`**: Hat ein Abo Altfelder, aber `display_config.placements.rows` ist keine Liste oder `placements.outlook_reports` fehlt/keine Liste (oder `placements` fehlt ganz), wird es nicht in den Plan genommen, sondern als `BLOCKIERT: <nutzer>/<datei>: Felder [...], kein placements.rows/outlook_reports` berichtet. Verhalten: Die Planung endet mit Exit 2 und es wird **nichts** geschrieben, solange blockierte Abos existieren. Abos ohne Altfelder sind nie betroffen. Für `compare_presets.json` gilt die Bedingung nicht (tote Datei, keine Quelle): dort wird ohne Tabellenprüfung entfernt; Nutzer-Ausnahme: ist die Datei unlesbar, BLOCKIERT.
3. Sicherung je Nutzer vor dem Schreiben (`migrate-3277-<uid>-<stempel>.tar.gz` mit `briefings/` und `compare_presets.json`), dann `schreiben(plaene)` aus 2792 (Sperre, Inhaltsvergleich, atomar, Rechte). `--execute`-Flag, `--backup-dir`, Exit 0 fertig/nichts zu tun, 1 offene Dateien, 2 blockiert.
4. Nachzählung: Aufruf `--nachzaehlen` (nur lesend) gibt je Feld die Zahl und Exit 1 bei Rest ≠ 0; wird auch als Basis des Dauerwächters genutzt (Funktion `zaehlen(root)` im Skript, vom Selftest nicht importierbar ohne `sys.path`; daher Selftest ruft Skript als Subprozess oder zählt selbst).
5. Playbook-Abschnitt "Altfelder entfernen (#3351)" mit den vier Befehlszeilen (Staging Probelauf/`--execute`, Prod Probelauf/`--execute`) plus Nachzählung, jeweils als `sudo -n -u claude-gregor uv run ...`.
6. Dauerwächter: `check_altfelder_guard()` in `.claude/hooks/prod_selftest.py` nach dem Muster `check_dead_trips_guard` (Zählung über `sudo -n -u claude-gregor python3`, FAIL bei Fund, SKIPPED bei Nicht-Prüfbarkeit).

**Dateiliste und LoC-Schätzung.**

| Datei | Art | LoC |
|---|---|---|
| `scripts/migrate_3277_altfelder.py` | neu | ca. 150 |
| `tests/tdd/test_migration_3277_altfelder.py` | neu (Probelauf, Bericht je Feld, Sicherung je Nutzer, zwei Nutzer, idempotent, fail-closed ohne rows/outlook_reports, compare_presets.json, Rechte, Sperre/Änderung seit Planung, Nachzählung, Merge-Erhalt fremder Felder) | ca. 230 |
| `.claude/hooks/prod_selftest.py` | Ergänzung `check_altfelder_guard` + Einhängen in `run_selftest` | ca. 40 |
| `tests/test_prod_selftest_altfelder_guard.py` | neu (nach Muster `test_prod_selftest_1708c_dead_trips_guard.py`) | ca. 60 |
| `docs/reference/operations_playbook.md` | neuer Abschnitt | ca. 25 |
| `docs/specs/modules/feat_3351_altfelder_datenlauf.md` | neue Spec mit ACs | ca. 90 (Doku) |
Produktivcode ca. 190 LoC (Skript + Selftest-Check), Tests ca. 290; unter dem üblichen LoC-Limit pro Workflow.

**Offene Tech-Lead-Entscheidungen und Empfehlung.**
1. *Blockiertes Abo: ganzen Lauf abbrechen oder weiterschreiben?* Empfehlung: Planung bricht mit Exit 2 ab, nichts wird geschrieben (strikt fail-closed, wie im Issue). Für Staging (1 blockiertes Test-Abo) Zusatzoption `--blockierte-auslassen`, die genau diese Dateien liegen lässt und den Rest schreibt; Nachzählung zeigt den Rest dann ausdrücklich. Prod hat 0 Blockierte, braucht die Option nicht. Alternative: das Staging-Testabo vorher von Hand reparieren (Tabelle neu speichern); aufwändiger.
2. *`compare_presets.json` nur Felder entfernen oder Datei ganz löschen?* Empfehlung: nur Felder entfernen (Auftrag, ADR-0101, reversibel). Löschen der Altdatei wäre eine eigene Entscheidung (toter Bestand, Sicherung besteht), nicht in diesem Ticket.
3. *Dienst stoppen?* Empfehlung nein: flock plus Inhaltsvergleich genügt (Briefings haben Sperrdateien), bei "seit der Planung geändert" einfach wiederholen.
4. *Skriptname*: `migrate_3277_altfelder.py` (Issue-Vorgabe, Entfernung stammt aus #3277), nicht `migrate_3351`.
5. *Dauerwächter*: Empfehlung ja, als Prod-Selftest-Check (additiv, fail-open bei Nicht-Prüfbarkeit), zusätzlich einmalige Nachzählung nach 3 bis 7 Tagen (Wiedervorlage im Issue; Workflow selbst bleibt bis Prod-Lauf + Nachzählung 0 offen, Issue-Schluss erst nach Wiederholungszählung).
6. *#3102 schließen?* Empfehlung: nur als Nachweis im Issue kommentieren, Abschluss erst, wenn die übrigen Punkte (Orakel-Löschung, Import-Sperre, Prüfkatalog grün) geprüft sind.
7. *Frontend- oder Go-Strip als Zusatzschutz* (Go verwirft Altfelder beim Speichern)? Empfehlung nein: zusätzliche Go-Schicht überlappt mit #3277/#3298-Sperren, Wächter + Nachzählung reichen; falls die Nachzählung später Wiederkehr zeigt, dann Go-Strip als Folge-Issue.

**Scoring-Empfehlung.** Komplexität gering bis mittel (bekanntes Muster, fertige Hilfsfunktionen `schreiben`/`altfelder_entfernen`), Risiko mittel (Produktivdaten, aber Altfelder wirkungslos, Sicherung je Nutzer, Prod hat keine Blockierten). Vorschlag: Scope klein/Datenlauf, Spec-Pflicht ja (kurze Spec mit 6 bis 8 ACs), Phase-Adversary mit Mutations-Gegenprobe auf die Fail-closed-Bedingung (Mutation "Bedingung entfernt" muss einen Test rot machen) und auf Sicherung vor Schreiben. Ausführung (Staging, Prod, Nachzählung) gehört in `/70-deploy`-Lauf, nicht in den Entwickler-Schritt.
