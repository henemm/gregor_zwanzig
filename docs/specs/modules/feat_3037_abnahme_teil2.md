---
entity_id: feat_3037_abnahme_teil2
type: feature
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: abnahme-3037-teil2
tags: [was-steht-wo, abnahme, mail-pruefweg, konfig, soll-ist-bild, "#3037", "#2795"]
---

# Abnahme „Was steht wo“, Fortsetzung: Mail-Prüfweg mit `--konfig` und Messläufe (#3037 Teil 2)

## Approval

- [ ] Approved

## Purpose

Schließt #3037 ab, nachdem die Vorbedingungen (#3419–#3422, #3364) live sind. Der Staging-Mail-Prüfweg lernt, die gespeicherte Konfiguration an den Validator zu reichen (`--konfig`) und einen Vergleich mit nur einem Ort anzulegen (`--orte-anzahl 1`). Damit lässt sich „Einstellung = Ausgabe“ für Trip, drei Orte und einen Ort gegen echt zugestellte Staging-Mails nachweisen. Die übrigen Fortsetzungsziele (Bilder, Elementliste, Katalog, Bildprüfer, Soll/Ist-Bilder an Henning) sind Messläufe und stehen als Abnahmekriterien.

## Source

- **File:** `.claude/tools/staging_mail_pruefen.py`, `tests/tdd/test_staging_mail_pruefweg.py`, `docs/reference/mail_validators.md`
- **Identifier:** `main(transport=…, validator_runner=…)` des Mail-Prüfwegs, Aufräumfunktion `_raeume_auf`

Schicht: Werkzeug-/Test-Schicht (Python-Skript, Kern-Schicht-Test ohne Netz, Referenzdoku). Kein Produktcode, kein Go, keine Änderung an Gate-Konfiguration; autarker Auftrag.

Querschnitt:

- **Mandantentrennung:** Jeder Lauf legt einen eigenen Wegwerf-Nutzer an; der Validator bekommt `--to-contains <Wegwerf-Nutzer>`, die Mail gehört nachweislich dem Nutzer des JSON. Kein Fallback auf `"default"`.
- **Kanäle:** Nachweis für E-Mail; Telegram, SMS und Premium-SMS deckt der Katalog #3047 (Kern-Schicht) ab.
- **Trip/Vergleich-Teilung:** unberührt, keine neue Komponente.

## Estimated Scope

