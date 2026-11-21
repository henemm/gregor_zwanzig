---
entity_id: feat_3157_migration_placements
type: feature
created: 2026-11-21
updated: 2026-11-21
status: approved
version: "1.0"
workflow: feat-3157-migration-was-steht-wo
tags: [issue-3157, epic-3122, scheibe-b6, migration, placements, was-steht-wo]
---

# Migration der Bestands-Abos ins Tabellenformat `placements` (B6, Schritte 1 bis 3)

## Approval

- [x] Approved
- PO-Freigabe 2026-11-21 (Stichwort „approved“), einschließlich der zwei bewussten Ausgabe-Änderungen `nur_text_folgt_html` (13 Trips) und `reihenfolge_wie_sms` (1 Trip, 3 Orts-Vergleiche) und der Abspaltung von Schritt 4 nach #3237.

## Purpose

Alle Bestands-Abos (Trips und Orts-Vergleiche), die noch im Altformat vorliegen, bekommen einmalig die gespeicherte Tabelle `display_config.placements`, berechnet von der einzigen Umrechnung `placements_from_legacy`. Die Freigabe dieser Spec gilt zugleich für die zwei bewussten Ausgabe-Änderungen aus dem Prod-Probelauf (AC-11 der Mutter-Spec).

## Source

- **File:** `scripts/migrate_3157_placements.py` (neu)
- **Identifier:** Skript mit Probelauf (Standard) und `--execute`; Umrechnung ausschließlich `services.placements.placements_from_legacy`
- **Mutter-Spec:** `docs/specs/modules/feat_3122_was_steht_wo.md` (Teil A Nr. 8, AC-11 bis AC-13), ADR-0124

> **Schicht-Hinweis:** Python-Core/Betriebsskript (`scripts/`), Tests unter `tests/`. Die Go-API wird nicht geändert; sie schreibt `placements` per Read-Modify-Write unter derselben Sperrdatei `<id>.json.lock`.
>
> **Trip/Orte-Teilung:** Ein Skript, eine Umrechnung für beide Flächen; kein Pendant nötig.
>
> **Mandantentrennung:** Das Skript arbeitet je Nutzerverzeichnis unter `--root`; der Test nutzt zwei Nutzer. Kein Fallback auf `"default"`.
>
> **Kanäle:** Betroffen ist der Inhalt aller vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) indirekt über `placements`; das Skript selbst ändert keine Kanallogik.

## Scope

