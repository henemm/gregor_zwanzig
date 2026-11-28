---
entity_id: bug_2923_ort_kopf_en
type: bugfix
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: fix-2923-ort-kopf-en
tags: [i18n, adr-0104, epic-2644, issue-2923, issue-2681, issue-3074, python, renderer]
---

# Bug #2923: Orts-Kopf im Stundenblock der EN-Vergleichs-Mail zeigt deutsches „ORT"

**Issue:** #2923 · **Refs:** #2644, #2681, #3074 (nur Teilpunkt „ORT"-Etikett) · **ADR:** ADR-0104 (zweisprachig DE/EN)

## Approval

- [ ] Approved

## Purpose

Ein englischer Nutzer, der eine Orts-Vergleichs-Mail erhält, sieht im Stundenblock vor jedem Ortsnamen das deutsche Etikett „ORT". Das Etikett soll aus dem Nachrichtenkatalog in der Nutzersprache kommen (EN „LOCATION", DE weiterhin „ORT"). Die deutsche Mail bleibt byte-gleich.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `_location_heading` (Parameter `eyebrow`, Default `"ORT"`), `_render_location_section` (Aufruf `_location_heading(loc, ts)` ohne `eyebrow`)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/renderers/email/`, `src/i18n/messages/`). Kein Go-, kein Frontend-Code. Mail-Validator liegt in `.claude/hooks/`.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Betroffen ist ausschliesslich der compare-eigene Mail-Renderer (Compare-Mail-Template). Kein neuer Baustein, kein Trip-Pendant, keine neue Komponente.
> - **Mandantentrennung:** Der Renderer ist eine reine Funktion, die Sprache kommt als Parameter `lang`. Es werden keine Nutzerdaten bewegt, kein neuer Endpoint.
> - **Kanäle:** Betroffen ist nur das HTML-Etikett der E-Mail. Klartext-Mail, Telegram, SMS und Premium-SMS enthalten kein Orts-Etikett und bleiben unverändert (Inhalt gleich, keine Kanalparitäts-Lücke).

## Root Cause

`_location_heading(..., eyebrow: str = "ORT", ...)` hat einen fest verdrahteten deutschen Default. `_render_location_section` ruft die Funktion ohne `eyebrow` auf, obwohl `lang` dort vorliegt. Die Ausblick-Aufrufe übergeben bereits `t("vergleich.ausblick.eyebrow", lang)` und sind das Vorbild. Die Python-i18n-Ratsche (`_SIGNAL_RE`) fängt nur Umlaute und Signalwörter, „ORT" hat keines davon und blieb unentdeckt.

## Estimated Scope

- **LoC:** ca. 35 (ca. +25/-10, Code und Tests) plus je 1 bis 3 Zeilen in zwei Goldens
- **Files:** 8
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `t(key, lang)` in `src/i18n` | module | Katalogzugriff für das Etikett |
| `src/i18n/messages/{de,en}/vergleich.json` | Katalog | neuer Schlüssel `vergleich.stunden.ort_eyebrow` |
| `katalogtext(...)` in `tests/helpers/einstellung_gleich_mail_orte.py` | Test-Helfer | sprachbewusstes `_ORT_RE` |
| `.claude/hooks/email_spec_validator.py` (`_ortskoepfe`) | Validator | erkennt Ortsköpfe sprachneutral über `letter-spacing:0.1em`; keine Logikänderung |
| `docs/reference/i18n_glossar.md` | Doku | Orte ↔ locations |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `eyebrow` ohne Default (Pflicht-Argument); `_render_location_section` übergibt `t("vergleich.stunden.ort_eyebrow", lang)` |
| `src/i18n/messages/de/vergleich.json` | MODIFY | Schlüssel `vergleich.stunden.ort_eyebrow` = „ORT" |
| `src/i18n/messages/en/vergleich.json` | MODIFY | Schlüssel `vergleich.stunden.ort_eyebrow` = „LOCATION" |
| `tests/helpers/einstellung_gleich_mail_orte.py` | MODIFY | `_ORT_RE` aus `katalogtext("vergleich.stunden.ort_eyebrow", lang)` bauen, `lang` durch `_ort_marken` und `_tabellen_je_ort` reichen (Default `"de"`) |
| `tests/tdd/test_einstellung_gleich_mail_orte.py` | MODIFY | Katalogfall O-SV-H-SPRACHE-EN (`test_orte_koepfe_in_nutzersprache_en`) erweitern |
| `tests/test_vergleichs_mail_zweisprachig.py` | MODIFY | Ausnahme `"ORT"` in `_ohne_ausnahmen` samt Docstring entfernen |
| `tests/golden/vergleichs_mail/ortsvergleich_3orte.en.html` | MODIFY | nur ORT → LOCATION (3 Stellen) |
| `tests/golden/amtliche_warnungen/vergleich_mit_warnungen.en.html` | MODIFY | nur ORT → LOCATION |