- **LoC:** ~190 (Skript ~70, Test ~120, Doku ~6 Zeilen)
- **Files:** 3
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3037_was_steht_wo_abnahme.md` | Spec | Teil 1, Abschnitt „Fortsetzung #3037“ |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py`, `_soll_aus_konfiguration.py` | Validatoren | `--konfig PFAD`, Compare zusätzlich `--orte`, `--to-contains` |
| `GET /api/trips/{id}`, `GET /api/compare/presets/{id}` | Go-API | gespeichertes Objekt lesen (nur genutzt) |
| `frontend/e2e/wsw-abnahme-3037.staging.spec.ts`, `scripts/soll_ist_bild.py` | Werkzeug | Bilder und Soll/Ist-Zusammensetzung |
| `scripts/elementliste_abgleich.ts` | Skript | `--abnahme --scope wetter/normal`, DE/EN |
| Katalog #3047 (`tests/fixtures/einstellung_gleich_mail/`) | Test | Kern-Schicht ohne `xfail` |
| `mockup-bildpruefer` | Agent | höchstens zwei Runden je Kontext/Breite |
| Staging, Staging-`.env`, Stalwart-Test-Postfach | Umgebung | Messläufe |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/tools/staging_mail_pruefen.py` | MODIFY | `--orte-anzahl {1,3}` (Default 3), `--konfig`: Objekt per GET lesen, `konfig.json` (+ `orte.json`) in `tempfile.mkdtemp` ablegen, Validator mit `--konfig`/`--orte`/`--to-contains`, Löschen im `finally` |
| `tests/tdd/test_staging_mail_pruefweg.py` | MODIFY | Kern-Schicht ohne Netz: Fake-Staging-Rand um GET erweitern, `_Runner` nimmt argv auf |
| `docs/reference/mail_validators.md` | MODIFY | Aufruf des Mail-Prüfwegs mit `--konfig` und `--orte-anzahl` |

Nicht im Scope: Produktcode, Gate-Konfiguration, Backend.

## Implementation Details

1. **`--orte-anzahl {1,3}`:** Anzahl der angelegten Orte des Wegwerf-Vergleichs; Standard 3, ohne die Option unverändertes Verhalten.
2. **`--konfig`:** Nach dem Anlegen wird das gespeicherte Objekt gelesen (Trip: `GET /api/trips/{id}`, Vergleich: `GET /api/compare/presets/{id}`). Ablage in einem Verzeichnis aus `tempfile.mkdtemp` (Modus 0700), Dateien 0600: `konfig.json`, bei Vergleich zusätzlich `orte.json` mit `{"<id>":"<Name>"}`. Der Validator wird mit `--konfig` (Vergleich zusätzlich `--orte`) und `--to-contains <Wegwerf-Nutzer>` aufgerufen. `--orte` wird nie ohne `--konfig` übergeben.
3. **Aufräumen:** Dateien und Verzeichnis werden im `finally` gelöscht, auch bei Validator-Exit ≠ 0 oder Ausnahme; die Wegwerf-Objekte räumt weiterhin `_raeume_auf` ab.
4. **Fehlerfall:** Schlägt das GET fehl, lautet das Ergebnis „umgebung“ und der Exit-Code ist 2 (kein Validator-Aufruf).
5. **Messläufe:** Abnahmelauf Bilder (`ABNAHME_KONTEXTE`, `BILD_DIR`, `.claude/validator.env` für Basic-Auth), Elementliste DE/EN, Staging-Mails Trip/drei Orte/ein Ort (je DE, Trip auch EN), Katalog #3047, Bildprüfer, Soll/Ist-Bilder mit `scripts/soll_ist_bild.py`.

## Test Plan

### Automated Tests (TDD RED, Kern-Schicht ohne Netz)

- [ ] `--konfig` ruft nach dem Anlegen GET auf Trip bzw. Preset und übergibt den Dateipfad als `--konfig` an den Validator.
- [ ] Vergleich mit `--konfig`: `--orte` zeigt auf `orte.json` mit allen angelegten Orten.
- [ ] `--orte-anzahl 1` legt genau einen Ort an; ohne Option drei.
- [ ] Ohne `--konfig` kein `--konfig`/`--orte` im Validator-Aufruf; `--to-contains` mit Wegwerf-Nutzer bei `--konfig`.
- [ ] Verzeichnis 0700, Dateien 0600; nach dem Lauf nicht mehr vorhanden, auch bei Validator-Exit ≠ 0.
- [ ] GET-Fehler ergibt Ergebnis „umgebung“, Exit 2, Wegwerf-Objekte aufgeräumt.

### Messläufe (Live, nur in der Abnahme)

Siehe Acceptance Criteria AC-7 bis AC-12.

## Definition of Done

- [ ] Spec freigegeben; Kern-Schicht-Tests zu AC-1 bis AC-6 vor der Umsetzung rot, danach grün
- [ ] Adversary mit Mutations-Gegenprobe VERIFIED
- [ ] PR mit allen 6 CI-Checks grün, Deploy und Selftest Exit 0
- [ ] Messläufe AC-7 bis AC-11 auf Staging grün bzw. jeder Befund mit Besitzer (Issue)
- [ ] Soll/Ist-Bilder an Henning, Inhalt als Kommentar im Issue (AC-12), danach #3037 geschlossen

## Known Limitations

- Handy nur im 390-px-Fenster; das echte Gerät sieht Henning über das Soll/Ist-Bild.
- Messläufe AC-7 bis AC-12 sind Live-Läufe gegen Staging, nicht Teil der CI.

## Acceptance Criteria

- **AC-1:** Given der Mail-Prüfweg wird mit `--konfig` für einen Trip aufgerufen / When der Wegwerf-Trip angelegt und versendet ist / Then liest das Werkzeug den gespeicherten Trip per API und der Validator läuft mit `--konfig <Datei>` und `--to-contains <Wegwerf-Nutzer>`.
  - Test: Kern-Schicht mit Fake-Staging-Rand prüft die Validator-Argumente (Verhalten des Aufrufs, kein Dateiinhalt-Check).
- **AC-2:** Given der Mail-Prüfweg wird mit `--konfig` für einen Ortsvergleich aufgerufen / When Preset und Orte angelegt sind / Then bekommt der Validator zusätzlich `--orte` mit allen angelegten Orten und `--orte` erscheint nie ohne `--konfig`.
  - Test: Kern-Schicht prüft die Argumente mit und ohne `--konfig`.
- **AC-3:** Given `--orte-anzahl 1` / When der Vergleich angelegt wird / Then entsteht genau ein Ort; ohne die Option entstehen wie bisher drei und das übrige Verhalten bleibt unverändert.
  - Test: Kern-Schicht zählt die angelegten Orte für Standard und `1`.
- **AC-4:** Given die Konfigurationsdateien liegen im Sitzungsordner / When der Lauf endet, auch bei Validator-Exit ungleich 0 / Then sind Verzeichnis (0700) und Dateien (0600) nicht weltlesbar und danach gelöscht.
  - Test: Kern-Schicht prüft Rechte während des Validator-Aufrufs und Abwesenheit danach bei Exit 0 und Exit 1.
- **AC-5:** Given das Lesen des gespeicherten Objekts schlägt fehl / When der Prüfweg läuft / Then lautet das Ergebnis „umgebung“, der Exit-Code ist 2, kein Validator läuft und die Wegwerf-Objekte sind entfernt.
  - Test: Kern-Schicht mit fehlschlagendem GET.
- **AC-6:** Given zwei Läufe nacheinander / When jeder seinen Wegwerf-Nutzer anlegt / Then gehört jede Mail dem Nutzer des jeweiligen JSON (`--to-contains`) und kein Lauf sieht Daten des anderen oder fällt auf `"default"` zurück.
  - Test: Kern-Schicht prüft unterschiedliche `--to-contains` je Lauf; ein Live-Lauf mit zweitem Konto bleibt Teil von AC-9.
- **AC-7:** Given Staging und Prüfkonto / When der Abnahmelauf für trip, orte und ort1 in DE und EN bei 1280 und 390 px läuft / Then ist er grün und für jeden Kontext und jede Breite liegt ein Mockup-Gegenbild vor.
  - Test: Staging-Abnahmelauf (Playwright), Bilder je Kontext/Sprache/Breite.
- **AC-8:** Given der Elementlisten-Abgleich mit `--abnahme --scope wetter/normal` / When er in DE und in EN läuft / Then gibt es 0 Abweichungen ohne Besitzer und der Abschnitt „was-steht-wo“ ist ohne Abweichung (Messung 26.11.: DE und EN je 0 ohne Besitzer).
  - Test: Live-Lauf gegen Staging, beide Sprachen.
- **AC-9:** Given Staging-Mails für Trip, drei Orte und einen Ort / When der Mail-Prüfweg mit `--konfig` läuft / Then endet der Validator jeweils mit Exit 0, im Ein-Ort-Fall heißt der Bereich „Orte“.
  - Test: Echte Staging-Mail im Stalwart-Test-Postfach, Trip auch in EN; der Wegwerf-Nutzer je Lauf wird danach gelöscht (Zweitkonto-Prüfung des Ein-Ort-Abos steckt im Abnahmelauf AC-7).
- **AC-10:** Given der Prüfkatalog #3047 / When die Kern-Schicht läuft / Then sind alle Fälle grün ohne `xfail` (Messung 26.11.: 929 passed, 0 xfail).
  - Test: Kern-Schicht-Lauf der benannten Katalog-Testdateien.
- **AC-11:** Given die Ganzseitenbilder je Kontext und Breite / When `mockup-bildpruefer` sie gegen das Mockup prüft / Then genügen höchstens zwei Runden und jeder Befund ist behoben oder hat ein eigenes Issue.
  - Test: Bildprüfer-Urteil je Kontext/Breite, Befunde im Issue vermerkt.
- **AC-12:** Given alle Messläufe sind grün / When die Soll/Ist-Bilder (Mockup links, Staging rechts, `scripts/soll_ist_bild.py`) an Henning gehen / Then steht ihr Inhalt als Kommentar im Issue #3037 und danach wird #3037 geschlossen.
  - Test: Issue-Kommentar vorhanden, Henning hat die Bilder erhalten, Issue geschlossen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (prüft ADR-0124 ab, setzt keine neue Entscheidung)
- **Rationale:** Reine Werkzeug-Erweiterung des Staging-Mail-Prüfwegs und Messläufe; keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor, Test-/Deploy-Strategie) wird geändert.

## Changelog

- 2026-11-26: Initial spec created
