# Context: rework-3425-compare-bausteine (Issue #3425)

## Request Summary

Folge zu #2991. In der Vergleichsmail sind Klartext (`src/output/renderers/comparison.py`) und HTML
(`src/output/renderers/email/compare_html.py`) weiterhin doppelt aufgebaut: Stundenzellen,
Abschnitte/Überschriften je Ort, Einfach-Form der Übersicht, Legenden-Bedingung, Zellformat.
Ziel: gemeinsamer Baustein, damit beide Fassungen nicht auseinanderlaufen. Sichtbare
Formatangleichung (`213°`/`4h`/`-` vs `213 °`/`4 h`/`–`) ist laut Issue eine Produktfrage.

## Related Files (Stand Explore-Bericht, Zeilen aktuell)

| Datei | Relevanz |
|---|---|
| `src/output/renderers/comparison.py` | Klartext-Renderer. Abschnitte 346-451, Stundenzeilen 391-426, Legende 464-470, `_PLAIN_FMT` 83-109 (Kommentar verweist auf #3425), `_pruefe_plain_fmt` 112-126, `_friendly_overview_text` 621-645, `_fmt_overview_cell` 648-678, `_ampel_stunde` 699-724, `_plain_metric_cell` 727-750, fehlender Wert `"-"` 301 |
| `src/output/renderers/email/compare_html.py` | HTML-Renderer. `_render_hour_row` 1169-1224, `_render_location_section` 1300ff, Ausblick 1401-1463, `_render_legend` 1671-1704, `_per_location` 1979-1994, Stunden-Kopf 1966-1971/2029, `_friendly_overview_html` 780-808, `_fmt_metric` ~771, `_fmt_deg` 188, `select_cv2_rows` 905-914, `rowless_count` 917, `CV2_ZEILEN` ~330-400, `derive_row_labels` 503 |
| `src/output/renderers/metric_format.py` | `NO_VALUE = "–"` (81) |
| `src/output/renderers/email/compact_compare.py`, `src/services/compare_*`, `validator_render_service.py` | importieren öffentliche Namen aus compare_html (nicht die privaten `_render_*`) |

## Existing Patterns

- #2991-Muster: öffentliche Funktion in `compare_html.py` (`select_cv2_rows`, `rowless_count`), die
  `comparison.py` importiert; Klartext-eigene reine Format-Zuordnung `_PLAIN_FMT` mit
  Import-Drift-Prüfung `_pruefe_plain_fmt`.
- Stundenzellen teilen bereits die Kette `_hour_einfach_text` → `_fmt_thunder` (Hagel, Signale) →
  `fmt_word_cell`; Windrichtungs-Zusammenlegung identisch über `_should_merge_wind_dir` +
  `degrees_to_compass`. Verbleibend doppelt: die Schleife selbst (Zeitlabel, Zellsequenz).

## Ist-Abweichungen (Kandidaten; Analyse muss je Punkt "fachlich gewollt vs. Drift" klären)

1. **Zeitlabel Stunde:** Klartext `07:00` (`local_fmt` %H:%M), HTML `07`.
2. **Stunden-Überschrift:** Klartext nur wenn mindestens eine Stundenzeile geschrieben wurde; HTML
   immer bei `hourly_enabled` (ohne Datenprüfung).
3. **Ort-Abschnitt:** Klartext zeigt Ort bei Stunden ODER Ausblickzeilen ODER Ausblick-Zustandstext,
   Kopf `Name (TZ)`; HTML trennt Stundenabschnitt (leer bei Fehler/ohne Daten) und Ausblick-Block mit
   eigener Überschrift „Name · 3-Tages-Ausblick“ bzw. Zustandsblock.
4. **Einfach-Form Übersicht:** gemeinsam ist `_friendly_outlook_text`; Klartext zusätzlich
   SMS-Variante (`cloud_stufe`) und `@HH`-Ampelstunde, HTML Ampelpunkt via `fmt_val`.
5. **Legende:** Bedingung `hourly_enabled or outlook_enabled` doppelt; HTML zusätzlich Risiko-Punkte
   und Warn-Kürzel-Zeile, Klartext keine Risiko-Legende.
6. **Zellformat Übersicht:** Windrichtung `f"{v}°"` (ungerundet) vs HTML `:.0f` + Leerzeichen;
   Sonne `4h` vs `4 h`; fehlender Wert `-` vs `–`. Niederschlag gleich.

## Dependencies / Dependents

- Upstream: `metric_format.format_value`, `fmt_val`, `degrees_to_compass`, i18n-Katalog
  (`vergleich.stunden.klartext_titel`, `vergleich.ausblick.titel`), `local_fmt`/`local_hour`.
- Downstream: Versand Vergleichsmail (multipart text+html), Vorschau (`compare_preview_service`),
  Mail-Validator `email_spec_validator.py` (prüft echt zugestellte Staging-Mail), Renderer-Commit-Gate.

## Existing Specs

- `docs/specs/compare_email.md`
- `docs/specs/modules/refactor_2991_compare_zeilenliste.md` (Vorbild)
- `docs/context/refactor-2991-compare-zeilenliste.md`
- `docs/reference/renderer_email_spec.md` (für Compare kaum relevant)

## Tests

- Parität: `tests/unit/test_compare_plaintext_html_rows_one_list.py`,
  `tests/unit/test_compare_mail_plaintext_html_label_parity.py`, `tests/unit/test_compare_metric_parity.py`
- Stunden: `tests/tdd/test_compare_hour_table_columns.py`, `test_compare_local_time_basis.py`,
  `test_hail_compare_fmt_thunder_and_hour_table.py`, `test_compare_validator_hour_format.py`,
  `test_compare_preview_hourly_parity.py`
- Modus-Matrix: `tests/tdd/test_channel_metric_matrix.py`, `tests/unit/test_compare_matrix_metric_selection.py`

## Risks

- Renderer-Commit-Gate: Mail-Inhalts-Commits brauchen frischen Modus-Matrix-Test + Validator.
- Jede Verhaltensangleichung (Punkte 1-3, 6) ist in der Mail sichtbar → PO-Entscheidung nötig,
  reine Zusammenlegung ohne sichtbare Änderung nicht.
- Scope-Limit ±250 LoC / 4-5 Dateien: alle fünf Punkte zusammen evtl. zu groß → Split prüfen.
- Validator `email_spec_validator.py` kann auf heutige Formate (`07:00`, `-`) eingestellt sein.

## Analysis

**Type:** Rework (Dedup) mit einem Spec-Fix im Randfall. Track: feature, Score 4.

### Bewertung der Ist-Abweichungen (Historie + Specs + Code verifiziert)

| Punkt | Urteil | Folge |
|---|---|---|
| 1 Zeitlabel `07:00`/`07` | Drift, aber je Medium festgenagelt (Validator `_STUNDE_RE` email_spec_validator.py:1167 Klartext, :1136 HTML, viele Klartext-Tests) | **nicht** vereinheitlichen |
| 2 Stunden-Überschrift | Klartext korrekt (#1366). HTML zeigt Überschrift bei `hourly_enabled` auch ohne einen Stundenabschnitt (compare_html.py 1964-1971 vs `_render_location_section` 1300-1308 gibt "" bei error/leer) → verstößt gegen feat_3122 AC-10 („Stundenverlauf entfällt als Block“) im Randfall „alle Orte Fehler/ohne Stundendaten“ | **hier fixen**, gemeinsames Prädikat |
| 3 Ort-Abschnitte/Ausblick-Kopf | gewollt je Medium (#1323, #1378, #1505, #2666) | kein Baustein, in Spec begründen |
| 4 Einfach-Form | gewollt je Kanal (feat_3122 Nr. 4: HTML Ampelpunkt, Text Stufenwort; SMS-`cloud_stufe`; `@HH` gehört zu #3047); Kern `_friendly_outlook_text` schon geteilt | kein Baustein, in Spec begründen |
| 5 Legende | nur die Bedingung `hourly_enabled or outlook_enabled` doppelt (comparison.py ~464, compare_html.py ~1694); Risiko-Punkte HTML-only kanalbedingt | gemeinsames Prädikat |
| 6 Zellformat Übersicht | ungeklärt: `213°`/`213 °`, `4h`/`4 h` ohne Entscheidung; Platzhalter: #1670 entschied „ein Platzhalter `NO_VALUE` (–)“, Klartext-Compare (comparison.py:301 `-`) fällt aus dem Testumfang; Klartext-Windrichtung ungerundet | **Folge-Ticket** mit PO-Frage |

### Affected Files (Change Type)

- `src/output/renderers/email/compare_html.py` MODIFY: neue öffentliche Bausteine
  `hour_cell_texts(...)` (Zell-Kette einer Stunde, Label+Text-Paare, `html`-Schalter),
  `hourly_block_visible(locations, hourly_enabled)` (true nur wenn ein Ort ohne error und mit
  `hourly_data`; dasselbe Prädikat nutzt `_render_location_section`), `legend_visible(hourly, outlook)`;
  `_render_hour_row` nutzt `hour_cell_texts`; Stunden-Kopf nur bei `hourly_block_visible`.
- `src/output/renderers/comparison.py` MODIFY: Stundenschleife nutzt `hour_cell_texts`; `have_hourly`/
  Überschrift und Legende über die geteilten Prädikate.
- `tests/unit/test_compare_text_html_bausteine.py` CREATE: (a) Zelltexte je Stunde in Klartext und HTML
  gleich (Werte, Hagel, Windrichtung), (b) alle Orte Fehler/leer → weder HTML noch Klartext zeigt
  Stunden-Überschrift, (c) Legende in beiden gleich an/aus.

### Scope / Risk

~120-160 LoC, 3 Dateien. Sichtbare Änderung nur im HTML-Randfall (keine leere Überschrift).
Mail-Inhalts-Commit → Renderer-Gate (Modus-Matrix + `email_spec_validator.py` gegen Staging-Mail).
Risiko mittel-niedrig: bestehende Stundentabellen-Tests sind das Geländer für „Ausgabe unverändert“.

### Technical Approach / Reihenfolge

1. RED: neue Testdatei (Randfall-Überschrift HTML rot; Paritäts-/Prädikat-Tests rot mangels Bausteinen).
2. `hour_cell_texts` herauslösen, beide Seiten umstellen (Ausgabe byte-gleich).
3. `hourly_block_visible` + HTML-Kopf bedingt; `_render_location_section` und Klartext `have_hourly` nutzen dasselbe Prädikat.
4. `legend_visible`.
5. Gate-Tests + Staging-Validator.

### Dependencies

Wie Context. Kein Datenmodell-, API- oder Kanal-Vertrag betroffen; Telegram/SMS/Kompakt unberührt.

### Open Questions

Keine für dieses Ticket. Formatangleichung (Punkt 6) als Folge-Ticket #3431 mit PO-Frage ausgelagert.