DE-Goldens (`*.de.*`, `orte_altbestand_ohne_grundauswahl.golden.html`) bleiben unverändert. Keine Änderung an Gate-Config, keine menschliche Sperre (override) nötig.

### Estimated Changes

- Files: 8
- LoC: ca. +25/-10

## Implementation Details

1. Neuer Katalogschlüssel `vergleich.stunden.ort_eyebrow` (DE „ORT", EN „LOCATION", Glossar Orte ↔ locations).
2. In `compare_html.py` den Default von `eyebrow` entfernen. Alle drei Aufrufer von `_location_heading` übergeben den Wert aus `t(...)` (Ausblick-Aufrufe tun das bereits, der Orts-Abschnitt kommt neu dazu). Damit ist die Ratschen-Lücke „deutsches Literal als Parameter-Default" an der einzigen Fundstelle geschlossen.
3. Bewusste Entscheidung gegen eine Erweiterung der i18n-Ratsche auf String-Defaults: Ein AST-Scan von `src/output` ergibt 266 String-Defaults in etwa 35 Dateien, rund 250 davon sind legitime Modus-Wörter (`lang="de"`, `"evening"` und ähnliche). Das gäbe etwa 250 Fehlalarme für einen echten Fund.
4. Test-Helfer: `_ORT_RE` bisher fest `>ORT</span>`, künftig sprachbewusst aus dem Katalog. Ohne das bricht `html_stundenverlauf(html, "en")` nach dem Fix.
5. EN-Goldens gezielt nachziehen (nicht pauschal neu einfrieren, vgl. #3074); der Diff darf ausschliesslich ORT → LOCATION zeigen.

## Expected Behavior

- **Input:** Orts-Vergleichs-Mail für Nutzer mit `language="en"` bzw. `language="de"`.
- **Output:** EN: Kopf je Ort im Stundenblock „LOCATION <Name>". DE: unverändert „ORT <Name>".
- **Side effects:** keine. Klartext-Mail, Telegram, SMS, Premium-SMS unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Erweiterter Katalogfall O-SV-H-SPRACHE-EN (`test_orte_koepfe_in_nutzersprache_en`): GIVEN EN-Nutzer mit Orte-Mail WHEN HTML gerendert THEN je Ort Kopf mit Katalogtext „LOCATION", und kein `>ORT</span>`. Schlägt vor dem Fix fehl (RED).
- [ ] Sprachbewusster Helfer `_ORT_RE` baut das Muster aus `katalogtext("vergleich.stunden.ort_eyebrow", lang)`; DE-Fälle des Katalogs bleiben grün.
- [ ] `tests/test_vergleichs_mail_zweisprachig.py`: Ausnahme „ORT" entfernt, EN-Mail enthält keinen deutschen Text mehr (RED vor dem Fix).
- [ ] Golden-Tests: DE-Goldens byte-gleich, die 2 EN-Goldens nur mit ORT → LOCATION.
- [ ] Katalog-Parität de/en (bestehender Test) bleibt grün mit dem neuen Schlüssel.
- [ ] Renderer-Commit-Gate: Modus-Matrix-Test und `email_spec_validator` gegen echt zugestellte Staging-Mail (`.claude/tools/staging_mail_pruefen.py --typ compare --lang en` und `--lang de`).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch und einem Orts-Vergleich mit mehreren Orten / When die Vergleichs-Mail (HTML) zugestellt wird / Then zeigt der Kopf jedes Orts im Stundenblock „LOCATION <Ortsname>" und nirgends in der Mail steht „ORT" als Etikett.
  - Test: Katalogfall O-SV-H-SPRACHE-EN (`test_orte_koepfe_in_nutzersprache_en`) prüft pro Ort das Etikett „LOCATION" und das Fehlen von „ORT".

- **AC-2:** Given ein Nutzer mit Sprache Deutsch und demselben Orts-Vergleich / When die Vergleichs-Mail zugestellt wird / Then ist die Mail byte-gleich zu bisher, der Kopf je Ort lautet weiterhin „ORT <Ortsname>" und alle deutschen Golden-Dateien sind unverändert.
  - Test: Golden-Vergleich der DE-Mail (`*.de.*`, `orte_altbestand_ohne_grundauswahl.golden.html`) ohne Diff.

- **AC-3:** Given eine echt zugestellte Staging-Vergleichs-Mail im Test-Postfach, einmal auf Deutsch und einmal auf Englisch / When der Mail-Prüfer `email_spec_validator` sie prüft / Then erkennt er in beiden Sprachen die Ortsköpfe weiterhin und findet die Stundentabelle je Ort (Exit 0).
  - Test: `.claude/tools/staging_mail_pruefen.py --typ compare --lang de` und `--lang en` gegen Staging, Validator-Ergebnis „E2E bestanden".

- **AC-4:** Given der Renderer baut den Orts-Kopf im Stundenblock / When der Text des Etiketts bestimmt wird / Then kommt er aus dem Katalogschlüssel `vergleich.stunden.ort_eyebrow` und `_location_heading` hat keinen deutschen Default mehr, `eyebrow` ist ein Pflicht-Argument.
  - Test: Verhalten: ein Aufruf ohne `eyebrow` scheitert (TypeError); EN- und DE-Mail zeigen den jeweiligen Katalogtext. Kein Dateiinhalt-Check.

- **AC-5:** Given ein Nutzer in einer beliebigen Sprache / When er die Klartext-Variante der Vergleichs-Mail erhält / Then ist sie unverändert, denn sie enthält kein Orts-Etikett.
  - Test: Klartext-Rendering für DE und EN vor und nach dem Fix identisch (bestehende Klartext-Goldens bleiben grün).

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), erweiterter Katalogfall O-SV-H-SPRACHE-EN vor der Umsetzung rot, danach grün
- [ ] DE-Goldens byte-gleich, EN-Goldens nur ORT→LOCATION geändert
- [ ] Mutations-Gegenprobe: „LOCATION“ im EN-Katalog zurück auf „ORT“ färbt den Katalogfall rot
- [ ] PR mit allen 6 CI-Checks grün, `email_spec_validator` gegen echt zugestellte Staging-Mail de und en bestanden, Prod-Deploy, Selftest Exit 0

## Known Limitations

- Out of Scope: übrige Punkte aus #3074 (DE-Fußzeile „Generated/Data", Risk-Legende).
- Out of Scope: Erweiterung der i18n-Ratsche auf String-Defaults (siehe Implementation Details, ca. 250 Fehlalarme).
- `email_spec_validator.py`: nur Docstring-Erwähnungen von „ORT" bleiben, keine Logikänderung und keine Gate-Config-Änderung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (bestehend, keine neue Entscheidung)
- **Rationale:** Der Fix setzt die bestehende Regel „neue Nutzertexte nur über den Katalog" um. Es entsteht keine neue Architekturentscheidung.

## Changelog

- 2026-11-28: Initial spec created (Issue #2923)
