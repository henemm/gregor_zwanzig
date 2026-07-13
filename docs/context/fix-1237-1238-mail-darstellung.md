# Context: fix-1237-1238-mail-darstellung

## Request Summary

Zwei gebündelte Mail-Darstellungs-Bugs (Label `bundle:G-mail-darstellung`):

- **#1237** — Stundentabelle der **Ortsvergleichs-Mail**: Zeit-Spalte soll nur die Stunde zeigen (`07` statt `07:00`), Sicht-Spalte den Wert ohne Einheit (`38.3` statt `38.3 km`), damit die Spalten schmaler werden.
- **#1238** — **Amtliche-Warnung-Sektion**, Trip-Standalone-Alarmmail: der PO versteht mehrere Elemente nicht bzw. sie widersprechen sich (doppelter Warn-Titel, „Gültig: unbekannt", Quelle-Box passt nicht zu den Route-Chips, redundanter „übrige Strecke frei"-Satz, unklares Label „Route:").
- **#1239** — **dieselbe Warn-Sektion, aber der Compare-Pfad** (Ortsvergleich-Standalone-Alarm, Preset „Le Var", 8 Warnungen über 8 Orte). Erbt alle Mängel aus #1238 **plus** eigene: unlesbarer Betreff, ebenso unlesbarer H1-Satz, 8 × 8 Route-Chips, keine Bündelung gleichartiger Warnungen.

#1216 (Vorlage übernehmen) wurde im Intake als erledigt geschlossen; #1238/#1239 sind der inhaltliche Rest-Scope an derselben Mail-Familie.

## Related Files

### #1237 — Stundentabelle

| Datei:Zeile | Relevanz |
|---|---|
| `src/output/renderers/email/compare_html.py:408` | `_render_hour_row()` — `dp.ts.strftime("%H:%M")` = **die „07:00"-Stelle** (einzige Quelle) |
| `src/output/renderers/email/compare_html.py:156-157` | `_fmt_visibility()` — `f"{v/1000:.1f} km"` = **die „38.3 km"-Stelle** (einzige Quelle) |
| `src/output/renderers/email/compare_html.py:190` | `HOUR_METRICS`-Eintrag: Spaltenkopf-Label „Sicht" |
| `src/output/renderers/email/compare_html.py:421-430` | `_render_hour_table()` — Spaltenköpfe, „Zeit" hart als erste Spalte |
| `src/output/renderers/email/compare_html.py:581-598` | `_render_legend()` — heute nur Ampel-/Warn-Kürzel, **keine Einheiten** |
| `src/output/renderers/email/html.py:253` | Trip-Briefing **mobile** Stundenliste: `f"{vis_km:.1f} km"` (einzige Trip-Stelle mit Einheit) |

