# Context: fix-1356-compare-metrik-reihenfolge

## Request Summary
Issue #1356 (Epic #2259): In der Ortsvergleich-Mail zeigen HTML-Fassung und
Klartext-Fassung dieselben Metrik-Zeilen in verschiedener Reihenfolge. Beide
sollen die Zeilenreihenfolge aus **einer** Quelle ziehen. Dazu gehört der
Nebenbefund C3-75: Der Mail-Sink reicht nur HTML durch, der Klartext der
Compare-Mail ist über den Sink nicht testbar.

## Ist-Stand (gemessen am Stand `origin/main` 217d3b762, 2026-11-03)

Das Ticket ist **teilweise überholt**: Seit #1359 (Scheibe 1) und #1335 folgen
HTML **und** Plain einer gespeicherten Nutzer-Reihenfolge (`enabled_metrics`,
georderte Liste, `comparison._ordered_rows` bzw. `compare_html._visible_metrics`).
Der Verschärfer aus dem Ticket („Plain nutzt enabled_metrics nur als Filter")
besteht nicht mehr.

**Es bleibt der Standardfall `enabled_metrics=None`** (Altbestand ohne gespeicherte
Auswahl, Weg: `resolve_compare_render_options({"display_config": {}})` → `None`):

| Kanal | Quelle der Standardreihenfolge | Reihenfolge |
|---|---|---|
| HTML | `CV2_METRICS` (`compare_html.py:327`) | warn, temp_max, wind_max, precip_sum, pop_max, thunder_max, sunny_hours, cloud_avg, uv_max, visibility_min, snow_depth, snow_new, temp_min, gust_max, freezing_level, wind_direction, wind_chill_min/max, cloud_low/mid/high, humidity, dewpoint, pressure, precip_type, snowfall_limit |
| Plain | `_PLAIN_ROWS` (`comparison.py:108`) | temp_max, wind_max, temp_min, gust_max, wind_direction, wind_chill_min/max, cloud_low/mid/high, precip_sum, pop_max, thunder_max, uv_max, visibility_min, freezing_level, humidity, dewpoint, pressure, precip_type, snowfall_limit, sunny_hours, cloud_avg, snow_depth, snow_new |
| Telegram / SMS | `_PLAIN_ROWS` (über `_PLAIN_ROWS_BY_ID` / `_ordered_rows`) | folgt Plain |
| Frontend-Editor | `COMPARE_METRIC_KEYS` (`corridorEditorState.ts:512`) | **deckt sich mit HTML** (temp_max, wind_max, precip_sum, pop_max, thunder, sunny, cloud_avg, uv, visibility, snow_depth, snow_new, temp_min, gust, freezing_level …) |
| Compare-Katalog | `get_compare_metric_catalog()` | eigene dritte Reihenfolge (snow_depth, snow_new, sunny, wind, …) – Anzeige-/Auslieferungs-Reihenfolge, nicht Mail-Standard |

Zwei hartkodierte Listen (`CV2_METRICS`, `_PLAIN_ROWS`) mit abweichender
Reihenfolge; Kommentare in `comparison.py` behaupten Deckungsgleichheit.
Die HTML-Reihenfolge ist die, die der Editor dem Nutzer zeigt → sie ist die
kanonische Standardreihenfolge, Plain/Telegram/SMS sind die Abweichler.

## Related Files
| File | Relevanz |
|------|----------|
| `src/output/renderers/comparison.py` | `_PLAIN_ROWS`, `_DAILY_PLAIN_ROWS`, `_ordered_rows` (Z.133), `render_comparison_text`, Telegram-/SMS-Zeilen (Z.757, 1000 nutzen `_PLAIN_ROWS_BY_ID`) – hier steht die abweichende Standardreihenfolge |
| `src/output/renderers/email/compare_html.py` | `CV2_METRICS` (Z.327), `_visible_metrics` (Z.805) – kanonische Reihenfolge |
| `src/output/renderers/compare_metric_ids.py` | `resolve_enabled_metrics` (reihenfolge-erhaltend), `FRONTEND_TO_RENDERER_METRIC_ID` |
| `src/services/report_config_resolver.py` | `resolve_compare_render_options` → `enabled_metrics` (`None` = Altbestand) |
| `src/services/notification_service.py:1534-1535` | `send_compare_report`: `mail_sink(subject=…, body=html_body)` – Klartext (`text_body`) wird nicht durchgereicht (C3-75). Verwandt, aber andere Mailtypen: Z.1405 (Trip-Amtswarnung), Z.1745 (`_dispatch_compare_official_email` hat `plain`, Sink verwirft es) |
| `tests/unit/test_compare_metric_order.py` | **AC-7 `TestAC7LegacyDefaultOrderUnchanged`**: friert `FROZEN_PLAIN_ORDER`, `FROZEN_TELEGRAM_ORDER`, `FROZEN_HTML_ORDER` ein → Änderung der Plain-Standardreihenfolge ist eine **bewusste Spec-/Test-Änderung** |
| `tests/helpers/compare_order.py` | Reihenfolge-Auslese je Kanal, Vakuum-Schutz (Soll aus Katalog) |
| `tests/unit/test_compare_mail_plaintext_html_label_parity.py` | Label-Parität Plain/HTML (Namen, nicht Reihenfolge) |
| `tests/tdd/test_compare_metric_order_and_wind_direction.py`, `tests/unit/test_compare_metric_parity.py` | angrenzende Reihenfolge-/Paritätstests |
| `.claude/hooks/email_spec_validator.py` | Pflicht-Validator Compare-Mail (liest nur HTML-Body; Klartext bleibt ungeprüft – siehe C3-75) |

## Existing Patterns
- Reihenfolge = Listenposition einer georderten Liste (`dict.fromkeys`), `None` = Altbestand-Standard, `[]` = bewusst leer (#1359 AC-7/AC-8).
- `_ordered_rows(rows, enabled_metrics)` ordnet Plain/Telegram/SMS; `_visible_metrics` ordnet HTML – gleiche Semantik, zwei Implementierungen.
- Wert-Quelle ist schon geteilt (`_metric_value`, HTML-Parität, #1285); Labels über `derive_row_labels` aus dem Register (#1401). Nur die **Reihenfolge** ist doppelt geführt.
- C3-75-Vorbild: Trip-Pfad (#1366) reicht den Klartext über den Sink durch.

## Dependencies
- Upstream: `CV2_METRICS`/`FRONTEND_TO_RENDERER_METRIC_ID`, Metrik-Register (`app.metric_catalog`), `format_value`.
- Downstream: Compare-Mail (HTML + Plain), Telegram-Kurz/-Lang, Compare-SMS und Premium-SMS (alle über `_PLAIN_ROWS`), Frontend-Vorschau (`WeatherV2MailPreview`), Editor-Standardreihenfolge.

## Existing Specs
- `docs/specs/modules/compare_metric_order.md` (#1359 S1, implemented) – AC-7 „Altbestand rendert unverändert" ist die Gegenposition; Änderung braucht neue Spec-Version/ADR-Notiz.
- `docs/specs/modules/compare_metric_parity.md`, `compare_metric_ssot_final.md`, `rework_1351_compare_catalog.md`, `fix_1703_s7_reihenfolge_matrix.md` (Reihenfolge-Matrix je Kanal).
- Epic #1372 Scheibe S5 (Kanal-Treue: gleiche Auswahl, gleiche Reihenfolge in allen Ausgaben).
- ADR-0095 (Kanal-Parität: jeder Kanal, gleicher Inhalt).

## Risks & Considerations
- **AC-7-Konflikt:** Plain-Standardreihenfolge ist eingefroren, um stille Änderungen an Altbestands-Mails zu verhindern. Die Angleichung ändert sichtbar die Plain-/Telegram-/SMS-Zeilenfolge für Nutzer ohne gespeicherte Auswahl. Das ist hier die ausdrückliche Absicht (Ticket, PO-bestätigt 24.07.), muss aber in Spec und Frozen-Tests bewusst nachgezogen werden – nicht still.
- **SMS-Zeichenbudget:** Die SMS kürzt nach Budget (#1362 S5b). Andere Reihenfolge ⇒ andere Metriken überleben die Kürzung; Premium-SMS-Format-Tests prüfen.
- **Renderer-Commit-Gate:** `comparison.py` und `compare_html.py` lösen das Gate aus (Modus-Matrix-Test + `email_spec_validator` gegen echt zugestellte Staging-Mail, Marker `X-GZ-Mail-Type: compare`). Staging-Mailweg: Prüfwerkzeug aus #2774 (frisch gemergt).
- **Trip/Compare-Teilung:** Die geteilte Reihenfolge-Quelle muss ein Modul sein, keine zweite Kopie; Compare-Eigenes bleibt nur die Darstellung.
- **Frontend-Parität:** `COMPARE_METRIC_KEYS` deckt sich bereits mit der HTML-Reihenfolge → bei Wahl von `CV2_METRICS` als Quelle kein Frontend-Eingriff nötig; Parität-Wächter (`compareMetricKeysParity.test.ts`) vergleicht sortiert.
- **C3-75-Umfang:** nur `send_compare_report` (Z.1534) ist Compare-Briefing. Die Sink-Stellen Z.1405/1745 sind Amtswarn-Mails; ob mit anfassen = Scope-Entscheidung der Analyse.
- Nicht anfassen: Orts-Reihenfolge (#1359 Scheibe 2), Alarm-Pfade, Editor-Marken (#2232 erledigt).

## Analysis

### Type
Bug (Nutzersichtbare Inkonsistenz, kein Datenfehler)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/comparison.py | MODIFY | `_PLAIN_ROWS` nach `CV2_METRICS`-Reihenfolge ableiten |
| src/services/notification_service.py | MODIFY | `send_compare_report`: Klartext über `mail_sink` durchreichen (C3-75) |
| tests/unit/test_compare_metric_order.py | MODIFY | `FROZEN_PLAIN_ORDER`/`FROZEN_TELEGRAM_ORDER` bewusst umstellen, Wächter ergänzen |
| docs/specs/modules/compare_metric_order.md | MODIFY | AC-7 neue Version (Begründung #1356) |

### Scope Assessment
- Files: 4 (+ ggf. Test-Sinks)
- Estimated LoC: +60/-40
- Risk Level: LOW–MEDIUM (Renderer-Gate, SMS-Budgetkürzung)

### Open Questions
- [ ] Keine für den PO; Sink-Signatur-Kompatibilität bestehender Test-Sinks in der Spec-/Red-Phase klären.

### Details (Analyse 2026-11-03)

**Messung:** `CV2_METRICS` (HTML) und `_PLAIN_ROWS` (Klartext/Telegram/SMS) führen
exakt dieselben Schlüssel (einzige Differenz: `warn`, die nur HTML hat und immer
Zeile 1 ist). Es fehlt also nur eine gemeinsame **Reihenfolge**, kein Inhalt.

**Ursache:** Zwei hartkodierte Listen; `_PLAIN_ROWS` ist von Hand in anderer
Reihenfolge gepflegt, Kommentare behaupten fälschlich Deckungsgleichheit.

**Lösungsansatz (empfohlen):**
1. `CV2_METRICS` ist die einzige Quelle der Standardreihenfolge (deckt sich mit
   dem Frontend-Editor `COMPARE_METRIC_KEYS`, kein Frontend-Eingriff).
   `_PLAIN_ROWS` wird nicht mehr von Hand geordnet, sondern beim Modulimport nach
   dem Index in `CV2_METRICS` sortiert (`warn` ausgenommen). Plain, Telegram und
   SMS folgen automatisch (alle über `_PLAIN_ROWS`/`_PLAIN_ROWS_BY_ID`).
2. Wächter-Test: Schlüsselreihenfolge in `_PLAIN_ROWS` == `CV2_METRICS` ohne
   `warn`; neuer Schlüssel nur in einer Liste ⇒ rot.
3. AC-7 in `compare_metric_order.md` und `FROZEN_PLAIN_ORDER`/`FROZEN_TELEGRAM_ORDER`
   in `tests/unit/test_compare_metric_order.py` bewusst auf die HTML-Reihenfolge
   umstellen (neue Spec-Version, begründet mit #1356, PO-bestätigt 24.07.).
4. **C3-75:** in `send_compare_report` (notification_service.py:1535) den Klartext
   über den Sink durchreichen (Vorbild #1366). Amtswarn-Sinks (Z.1405, Z.1745)
   bleiben **außerhalb** des Scope (andere Mailtypen). Bestehende Test-Sinks, die
   nur `body` annehmen, auf Signatur-Kompatibilität prüfen.

**Risiken:** SMS-Budgetkürzung verschiebt, welche Metriken überleben
(Premium-SMS-Format-Tests laufen lassen); Renderer-Commit-Gate (Modus-Matrix +
`email_spec_validator` gegen echte Staging-Mail, Werkzeug aus #2774);
Altbestands-Nutzer ohne gespeicherte Auswahl sehen die neue Plain-Reihenfolge
(gewollt).

**Scope:** `comparison.py`, `notification_service.py`, 2 Tests + 1 Spec; klein,
Backend-only (Python), kein Frontend.
