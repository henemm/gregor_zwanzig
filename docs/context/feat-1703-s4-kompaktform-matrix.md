# Context: Epic #1703 Scheibe 4 — Kompaktform-Matrix

## Request Summary

Epic #1703, Scheibe 4: Vier bisher unbewachte, namensähnliche "compact"-Ausgabeorte als eigene
Achse in `tests/tdd/test_channel_metric_matrix.py` aufnehmen (Fortsetzung der Achsen aus Scheibe
1–3, AC-Präfix `AC-S4-n`). Ziel laut `docs/reference/metric_output_matrix.md` Abschnitt 4.2 (Fläche
6+7) und Abschnitt 6 (Scheibe 4): die drei Verwechslungs-Orte + Telegram-Kurzform testtechnisch
disambiguieren.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compact.py:96` (`render_compact`) | Eigenständiges Kurzformat der E-Mail (Text-only). Nutzt `resolve_trip_active_metrics(dc.metrics, altbestand=...)` — **derselbe Resolver** wie an anderer Stelle im Vollmail-Pfad (Issue #1394 T2b). Ignoriert laut Docstring explizit alle Baustein-Toggles (`show_highlights` etc.) — PO-Entscheidung #722 —, **nicht** aber die Metrik-Auswahl selbst. |
| `src/output/renderers/email/html.py:878` (`_render_mobile_compact_rows`) | Mobile Kompaktzeilen **innerhalb** der Vollmail (kein eigenständiger Kanal). Rendert Stundentabellen-Zeilen über `allowed_col_keys`/`col_order`, die von außen hereingereicht werden — keine eigene Metrik-Selektionslogik hier, sondern reiner Präsentations-Layer. |
| `src/output/renderers/compact_summary.py` (`CompactSummaryFormatter`, `format_stage_summary` ab Z.42; `format_location_summary` ab Z.625) | Fließtext-Kompakt-Zusammenfassung. **Zwei Wrapper um einen geteilten Kern** (`format_weather_summary`, Issue #1278): Trip-Wrapper (`format_stage_summary`) nutzt rohes `dc.metrics` gefiltert auf `.enabled` (Z.168); Compare-Wrapper (`format_location_summary`) nutzt Parameter `enabled_metrics` (Compare-Renderer-IDs), übersetzt via `RENDERER_TO_TRIP_METRIC_ID`. Einzige der vier Stellen mit **etwas** Testabdeckung — aber nur für Gewitter/Hagel, nicht für Metrik-Selektion generell. |
| `src/output/renderers/narrow.py` (`render_telegram_bubbles` ab Z.625; Helfer ab Z.346, Z.586–597) | Telegram-Kurzform (SPEC: `docs/specs/modules/feat_1001_telegram_redesign.md`). Nutzt `dc.get_enabled_metric_ids()` (Z.735/741/776) — **ein dritter Mechanismus**, weder `resolve_trip_active_metrics` noch rohes `dc.metrics`-Filtern. Kommentar Z.649/721: ein Flag `telegram_kurzform` ist hier laut AC-10 (#1001) **wirkungslos** — bereits dokumentiertes, gewolltes Verhalten, keine neue Lücke. |
| `tests/tdd/test_channel_metric_matrix.py` (2843 Zeilen) | Bestehender Matrix-Wächter, Option C (#1514 Entscheidung): **ein** Register, achsenweise erweitert. Etablierte Konvention: `AC-S1-n` (Scheibe 1, Alarm-Renderer), `AC-S2-n` (Scheibe 2, Ausblick-Tabelle). Scheibe 4 würde `AC-S4-n` fortsetzen. |
| `docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md`, `fix_1703_s2_ausblick_matrix.md`, `fix_1703_s3_selectable_metrics.md` | Vorbild-Specs der bereits gelieferten Scheiben — Format, AC-Struktur, Umgang mit "Soll-Menge gerechnet, nie getippt". |
| `src/output/renderers/trip_metric_ids.py` (`resolve_trip_active_metrics`) | Kanonischer Resolver, von Scheibe 4 potenziell als Referenzverhalten heranzuziehen. |
| `src/app/models.py` (`UnifiedWeatherDisplayConfig.get_enabled_metric_ids`) | Der von `narrow.py` genutzte alternative Resolver — Abweichungsverhalten zu `resolve_trip_active_metrics` ist ungeklärt. |

## Existing Patterns

- **Achsen-Erweiterung statt neues Register** (Option C, PO-Entscheid aus #1514): jede Scheibe fügt
  `AC-Sn-*`-Tests in dieselbe Datei ein, mit ausführlichem Docstring-Block, der Scope und
  Nicht-Scope der Achse festhält (siehe Kopf von Scheibe 1/2 in der Testdatei, Z.36–51).
- **Soll-Menge GERECHNET, nie getippt** — Vorbild `tests/helpers/outlook_columns.py`,
  `test_compare_hourly_catalog_columns.py:122`. Für Scheibe 4 wäre die Soll-Menge vermutlich aus
  `_METRICS`/`_SELECTABLE_GATE_EXEMPT` (wie S1/S3) oder aus dem jeweiligen Resolver selbst
  abzuleiten — zu klären in der Analyse.
- **Gegenprobe ist Pflicht** (Token-Grenzen-Bewusstsein, Mutations-Gegenprobe) — S1 hatte dafür
  `test_ac_s1_2_sms_praefix_gegenprobe`.
- **Charakterisierung vor Fix:** S1/S3 haben bewusstes, dokumentiertes Verhalten (z.B.
  `temperature_cold`-Dublette, `telegram_kurzform` wirkungslos) NICHT repariert, sondern als
  Ist-Zustand bewacht — nur echte, unbewachte Lücken wurden geschlossen.

## Dependencies

- **Upstream:** `resolve_trip_active_metrics()` (compact.py), `dc.get_enabled_metric_ids()`
  (narrow.py), rohes `dc.metrics`/`enabled_metrics`-Parameter (compact_summary.py) — drei
  unterschiedliche Selektionswege für denselben fachlichen Zweck ("welche Metrik ist aktiv").
  `_METRICS`/`_SELECTABLE_GATE_EXEMPT` (`metric_catalog.py`), `RENDERER_TO_TRIP_METRIC_ID`
  (`compare_metric_ids.py`), `format_hail_note`/`hail_priority` (`metric_format.py`).
- **Downstream:** `render_compact()` wird im E-Mail-Kompaktformat-Dispatch genutzt (Format `compact`
  neben `full`, siehe `X-GZ-Format`-Header-Konvention aus CLAUDE.md); `render_telegram_bubbles()`
  ist der produktive Telegram-Ausgabeweg; `CompactSummaryFormatter`/`format_location_summary`
  speisen sowohl Trip-Mails als auch Ortsvergleich-Renderer.

## Existing Specs

- `docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md`
- `docs/specs/modules/fix_1703_s2_ausblick_matrix.md`
- `docs/specs/modules/fix_1703_s3_selectable_metrics.md`
- `docs/specs/modules/feat_1001_telegram_redesign.md` (Telegram-Bubbles, u.a. AC-10 zu
  `telegram_kurzform`)
- `docs/specs/modules/issue_722_email_compact_format.md` (`render_compact`, Baustein-Ignoranz)
- `docs/reference/metric_output_matrix.md` Abschnitt 4.2 (Flächen 6+7), Abschnitt 6 (Scheibe-4-Text)

## Risks & Considerations

- **Kernrisiko der Scheibe (aus dem Matrix-Dokument wörtlich):** die drei "compact"-benannten Orte
  werden im Code und in Commits regelmäßig verwechselt — Testnamen MÜSSEN das auflösen (z.B.
  `test_ac_s4_x_email_compact_...` vs. `..._mobile_compact_rows_...` vs.
  `..._compact_summary_...` vs. `..._telegram_narrow_...`).
- **Drei-Wege-Divergenz bei der Metrik-Selektion** (Hauptfund dieser Kontext-Phase): `compact.py`
  nutzt den kanonischen Resolver, `narrow.py` einen anderen (`get_enabled_metric_ids`),
  `compact_summary.py` filtert roh auf `.enabled` bzw. nimmt einen übersetzten Parameter. Ob diese
  drei Wege bei denselben Eingaben dasselbe Ergebnis liefern, ist **ungeklärt** — passt zum
  wiederkehrenden Projektmuster "dc.metrics kollabiert je nach Kanal unterschiedlich"
  (vgl. Memory zu #1719 S2, `reference_trip_renderers_see_collapsed_metrics`). Das ist vermutlich
  die eigentliche Prüffläche der Scheibe, nicht nur Vollständigkeit.
- **`confidence`/`cape` (Fläche 3, Scheibe 3 Vorbild)** — zu prüfen, ob diese vier Orte dieselbe
  Blindstelle hätten wie die bereits gefixten Kanäle, falls die Scheibe-3-Wächter sie nicht
  automatisch mitdecken.
- **Bereits dokumentiertes, NICHT zu reparierendes Verhalten** (nur charakterisieren):
  `telegram_kurzform` ist laut #1001 AC-10 wirkungslos; `render_compact()` ignoriert
  Baustein-Toggles bewusst (#722); `CompactSummaryFormatter` migriert bewusst NICHT auf
  `metric_format.format_value` (Klassifikation Issue #1214 Scheibe 5c) — eigene Wolken-Emoji-Skala
  weicht bewusst von der Katalog-Skala ab (Angleichung ist Scheibe 6, nicht Scheibe 4).
- **`_render_mobile_compact_rows` (html.py:878) hat vermutlich keine eigene Metrik-Selektionslogik**
  — reiner Präsentations-Layer über von außen hereingereichte `allowed_col_keys`. Zu klären in der
  Analyse: ob diese Stelle überhaupt eine eigene Achse braucht oder ob sie über den bestehenden
  Vollmail-Tabellenwächter bereits indirekt gedeckt ist (Fläche 6 nennt sie trotzdem separat).
- **Risiko laut Matrix-Dokument: mittel, Größe: mittel** (Scheibe 4).

## Analysis

### Type
Feature (Erweiterung eines bestehenden Test-Wächters um eine neue Achse, kein Bug-Fix).

### Bestätigter Kernbefund (Sub-Agent, mit Code-Zitaten verifiziert)

Reale, unbeabsichtigte Divergenz zwischen den drei Metrik-Selektionswegen:
- `resolve_trip_active_metrics()` (`trip_metric_ids.py:54-56`): Fallback auf `DEFAULT_TRIP_METRIC_IDS`, wenn aktive Auswahl leer UND `altbestand=True`.
- `get_enabled_metric_ids()` (`models.py:802-804`): KEIN Fallback, liefert `[]`.
- **Beide** wenden das `selectable=False`-Gate NICHT an — anders als `get_metrics_for_channel()`/`get_metrics_for_report_type()` (`models.py:684`, Kommentar Z.845-846, #1585). Eine zentral nicht-wählbare Metrik (`cape`, `confidence`) könnte bei Altbestandstrips mit `enabled=True` über `render_compact()` oder `render_telegram_bubbles()` durchrutschen.
- `compact_summary.py` ist ein **dritter** Weg: keine generische Resolver-Funktion, sondern eine handgeschriebene `if/elif`-Kette für ~10 fest benannte Metrik-IDs — die übrigen ~16 wählbaren Katalog-Metriken (z.B. `uv_index`, `snow_depth`, `freezing_level`) haben dort **strukturell keine Zelle**.

### Zusätzlich gefundene Specs (Ergänzung zur Related-Specs-Liste oben)
`docs/specs/modules/compact_summary.md` (v1.4, approved), `docs/specs/modules/compare_location_summary.md` (v2.1, draft), `docs/specs/_archive/modules/issue_614_615_telegram_kurzform.md`, `docs/specs/modules/feat_1260_telegram_kurzstil.md` (v1.0, draft), `docs/specs/_archive/modules/issue_729_render_compact_empty_guard.md`, `docs/specs/_archive/modules/issue_831_mobile_einfach_stundenraster.md`, `docs/specs/_archive/modules/fix_1330_compact_summary_daywindow.md`, `docs/specs/_archive/modules/bug_305_mobile_email_v2.md`, `docs/specs/_archive/modules/bug_636_mobile_email_table.md`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | Neue Achse `AC-S4-1` (email/compact.py) bis `AC-S4-4` (narrow.py), analog S1-S3-Muster. Geschätzt 12-16 neue Testfunktionen. |
| `docs/specs/modules/fix_1703_s4_kompaktform_matrix.md` | CREATE | Spec analog S1-S3. |
| `docs/reference/metric_output_matrix.md` | MODIFY | Flächen 6+7 nach Abschluss auf den neuen Wächter umtragen (DoD jeder Scheibe). |
| Produktivcode (`compact.py`, `html.py`, `compact_summary.py`, `narrow.py`) | KEINE Änderung | Charakterisierung, kein Fix — siehe Technical Approach. |

### Scope Assessment
- Files: 2-3 (Testdatei, Spec, Matrix-Dokument-Update)
- Estimated LoC: Produktivcode 0; Testcode ~150-250 Zeilen (12-16 Testfunktionen)
- Risk Level: LOW-MEDIUM — kein Assertion-Overlap mit den vier Bestandstestdateien zu diesen Renderern (`test_issue_729_render_compact_empty.py`, `test_compact_summary_*.py`, `test_issue_1001_telegram_bubbles.py`, `test_bug305_mobile_email.py`/`test_bug_636_...py`), da diese Struktur/Leerfälle prüfen, nicht Metrik-Vollständigkeit.

### Technical Approach (Empfehlung des Plan-Agenten)
**Charakterisierung, nicht Fix.** Die Resolver-Divergenz ist derselbe Fehlertyp wie in Scheibe 3 (fehlendes `_is_selectable`-Gate an einem weiteren Choke-Point) — dort war die Antwort ein Test, kein Redesign. Eine Vereinheitlichung der drei Resolver wäre echte Produktivcode-Änderung mit Verhaltensänderung an mehreren Kanälen gleichzeitig — das ist PO-Sache, nicht Teil dieser Scheibe.

Vier Namensblöcke in der Matrix-Datei:
- `AC-S4-1_email_compact_*` (render_compact, generisch über alle 26 Metriken, ~3-4 Tests)
- `AC-S4-2_mobile_compact_rows_*` — **schlank**: kein eigener Selektionsweg (nimmt `allowed_col_keys`/`col_order` vom Aufrufer entgegen), deckt sich mit Bestand AC-13. Ein Charakterisierungstest reicht, keine volle 26er-Parametrisierung.
- `AC-S4-3_compact_summary_*` — mit benannter Positivliste (~10 Metrik-IDs) + expliziter Nichtscope-Aussage für den Rest, analog `_NIGHT_SCALAR_IDS`-Muster (`channel_layout.py:88`). ~5-6 Tests (Trip-Wrapper, Compare-Wrapper, Nichtscope, Gate-Charakterisierung).
- `AC-S4-4_telegram_narrow_*` (render_telegram_bubbles, generisch über alle 26, ~3-4 Tests inkl. Divergenz-Charakterisierung ggü. AC-S4-1).

`_render_mobile_compact_rows` bekommt bewusst **keine** volle eigene Achse — Risiko sonst: ein Test, der `resolve_metric_col_order()` faktisch ein zweites Mal prüft.

### Dependencies
Wie in "Dependencies" oben, bestätigt durch Sub-Agent-Recherche. Keine neuen gefunden.

### Open Questions — GEKLÄRT (PO-Entscheid 2026-08-12)

- [x] **(a) Resolver-Divergenz — mit Wirkort-Nachweis geklärt.** PO-Sorge war zunächst: „confidence" könnte über die drei Kurzformen durchrutschen. **Nachgemessen an der echten Versandstelle** (`TripReportFormatter.format_email()`, nicht isoliert): Kein aktueller Verstoß. `format_email()` filtert `dc` IMMER über `get_metrics_for_channel()` (das `_is_selectable()`-Gate, #1585), BEVOR `render_compact()`, `CompactSummaryFormatter.format_stage_summary()` oder `render_telegram_bubbles()` (via `_dc_telegram`, bereits mit Adversary-Fix aus einer früheren Scheibe abgesichert) die Metrikliste sehen. `report_type` ist in JEDER Produktiv-Aufrufstelle (`preview_service.VALID_REPORT_TYPES`) hart auf `("morning", "evening")` beschränkt — der ungefilterte Zweig in `format_email()` (Zeile ~129 ff., nur für andere `report_type`-Werte) ist damit in Produktion **totes Gleis**. Die vierte Stelle, `format_location_summary()` (Compare-Wrapper), ist **selbst tot** — nirgends mehr aufgerufen seit Rework #1300 (PO-Entscheid 2026-07-17, Summary-Block aus Vergleichs-Mail entfernt; `docs/specs/modules/rework_1300_compare_summary_block_removal.md`, Status im Dokument noch "draft", aber Aufrufstellen in `compare_html.py`/`comparison.py` bestätigt entfernt).
  **Restrisiko (strukturell, nicht akut):** Die drei Funktionen haben selbst KEIN eigenes Gate — sie verlassen sich vollständig auf den vorgeschalteten Aufrufer. Ein künftiger neuer Aufrufer, der diese Vorfilterung vergisst, würde lautlos durchrutschen, ohne dass ein bestehender Test es fängt.
  **PO-Entscheid:** Scheibe 4 bewacht NUR den heutigen (korrekten) Zustand — Tests laufen über die ECHTE Aufrufkette (`format_email()`), nicht isoliert gegen die nackten Renderer-Funktionen (Prüfort=Wirkort-Prinzip, wie bei S1-S3). KEIN zusätzliches Produktivcode-Schloss in dieser Scheibe. Das strukturelle Restrisiko (kein Defense-in-Depth in den Funktionen selbst) wird als Nebenbefund in #1199 gebucht, kein eigenes Issue (nicht nutzersichtbar, aktuell kein Fehlverhalten).
- [x] **(b) CompactSummaryFormatter-Nichtscope:** PO-Entscheid: **Ja, als Sollzustand festschreiben.** Die Positivliste (~10 von 26 Metriken im Fließtext) bleibt bewusster Dauerzustand, keine Erweiterung.

### Konsequenz für den Testaufbau (wichtig, ersetzt frühere Annahme)

Die AC-S4-Tests für `render_compact()`, `CompactSummaryFormatter.format_stage_summary()` und `render_telegram_bubbles()` MÜSSEN wie die bestehenden AC-1/AC-2-Tests (Scheibe 3) über `TripReportFormatter().format_email()` mit `report_type` in `{"morning","evening"}` laufen — NICHT durch isolierten Direktaufruf der nackten Funktionen mit `_single_metric_dc()`. Ein isolierter Test würde einen Zustand prüfen, der in Produktion nie eintritt (falscher Prüfort), und könnte fälschlich ROT werden, obwohl nichts kaputt ist. `format_location_summary()` (Compare-Wrapper) bekommt KEINE eigene AC — sie ist tot; ein kurzer Charakterisierungssatz im Spec-Dokument reicht („nicht produktiv verdrahtet seit #1300").

## Related Non-Scope (für die Analyse-Phase markiert, nicht Teil von Scheibe 4)

- Scheibe 5 (Compare-Zellwert-Vollständigkeit) — Fläche 4.
- Scheibe 6 (Form-Wächter über Grammatik-Klassen, u.a. die Wolken-Emoji-Skala-Angleichung) —
  Fläche 8 teilweise.
- Scheibe 7 (Reihenfolge jenseits E-Mail/Telegram-rich) — Fläche 5, blockiert bis 7a entschieden.