**Bereits konform (nicht anfassen):** Trip-Briefing-Stundentabelle — `email/helpers.py:89,140` liefert Zeit schon als `"07"`, `helpers.py:596-600` die Sicht schon ohne Einheit (#814 AC-5). Einheiten stehen dort in der Legende (`build_units_legend`, `helpers.py:338-356`), gespeist aus `app/metric_catalog.py:336-350` (`display_unit="km"`).

**Nicht betroffen:** SMS/Telegram (`sms_trip.py`, `narrow.py` — andere Formate), Frontend (rendert die Mail-Tabelle nicht), Plain-Vergleich (`renderers/comparison.py:130` nutzt `%H:%M`, hat aber keine Sicht-Spalte).

### #1238 — Warn-Sektion

Hauptdatei: `src/output/renderers/alert/official_alerts.py` (~1140 Zeilen).

| Mangel | Datei:Zeile | Ursache |
|---|---|---|
| M1 doppelter Titel | `official_alerts.py:579-587` (`_standalone_warn_type_html`), `:608`, `:644` | `typ` aus `_hazard_display` (starr „Zugang gesperrt") **+** voller Quell-Label (`"Zugang eingeschränkt — Monts Toulonnais"`, gebaut in `services/official_alerts/massif_closure.py:58-65`) werden **konkateniert** → zwei widersprüchliche Stufen |
| M2 „Gültig: unbekannt" | `official_alerts.py:328-333` (`_format_validity`) | Liefert `"unbekannt"`, sobald `valid_from`/`valid_to` fehlen. `massif_closure.py:66-69` und `meteo_forets.py:113-119` setzen **keine** Zeiten, obwohl beide **tagesbezogen** sind (J1-Index) |
| M3 Quelle-Box widersprüchlich | `official_alerts.py:663-679` (`_standalone_src_sentence`), eingebunden `:694` | Satz nutzt nur `ordered[0].scope_label`, steht aber unter **allen** Warnungen → verallgemeinert die führende Warnung |
| M4 redundanter Satz | `official_alerts.py:611-618` (`.route-note`) | Wiederholt in Prosa, was die durchgestrichenen Chips (`:610`) schon zeigen — bei 7–8 Orts-Chips wird daraus ein Absatz |
| M5 Label „Route:" | `official_alerts.py:630` (grid), `:659` (stacked) | Hartkodiert — auch für Compare-Notices (Chips = **Orte**, keine Route) und Massiv-Sperren |

### #1239 — zusätzliche Mängel im Compare-Standalone-Alarm

| Mangel | Datei:Zeile | Ursache |
|---|---|---|
| M6 unlesbarer Betreff | `official_alerts.py:381-407` (`render_official_alert_subject`), Aufruf `services/notification_service.py:608` | `[{prefix}] {leading.scope_label} · {alle Warnungen mit " + "}`. Bei Compare ist `scope_label` bei mehreren betroffenen Orten die **komplette Kommaliste** (`:1132`), und die Warnungs-Aufzählung ist **ungedeckelt** (8 Stück). Vorlage (Z. 167): `[KHW 403] gesamte Route · GELB Hitze (Fr) + Gewitter (Sa)` |
| M7 H1-Satz wiederholt den Betreff | `official_alerts.py` (Headline in `render_official_alert_html`, `:704-758`) | Zählt Typen **und** alle Orte erneut auf → zweiter Textblock derselben Information |
| M8 keine Bündelung gleichartiger Warnungen | `dedupe_official_alerts` (`:212-242`) + `build_compare_official_alert_notices` (`:1104-1140`) | Dedup-Schlüssel = (`dedup_id`\|`region_label`\|`label`, `hazard`). Waldbrand Stufe 3 in zwei **verschiedenen Zonen** ⇒ zwei getrennte Notices, jede mit eigener 8er-Chip-Liste. Die Vorlage fordert das Gegenteil (Z. 245: „Deckt eine Warnung mehrere Segmente ab, wird sie **einmal** genannt mit Segment-Liste") |
| M9 Chip-Explosion | `official_alerts.py:609-610` | Jede der 8 Warnungen rendert **alle** 8 Orte (meist durchgestrichen) ⇒ 64 Chips. Vorlage: ≤4 Segment-Chips |
| M10 Stufe doppelt | `services/official_alerts/meteo_forets.py` (Label „Waldbrand-Gefahr — Stufe 3") + Eskalations-Meter „ORANGE · 2/3" | Label codiert die Stufe im Text, das Meter zeigt sie nochmal — zwei Skalen nebeneinander (Stufe 3 vs. 2/3) |
| M11 Umbruch „ORANG/E" | `official_alerts.py:620` (`grid-template-columns:130px`) | Meter + Stufenwort passen bei „ORANGE" nicht in die 130-px-Spalte (kosmetisch) |

**Korrektes Vorbild im eigenen Code (für M1):** `_typ_tag` (Betreff, `official_alerts.py:358-378`) und der embedded Block (`:849-868`) **ersetzen** das generische Typ-Wort durch den reicheren Label, statt zu präfixen. Nur der Standalone-Grid/Stacked-Pfad konkateniert.

### Aufrufer von `render_warn_block` (`official_alerts.py:920-948`)

| Aufrufer | Variante |
|---|---|
| `src/output/renderers/email/html.py:1440` | Trip-Briefing, `embedded` |
| `src/output/renderers/email/compare_html.py:370` | Ortsvergleich-Banner, `embedded` |
| `src/services/notification_service.py:513` | Trip-Standalone-Alarmmail, `standalone` |
| `src/services/notification_service.py:612` | Compare-Standalone-Alarmmail, `standalone` |

Der **embedded** Pfad (`_render_warn_block_embedded`, `:794-917`) ist von M1/M3/M4/M5 **nicht** betroffen (er ersetzt korrekt, hat keine route-note, kein „Route:"-Label, keine Quelle-Box). Von M2 („Gültig: unbekannt", `:890`) ist er betroffen.

## Existing Patterns

- **Label-Anreicherung (F004):** reicherer Quell-Label ersetzt das Typ-Wort, wenn `w in label or "—" in label` — bereits in Betreff und embedded Block.
- **Einheiten im Trip-Briefing:** nicht in der Zelle, sondern in einer Fuß-Legende (`build_units_legend`), gespeist aus dem Metrik-Katalog (`display_unit`). Der Ortsvergleich hat diese Legende **nicht**.
- **Design-Vorlagen sind 1:1-Referenz** (Projektregel Design-Fidelity), nicht Prosa-Vorlage.

## Existing Specs

| Spec | Aussage |
|---|---|
| `docs/specs/modules/issue_1216_official_alert_template.md:84-87`, AC-6 (Z. 130) | **Schreibt „Gültig: unbekannt" ausdrücklich vor** → M2 ist spec-konform implementiert, der Fix braucht eine **Spec-Änderung** |
| `docs/specs/modules/issue_1233_alert_amtliche_warnung.md:80-83` | Punkt 4: „Gültig:"/„Route:"-Facts + route-note; Punkt 6: Quelle-Box mit prosaischem Scope-Satz |
| `docs/specs/modules/issue_1216_embedded_warnblock.md:52`, AC-1/AC-7 | embedded `wb-item` ohne Labels, ohne Quelle-Satz |
| `docs/specs/modules/issue_1216_f004_label_fidelity.md` | Die Label-Anreicherung, die M1 verursacht |

## Design-Vorlagen (1:1-Referenz)

- `docs/design-requests/issue_1233_alert_amtliche_warnung/Gregor 20 - Alert Amtliche Warnung.html`
  - Z. 190/199: `.type` ist ein **nacktes Gefahren-Wort** („Hitze", „Gewitter") — **kein** Label-Anhang ⇒ M1 ist auch ein Fidelity-Bruch.
  - Z. 194/290: Route-Chips sind **Segment-Chips** („Segment 1", „Segment 2–4", „Ziel") — kompakt, ≤4 Stück. Unsere Mail rendert **7–8 Ortsnamen-Chips** ⇒ Ursache der optischen Überfüllung.
  - Z. 291: die `.route-note` („übrige Strecke frei — keine amtliche Warnung für Segment 1 und Ziel") ist **so in der Vorlage angelegt** ⇒ M4 ist kein Bug, sondern skaliert nur schlecht mit Ortsnamen.
  - Z. 208/296: die `.src`-Box nennt **konkrete** Orte/Segmente, der Code nur `ordered[0].scope_label` ⇒ M3 ist ein Fidelity-Bruch.
- `docs/design-requests/issue_1216_warn_im_briefing/Gregor 20 - Warnung im Briefing.html` (embedded) — Z. 52: Item-Reihenfolge „Dot · Stufe-Wort · Typ · Gültig · Route/Umfang · Quelle", **ohne** Label-Texte.

## Dependencies

- **Upstream:** `services/official_alerts/{massif_closure,meteo_forets,vigilance,geosphere}.py` liefern `OfficialAlert` (`models.py:15-33`, `valid_from`/`valid_to` optional); `build_official_alert_notices` / `build_compare_official_alert_notices` (`official_alerts.py:1070-1135`) bauen `scope_label`, `affected_chips`, `free_chips`.
- **Downstream:** vier Mail-Pfade (s.o.) + Telegram/SMS-Renderer teilen `_hazard_display`.

## Tests & Goldens, die brechen werden

**#1237:** `tests/tdd/test_issue_1106_hourly_metrics_config.py:407,437,473,481-482` (Header-Liste + `\b8[.,]0\s*km\b`), `tests/tdd/test_issue_1110_compare_mail_v2.py:486,506,528` (Header-Liste + `"12:00"`/`"09:00"`). **Keine Goldens** — für den Ortsvergleich existieren keine.

**#1238:** `tests/tdd/test_official_alert_standalone_render.py:363`, `test_warn_block_render.py`, `test_official_alert_template_render.py`, `test_official_alert_subject_label_fidelity.py:55-157,214,218`, `test_official_alert_mail_validator.py`, `test_issue_1037_massif_closure.py`. Goldens: `tests/golden/email/corsica-vigilance-{html,plain}.txt` (enthalten den embedded `.wb`-Block) — brechen nur bei Änderung am embedded Pfad (M2).

**Hook:** `.claude/hooks/official_alert_mail_validator.py:172-173` (Regel P-3) verlangt, dass `„Gültig:"` im Body steht ⇒ das Label darf **nicht** entfallen; nur sein Wert darf sich ändern.

## Risks & Considerations

1. **M2 erfordert Spec-Änderung** (`issue_1216_official_alert_template.md` schreibt „unbekannt" vor). Nicht heimlich überschreiben — transparent im Spec-Changelog.
2. **Renderer-Commit-Gate (#811)** greift: `alert/*.py` + `email/*.py` staged ⇒ vor dem Commit müssen zwei echt zugestellte Test-Mails validiert sein (Briefing- **und** Vergleichs-Validator; für die Warn-Mail existiert `official_alert_mail_validator.py`).
3. **Geteilte Bausteine:** `_hazard_display` speist auch SMS-Kürzel und Telegram — Änderungen am Typ-Wort dürfen die dortigen Kürzel nicht verschieben (Golden `test_sms_golden.py`).
4. **Chips = Orte statt Segmente** ist eine Design-Abweichung mit UX-Folgen. Umstellung auf Segment-Chips wäre vorlagentreu, aber für den Nutzer womöglich **weniger** informativ („Segment 3" sagt weniger als „Toulon") — PO-Entscheidung nötig.
5. **Compare-Kontext:** „Route:" ist dort schlicht falsch (es gibt keine Route, nur Orte).
