---
entity_id: feat_3351_altfelder_datenlauf
type: module
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: feat-3351-altfelder-datenlauf
tags: [was-steht-wo, placements, datenlauf, migration, altfelder, epic-3122]
---

# Was steht wo B6b-5: Datenlauf Altfelder entfernen (#3351)

## Approval

- [ ] Approved

## Purpose

Seit #3277 liest und liefert das Backend die zehn Altfelder (`ALTFELDER` in `src/app/loader.py`) nicht mehr, sie liegen aber noch in gespeicherten Abos (Trip und Ortsvergleich) und in der toten Altdatei `compare_presets.json`. Ein einmaliges Skript `scripts/migrate_3277_altfelder.py` entfernt sie je Nutzer per Read-Modify-Write mit Merge (ADR-0101), mit Sicherung, Dateisperre und fail-closed-Schutz für Abos ohne Tabelle `placements`. Für Nutzer ändert sich nichts Sichtbares; die Zielzahl "0 Altfelder im Bestand" wird belegt.

## Source

- **File:** `scripts/migrate_3277_altfelder.py`
- **Identifier:** `planen`, `zaehlen`, `main` (Strukturvorbild `scripts/migrate_2794_preset_horizons.py`; `schreiben` aus `scripts/migrate_2792_profil_ampel.py`)

> **Schicht-Hinweis:** Nur Skript, Tests und Doku (Betriebs-Playbook). Kein Eingriff in Go, Frontend, Core-Logik oder gesperrte Hook-Dateien (kein Dauerwächter im Prod-Selftest). Namensliste und Entfernlogik kommen per Import aus `app.loader` (`ALTFELDER`, `altfelder_entfernen`); das Skript enthält keine Altnamen-Literale, damit `tests/test_altfeld_namen_sperre.py` grün bleibt.

> **Querschnitts-Prüfpunkte:**
> - **Mandantentrennung:** Der Nutzer ergibt sich aus dem Ordner unter der Datenwurzel, nie ein Fallback auf `"default"`. Sicherung und Bericht getrennt je Nutzer; Test mit zwei Nutzern.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS unberührt; die Altfelder sind seit #3277 wirkungslos, die Ausgabe entsteht aus `placements`.
> - **Trip/Ortsvergleich-Teilung:** keine neue Komponente; beide Abo-Arten laufen durch dieselbe Skriptlogik.
> - **Datenschutz:** Spec, Issue und PR nennen nur aggregierte Zahlen (öffentliches Repo), keine Abo-IDs, keine personenbezogenen Daten.

## Estimated Scope