- **Drin:** Migrationsskript `scripts/migrate_3157_placements.py` (Probelauf, Sicherung, Schreiben), Test `tests/test_3157_migration_placements.py`, Nachträge in der Mutter-Spec (AC-11 mit Prod-Zahlen, Nr. 8), Eintrag im Betriebshandbuch, Prod-Lauf nach dem Deploy.
- **Nicht drin:** Altfelder aus den Daten entfernen, Lese-Adapter und Differenz-Orakel löschen, Import-Sperre (Kind-Issue #3237); Frontend.

## Definition of Done

- Alle Tests aus dem Test Plan grün, Adversary-Verdict VERIFIED.
- Nach dem Prod-Deploy: Probelauf und `--execute` als `claude-gregor` gelaufen, alle 21 Prod-Abos tragen `placements`, ein zweiter Probelauf meldet kein Abo mehr als „wird umgerechnet“, Sicherungen liegen vor, Prod-Selftest Exit 0.
- Briefings ändern sich nur in den zwei freigegebenen Arten (`nur_text_folgt_html`, `reihenfolge_wie_sms`).

## Estimated Scope

- **LoC:** ca. +500 (Skript ~250, Test ~250)
- **Files:** 4 (Skript, Test, Mutter-Spec, Betriebshandbuch)
- **Effort:** medium (Risiko mittel: schreibt Prod-Daten, abgesichert durch Probelauf, Sicherung, Merge, Idempotenz)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.placements.placements_from_legacy` | function | einzige Umrechnung, liefert `placements`, Änderungsarten, `show_stability_off` |
| `services.placements.read_placements` | function | erkennt Abos, die schon `placements` tragen |
| `scripts/migrate_2792_profil_ampel.py` (`schreiben`) | module | Muster: Sperre, atomares Schreiben, Inhaltsvergleich |
| `scripts/migrate_3196_trip_tempo.py` | module | Muster: `--root`, `--backup-dir`, `--execute`, Probelauf |
| `file_lock.exclusive_lock` | function | Sperre über `<id>.json.lock`, gleiche Datei wie Go-PUT |
| `src/app/loader.py` / Lade-Wege der Tabellen-Ansicht | module | Abo laden für die Umrechnung |
| ADR-0101, ADR-0083, ADR-0124 | ADR | Read-Modify-Write mit Merge, Datenmigration, Tabelle |

## Implementation Details

- **Aufruf:** `migrate_3157_placements.py --root <users-Verzeichnis> [--backup-dir <Pfad>] [--execute]`. Ohne `--execute` wird nichts geschrieben. Standard für `--backup-dir`: `<root>/../.backups`.
- **Erfassung:** je Nutzerverzeichnis alle `briefings/<id>.json`; Fläche aus `kind` (`vergleich` = Orte, sonst Trip).
- **Bericht je Abo:** Nutzer, Abo-Id, Fläche (Trip/Orte), Status (`hat schon placements` | `wird umgerechnet` | `Fehler`), gefundene Änderungsarten mit Anzahl. Am Ende Summen je Status und je Änderungsart.
- **Schreiben (nur mit `--execute`):** je Nutzer zuerst eine Sicherung `migrate-3157-<uid>-<timestamp>.tar.gz`; schlägt sie fehl, wird für diesen Nutzer nichts geschrieben. Dann je Abo unter Sperre: Roh-JSON lesen, nur `display_config.placements` setzen, bei `show_stability_off` zusätzlich `report_config.show_stability=false`, atomar zurückschreiben (Temp-Datei und Ersetzen). Es wird nicht über Modelle serialisiert; alle übrigen Felder bleiben inhaltsgleich. Wurde die Datei zwischen Planung und Schreiben geändert, bleibt sie offen und der Lauf endet mit Exit 1.
- **Unangetastet:** Abos mit vorhandenem `placements`.
- **Fail-closed:** Hat ein Abo die Änderungsart `unerklaert` oder scheitert Laden oder Umrechnen, wird für dieses Abo nichts geschrieben, es wird gemeldet, und der Lauf endet mit Exit ungleich 0. Andere Abos werden weiter verarbeitet.
- **Idempotenz:** Ein Abo mit `placements` wird übersprungen; ein zweiter Lauf ändert keine Datei.
- **Altfelder bleiben stehen** (`channel_layouts`, `outlook_metrics`, `show_outlook` usw.), weil Frontend und Validator sie noch lesen.
- **Prod-Ausführung nach dem Deploy:** als Dienstnutzer `claude-gregor`, Datenverzeichnis `/var/lib/gregor`; erst Probelauf, dann `--execute`. Eintrag im Betriebshandbuch `docs/reference/operations_playbook.md` (Abschnitt nach dem Trip-Tempo-Eintrag #3196). Ausgabe nicht weltlesbar ablegen.

## Expected Behavior

- **Input:** Datenverzeichnis mit Nutzern und Abo-Dateien, Optionen.
- **Output:** Bericht je Abo und Summen; Exit 0, wenn kein Abo offen oder fehlerhaft ist, sonst Exit ungleich 0.
- **Side effects:** nur mit `--execute`: je Nutzer eine Sicherung, je umgerechnetem Abo `display_config.placements` (und ggf. `report_config.show_stability=false`).

## Acceptance Criteria

- **AC-1:** Given Bestandsdaten zweier Nutzer mit Altfeld-Abos (Trips und Orte) / When das Skript ohne `--execute` läuft / Then bleibt jede Datei und jedes Verzeichnis byteweise unverändert, und der Bericht nennt je Abo Nutzer, Abo-Id, Fläche, Status und die gefundenen Änderungsarten mit Anzahl.
  - Test: Dateibaum vor und nach dem Probelauf vergleichen, Berichtszeilen je Abo prüfen.

- **AC-2:** Given Bestandsdaten zweier Nutzer / When das Skript mit `--execute` läuft / Then liegt für jeden Nutzer mit umzurechnenden Abos vor dem ersten Schreiben eine lesbare tar.gz-Sicherung seiner Abo-Dateien, und schlägt die Sicherung fehl, wird für diesen Nutzer nichts geschrieben.
  - Test: Sicherung öffnen und mit Originalen vergleichen; Sicherungsverzeichnis nicht beschreibbar machen, Dateien bleiben unverändert.

- **AC-3:** Given ein Abo im Altformat mit allen üblichen Feldern / When es migriert wird / Then ist nur `display_config.placements` neu (bei `show_stability_off` zusätzlich `report_config.show_stability=false`), alle übrigen Felder einschließlich der Altfelder sind inhaltsgleich zum Zustand vorher.
  - Test: JSON vor und nach laden, Schlüssel für Schlüssel vergleichen, erlaubte Differenz genau diese Stellen.

- **AC-4:** Given ein Abo im Altformat / When es migriert wird / Then ist das gespeicherte `placements` gleich dem Ergebnis von `placements_from_legacy` für dieses Abo, und das Skript enthält keine eigene Umrechnungslogik.
  - Test: gespeicherte Tabelle gegen die Umrechnung derselben Abo-Daten vergleichen, Trip und Orte.

- **AC-5:** Given ein Trip mit `show_outlook: false` / When er migriert wird / Then ist in `placements` der 3-Tages-Ausblick aus, die Großwetterlage ist aus (`report_config.show_stability` ist `false`), und das Briefing zeigt beides nicht.
  - Test: Abnahmefall aus Issue #3157, gespeicherte Tabelle und `show_stability` prüfen, Briefing über den echten Renderer erzeugen.

- **AC-6:** Given ein Orte-Abo mit `outlook_enabled: false` / When es migriert wird / Then ist der 3-Tages-Ausblick in `placements` aus, und das Orte-Briefing zeigt keinen Ausblick.
  - Test: gespeicherte Tabelle prüfen, Orte-Briefing erzeugen.

- **AC-7:** Given ein Abo, das schon `placements` trägt / When das Skript schreibend läuft / Then bleibt seine Datei byteweise unverändert und der Bericht nennt es als „hat schon placements“.
  - Test: Datei vor und nach `--execute` vergleichen, Berichtsstatus prüfen.

- **AC-8:** Given Daten, die ein erster schreibender Lauf bereits migriert hat / When das Skript ein zweites Mal schreibend läuft / Then ändert sich keine Datei, es entsteht keine neue Sicherung mit Inhalt, und der Exit-Code ist 0.
  - Test: Dateibaum nach erstem und zweitem Lauf vergleichen.

- **AC-9:** Given Bestandsdaten von Nutzer A und Nutzer B mit unterschiedlichen Abos / When das Skript schreibend läuft / Then enthält kein Abo und keine Sicherung des einen Nutzers Daten des anderen, und jede Sicherung enthält nur Dateien ihres Nutzers.
  - Test: Abo-Ids und Inhalte je Nutzer vor und nach prüfen, Archivinhalte je Nutzer prüfen.

- **AC-10:** Given ein Abo mit der Änderungsart `unerklaert` und ein Abo, dessen Datei nicht ladbar ist, neben einem gesunden Abo / When das Skript schreibend läuft / Then bleiben die beiden Problem-Abos unverändert, sie stehen mit Grund im Bericht, das gesunde Abo wird migriert, und der Exit-Code ist ungleich 0.
  - Test: drei Dateien vorbereiten, Dateivergleich, Exit-Code und Bericht prüfen.

- **AC-11:** Given die 21 Prod-Abos nach dem Deploy / When das Skript als Dienstnutzer erst im Probelauf und dann mit `--execute` läuft / Then tragen danach alle 21 Abos `placements`, die Briefings sind bis auf die zwei freigegebenen Änderungsarten unverändert (`nur_text_folgt_html`, `reihenfolge_wie_sms`), und ein zweiter Probelauf meldet kein Abo mehr als „wird umgerechnet“.
  - Test: Prod-Lauf nach Deploy (Betriebsnachweis): Bericht mit 21 Abos, danach Selftest und Stichproben-Briefing; kein Automatiktest.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/test_3157_migration_placements.py`, keine Mocks, echte JSON-Dateien in einem Temp-Verzeichnis mit zwei Nutzern (je ein Trip und ein Orte-Abo im Altformat, dazu Sonderfälle):

- [ ] Test 1 (AC-1): GIVEN zwei Nutzer mit Altfeld-Abos WHEN Probelauf THEN Dateibaum unverändert und Bericht nennt je Abo Änderungsarten.
- [ ] Test 2 (AC-2): GIVEN Altfeld-Abos WHEN `--execute` THEN Sicherung je Nutzer vorhanden und gleich den Originalen; bei nicht beschreibbarem Sicherungsverzeichnis keine Änderung.
- [ ] Test 3 (AC-3): GIVEN Abo mit vielen Feldern WHEN migriert THEN nur `placements` (und ggf. `show_stability`) verändert.
- [ ] Test 4 (AC-4): GIVEN Trip und Orte WHEN migriert THEN gespeichert gleich `placements_from_legacy`.
- [ ] Test 5 (AC-5, AC-6): GIVEN Trip `show_outlook: false` und Orte `outlook_enabled: false` WHEN migriert THEN Ausblick aus, Großwetterlage aus.
- [ ] Test 6 (AC-7): GIVEN Abo mit `placements` WHEN `--execute` THEN Datei unverändert.
- [ ] Test 7 (AC-8): GIVEN migrierter Bestand WHEN zweiter Lauf THEN keine Änderung, Exit 0.
- [ ] Test 8 (AC-9): GIVEN zwei Nutzer WHEN `--execute` THEN kein Datenübertrag, Sicherungen getrennt.
- [ ] Test 9 (AC-10): GIVEN unerklärter und kaputter Fall plus gesundes Abo WHEN `--execute` THEN nur das gesunde Abo geändert, Exit ungleich 0.

### Betriebsnachweis (kein Automatiktest)

- [ ] AC-11: Prod-Probelauf und `--execute` nach dem Deploy als `claude-gregor`, Bericht mit 21 Abos, zweiter Probelauf ohne „wird umgerechnet“, danach Prod-Selftest.

## Out of Scope

- Entfernen der Altfelder aus den Daten, Lese-Adapter, Differenz-Orakel (`tests/helpers/kanal_liste_orakel.py` samt Tests), Import-Sperre und Umstellung der Aufrufer in `api/routers/validator.py` und `channel_layout.py`: Kind-Issue #3237 (setzt #3218, Validator-Soll auf `placements`, voraus). Die Mutter-Spec (Teil A Nr. 8) wird entsprechend nachgetragen.
- Frontend-Änderungen; das Frontend liest die Altfelder weiter.

## Known Limitations

- Altfelder bleiben nach der Migration in den Daten stehen, bis #3237 sie entfernt; `placements` ist dann maßgeblich, die Altfelder sind redundant.
- Drei Fälle aus #3164 Abschnitt A haben keine eigene Änderungsart und würden in `unerklaert` landen; in den Prod-Daten kommt keiner vor (Probelauf 2026-11-21: 0 unerklärt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (keine neue Entscheidung)
- **Rationale:** Die Migration setzt Nr. 8 der Mutter-Spec und die Folgepflichten aus ADR-0124 um. Neu ist nur die zeitliche Verschiebung der Altfeld-Entfernung (#3237), die in der Mutter-Spec datiert nachgetragen wird.

## Changelog

- 2026-11-21: Initial spec created (Scheibe B6, Schritte 1 bis 3; Altfeld-Entfernung nach #3237 verschoben).
