# Context: feat-3097 — Roh/Einfach je Zeile im Orte-Stundenverlauf (Konzept W11)

> **Hinweis (2026-11-17, [ADR-0124](../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Diese Notiz ist Historie eines gebauten Schritts. Wo sie die Karte „Inhalt je Kanal und Fläche“ (eigene Liste je Kanal und Fläche, #3031–#3037, PR #3042, #3060) als künftiges Soll nennt, gilt das nicht mehr: ADR-0124 (PO 2026-11-17) ersetzt die Karte durch **eine** Tabelle „Was steht wo“ im Reiter Wetter. Aktueller Stand: ADR-0124 und `docs/context/einstellungen_neu.md`. Die Verlagerung nach `channel_layouts.hourly` mit #3060 entfällt in dieser Form.

Issue #3097, Teil von Epic #3058 (Phase 3b von #3047). Abnahme: `O-SV-H-DARST` und
`O-SV-K-DARST` in `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` von
`offen_feature` auf `gruen` (Test `tests/tdd/test_einstellung_gleich_mail_orte.py::test_w11_darstellung_je_zeile`).

## Request Summary

PO-Entscheidung W11 (`docs/context/einstellungen_neu.md:118`): „Darstellung Roh oder Einfach
je Metrik, in jeder Liste … Rein als Umschalter je Zeile in jeder Liste: E-Mail, Telegram, SMS,
Premium-SMS, Vergleichstabelle, Stundenverlauf und 3-Tages-Ausblick.“ Vergleichstabelle (#3039,
`channel_layouts.email`) und Ausblick (`outlook_metric_formats`) können es; der Orte-Stundenverlauf
nicht (Befund B-OM-5, Runde 7 von #3047).

## Ist-Stand (Kontext)

- Stundenverlauf gibt es nur in der Orte-Mail (HTML + Klartext), nicht in Telegram/SMS.
- HTML: `src/output/renderers/email/compare_html.py` `_hour_zeilen` (:465), `_render_hour_row`
  (:1126, `fmt_word_cell`, kein Einfach-Zweig), `_render_hour_table` (:1175).
  Klartext: `src/output/renderers/comparison.py:386-457`, dieselben Helfer.
- Einfach-Helfer: Vergleichstabelle `_friendly_overview_html` (compare_html.py:765, Ampelpunkt via
  `fmt_val`), Ausblick `_friendly_outlook_text`/`format_outlook_value`
  (`src/output/renderers/compare_outlook_metric_ids.py:460/:501`). `_friendly_outlook_text`
  nutzt für Niederschlag die Tagessummen-Skala (AC-9 #2049) — für Stundenwerte falsch.
- Resolver `src/services/channel_list_resolver.py:252`: `hourly` mit `format=None`
  (ADR-0121 Nachtrag 2b Nr. 3: „Roh/Einfach dort = #3058“).
- Verbraucher der Stundenliste: `report_config_resolver.py:308-369`, `scheduler_dispatch_service.py:1000`,
  `compare_preview_service.py:175`, `validator_render_service.py:571-580` (umgeht den Resolver).
- Speicherung: `display_config.hourly_metrics` = `string[]` ohne Format. `channel_layouts.hourly`
  reserviert, laut ADR-0121 Nr. 7 erst mit Editor #3060 (offen) schreibbar (Go `mergeConfigMap`
  ersetzt Unterschlüssel, ADR-0077).
- Frontend: `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte:259/:336`
  („Roh/Einfach-Umschalter gibt es im Stundenverlauf nicht“, `friendlyMap={{}}`);
  `shared/OutputLayoutEditor.svelte` kann `friendlyMap`; Vorbild Ausblick
  `shared/OutlookLayoutControls.svelte:224-241`, Persistenz `outlook_metric_formats` in
  `compareEditorSave.ts`, `pickEigenfelder.ts`, Test `compare_outlook_metric_formats_persistenz.test.ts`.

## Analysis

### Type
Feature

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/compare_outlook_metric_ids.py (oder compare_hourly_metric_ids.py) | MODIFY | Stunden-Einfach-Helfer `_friendly_hour_text`: Niederschlag Stundenskala (`format_precip_intensity`), sonst Delegation an `_friendly_outlook_text`; Auflösung `resolve_hourly_metric_formats` |
| src/output/renderers/email/compare_html.py | MODIFY | `_render_hour_row`/`_render_hour_table`: Parameter Stundenformate, Einfach-Zweig (Wind/Böen Ampelpunkt wie Vergleichstabelle, Wolken Symbol) |
| src/output/renderers/comparison.py | MODIFY | Klartext-Stundenschleife: derselbe Einfach-Zweig |
| src/services/channel_list_resolver.py | MODIFY | `hourly[].format` aus `display_config.hourly_metric_formats` statt `None` |
| src/services/report_config_resolver.py | MODIFY | Stundenformate in die Render-Optionen |
| src/services/scheduler_dispatch_service.py, compare_preview_service.py, validator_render_service.py | MODIFY | Format durchreichen (Vorschau = Mail) |
| frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte | MODIFY | echter `friendlyMap`, Umschalter nur bei Metriken mit Einfachform |
| frontend/src/lib/components/compare/compareEditorSave.ts, shared/pickEigenfelder.ts, lib/types.ts | MODIFY | Persistenz `hourly_metric_formats` analog `outlook_metric_formats` |
| tests/tdd/test_einstellung_gleich_mail_orte.py | MODIFY | `test_w11_darstellung_je_zeile` auf `hourly_metric_formats` umstellen, Gegenprobe: `channel_layouts.email` allein ändert den Stundenverlauf nicht |
| tests/fixtures/einstellung_gleich_mail/fallliste_orte.json | MODIFY | O-SV-H/K-DARST → `gruen`, Verweis anpassen |
| frontend Persistenz-Test, tests/tdd Resolver-/Vorschau-Paritätstest | CREATE | Absicherung Speichern und drei Verbraucher |
| docs/adr/0121-kanonische-kanal-liste.md | MODIFY | Nachtrag 3b: Stundenverlauf-`format` aus `hourly_metric_formats` |
| docs/reference/api_contract.md | MODIFY | neues Feld `display_config.hourly_metric_formats` |

### Scope Assessment
- Files: ca. 15
- Estimated LoC: Python +120/-160, Frontend +60/-90, Tests/Doku zusätzlich
- Risk Level: MEDIUM (Mail-Inhalt; ohne Einstellung bleibt die Mail byte-gleich, Goldens unverändert)

### Technical Approach (Tech-Lead-Entscheidung)
1. **Speicherort `display_config.hourly_metric_formats` `{metric_id: bool}`** — Schwesterfeld zu
   `outlook_metric_formats`. Verworfen: `channel_layouts.email` (wäre derselbe Schalter wie die
   Vergleichstabelle, W11 verlangt je Liste eigene Werte); `channel_layouts.hourly` (ADR-0121 Nr. 7:
   erst mit #3060, Go-Merge ersetzt Unterschlüssel → Datenverlustrisiko). Spätere Migration nach
   `channel_layouts.hourly` mit #3060 verlustfrei möglich. Fehlt = Roh (ADR-0119 Nr. 4).
2. Resolver füllt `hourly[].format` (`simplified`/`raw`/`null`); Renderer liest es; alle drei
   Verbraucher reichen es durch (Vorschau-Parität).
3. **Einfachformen im Stundenverlauf:** Wind/Böen Ampelpunkt (wie Vergleichstabelle), Wolken
   (gesamt/tief/mittel/hoch) Symbol, Windrichtung Kompass, Regenwahrscheinlichkeit und Sonnenschein
   Wortskala, Niederschlag Stundenintensität (trocken/leicht/mäßig/stark). Gewitter bleibt draußen
   (Roh ist dort bereits Text, #1475). Temperatur u. a. ohne Einfachform → Zahl, kein Umschalter.
   Metriken mit nur einem `format_mode` ignorieren Einfach (Regel aus `_friendly_effective`).
4. **Umschalter in dieser Scheibe** im heutigen Stundenverlauf-Editor (sonst für Nutzer
   unerreichbar), über die vorhandene `friendlyMap` von `OutputLayoutEditor` — keine neue
   Compare-Komponente. Speichern als Read-Modify-Write.
5. Test `test_w11_darstellung_je_zeile` nahm den Speicherort ausdrücklich vorläufig an; wird auf
   `hourly_metric_formats` umgestellt.

Reihenfolge: ADR-Nachtrag + Test rot → Stunden-Einfach-Helfer → Renderer HTML/Klartext →
Resolver + Verbraucher → Frontend-Umschalter + Persistenz → Fallliste grün, Goldens prüfen.

### Dependencies
Keine harte Abhängigkeit zu #3060, #3082, #3101. Telegram/SMS (#3098–#3100) unberührt
(kein Stundenverlauf). Validator `.claude/hooks/email_spec_validator.py` (Stundentabellen-
Vollständigkeit :941-1012) vor Umsetzung prüfen: Symbol-/Wortzellen dürfen nicht als leer gelten.

### Open Questions
- [x] Speicherort — Tech-Lead-Entscheidung (siehe oben), keine PO-Frage.
- [x] Umschalter in dieser Scheibe — ja (W11 freigegeben).
- [ ] Validator-Verhalten bei Wort-/Symbolzellen in der Stundentabelle — in Spec/TDD klären.
