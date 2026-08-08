---
entity_id: fix_1575_plain_column_order
type: module
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [trip, output, email, weather-metrics, khw]
---

# Fix #1575 Scheibe 2 — Die eingestellte Metrik-Reihenfolge wirkt auch im Plain-Text-Teil

## Approval

- [ ] Approved

## Purpose

Scheibe 1 (PR #1580, gemergt) hat die eingestellte Metrik-Reihenfolge im **HTML**-Teil
der Briefing-Mail wirksam gemacht. Der **Plain-Text**-Teil kennt den Mechanismus
(`col_order` aus `dc.metrics`) bis heute nicht und sortiert weiterhin strikt nach
Katalog-Reihenfolge — HTML und Plain derselben Mail zeigen dieselbe Konfiguration
unterschiedlich sortiert. Zusätzlich divergieren beide Teile schon heute in der
Position von `TmpMin` (`temperature_cold`, `selectable=False`): Position 2 im
Plain-Teil, letzte Stelle im HTML-Teil. Diese Scheibe zieht Plain auf den bereits
produktiven HTML-Mechanismus nach und beseitigt beide Divergenzen.

## Messung (Ist-Stand, nicht vermutet)

Gemessen am 2026-08-07 (Context-Phase, gegen den echten Render-Pfad
`TripReportFormatter.format_email`):

| Teil | Ist-Stand vor diesem Fix |
|---|---|
| HTML (Scheibe 1, bereits produktiv) | folgt `dc.metrics` über `_col_order` (html.py:1018-1029) → `ordered+remaining`-Merge (html.py:664-682). Baseline für Altbestand (`order=0` überall): `Temp, Feels, Wind, Gust, Rain, Thdr, SnowL, Cloud, Sun, TmpMin` — TmpMin am Ende, weil `temperature_cold.selectable=False` es aus `_col_order` herausfiltert und der `remaining`-Zweig es anhängt. (Quelle: `tests/unit/test_mail_column_order.py::test_legacy_config_without_order_keeps_catalog_order`, bereits verifiziert.) |
| Plain (dieser Fix) | `_render_text_table()` (`plain.py:59`) ruft ausschließlich `visible_cols(rows)` (Katalog-Reihenfolge, Alt-Pfad) auf — `dc` liegt zwar als Parameter von `render_plain()` vor, wird für die Spaltenfolge aber nirgends genutzt. `TmpMin` steht dadurch an Katalog-Position (Position 2, direkt nach `Temp`), nicht am Ende. Eine Reihenfolge-Einstellung im Editor hat auf den Plain-Teil **keine** Wirkung. |

**Ursachenkette (Code gelesen):** Beide Aufrufstellen von `_render_text_table()` in
`render_plain()` — Segment-Tabellen (`plain.py:280`) und Nacht-Tabelle
(`plain.py:287`) — reichen keinen `col_order` durch, weil der Parameter dafür in
`_render_text_table()` schlicht fehlt.

## Source

- **File:** `src/output/renderers/email/plain.py`
- **Identifier:** `_render_text_table`, `render_plain`

Schicht: **Python-Core / Domain-Backend** (`src/output/renderers/email/`).
Zusätzlich betroffen: `src/output/renderers/email/helpers.py` (neuer geteilter
Helper) und `src/output/renderers/email/html.py` (reines Refactoring, ruft den
neuen Helper statt der bisherigen Inline-Schleife auf). Beide Dateien sind
gate-geschützte Mail-Inhalts-Dateien (`renderer_mail_gate.py`, Issue #811).

## Estimated Scope

- **LoC:** ~+50/-15 Produktivcode, ~+150 Test
- **Files:** 4 (3 MODIFY: `helpers.py`, `html.py`, `plain.py`; 1 CREATE:
  `tests/unit/test_mail_plain_column_order.py`)
- **Effort:** low-medium (Mechanismus in HTML bereits produktiv erprobt; reines
  Nachziehen + Konsolidieren über einen geteilten Helper, keine neue Logik)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/helpers.py` | MODIFY | Neuer geteilter Helper `resolve_metric_col_order(dc)`, extrahiert aus der `_col_order`-Bauschleife in `html.py:1018-1029` (dc.metrics → enabled + selectable filtern → Liste von `col_key`s). |
| `src/output/renderers/email/html.py` | MODIFY | `_col_order`-Bauschleife (Z.1018-1029) durch Aufruf `resolve_metric_col_order(dc)` ersetzen. Reines Refactoring, Verhalten unverändert (AC-6). |
| `src/output/renderers/email/plain.py` | MODIFY | `_render_text_table()` bekommt einen neuen optionalen `col_order`-Parameter mit `ordered+remaining`-Merge-Logik analog `html.py:664-682` (Header- UND Datenzeilen-Reihenfolge aus derselben `cols`-Liste). `render_plain()` berechnet `col_order` einmal via `resolve_metric_col_order(dc)` und übergibt ihn an **beide** Aufrufstellen (Segment-Tabellen Z.280, Nacht-Tabelle Z.287). |
| `tests/unit/test_mail_plain_column_order.py` | CREATE | Tests am Wirkort (`render_plain`/Plain-Teil von `format_email`), analog `test_mail_column_order.py`. |

### Nicht betroffen (Regressionsschutz, explizit geprüft)

- `src/output/renderers/channel_layout.py` (`render_for_channel`) — Telegram und
  Ortsvergleich nutzen bereits die eigene `(bucket, order)`-Sortier-Semantik, nicht
  den hier geänderten `visible_cols`-Alt-Pfad (AC-4).
- `build_units_legend`/`build_column_legend` (`helpers.py:520-547`) — Prosa-Legenden,
  bleiben in Katalog-Reihenfolge; das Issue nennt ausdrücklich nur die
  Tabellen-Spaltenfolge, kein AC dafür.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig.get_metrics_for_channel` | Datenmodell (Scheibe 1) | liefert `dc.metrics` bereits stabil nach `(bucket, order)` sortiert — Voraussetzung, unverändert |
| `email/html.py` `_col_order`-Mechanismus | Referenzimplementierung | Vorbild für den neuen geteilten Helper und die Plain-Merge-Logik |
| `email/helpers.py` `visible_cols()` (Alt-Pfad) | Bestehender Baustein | liefert die Katalog-Basisliste `cols`, auf die `col_order` als zusätzlicher Sortierschritt angewendet wird — Funktion selbst bleibt unverändert |
| `src/app/metric_catalog.py` `get_metric`/`selectable` | Katalog | bestimmt, welche `dc.metrics`-Einträge `resolve_metric_col_order` in die Liste aufnimmt (`temperature_cold.selectable=False` fällt heraus → `remaining`-Zweig) |
| `.claude/hooks/renderer_mail_gate.py` (#811) | Commit-Gate | blockiert den Commit auf `plain.py`/`html.py` ohne frischen `briefing_mail_validator.py`-Lauf (AC-7) |

## Implementation Details

```
# helpers.py — neuer geteilter Helper
def resolve_metric_col_order(dc: UnifiedWeatherDisplayConfig) -> list[str]:
    # 1:1 aus html.py:1018-1029 extrahiert.
    order: list[str] = []
    for mc in dc.metrics:
        if not mc.enabled:
            continue
        try:
            mdef = get_metric(mc.metric_id)
            if mdef.selectable:
                order.append(mdef.col_key)
        except KeyError:
            continue
    return order

# html.py — ersetzt die bisherige Inline-Schleife
_col_order = resolve_metric_col_order(dc)

# plain.py — _render_text_table() bekommt col_order-Parameter
def _render_text_table(rows, *, friendly_keys, format_modes=None,
                        col_order: Optional[list[str]] = None) -> str:
    cols = visible_cols(rows)
    if col_order:
        col_map = {k: label for k, label in cols}
        ordered = [(k, col_map[k]) for k in col_order if k in col_map]
        remaining = [(k, label) for k, label in cols if k not in col_order]
        cols = ordered + remaining
    ...  # headers/widths/Zeilenbau unverändert, nutzt jetzt das sortierte cols

# plain.py — render_plain() berechnet col_order EINMAL, reicht ihn an beide
# Aufrufstellen durch
_col_order = resolve_metric_col_order(dc)
...
lines.append(_render_text_table(rows, friendly_keys=friendly_keys,
                                 format_modes=format_modes, col_order=_col_order))
...
lines.append(_render_text_table(night_rows, friendly_keys=friendly_keys,
                                 col_order=_col_order))
```

## Expected Behavior

- **Input:** `UnifiedWeatherDisplayConfig` mit im Editor gesetzten `bucket`/`order`-
  Werten je Wettergröße (identisch zum Input aus Scheibe 1).
- **Output:** Die Spaltenreihenfolge des Plain-Text-Teils (Segment- **und**
  Nacht-Tabelle) folgt derselben `(bucket, order)`-Reihenfolge wie der HTML-Teil
  derselben Mail; `TmpMin` steht in beiden Teilen an derselben (letzten) Stelle.
- **Side effects:** Keine. `html.py`-Verhalten bleibt byte-gleich (reines
  Refactoring). Telegram, Ortsvergleich und die Prosa-Legenden bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen Wettergrößen im Editor in eine vom Katalog
abweichende Reihenfolge gezogen wurden / When das Briefing als E-Mail gerendert
wird / Then folgen die Spalten der Stundentabelle im **Plain-Text**-Teil (Segment-
Tabellen) genau dieser eingestellten Reihenfolge (links → rechts), nicht der
Katalog-Reihenfolge.
- Test: `render_plain`/Plain-Teil von `format_email`, Header-Zeile der ersten
  Segment-Tabelle geparst — dieselbe Prüfung wie
  `test_mail_column_order.py::test_configured_order_drives_mail_columns`, aber
  gegen den Plain-Text-Output statt gegen `<thead>`.

- **AC-2:** Given zwei Größen im selben Bucket mit den Positionen 1 und 2 / When die
beiden Positionen im Editor getauscht werden / Then tauschen auch die zugehörigen
Spalten im Plain-Text-Teil ihren Platz — die Wirkung ist am gerenderten Text
messbar, nicht nur am gespeicherten Wert.
- Test: zwei Renderings mit vertauschter Position, Spaltenindex-Vergleich in der
  geparsten Plain-Header-Zeile.

- **AC-3:** Given ein Bestands-Trip, dessen gespeicherte Größen alle `order = 0`
tragen (Altbestand vor der Reihenfolge-Funktion) / When das Briefing gerendert
wird / Then bleibt die relative Reihenfolge aller Größen **außer** `TmpMin`
gegenüber dem Ist-Stand vor diesem Fix unverändert (`Temp, Feels, Wind, Gust,
Rain, Thdr, SnowL, Cloud, Sun`) — die Sortierung erfindet für Altbestand keine
neue Reihenfolge. Einzige zulässige Verschiebung ist `TmpMin` (siehe AC-5).
- Test: Vorgabe-Konfiguration (`build_default_display_config()`, alle `order=0`)
  rendern, Plain-Spaltenfolge minus `TmpMin` gegen die genannte Liste prüfen.

- **AC-4:** Given derselbe Trip / When Telegram-Kurzform und Ortsvergleich gerendert
werden / Then ist deren Spalten-/Zeilenfolge unverändert gegenüber heute — diese
Kanäle nutzen `channel_layout.render_for_channel`, nicht den hier geänderten
`visible_cols`-Alt-Pfad, und dürfen durch diese Änderung nichts verschieben.
- Test: `render_for_channel("telegram", …)`-Ergebnis vor/nach der Implementierung
  identisch (Regressionsschutz, analog Scheibe-1-AC-5).

- **AC-5:** Given ein Trip mit `TmpMin` (`temperature_cold`) unter den aktiven
Größen / When das Briefing gerendert wird / Then steht `TmpMin` im Plain-Teil an
derselben (letzten) Stelle wie im HTML-Teil **derselben** Mail — HTML und Plain
zeigen für dieselbe Konfiguration dieselbe `TmpMin`-Position (HTML↔Plain-
Konsistenz, Konvergenzrichtung: Plain gleicht sich an das bereits produktive
HTML-Verhalten an, nicht umgekehrt).
- Test: eine Mail rendern, `TmpMin`-Index in der HTML-`<thead>`-Zeile und in der
  Plain-Header-Zeile vergleichen — beide müssen die letzte Position sein.

- **AC-6:** Given dieselbe Konfiguration wie in den bestehenden Scheibe-1-HTML-Tests
(`tests/unit/test_mail_column_order.py`) / When das Briefing nach der
Helper-Extraktion (`resolve_metric_col_order`) gerendert wird / Then ist die
HTML-Spaltenfolge byte-gleich zum Ist-Stand vor diesem Fix — die Extraktion ist
reines Refactoring, kein Verhaltenswechsel am bereits verifizierten HTML-Pfad.
- Test: bestehende HTML-Spaltenfolge-Tests aus Scheibe 1 laufen nach diesem Fix
  unverändert grün (keine Anpassung der Erwartungswerte nötig).

- **AC-7:** Given ein Trip mit `night_rows` (Nacht-Tabelle am Ziel) und einer
eingestellten Reihenfolge / When das Briefing gerendert wird / Then folgt auch die
Nacht-Tabelle im Plain-Teil derselben Reihenfolge wie die Segment-Tabellen — beide
Aufrufstellen von `_render_text_table()` (`plain.py:280` und `plain.py:287`)
erhalten denselben `col_order` und sind synchron.
- Test: Rendering mit `night_rows` und gesetzter Reihenfolge, Header-Zeile der
  Nacht-Tabelle gegen dieselbe erwartete Reihenfolge wie die Segment-Tabelle
  geprüft.

- **AC-8:** Given ein Commit, der `plain.py`, `html.py` oder `helpers.py` staged /
When der Commit vorbereitet wird / Then liegt zusätzlich zum grünen Kern-Unit-Test
(AC-1 bis AC-7) ein frischer, erfolgreicher `briefing_mail_validator.py`-Lauf gegen
eine **echt zugestellte Staging-Mail** (IMAP, `X-GZ-Mail-Type: trip-briefing`) vor
— ohne diesen Nachweis blockiert `renderer_mail_gate.py` (#811) den Commit
un-überspringbar.
- Test: Live-E2E gegen Staging — Test-Mail mit abweichender Reihenfolge über
  `/e2e-verify`-Pfad versenden, per IMAP abrufen, `briefing_mail_validator.py`
  gegen die zugestellte Mail laufen lassen (Exit 0 Pflicht vor „E2E bestanden").

## Nicht in dieser Scheibe (bewusst)

- **Einheiten-/Spalten-Legenden** (`build_units_legend`/`build_column_legend`).
  Bleiben Prosa in Katalog-Reihenfolge — das Issue nennt ausdrücklich nur die
  Spaltenfolge der Stundentabelle, kein AC dafür.
- **Symptom B aus #1575 (Kanal-Trennung im Editor).** Bereits in Scheibe 3
  (PR #1600) erledigt, kein Teil dieser Scheibe.

## Known Limitations

- Die `TmpMin`-Konvergenzrichtung (Plain gleicht sich an HTML an) ist eine
  technische Konsistenzentscheidung, kein PO-Bedienkonzept (`temperature_cold`
  ist `selectable=False`, damit nie nutzerkonfigurierbar). Sollte künftig eine
  nutzerseitig konfigurierbare Alarm-Pseudogröße mit ähnlicher Eigenschaft
  hinzukommen, ist die Positionsfrage neu zu bewerten.
- `visible_cols()` (Alt-Pfad) selbst bleibt unverändert — die Reihenfolge-Logik
  ist bewusst ein zusätzlicher Schritt **nach** `visible_cols()`, um den von
  `html.py` **und** `plain.py` geteilten Alt-Pfad nicht anzufassen (Risiko aus
  Context-Dokument).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Nachziehen eines in Scheibe 1 bereits etablierten,
  produktiv laufenden Mechanismus auf einen zweiten Renderer-Pfad (Plain statt
  HTML) plus Konsolidierung über einen geteilten Helper. Keine neue
  Architektur-Entscheidung, keine Abweichung von bestehenden ADRs.

## Testing

Kern-Schicht, deterministisch, ohne Netz — bis auf AC-8 (Live-E2E/Staging-Marker,
IMAP-Pflicht). Nachweis am **Wirkort**: die gerenderte Mail (`render_plain`/
`format_email`), nicht die Sortierfunktion isoliert — Lehre aus #1457.

| AC | Testart |
|---|---|
| AC-1, AC-2 | `render_plain`/`format_email` mit permutiertem `order`, Spaltenfolge aus der Plain-Header-Zeile geparst |
| AC-3 | Altbestand-Konfiguration (`order` überall 0) → relative Plain-Spaltenfolge (ohne TmpMin) identisch zum Ist-Stand |
| AC-4 | `render_for_channel("telegram", …)` und Compare-Pfad vor/nach identisch (Regressionsschutz) |
| AC-5 | eine Mail rendern, `TmpMin`-Position in HTML-`<thead>` und Plain-Header vergleichen |
| AC-6 | bestehende `test_mail_column_order.py`-HTML-Tests laufen unverändert grün nach der Helper-Extraktion |
| AC-7 | Rendering mit `night_rows`, Nacht-Tabellen-Header gegen Segment-Tabellen-Reihenfolge geprüft |
| AC-8 | Live-E2E: `briefing_mail_validator.py` gegen echt zugestellte Staging-Mail (IMAP) — Pflicht für Commit-Gate #811 |

## Changelog

- 2026-08-08: Initial spec created