- **LoC:** Skript ca. +150, Tests ca. +290, Playbook ca. +30
- **Files:** 3 neu (Skript, Test, Spec), 1 geändert (`docs/reference/operations_playbook.md`)
- **Effort:** klein bis mittel (bekanntes Muster, Hilfsfunktionen vorhanden; Ausführung auf Staging und Prod gehört in den Deploy-Lauf)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3277_altfelder_entfernen` | Spec | Backend verwirft/liefert Altfelder nicht mehr; Quelle von `ALTFELDER` |
| `feat_3297_trip_pfad_ohne_altfelder`, `feat_3298_altfeld_typen_sperre` | Spec | Frontend schreibt keine Altfelder mehr (live) |
| `feat_3122_was_steht_wo` | Spec | Epic-Spec, Teil A Nr. 8 "Bestand folgt #3351" |
| `app.loader` (`ALTFELDER`, `altfelder_entfernen`) | Python | Namensliste und Entfernlogik, alle drei Ebenen |
| `scripts/migrate_2792_profil_ampel.py` | Skript | `schreiben()`: Sperre, Inhaltsvergleich, atomares Schreiben |
| `scripts/migrate_2794_preset_horizons.py` | Skript | Strukturvorbild (Sicherung je Nutzer, Exit-Codes) |
| `services.file_lock` | Python | `exclusive_lock`, dieselbe Sperre wie der Go-Schreiber (ADR-0083) |
| `tests/test_altfeld_namen_sperre.py` | Test | Scannt `scripts/`; Skript darf keine Altnamen-Literale tragen |
| `tests/tdd/test_migration_2792_profil_ampel.py`, `test_migration_vorlagen_horizonte.py` | Test | Vorbild echte tmp-Datenbäume, Skript als Subprozess |
| ADR-0101, ADR-0124 | ADR | Merge statt Replace; `placements` einzige Quelle |
| Issues #3351, #3102, #3009 | Issues | Paket, Nachweis-Empfänger, Abnahme mit Wiederholungszählung |

## Scope

### Entscheidungen (Tech Lead, verbindlich)

- **Ebenen:** je Datei werden oberste Ebene, `report_config` und `display_config` geprüft (wie `altfelder_entfernen`). Gilt für `briefings/*.json` (Trip und Vergleich) jedes Nutzers.
- **`compare_presets.json`** (tote Altdatei): nur die Felder je Eintrag werden entfernt; die Datei wird nicht gelöscht, die Tabellenprüfung entfällt.
- **Probelauf ist Standard:** ohne Schalter nur Bericht je Feld, Abo-Art und Nutzeranzahl, aggregiert, ohne Schreiben.
- **`--ausfuehren`:** zuerst Sicherung je Nutzer (tar.gz unter `.backups` der Datenwurzel), dann Read-Modify-Write mit Merge: nur Altfelder entfernen, alles andere unverändert. Atomar, unter Datei-Sperre wie der Go-Schreiber, mit Inhaltsvergleich seit der Planung (geändert ⇒ neu planen oder überspringen).
- **Idempotent:** ein zweiter Lauf ändert nichts.
- **Fail-closed:** ein Abo mit Altfeldern, aber ohne `placements.rows` oder ohne `placements.outlook_reports`, gilt als BLOCKIERT. Ohne Schalter bricht der Lauf vor jedem Schreiben mit Exit 2 ab. Mit `--blockierte-auslassen` (für Staging) bleiben blockierte Abos unverändert und werden berichtet.
- **`--nachzaehlen`:** rein lesend; Exit 1, wenn ein Altfeld übrig ist; blockierte und ausgelassene Abos werden separat ausgewiesen.
- **Datenwurzel** als Argument; Lauf als Dienstnutzer (`sudo -n -u claude-gregor`). Ablauf im Playbook `docs/reference/operations_playbook.md`.
- **Reihenfolge:** erst Staging (`--blockierte-auslassen`, der blockierte Fall wird im Issue aggregiert benannt), dann Prod (fail-closed). Danach je eine Nachzählung mit 0, auf Staging außer bei ausgelassenen Abos.
- **Nachweis:** Kommentar mit aggregierten Zahlen an #3351 und #3102. #3102 wird nicht geschlossen (weitere Punkte offen). (Erledigt, #3102: Abschluss Phase 3 nach diesem Lauf.)
- **Kein Dauerwächter** im Prod-Selftest in diesem Paket (gesperrte Hook-Dateien); stattdessen Abschnitt Known Limitations.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/migrate_3277_altfelder.py` | CREATE | Planen, Bericht, Sicherung, Schreiben, `--nachzaehlen`, `--blockierte-auslassen` |
| `tests/tdd/test_migration_3277_altfelder.py` | CREATE | Kern-Tests mit echten tmp-Datenbäumen, Skript als Subprozess |
| `docs/reference/operations_playbook.md` | MODIFY | Abschnitt "Altfelder entfernen (#3351)" mit Lauf-Rezept und Nachzählung |
| `docs/specs/modules/feat_3351_altfelder_datenlauf.md` | CREATE | diese Spec |

### Estimated Changes

- Files: 3 neu, 1 geändert
- LoC: Produktion ca. +150, Tests ca. +290, Doku ca. +30

### Nicht in dieser Spec

- Dauerwächter im Prod-Selftest (gesperrte Hook-Dateien); Go-seitiges Entfernen von Altfeldern (Folge-Issue nur, wenn die Wiederholungszählung Wiederkehr zeigt).
- Löschen der Datei `compare_presets.json` (eigene Entscheidung).
- Schließen von #3102 und Epic #3122. (Erledigt, #3102: Abschluss Phase 3.)

## Implementation Details

1. **`planen(root)`:** je Nutzerordner (Ordner mit `.` oder `_` am Anfang übersprungen) alle `briefings/*.json` (ohne `.lock`) und `compare_presets.json` (Array). Je Datei laden (unlesbar ⇒ BLOCKIERT, berichtet, nie stumm), Altfelder je Ebene mit `ALTFELDER` suchen, je Feld und Abo-Art zählen. Neues Objekt per `altfelder_entfernen(copy.deepcopy(obj))`; Plan nur bei tatsächlicher Änderung. Container, die danach leer wären, bleiben als leeres Objekt stehen.
2. **Fail-closed:** gilt nur für `briefings/*.json`. Hat ein Abo Altfelder, aber `placements.rows` oder `placements.outlook_reports` ist keine Liste oder `placements` fehlt, wird es als BLOCKIERT berichtet und nicht geplant. Ohne `--blockierte-auslassen`: Exit 2, nichts geschrieben. Abos ohne Altfelder sind nie betroffen.
3. **Ausführen:** alle Sicherungen je Nutzer vor dem ersten Schreiben (Fehler dort ⇒ nichts geschrieben, Exit 1), dann `schreiben(plaene)` aus 2792 (Sperre, Inhaltsvergleich, atomar, Rechte erhalten). Bei "seit der Planung geändert" wird die Datei nicht überschrieben, Exit 1, Wiederholung.
4. **`zaehlen(root)`:** liest dieselbe Dateimenge, zählt je Feld und Ebene, weist BLOCKIERTE und ausgelassene Abos getrennt aus; `--nachzaehlen` nutzt sie, Exit 1 bei Rest.
5. **Exit-Codes:** 0 fertig oder nichts zu tun, 1 offene Dateien, Fehler oder Altfeld übrig, 2 blockiert (fail-closed).
6. **Format-Hinweis:** neu geschriebene Dateien tragen Python-Format (`indent=2`, `ensure_ascii=False`), semantisch gleich.
7. **Playbook:** Abschnitt mit den Befehlen für Staging (Probelauf, `--ausfuehren --blockierte-auslassen`, Nachzählung) und Prod (Probelauf, `--ausfuehren`, Nachzählung), jeweils als `sudo -n -u claude-gregor uv run python3 scripts/migrate_3277_altfelder.py --root <Datenwurzel>`; Hinweis, dass Berichte mit Abo-IDs nicht in Issues oder PRs gehören.

## Expected Behavior

- **Input:** Datenwurzel mit Nutzerordnern; Schalter `--ausfuehren`, `--blockierte-auslassen`, `--nachzaehlen`.
- **Output:** Bericht (je Feld, Abo-Art, Nutzeranzahl, aggregiert), Exit-Code. Nach dem Lauf enthält kein Abo und kein Eintrag in `compare_presets.json` mehr eines der zehn Altfelder, außer bewusst ausgelassene blockierte Abos (Staging).
- **Side effects:** je Nutzer eine Sicherung unter `.backups`; betroffene Dateien neu im Python-Format. Keine sichtbare Änderung in Editor, Mail oder Kanälen (DE und EN).

## Acceptance Criteria

- **AC-1:** Given ein Datenbaum mit zwei Nutzern, deren Abos Altfelder auf oberster Ebene, in `report_config` und in `display_config` tragen / When das Skript im Standardmodus (Probelauf) läuft / Then meldet es je Feld, Abo-Art und Nutzeranzahl aggregiert, ändert aber keine Datei und legt keine Sicherung an.
  - Test: Subprozess-Lauf auf tmp-Baum, Dateiinhalt und Änderungszeit vor und nach dem Lauf gleich, Bericht nennt alle drei Ebenen.

- **AC-2:** Given Abos mit Altfeldern auf allen drei Ebenen (Trip und Vergleich) mit vorhandener Tabelle `placements` / When das Skript mit `--ausfuehren` läuft / Then enthält danach keine Datei mehr eines der zehn Altfelder auf irgendeiner Ebene.
  - Test: Subprozess-Lauf `--ausfuehren`, danach Durchsicht aller Ebenen jeder Datei beider Nutzer über die importierte Namensliste.

- **AC-3:** Given Abos mit Altfeldern und vielen weiteren Feldern (Orte, Zeiten, Empfänger, `placements`, übrige Konfiguration) / When `--ausfuehren` die Altfelder entfernt / Then bleiben alle anderen Felder inhaltlich unverändert erhalten, und ein Container, der nur Altfelder trug, bleibt als leeres Objekt stehen.
  - Test: Vergleich der geladenen JSON-Objekte vorher/nachher abzüglich Altfelder; Fall mit Nur-Altfeld-Container.

- **AC-4:** Given ein Datenbaum mit Abos von zwei Nutzern / When `--ausfuehren` läuft / Then liegt je Nutzer eine eigene Sicherung (tar.gz unter `.backups` der Datenwurzel) mit dessen Originaldateien vor dem ersten Schreiben, und die Dateien des einen Nutzers stehen nicht in der Sicherung des anderen.
  - Test: Sicherungen öffnen, Originalinhalt mit Altfeldern vorhanden, Nutzertrennung geprüft; bei erzwungenem Sicherungsfehler bleibt jede Datei unverändert.

- **AC-5:** Given ein Abo mit Altfeldern, aber ohne `placements.rows` oder ohne `placements.outlook_reports` (neben unkritischen Abos) / When das Skript ohne `--blockierte-auslassen` mit `--ausfuehren` läuft / Then bricht es mit Exit 2 ab, nennt das Abo als BLOCKIERT und schreibt keine einzige Datei und keine Sicherung.
  - Test: Subprozess-Lauf, Exit 2, alle Dateien byte-gleich, keine Sicherung; je ein Fall für fehlende `rows`, fehlende `outlook_reports`, fehlendes `placements`.

- **AC-6:** Given derselbe Baum mit blockiertem Abo / When das Skript mit `--ausfuehren --blockierte-auslassen` läuft / Then bleibt das blockierte Abo byte-gleich, alle übrigen Abos sind bereinigt, der Bericht weist das blockierte Abo aus, und Exit ist 0.
  - Test: Subprozess-Lauf; blockierte Datei byte-gleich, übrige ohne Altfelder, Bericht nennt die Anzahl blockierter Abos.

- **AC-7:** Given ein bereits bereinigter Datenbaum / When das Skript erneut mit `--ausfuehren` läuft / Then ändert es keine Datei (gleiche Bytes, gleiche Änderungszeit), meldet "Nichts zu tun" und beendet sich mit Exit 0.
  - Test: zweiter Lauf auf tmp-Baum, Dateiinhalt und Änderungszeit unverändert.

- **AC-8:** Given ein Datenbaum / When `--nachzaehlen` läuft / Then ändert es nichts, endet mit Exit 1, solange irgendwo ein Altfeld steht, mit Exit 0 bei 0 Altfeldern, und weist blockierte und ausgelassene Abos getrennt aus.
  - Test: Subprozess-Lauf vor und nach der Bereinigung sowie mit ausgelassenem Abo; Exit-Codes und getrennte Ausweisung geprüft, Dateien unverändert.

- **AC-9:** Given Nutzerordner mit `compare_presets.json` (Array, Einträge mit Altfeldern) / When `--ausfuehren` läuft / Then sind die Altfelder je Eintrag entfernt, die Datei und alle übrigen Felder und Einträge bleiben erhalten, und die Tabellenprüfung gilt für diese Datei nicht.
  - Test: Eintrag ohne `placements` in `compare_presets.json` wird bereinigt (kein Exit 2), Anzahl Einträge und übrige Felder gleich.

- **AC-10:** Given eine Datei, die sich zwischen Planung und Schreiben ändert (gleichzeitiger Schreiber) / When das Skript schreiben will / Then überschreibt es die geänderte Datei nicht, meldet sie als seit der Planung geändert und beendet sich mit Exit 1; ein Wiederholungslauf bereinigt sie.
  - Test: Datei zwischen Planung und Schreiben verändern (Test-Eingriff in `schreiben` über echten Dateizugriff, kein Mock der Entfernlogik); geänderter Inhalt bleibt, Wiederholung bereinigt.

- **AC-11:** Given der Quelltext des Skripts / When die Altnamen-Sperre `tests/test_altfeld_namen_sperre.py` läuft / Then bleibt sie grün, weil das Skript die Namen nur über `from app.loader import ALTFELDER` bezieht und keinen Namen als Literal enthält.
  - Test: `tests/test_altfeld_namen_sperre.py` grün mit dem neuen Skript (`# doc-compliance-test`); Skript-Test prüft, dass die Entfernung die importierte Liste vollständig abdeckt (jedes der zehn Felder je Ebene).

- **AC-12:** Given der abgeschlossene Lauf auf Staging und Prod / When die Nachzählung läuft / Then zeigt Prod 0 Altfelder, Staging 0 (außer bewusst ausgelassenen blockierten Abos, aggregiert benannt), und ein Kommentar mit diesen aggregierten Zahlen steht an #3351 und #3102, ohne Abo-IDs.
  - Test: `--nachzaehlen` gegen Staging und Prod als Dienstnutzer im Deploy-Lauf (Exit 0 bzw. nur ausgelassene Abos), Zahlen im Issue-Kommentar belegt; #3102 bleibt offen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN zwei Nutzer mit Altfeldern auf drei Ebenen WHEN Probelauf THEN Bericht aggregiert, nichts geschrieben, keine Sicherung (AC-1)
- [ ] Test 2: GIVEN Trip- und Vergleichs-Abos mit Tabelle WHEN `--ausfuehren` THEN keine Altfelder auf allen drei Ebenen (AC-2)
- [ ] Test 3: GIVEN Abos mit vielen Fremdfeldern WHEN `--ausfuehren` THEN alle anderen Felder erhalten, Nur-Altfeld-Container bleibt leer stehen (AC-3)
- [ ] Test 4: GIVEN zwei Nutzer WHEN `--ausfuehren` THEN Sicherung je Nutzer vor dem ersten Schreiben, getrennt; Sicherungsfehler ⇒ nichts geschrieben (AC-4)
- [ ] Test 5: GIVEN blockiertes Abo (fehlende `rows`, `outlook_reports`, `placements`) WHEN `--ausfuehren` ohne Auslassen THEN Exit 2, null Schreibwirkung (AC-5)
- [ ] Test 6: GIVEN blockiertes Abo WHEN `--blockierte-auslassen` THEN blockiertes byte-gleich, Rest bereinigt, Exit 0 (AC-6)
- [ ] Test 7: GIVEN bereinigter Baum WHEN zweiter Lauf THEN keine Änderung, Exit 0 (AC-7)
- [ ] Test 8: GIVEN Baum vor und nach Bereinigung, mit ausgelassenem Abo WHEN `--nachzaehlen` THEN Exit 1 bzw. 0, getrennte Ausweisung, rein lesend (AC-8)
- [ ] Test 9: GIVEN `compare_presets.json` mit Altfeldern WHEN `--ausfuehren` THEN Felder entfernt, Datei und Rest erhalten, keine Tabellenprüfung (AC-9)
- [ ] Test 10: GIVEN Datei ändert sich zwischen Planung und Schreiben WHEN Schreiben THEN nicht überschrieben, Exit 1, Wiederholung bereinigt (AC-10)
- [ ] Test 11: GIVEN neues Skript WHEN `tests/test_altfeld_namen_sperre.py` THEN grün, Entfernung deckt alle zehn Namen je Ebene ab (AC-11)

Test-Politik: kein Mock-Theater; echte tmp-Datenbäume, Skript als Subprozess, Vorbild `test_migration_2792_profil_ampel.py` und `test_migration_vorlagen_horizonte.py`. Fixtures dürfen Altnamen nennen (Tests werden von der Sperre nicht gescannt). Adversary-Mutationen (per String-Ersetzung mit externer Sicherungskopie): fail-closed-Bedingung entfernen und Sicherung vor Schreiben entfernen müssen je einen Test rot machen. AC-12 ist ein Betriebsnachweis im Deploy-Lauf.

## Definition of Done

- AC-1 bis AC-11 durch Kern-Tests grün (benannte Testdatei, `tests/test_altfeld_namen_sperre.py`); keine Altnamen-Literale im Skript.
- Adversary mit Mutations-Gegenprobe auf fail-closed und Sicherung-vor-Schreiben ohne offenes Finding.
- Playbook-Abschnitt "Altfelder entfernen (#3351)" vorhanden.
- Staging-Lauf (`--blockierte-auslassen`), danach Prod-Lauf (fail-closed), je eine Nachzählung mit 0 (Staging außer ausgelassenen Abos); Zahlen aggregiert, ohne Abo-IDs.
- Nachweis-Kommentar mit Zahlen an #3351 und #3102; #3102 und Epic #3122 bleiben offen. (Erledigt, #3102: Abschluss Phase 3.)
- Wiederholte Nachzählung nach einigen Tagen ist Teil der Abnahme in #3009.
- Keine Änderung an Gate-Konfiguration oder gesperrten Hook-Dateien.

## Known Limitations

- Go reicht `report_config` und `display_config` als Maps durch (`internal/handler/trip.go`, `mergeConfigMap`); alte Browser-Tabs, die vor dem Deploy von #3297/#3298 geladen wurden, oder externe API-Clients können Altfelder neu erzeugen. Die Felder sind wirkungslos, verletzen aber die Zielzahl 0.
- Es gibt keinen Dauerwächter im Prod-Selftest; die Nachzählung wird nach einigen Tagen Betrieb wiederholt (Teil der Abnahme in #3009). Zeigt sie Wiederkehr, folgt ein eigenes Issue (Go-seitiges Entfernen oder Selftest-Check).
- Auf Staging bleibt ein blockiertes Test-Abo bewusst unverändert und wird in der Nachzählung separat ausgewiesen.
- `compare_presets.json` wird nur bereinigt, nicht gelöscht; die Datei ist toter Bestand ohne Laufzeit-Leser.
- Neu geschriebene Dateien tragen Python-Format; semantisch gleich, aber die Bytes unterscheiden sich vom Go-Format.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0101, ADR-0124)
- **Rationale:** ADR-0101 verlangt für Bestandsdaten Read-Modify-Write mit Merge statt Replace, mit Sicherung vorab; das Skript entfernt nur die Altfelder und erhält alles andere. ADR-0124 hat `placements` zur einzigen Quelle erklärt, daher werden Abos ohne Tabelle nie angefasst (fail-closed), sonst gingen Metrik-Wahl und Ausblick verloren. Keine frühere Entscheidung wird berührt.

## Changelog

- 2026-11-25: Initial spec created (B6b-5, Issue #3351, Epic #3122).
