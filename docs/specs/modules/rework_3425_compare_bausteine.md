---
entity_id: rework_3425_compare_bausteine
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: rework-3425-compare-bausteine
tags: [compare, renderer, klartext, html, refactor, "#3425", "#2991", "#3431", "#3047"]
---

# Vergleichsmail: Stundenzellen, Stunden-Ueberschrift und Legende aus einem Baustein (#3425)

## Approval

- [ ] Approved

## Purpose

In der Ortsvergleich-Mail sind Klartext (`comparison.py`) und HTML (`compare_html.py`) bei Stundenzellen, Stunden-Ueberschrift und Legenden-Bedingung noch doppelt aufgebaut und koennen auseinanderlaufen. Dieses Rework legt dafuer je einen oeffentlichen Baustein in `compare_html.py` an, den beide Fassungen nutzen (Folge zu #2991, Leitentscheidung ADR-0127). Sichtbar aendert sich genau ein Randfall: Hat kein Ort Stundendaten (alle Orte Fehler oder ohne Daten), zeigt auch die HTML-Fassung keine nackte Ueberschrift "Stundenverlauf" mehr, wie es der freigegebene Spec `feat_3122_was_steht_wo.md` (AC-10: Block entfaellt) und die Klartext-Fassung (#1366) schon verlangen.

## Source

- **File:** `src/output/renderers/email/compare_html.py` (Bausteine), `src/output/renderers/comparison.py` (Klartext, importiert die Bausteine)
- **Identifier:** `hour_cell_texts()`, `hourly_block_visible()`, `legend_visible()` (alle neu, oeffentlich); angepasst `_render_hour_row`, `_render_location_section`, `_render_legend` und die Stundenschleife, Stunden-Ueberschrift und Legende in `comparison.py`

Schicht-Zuordnung: ausschliesslich Python-Core (`src/output/renderers/`). Go-API, Frontend, Datenmodell und Provider bleiben unberuehrt.

Querschnitts-Pruefpunkte:

- **Trip/Ortsvergleich-Teilung:** Keine neue Komponente mit Trip-Pendant; zwei Compare-eigene Renderer-Pfade werden auf einen Baustein zurueckgefuehrt (kein Pendant-Verstoss, #1170).
- **Mandantentrennung:** Reine Renderer-Logik ohne Nutzerdaten, keine `user_id` gelesen oder geschrieben; kein Zwei-Nutzer-Test noetig.
- **Kanaele:** Betroffen ist nur die Vergleichsmail (Klartext + HTML, E-Mail-Kanal). Telegram, SMS, Premium-SMS und Compact-Mail bleiben unveraendert; es aendert sich kein Inhalt, nur die Quelle der Entscheidung (Ausnahme: Randfall HTML, siehe Purpose).

## Scope

**Drin:**

- `hour_cell_texts(...)`: Zellkette einer Stunde (`_hour_einfach_text`, `_fmt_thunder` inkl. Hagel und Signale, `fmt_word_cell`, Windrichtungs-Zusammenlegung) als Liste von Label/Text-Paaren; ein `html`-Schalter liefert die Ampel-Auszeichnung. `_render_hour_row` und die Klartext-Stundenschleife nutzen ihn.
- `hourly_block_visible(locations, hourly_enabled)`: wahr nur, wenn `hourly_enabled` gilt und mindestens ein Ort ohne `error` und mit `hourly_data` existiert. Dasselbe Prädikat steuert die Stunden-Ueberschrift in HTML, die Entscheidung `have_hourly` samt Ueberschrift im Klartext und `_render_location_section`.
- `legend_visible(hourly_enabled, outlook_enabled)`: gemeinsame Bedingung beider Legenden (heute zweimal `hourly_enabled or outlook_enabled`).

**Bewusst nicht geteilt (je Medium/Kanal gewollt, kein Baustein):**

- **Zeitlabel der Stunde:** Klartext `HH:MM`, HTML `HH`. Je Medium festgenagelt durch den Validator (`email_spec_validator.py`, `_STUNDE_RE` Klartext und HTML) und viele Klartext-Tests; bleibt im jeweiligen Renderer.
- **Ort-Abschnittsstruktur und Ausblick-Ueberschrift:** Klartext fasst Stunden, Ausblickzeilen und Zustandstext unter `Name (TZ)` zusammen, HTML trennt Stundenabschnitt und Ausblick-Block ("Name · 3-Tages-Ausblick", Zustandsblock). Gewollt laut #1323, #1378, #1505, #2666.
- **Einfach-Form der Uebersicht:** HTML Ampelpunkt, Text Stufenwort (feat_3122 Nr. 4), SMS-Variante `cloud_stufe`; der Kern `_friendly_outlook_text` ist bereits geteilt. Die Ampelstunde `@HH` gehoert zu #3047.
- **Nur-HTML-Elemente:** Risiko-Punkte und Warn-Kuerzel-Zeile der Legende (kanalbedingt, Klartext hat keine Risiko-Legende).
- **Zellformate der Uebersicht:** `213°`/`4h`/`-` (Klartext) gegen `213 °`/`4 h`/`–` (HTML). Produktfrage, ausgelagert in #3431.

## Nicht im Umfang

- **#3431:** Angleichung der Uebersichts-Zellformate (Windrichtung, Sonnenstunden, Platzhalter `-` gegen `NO_VALUE` `–`). Braucht eine PO-Entscheidung, aendert sichtbare Formate und den Golden-Snapshot.
- **#3047:** Ampelstunde `@HH` in der Einfach-Form der Uebersicht.
- Zeitlabel-Vereinheitlichung (`HH:MM` gegen `HH`), gemeinsame Ort-Abschnittsstruktur, gemeinsame Einfach-Form, Risiko-Legende im Klartext, Trip-Pfad, Telegram/SMS/Compact.

## Estimated Scope

- **LoC:** ca. +120 bis +160 (inkl. Tests), Produktion netto nahe null durch entfallende Doppelung; deutlich innerhalb +/-250, jede Funktion <= 50 LoC
- **Files:** 3 (2 Produktion, 1 neue Testdatei)
- **Effort:** small bis medium

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `hour_cell_texts`, `hourly_block_visible`, `legend_visible` neu; `_render_hour_row`, `_render_location_section`, Stunden-Kopf und `_render_legend` nutzen sie |
| `src/output/renderers/comparison.py` | MODIFY | Stundenschleife nutzt `hour_cell_texts`; `have_hourly`/Ueberschrift und Legenden-Bedingung ueber die geteilten Praedikate |
| `tests/unit/test_compare_text_html_bausteine.py` | CREATE | echte Renderer-Aufrufe, Zelltext-Paritaet, Randfall Ueberschrift, Legenden-Schalter, DE und EN |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_hour_einfach_text`, `_fmt_thunder`, `fmt_word_cell` | Funktionen | bestehende Zellkette, wird gekapselt, nicht veraendert |
| `_should_merge_wind_dir`, `degrees_to_compass` | Funktionen | Windrichtungs-Zusammenlegung, schon geteilt |
| `local_fmt`, `local_hour` | Funktionen | Zeitlabel je Medium, bleibt im jeweiligen Renderer |
| i18n-Katalog (`vergleich.stunden.klartext_titel`, `vergleich.ausblick.titel`) | Katalog | Ueberschriften und Zellbeschriftungen in DE/EN; keine neuen Nutzertexte |
| `select_cv2_rows`, `rowless_count` (#2991) | Funktionen | Vorbild-Muster oeffentlicher Baustein in `compare_html.py`, von `comparison.py` importiert |
| `compact_compare.py`, `compare_*`-Services, `validator_render_service.py` | Konsumenten | importieren oeffentliche Namen aus `compare_html`; private `_render_*` werden nicht von aussen genutzt |
| `feat_3122_was_steht_wo.md` (AC-10), #1366 | Specs/Issues | Sollverhalten: Stundenblock entfaellt ohne Stundendaten |
| `.claude/hooks/email_spec_validator.py` | Validator | prueft echt zugestellte Staging-Mail (Stundenzeilen-Format) |

## Implementation Details

1. **`hour_cell_texts(...)`** in `compare_html.py`: liefert fuer eine Stunde die Zellfolge als Paare (Label, Text) in der heutigen Reihenfolge, inklusive Hagel, Signalen und zusammengelegter Windrichtung. Mit `html=True` kommt die Ampel-Auszeichnung der HTML-Zellen, sonst Klartext. `_render_hour_row` bettet die Paare in die Tabellenzellen, die Klartext-Schleife in die Textzeile; Zeitlabel setzt jede Seite selbst.
2. **`hourly_block_visible(locations, hourly_enabled)`**: `hourly_enabled` und `any(not loc.error and loc.hourly_data)`. `_render_location_section` gibt "" fuer Orte mit Fehler oder ohne Stundendaten zurueck; der Stunden-Kopf im HTML (`_per_location`) wird nur geschrieben, wenn das Praedikat wahr ist. Klartext ersetzt `have_hourly` bzw. die Ueberschriftsentscheidung durch dasselbe Praedikat (Klartext-Verhalten bleibt gleich, #1366). Der Ausblick bleibt vom Praedikat unabhaengig und erscheint weiter.
3. **`legend_visible(hourly_enabled, outlook_enabled)`**: `hourly_enabled or outlook_enabled`; beide Legenden rufen es auf. Inhalt der Legenden bleibt je Medium unveraendert.
4. Bestehende Stundentabellen-Tests dienen als Geländer fuer "Ausgabe byte-gleich" in allen Normalfaellen.

## Expected Behavior

- **Input:** `render_compare_email(...)` (Klartext + HTML) mit beliebiger Kombination aus `hourly_enabled`, `outlook_enabled`, Orten mit/ohne Stundendaten oder Fehler, Sprache DE/EN.
- **Output:** Alle Normalfaelle byte-identisch zu vorher. Einzige Aenderung: HTML ohne jeden Ort mit Stundendaten zeigt keine Ueberschrift "Stundenverlauf" mehr.
- **Side effects:** Keine. Keine Datenmigration, keine Permissions, keine AppStorage-Keys, keine neuen Katalogtexte.

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `tests/unit/test_compare_text_html_bausteine.py` (Kern-Schicht, deterministisch, ohne Netz, echte Renderer-Aufrufe, kein `Mock`/`patch`/`MagicMock`), parametrisiert ueber DE und EN, wo Beschriftungen zaehlen.

- [ ] Test 1: GIVEN Orte mit Stundendaten inkl. Hagel und Windrichtung / WHEN Klartext und HTML gerendert werden / THEN stehen je Stunde dieselben Zellwerte in beiden Fassungen (Werte, Hagel-Signal, zusammengelegte Windrichtung), nur Zeitlabel und Ampel-Auszeichnung unterscheiden sich.
- [ ] Test 2: GIVEN alle Orte mit Fehler oder ohne `hourly_data`, `hourly_enabled` an / WHEN gerendert wird / THEN zeigt weder Klartext noch HTML die Stunden-Ueberschrift (RED: HTML zeigt sie vorher).
- [ ] Test 3: GIVEN derselbe Randfall mit `outlook_enabled` an / WHEN gerendert wird / THEN erscheint der Ausblick weiterhin in beiden Fassungen.
- [ ] Test 4: GIVEN mindestens ein Ort mit Stundendaten / WHEN gerendert wird / THEN steht die Stunden-Ueberschrift in beiden Fassungen; ein zweiter Ort mit Fehler aendert daran nichts.
- [ ] Test 5: GIVEN die vier Kombinationen von `hourly_enabled` und `outlook_enabled` / WHEN gerendert wird / THEN ist die Legende in Klartext und HTML jeweils gleichzeitig vorhanden oder fehlt in beiden.
- [ ] Test 6: GIVEN eine Stundenzeile / WHEN gerendert wird / THEN lautet das Zeitlabel im Klartext `HH:MM` und im HTML `HH` (Pin gegen Vereinheitlichung).
- [ ] Test 7: GIVEN die nicht geteilten Teile / WHEN gerendert wird / THEN bleiben Ort-Abschnittsform samt Ausblick-Ueberschrift, Einfach-Form und Uebersichts-Zellformate (`213°`, `4h`, `-` im Klartext) unveraendert.

Regressionsanker (unveraendert gruen): `tests/tdd/test_compare_hour_table_columns.py`, `test_compare_local_time_basis.py`, `test_hail_compare_fmt_thunder_and_hour_table.py`, `test_compare_validator_hour_format.py`, `test_compare_preview_hourly_parity.py`, `tests/unit/test_compare_plaintext_html_rows_one_list.py`, `test_compare_mail_plaintext_html_label_parity.py`, `test_compare_metric_parity.py`, `tests/tdd/test_channel_metric_matrix.py`, `tests/unit/test_compare_matrix_metric_selection.py`.

## Acceptance Criteria

- **AC-1:** Given eine Vergleichsmail mit Stundenverlauf, in der Stunden Hagel und eine zusammengelegte Windrichtung haben / When Klartext- und HTML-Fassung gerendert werden (DE und EN) / Then zeigen beide fuer jede Stunde dieselben Zellwerte und Beschriftungen, nur Zeitlabel und Ampel-Auszeichnung unterscheiden sich.
  - Test: `tests/unit/test_compare_text_html_bausteine.py::test_stundenzellen_gleich_in_klartext_und_html` (parametrisiert DE/EN, echte Renderer-Aufrufe).

- **AC-2:** Given Stundenverlauf und Ausblick sind eingeschaltet, aber alle Orte haben einen Fehler oder keine Stundendaten / When die Mail gerendert wird / Then steht weder in der Klartext- noch in der HTML-Fassung die Ueberschrift "Stundenverlauf", und der Ausblick wird in beiden weiterhin gezeigt.
  - Test: `tests/unit/test_compare_text_html_bausteine.py::test_ohne_stundendaten_keine_ueberschrift_ausblick_bleibt` (RED: HTML zeigt die Ueberschrift vorher).

- **AC-3:** Given mindestens ein Ort hat Stundendaten (auch wenn ein anderer Ort einen Fehler hat) / When die Mail gerendert wird / Then steht die Stunden-Ueberschrift wie bisher in Klartext und HTML, und die Ausgabe der Normalfaelle ist unveraendert.
  - Test: `tests/unit/test_compare_text_html_bausteine.py::test_normalfall_ueberschrift_in_beiden` plus die bestehenden Stundentabellen-Tests unveraendert gruen.

- **AC-4:** Given alle vier Kombinationen aus Stundenverlauf an/aus und Ausblick an/aus / When Klartext und HTML gerendert werden / Then ist die Legende in beiden Fassungen jeweils gleichzeitig vorhanden oder gleichzeitig abwesend.
  - Test: `tests/unit/test_compare_text_html_bausteine.py::test_legende_schalter_in_beiden_gleich` (vier parametrisierte Faelle).

- **AC-5:** Given eine Stundenzeile in der Vergleichsmail / When die Mail gerendert wird / Then lautet das Zeitlabel im Klartext weiterhin `HH:MM` und im HTML weiterhin `HH`, sodass der Mail-Validator beide Formate wie bisher erkennt.
  - Test: `tests/unit/test_compare_text_html_bausteine.py::test_zeitlabel_je_medium_unveraendert` und `tests/tdd/test_compare_validator_hour_format.py` unveraendert gruen.

- **AC-6:** Given die bewusst nicht geteilten Teile (Ort-Abschnittsform samt Ausblick-Ueberschrift, Einfach-Form der Uebersicht, Risiko-Legende nur im HTML, Uebersichts-Zellformate `213°`/`4h`/`-`) / When die Mail nach dem Umbau gerendert wird / Then sind diese Teile byte-gleich zu vorher.
  - Test: `tests/unit/test_compare_text_html_bausteine.py::test_nicht_geteilte_teile_unveraendert` plus `tests/test_compare_top_n_render_invariance.py` (Golden-Snapshot) und `tests/tdd/test_channel_metric_matrix.py` unveraendert gruen.

## Definition of Done

- AC-1 bis AC-6 durch automatisierte Tests belegt, alle gruen; Kern-Testschicht gruen; alle 6 CI-Checks gruen.
- Renderer-Commit-Gate: Modus-Matrix-Test (`tests/tdd/test_channel_metric_matrix.py`) und `.claude/hooks/email_spec_validator.py` frisch gruen.
- Staging-Verifikation: echt zugestellte Vergleichsmail besteht den Validator (Exit 0).

## Known Limitations

- Die Formatunterschiede der Uebersicht zwischen Klartext und HTML bleiben bestehen (#3431); die Ampelstunde `@HH` bleibt bei #3047.
- Zeitlabel `HH:MM` gegen `HH` bleibt je Medium unterschiedlich, weil Validator und Tests es so festschreiben.
- Verworfene Varianten: B (gemeinsamer Zellformatter inkl. Uebersicht, aendert sichtbare Formate) und die volle Vereinheitlichung der Ort-Abschnitte (verletzt #1323/#1378/#1505).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt ADR-0127 (ein Katalog, eine Verarbeitung) fuer Stundenzellen, Stunden-Ueberschrift und Legende um; aendert weder Kanaele, Provider, Datenmodell noch Auth. Der Randfall-Fix stellt nur das bereits freigegebene Verhalten aus feat_3122 AC-10 her.

## Changelog

- 2026-11-26: Initial spec created (Variante A aus `docs/context/rework-3425-compare-bausteine.md`; Formatangleichung nach #3431 ausgelagert)
