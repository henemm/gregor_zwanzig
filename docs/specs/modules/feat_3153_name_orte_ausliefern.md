---
entity_id: feat_3153_name_orte_ausliefern
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3153-name-orte
tags: [orte, i18n, kanaele, epic-3122]
---

# Name „Orte“ und Ein-Ort-Texte ausliefern (Epic #3122, Teil B5)

## Approval

- [ ] Approved

> Der Fachinhalt (Name „Orte“, Ein-Ort-Texte) wurde am 17.11.2026 in `docs/specs/modules/feat_3122_was_steht_wo.md` (Teil B Nr. 16, AC-35, AC-36, ADR-0124 Nr. 10) freigegeben. Diese Spec legt nur die Liefer-Fassung zur Freigabe vor; sie erfindet keinen neuen Fachinhalt.

## Purpose

Der fertige Bau B5 (PR #3136) macht überall dort, wo ein Nutzer Texte zu Orte-Abos sieht, aus „Vergleich“, „Orts-Vergleich“ und „Orts-Briefing“ den einheitlichen Namen „Orte“ (EN „Locations“) und liefert korrekte Ein-Ort-Texte. Diese Spec regelt die Auslieferung: Zusammenführen mit dem inzwischen veränderten `main`, ohne dass Inhalte verloren gehen, und Nachweis an echt zugestellten Mails.

## Source

- **File:** `src/output/renderers/comparison.py`, `src/output/renderers/email/compare_html.py`, `src/services/trip_command_processor.py`, `src/i18n/messages/{de,en}/*.json`
- **Identifier:** Renderer-Köpfe und SMS-Anfang für Orte, Befehlsantworten, API-Fehlertexte (Python-Core; kein Frontend- und kein Go-Code)

## Scope

Scheibe B5 der Epic-Spec `feat_3122_was_steht_wo.md` (Teil B Nr. 16). Zitiert deren AC-35 und AC-36 als AC-1 und AC-2, ändert sie nicht; AC-3 bis AC-6 sichern die Auslieferung des fertigen Baus ab. Geliefert werden nur Ausgabe-Texte (Mail, Telegram, SMS, Premium-SMS, Befehlsantworten, API-Fehlertexte), keine Oberfläche.

## Estimated Scope

- **LoC:** Eigenarbeit ca. +40/-40 (Konflikte), Golden-Dateien maschinell neu erzeugt
- **Files:** ca. 95 (davon ca. 10 Eigenarbeit, Rest fertig im B5-Zweig)
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/comparison.py` | MODIFY | SMS-Anfang „Orte TT.MM.:“ bzw. „{Ort} TT.MM.:“, Telegram-Kopf |
| `src/output/renderers/email/compare_html.py` | MODIFY | Kopf „ORTE“, Fußzeile „1 Ort“, Ein-Ort-Übersicht |
| `src/services/trip_command_processor.py` | MODIFY | Befehlsantworten ohne „Vergleich“, neues Wort „Orte-Abo“ |
| `src/i18n/messages/{de,en}/*.json` | MODIFY | Alle Texte im Katalog, `.one`/`.other` |
| `.claude/hooks/email_spec_validator.py`, `_soll_aus_konfiguration.py` | MODIFY | Prüfung Bereichsname mit `--konfig`, Ein-Ort-Fall |
| `docs/reference/sms_format.md` | MODIFY | Zusammenführung mit main, beide Seiten behalten |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` | MODIFY | Zusammenführung, beide Fallgruppen behalten |
| `tests/fixtures/ein_vokabular_3101/*.golden.json`, `pruefkatalog_golden.sha256.json` | MODIFY | Neu erzeugt, Diff nur Namenswechsel |
| `tests/tdd/test_orte_bereichsname_in_ausgaben.py`, `test_orte_befehlsantworten_ohne_alten_namen.py` | CREATE | Nachweise AC-1 bis AC-3 (aus B5) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3122_was_steht_wo.md` | Spec | Freigegebener Fachinhalt (AC-35, AC-36) |
| ADR-0124 Nr. 10 | ADR | Entscheidung zum Namen „Orte“ |
| `compare_metric_ids.py` (#3101) | module | Renderer-Adapter, über den Orte-Ausgaben laufen |
| View-Model B1b | module | Quelle der Ausblick-Spalten und Tabelle „Was steht wo“ |
| `email_spec_validator.py` | hook | Nachweis an echt zugestellter Staging-Mail |

## Implementation Details

1. Arbeitszweig aus dem B5-Stand, `origin/main` hineinführen; die zwei Textkonflikte (`sms_format.md`, `fallliste_orte.json`) so lösen, dass beide Seiten erhalten bleiben.
2. Die seit #3101/B1b über den Renderer-Adapter laufenden Orte-Ausgaben (inkl. SMS-Beispielzeile der Tabelle „Was steht wo“) übernehmen den neuen Wortlaut automatisch; Golden-Dateien `ein_vokabular_3101` mit `EIN_VOKABULAR_GOLDEN_SCHREIBEN=1` neu erzeugen und je Datei prüfen, dass der Diff nur den Namenswechsel (bzw. eine Wertzelle mehr wegen des kürzeren SMS-Kopfs) zeigt.
3. Validator `email_spec_validator.py --konfig` gegen echt zugestellte Staging-Mails.

## Expected Behavior

- **Input:** Orte-Abo mit einem oder mehreren Orten, Nutzersprache DE oder EN.
- **Output:** Alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) und Befehlsantworten tragen den Namen „Orte“/„Locations“ mit gleichem Inhalt, kanalgerechter Form.
- **Side effects:** keine Datenänderung; Protokoll-Token (`sms_code`, Kürzel) bleiben unübersetzt.

## Acceptance Criteria

- **AC-1:** Given ein Orte-Abo mit drei Orten in Deutsch und in Englisch / When Briefing-Mail, Telegram, SMS und Premium-SMS zugestellt werden / Then steht im Kopf „ORTE“ bzw. „LOCATIONS“, die SMS beginnt in beiden Sprachen mit „Orte TT.MM.:“ (Protokoll-Kopf, wird nicht übersetzt), und kein Text enthält „Vergleich“, „Orts-Vergleich“ oder „Orts-Briefing“.
  - Test: Kern-Schicht (`test_orte_bereichsname_in_ausgaben.py`) für Telegram, SMS, Premium-SMS und Mail-Kopf; Staging-Mail per Validator (AC-6).

- **AC-2:** Given ein Orte-Abo mit genau einem Ort / When Briefing-Mail, Telegram, SMS und Premium-SMS zugestellt werden / Then enthält die Mail die Übersichtstabelle mit den Tageswerten des Orts, kein Text sagt „alle Orte“ oder „1 Orte“, die Fußzeile sagt „1 Ort“, und die SMS beginnt mit dem Namen des Orts und dem Datum.
  - Test: Ein-Ort-Fall in der Kern-Schicht und im Validator mit `--konfig`, DE und EN.

- **AC-3:** Given ein Nutzer mit Orte-Abo / When er Befehle per Kanal sendet (Inbound) oder die API einen Fehler zu Orten meldet / Then nennt die Antwort weder „Ortsvergleich“ noch „Vergleich“, sondern „Orte-Abo“ (EN: „Locations subscription“).
  - Test: `test_orte_befehlsantworten_ohne_alten_namen.py` über den echten Befehlseingang und die API-Fehlerantworten, DE und EN.

- **AC-4:** Given die Tabelle „Was steht wo“ und alle Orte-Ausgaben, die seit #3101/B1b über den Renderer-Adapter laufen / When die Ausgaben erzeugt werden / Then trägt auch die SMS-Beispielzeile der Tabelle den neuen SMS-Anfang, und die neu erzeugten Golden-Dateien `ein_vokabular_3101` unterscheiden sich vom Stand auf main nur durch den Namenswechsel oder eine zusätzliche Wertzelle wegen des 5 Zeichen kürzeren SMS-Kopfs.
  - Test: `test_3101_ein_vokabular.py` und `test_placements_*` grün; Diff-Prüfung je Golden-Datei.

- **AC-5:** Given der B5-Stand und der aktuelle `main` mit Änderungen an beiden Seiten / When beide zusammengeführt werden / Then bleiben alle Fallgruppen in `fallliste_orte.json` und alle Abschnitte in `sms_format.md` von beiden Seiten erhalten, und die Orte-Tests von main (Ausgaben lesen View-Model, Einstellung-gleich-Mail, Top-N-Invarianz) laufen grün.
  - Test: `test_einstellung_gleich_mail_fallliste.py`, `test_einstellung_gleich_mail_orte_tabelle.py`, `test_orte_ausgaben_lesen_view_model.py`, `tests/unit/test_compare_mail_blocks.py`.

- **AC-6:** Given echt zugestellte Staging-Mails für ein Orte-Abo mit drei Orten und mit einem Ort, jeweils in Deutsch und Englisch / When `email_spec_validator.py --konfig` sie prüft / Then endet der Validator mit Exit 0 („E2E bestanden“).
  - Test: Validator gegen das Stalwart-Test-Postfach auf Staging, vier Mails.

## Definition of Done

- AC-1 bis AC-6 durch benannte Tests bzw. Validator grün; Adversary mit Mutations-Gegenprobe ohne offenen Befund.
- Alle sechs CI-Checks grün, Staging-Verifikation, Prod-Deploy, Prod-Selftest Exit 0.
- `sms_format.md`, `renderer_email_spec.md`, `telegram_format.md` tragen den neuen Wortlaut.

## Test Plan

- **Kern-Schicht (ohne Netz):** `tests/tdd/test_orte_bereichsname_in_ausgaben.py` (AC-1, AC-2 für Telegram/SMS/Premium-SMS/Mail-Text), `test_orte_befehlsantworten_ohne_alten_namen.py` (AC-3), `test_3101_ein_vokabular.py` mit neu erzeugten Golden-Dateien (AC-4), main-seitige Orte-Tests (`test_orte_ausgaben_lesen_view_model.py`, `test_einstellung_gleich_mail_*`, `test_compare_mail_blocks.py`, `test_placements_*`) (AC-5).
- **RED-Nachweis:** die beiden B5-Tests laufen gegen den Stand von `main` rot.
- **Staging:** `email_spec_validator.py --konfig` gegen echt zugestellte Mails, drei Orte und ein Ort, DE und EN (AC-1, AC-2, AC-6).
- **Mutations-Gegenprobe:** alter Kopf „ORTS-VERGLEICH“ zurück, „1 Orte“ statt „1 Ort“, SMS-Anfang „Vergleich“, Befehlsantwort mit „Ortsvergleich“ — jede Verfälschung muss ein Test fangen.

## Known Limitations

- Der SMS-Kopf ist 5 Zeichen kürzer; in voll gekürzten SMS passt dadurch teils eine Wertzelle mehr (bewusst).
- Außerhalb dieses Schritts: AC-37/AC-38 der Epic-Spec.

## Out of Scope

- Oberfläche (Reiter Orte, Anlegen mit einem Ort, Menü, Listen, Untergrenze des Validators): bleibt bei #2798. Dieser Zuschnitt ist bereits in der am 17.11. vom PO freigegebenen Epic-Spec `feat_3122_was_steht_wo.md` festgelegt (Teil B Nr. 16: „Diese Spec legt die Texte der Ausgaben fest; #2798 behält Reiter Orte, Anlegen mit einem Ort, Menü, Listen und die Untergrenze des Validators“; ebenso deren Out of Scope). Der Satz „Oberfläche“ im Fertig-Kriterium von #3153 wird damit über #2798 eingelöst, nicht in diesem Schritt; Epic #3122 gilt erst als fertig, wenn auch #2798 live ist.
- „Orte-Abo“ ist ein neues sichtbares Wort in Befehlsantworten; es wird bei der Abnahme (#3037) gezeigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Nr. 10), bereits entschieden
- **Rationale:** Diese Auslieferung setzt die Entscheidung um; kein neues ADR nötig.

## Changelog

- 2026-11-19: Initial spec created (Liefer-Fassung von AC-35/AC-36 aus feat_3122)
