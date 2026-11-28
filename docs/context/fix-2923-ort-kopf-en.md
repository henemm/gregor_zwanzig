# Kontext: fix-2923-ort-kopf-en (Issue #2923)

## Request Summary

Englische Orts-Vergleichs-Mail (Nutzer `language="en"`): im Stundenblock steht vor jedem
Ortsnamen das deutsche Etikett **„ORT“**. Ziel: EN zeigt „LOCATION“ (Glossar-Linie
„ORTE“/*LOCATIONS*), DE bleibt byte-gleich „ORT“. Auch #3074 (2. Punkt) meldet denselben
Befund; dessen übrige Punkte (DE-Fußzeile „Generated/Data“, Risk-Legende) sind NICHT Teil
dieses Tickets.

## Root Cause (belegt)

- `src/output/renderers/email/compare_html.py:1271-1306` `_location_heading(..., eyebrow: str = "ORT", ...)`
  – fest verdrahteter Parameter-Default.
- `compare_html.py:1328` `_render_location_section` ruft `_location_heading(loc, ts)` OHNE
  `eyebrow` auf, obwohl `lang` dort verfügbar ist. Die Ausblick-Aufrufe (1440, 1483)
  übergeben bereits `t("vergleich.ausblick.eyebrow", lang)` – das ist das Muster.
- Python-i18n-Ratsche (`tests/test_i18n_keine_hartkodierten_nutzertexte_python.py`, `_SIGNAL_RE`
  Zeile 46) fängt nur Umlaute/Signalwörter – „ORT“ hat beides nicht, daher unentdeckt.

## Related Files

| Datei | Rolle |
|---|---|
| `src/output/renderers/email/compare_html.py` | Fix-Stelle (Default + Aufruf 1328) |
| `src/i18n/messages/{de,en}/vergleich.json` | neuer Schlüssel, z. B. `vergleich.stunden.ort_eyebrow` = „ORT“/„LOCATION“ |
| `.claude/hooks/email_spec_validator.py:850-905` | `_ortskoepfe` ist seit #3047 sprachunabhängig (liest das Orts-Etikett nicht) → keine Logikänderung nötig; nur Docstrings „ORT“ (859, 876, 888) |
| `tests/tdd/test_einstellung_gleich_mail_orte.py:663` `test_orte_koepfe_in_nutzersprache_en` | laut PO-Kommentar im Issue: Nachweis durch Erweitern dieses Katalogfalls (O-SV-H-SPRACHE-EN), kein eigener Test |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json:1864` | Katalogfall O-SV-H-SPRACHE-EN |
| `tests/test_vergleichs_mail_zweisprachig.py:57-70` | `_ohne_ausnahmen` nimmt „ORT“ ausdrücklich aus (Begründung: Validator-Marke) → Ausnahme entfällt, damit der Test das Etikett künftig mitprüft |
| `tests/golden/vergleichs_mail/ortsvergleich_3orte.en.html` (3× `>ORT<`) | EN-Review-Referenz ändert sich → gezielt nachziehen (nicht pauschal neu einfrieren, vgl. #3074) |
| `tests/golden/amtliche_warnungen/vergleich_mit_warnungen.en.html` | ebenfalls `>ORT<` → nachziehen |
| DE-Goldens (`*.de.*`, `orte_altbestand_ohne_grundauswahl.golden.html`) | müssen byte-gleich bleiben |
| `tests/unit/test_compare_validator_single_name_form.py:130`, `test_compare_mail_validator_column_order.py:106` | Validator-Unit-Fixtures mit DE-„ORT“ – bleiben gültig |

## Existing Patterns

- Katalogtexte über `t(key, lang)`; Ausblick-Kopf nutzt bereits `eyebrow=t("vergleich.ausblick.eyebrow", lang)`.
- Glossar `docs/reference/i18n_glossar.md:27`: Orte ↔ *locations*, Kopf „ORTE“/*LOCATIONS*.
- Regeln: `docs/reference/i18n_konventionen.md` (neue Nutzertexte nur über Katalog).

## Dependencies / Dependents

- `_location_heading` hat nur die drei Aufrufer in `compare_html.py`.
- Validator, Ableser in Tests erkennen den Kopf über `letter-spacing:0.1em` + Ausschluss der
  Abschnitts-/Ausblick-Etiketten → sprachneutral.

## Existing Specs

- `docs/specs/modules/i18n_p4_vergleichs_mail_2666.md` (Vergleichs-Mail zweisprachig)
- ADR-0104 (zweisprachig DE/EN)

## Risks

- Renderer-Commit-Gate: Modus-Matrix-Test + `email_spec_validator` gegen echt zugestellte
  Staging-Mail (`staging_mail_pruefen.py --typ compare --lang en` und `--lang de`).
- DE darf sich byte-genau nicht ändern (Golden-Test).
- Ratschen-Lücke (Issue „mitprüfen“): deutsche Literale als Parameter-Defaults in Renderern.
  Option: Default ganz entfernen (eyebrow Pflicht-Argument) statt Ratsche zu verbreitern –
  Analyse entscheidet; Ratschen-Erweiterung wäre eigener Umfang (Nebenbefund-Issue).

## Analysis

**Type:** Bug (Root Cause belegt, siehe oben)

### Affected Files (Change Type)

| Datei | Change | Inhalt |
|---|---|---|
| `src/output/renderers/email/compare_html.py` | MODIFY | `_location_heading`: `eyebrow` ohne Default (Pflicht-Keyword); `_render_location_section` (1328) übergibt `t("vergleich.stunden.ort_eyebrow", lang)` |
| `src/i18n/messages/de/vergleich.json` | MODIFY | `vergleich.stunden.ort_eyebrow`: „ORT“ |
| `src/i18n/messages/en/vergleich.json` | MODIFY | `vergleich.stunden.ort_eyebrow`: „LOCATION“ |
| `tests/helpers/einstellung_gleich_mail_orte.py` | MODIFY | `_ORT_RE` (Z. 493) fest `>ORT</span>` → aus `katalogtext("vergleich.stunden.ort_eyebrow", lang)` bauen, `lang` durch `_ort_marken`/`_tabellen_je_ort` reichen (Default "de"). Ohne das bricht `html_stundenverlauf(html,"en")` nach dem Fix |
| `tests/tdd/test_einstellung_gleich_mail_orte.py` | MODIFY | Katalogfall O-SV-H-SPRACHE-EN erweitern (`test_orte_koepfe_in_nutzersprache_en` / `pruefe_stundenverlauf` html): EN-Etikett vorhanden, `>ORT</span>` nicht vorhanden |
| `tests/test_vergleichs_mail_zweisprachig.py` | MODIFY | Ausnahme `z == "ORT"` in `_ohne_ausnahmen` + Docstring entfernen |
| `tests/golden/vergleichs_mail/ortsvergleich_3orte.en.html` | MODIFY | ORT→LOCATION (nur diese Bytes) |
| `tests/golden/amtliche_warnungen/vergleich_mit_warnungen.en.html` | MODIFY | ORT→LOCATION |

Klartext-Mail hat kein Orts-Etikett (kein Änderungsbedarf). DE-Goldens bleiben byte-gleich.
Validator `email_spec_validator.py`: keine Logikänderung (`_ortskoepfe` sprachneutral); Docstrings optional.

### Scope / Risk

~25 LoC Code/Tests in 6 Dateien + 2 Golden-Diffs (je 1–3 Zeilen). Risiko mittel-niedrig: Mail-Inhalt,
DE-Byte-Gleichheit durch Goldens abgesichert. Renderer-Commit-Gate: Modus-Matrix + Validator gegen
Staging-Mail de/en.

### Technical Approach

1. Katalogschlüssel `vergleich.stunden.ort_eyebrow` (DE „ORT“, EN „LOCATION“ laut Glossar Orte↔locations).
2. Ratschen-Lücke: Option (a) – Default entfernen, `eyebrow` Pflicht-Keyword; alle 3 Aufrufer übergeben
   `t(...)`. Option (b) (Ratsche auf String-Defaults erweitern) verworfen: AST-Scan `src/output` ergibt
   266 String-Defaults in ~35 Dateien, ~250 legitime Modus-Wörter (`lang="de"`, 'evening', …) – nur
   ein echter Nutzertext-Default; Allowlist ~40 Einträge für einen Fund. → kein eigenes Issue nötig,
   Lücke ist durch (a) an der einzigen Stelle geschlossen.
3. Nachweis: sprachbewusster Test-Helfer + Assertion im Katalogfall (PO-Kommentar im Issue).
4. EN-Goldens gezielt nachziehen, Diff darf nur ORT→LOCATION zeigen.

### Dependencies

Nur die drei Aufrufer in `compare_html.py`; Test-Helfer `_ORT_RE` ist der einzige weitere Literal-Konsument.

### Open Questions

Keine.
