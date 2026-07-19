---
entity_id: feature_574_segment_km_header
type: feature
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [email, mail-render, segment-header, issue-574, po-1310]
workflow: feat-574-segment-km-header
---

<!-- Issue #574 (PO-bestätigt via #1310). Tiefenanalyse in
     docs/context/feat-574-segment-km-header.md — Single Source dieser Spec,
     alle Aussagen file:line-belegt. -->

# Issue #574 — Segment-Header zeigt kumulativen km-Bereich in HTML (Desktop + Mobile)

## Approval

- [ ] Approved

## Purpose

Die Briefing-Mail zeigt in den Segment-Überschriften den kumulativen
Kilometer-Bereich der Etappe (`km 0.0–4.2`), damit Wanderer auf einen Blick
sehen, wo im Streckenverlauf das jeweilige Zeitfenster liegt. Plain-Text
rendert dieses Format bereits seit `320e9fac`; HTML (Desktop-Segment-Header
und Mobile-Kompakt-Header) fehlt es bisher — dort steht nur die reine
Segmentlänge in einem abweichenden Format (`4.2 km - 9.3 km`). Diese Spec
zieht HTML auf das Plain-Format nach und konsolidiert die Formatierung in
einer gemeinsamen Hilfsfunktion.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** Desktop-Segment-Header-Aufbau `seg_header_desktop`
  (Z.1025-1037, Format-Zeile Z.1034), Mobile-Segment-Header
  `seg_header_mobile` (Z.1050-1055, Format-Zeile Z.1054)

Vorbild-Code (bereits korrekt, dient als Referenz beim Fix):
`src/output/renderers/email/plain.py:222` (Inline-f-String
`km {start:.1f}–{end:.1f}`, En-Dash).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py` | Modul | Ziel-Ort für die neue geteilte Hilfsfunktion `_km_range(from_km, to_km) -> str`; bereits von `html.py` und `plain.py` importiert |
| `src/output/renderers/email/helpers.py::build_segment_label()` (Z.901-935) | Funktion (#397/#816/#832, Alert-Pfad) | ANDERER Baustein für Alert-/Change-Zeilen (strippt `.0` via `_fmt_km`, Z.896-898) — bewusst NICHT wiederverwendet, siehe ADR |
| `src/output/renderers/email/plain.py::render_plain()` Z.222 | Funktion | Bereits korrektes Vorbild-Format; Call-Site wird auf die neue Hilfsfunktion umgestellt, Ergebnis bleibt byte-identisch |
| `src/output/renderers/email/html.py::render_html()` Z.947-956 (`_cum_km`/`_from_km`/`_to_km`) | Bestehende Logik (#956 Teil B) | Kumulative Laufsumme ist bereits berechnet — nur das Ausgabeformat wird getauscht, kein Modellwechsel |
| `tests/tdd/test_feature_574_segment_km_header.py` | Testdatei | 3 passed + 3 xfail (AC-2/AC-3-Tests), verifiziert am 2026-07-19; definiert das Soll exakt |
| `tests/golden/email/regenerate.py` + 5 HTML-Golden-Fixtures | Tooling/Fixtures | Golden-Refreeze-Prozess aus #1306 frisch erprobt; Fixtures brechen erwartbar und werden einmalig regeneriert |
| Renderer-Mail-Gate #811 (`renderer_mail_gate.py`) | Pre-Commit-Gate | `html.py` ist Gate-Datei — Commit blockiert ohne frischen `test_issue_811_mode_matrix` + `briefing_mail_validator`-Lauf |
| `docs/specs/modules/issue_956_email_format.md` | Spec (superseded, s. ADR) | Schrieb das heutige `X.X km - Y.Y km`-Segment-Header-Format fest; wird durch diese Spec im Segment-Header-Punkt abgelöst (Datenmodell bleibt) |

## Estimated Scope

- **LoC:** ~10-14 Produkt (helpers.py +~3, html.py 2 Format-Zeilen, plain.py 1
  Call-Site-Umstellung), plus 1 Test-Anker-Zeile und xfail-Ausbau (3 Marker
  entfernt). Golden-Fixtures (regeneriert) zählen nicht gegen das LoC-Limit.
- **Files:** 3 Produktdateien (MODIFY), 1 Testdatei (MODIFY), 5 Golden-
  Fixtures (MODIFY, generiert)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/helpers.py` | MODIFY | Neue Funktion `_km_range(from_km: float, to_km: float) -> str` (~3 LoC), Rückgabe `f"km {from_km:.1f}–{to_km:.1f}"` (En-Dash `–`, analog `plain.py:222`) |
| `src/output/renderers/email/html.py` | MODIFY | Z.1034 (Desktop): Inline-Format `{_from_km:.1f} km - {_to_km:.1f} km` durch `{_km_range(_from_km, _to_km)}` ersetzen; Z.1054 (Mobile): `SEG {seg_id} · {seg_time}` um `· {_km_range(_from_km, _to_km)}` ergänzen (Format `SEG N · Zeit · km X.X–Y.Y`); Import von `_km_range` in bestehenden `helpers`-Import-Block (Z.27-34) ergänzen |
| `src/output/renderers/email/plain.py` | MODIFY | Z.222: Inline-f-String `km {seg.start_point.distance_from_start_km:.1f}–{seg.end_point.distance_from_start_km:.1f}` durch Aufruf `_km_range(seg.start_point.distance_from_start_km, seg.end_point.distance_from_start_km)` ersetzen — identischer Input, identische Ausgabe |
| `tests/tdd/test_feature_574_segment_km_header.py` | MODIFY | 3 `xfail`-Marker entfernen (Z.280, Z.316, Z.365); in `test_html_destination_segment_has_no_km_range` Test-Anker `"Wetter am Ziel"` (Z.348) case-korrekt auf `"WETTER AM ZIEL"` nachziehen (Renderer gibt seit #956/#1306 Uppercase aus, Z.986/Z.1012 in html.py) |
| `tests/visual/test_issue_956_email_pixel_diff.py` | MODIFY | Adversary-F001: Soll-Strings der beiden km-Spannen-Assertions (Z.315, Z.353) vom #956-Zwischenformat (`"0.0 km - 4.6 km"`, `"4.6 km - 9.3 km"`) auf das #574-Format (`"km 0.0–4.6"`, `"km 4.6–9.3"`, En-Dash) nachgezogen — fachlicher Zweck (Header zeigt kumulierte km-Spanne) bleibt unverändert |
| `tests/golden/email/gr20-spring-morning-html.txt`, `gr221-mallorca-evening-html.txt`, `gr20-summer-evening-html.txt`, `arlberg-winter-morning-html.txt`, `corsica-vigilance-html.txt` | MODIFY (generiert) | Einmalig neu eingefroren nach Segment-Header-Formatwechsel; Diff MUSS ausschließlich km-Zeilen zeigen (keine #1306-Regression) |

## Implementation Details

**helpers.py — neue geteilte Hilfsfunktion:** `_km_range(from_km, to_km)`
gibt `"km {from_km:.1f}–{to_km:.1f}"` zurück (En-Dash `–`, eine
Nachkommastelle inkl. `.0`, KEIN `_fmt_km`-Strip). Platzierung neben `_fmt_km`
(Z.896-898), da beide Kilometer formatieren, aber unterschiedliche
Anforderungen haben (Strip vs. feste Nachkommastelle) — deshalb zwei
getrennte Funktionen, nicht eine parametrisierte.

**html.py — Desktop (Z.1034):** Der bestehende Format-String
`f'{seg_time} · {_from_km:.1f} km - {_to_km:.1f} km · {s_elev} - {e_elev} m'`
wird zu `f'{seg_time} · {_km_range(_from_km, _to_km)} · {s_elev} - {e_elev} m'`.
Die Werte `_from_km`/`_to_km` sind bereits vorhanden (Z.953/956, kumulative
Laufsumme aus #956 Teil B) — nur der Ausgabetext ändert sich.

**html.py — Mobile (Z.1054):** Der bestehende Header
`f'SEG {seg_id} · {seg_time}</div>'` wird zu
`f'SEG {seg_id} · {seg_time} · {_km_range(_from_km, _to_km)}</div>'`. Da
`_from_km`/`_to_km` im selben Schleifendurchlauf (Z.953-956) berechnet werden
und der Mobile-Header direkt nach dem Desktop-Header im selben Block
gerendert wird (Z.1050 folgt auf Z.1038-1049), sind beide Variablen an
dieser Stelle bereits im Scope — keine zusätzliche Berechnung nötig.

**plain.py — Konsolidierung (Z.222):** Der bestehende Inline-f-String wird
durch den Aufruf der neuen geteilten Funktion ersetzt. Die Eingabewerte
(`seg.start_point.distance_from_start_km`, `seg.end_point.distance_from_start_km`)
bleiben unverändert — das sind bereits kumulative GPX-Punktwerte, keine
Neuberechnung. Ergebnis ist byte-identisch zur bisherigen Ausgabe (gleiche
Zahlen, gleiches Format, gleicher En-Dash).

**Testanpassung:** Die drei `xfail`-Marker in
`test_feature_574_segment_km_header.py` (Z.280 `test_html_normal_segment_has_km_range`,
Z.316 `test_html_destination_segment_has_no_km_range`, Z.365
`test_mobile_compact_header_contains_km_range`) werden nach dem jeweiligen
Fix entfernt — die xfail-`reason`-Texte referenzieren exakt #1310 und die
hier beschriebene Ursache. Zusätzlich: in
`test_html_destination_segment_has_no_km_range` sucht der Test-Anker
`result.find("Wetter am Ziel")` (Z.348) nach einer Groß-/Kleinschreibung, die
der Renderer seit #956/#1306 nicht mehr ausgibt (`html.py` rendert
`"WETTER AM ZIEL"` in Großbuchstaben, Z.986 und Z.1012) — diese eine Zeile
wird auf `"WETTER AM ZIEL"` korrigiert, unabhängig vom Feature #574 selbst.

## Expected Behavior

- **Input:** `render_html(segments=[...], ...)` mit normalen Segmenten
  (`segment_id != "Ziel"`) und optional einem Ziel-Segment
  (`segment_id == "Ziel"`)
- **Output:** Desktop-Segment-Header enthält `km {from:.1f}–{to:.1f}`
  statt `{from:.1f} km - {to:.1f} km`; Mobile-Kompakt-Header
  (`class="mobile-compact"`) enthält denselben km-Bereich zusätzlich zu
  `SEG N · Zeit`; das Ziel-Segment (Ankunfts-Block) bleibt ohne
  km-Bereich in Desktop und Mobile
- **Side effects:** Jede künftig gerenderte HTML-Briefing-Mail zeigt in
  Segment-Headern das neue Format; Plain-Text-Ausgabe bleibt unverändert
  (byte-identisch, nur intern über die geteilte Funktion geroutet)

## Acceptance Criteria

- **AC-1:** Given ein Briefing mit normalen Segmenten, When `render_html` den Desktop-Segment-Header rendert, Then zeigt er den kumulativen Bereich im Format `km 0.0–4.2` (En-Dash, je eine Nachkommastelle) statt `0.0 km - 4.2 km` — der bisher xfail-Test `test_html_normal_segment_has_km_range` ist echt grün.
  - Test: `uv run pytest tests/tdd/test_feature_574_segment_km_header.py::TestAC2HtmlKmRangeNormalSegmentOnly::test_html_normal_segment_has_km_range -v` grün ohne `xfail`-Decorator, kein `xpass`.

- **AC-2:** Given der mobile Kompakt-Header (`class="mobile-compact"`), When gerendert wird, Then enthält er denselben km-Bereich (`SEG N · Zeit · km X.X–Y.Y`) — `test_mobile_compact_header_contains_km_range` echt grün.
  - Test: `uv run pytest tests/tdd/test_feature_574_segment_km_header.py::TestAC3MobileHeaderKmRange::test_mobile_compact_header_contains_km_range -v` grün ohne `xfail`-Decorator.

- **AC-3:** Given das Ziel-Segment (Ankunfts-Block), When gerendert wird, Then bleibt es OHNE km-Bereich; der stale Test-Anker („Wetter am Ziel" vs. Uppercase-Renderer seit #956) wird mit 1 Zeile case-korrekt nachgezogen — `test_html_destination_segment_has_no_km_range` echt grün.
  - Test: `uv run pytest tests/tdd/test_feature_574_segment_km_header.py::TestAC2HtmlKmRangeNormalSegmentOnly::test_html_destination_segment_has_no_km_range -v` grün ohne `xfail`-Decorator; Diff zeigt genau die eine Anker-Zeile korrigiert (`"Wetter am Ziel"` → `"WETTER AM ZIEL"`).

- **AC-4:** Given Plain- und HTML-Renderer, When beide km-Bereiche ausgeben, Then nutzen sie EINE geteilte Formatier-Hilfsfunktion (`helpers.py`, `km {:.1f}–{:.1f}`) — kein dupliziertes Inline-Format mehr (Konsolidierungs-Gebot); Plain-Ausgabe bleibt byte-identisch zu heute.
  - Test: `uv run pytest tests/tdd/test_feature_574_segment_km_header.py -v` — alle 6 Tests grün (die 2 bereits passierenden AC-1-Plain-Tests unverändert grün, kein Byte-Unterschied in `result`); Code-Review bestätigt genau eine `_km_range`-Definition in `helpers.py` und drei Call-Sites (html.py ×2, plain.py ×1).

- **AC-5:** Given `html.py` ist Renderer-Mail-Gate-Datei (#811), When committet wird, Then liegen frisch vor: `test_issue_811_mode_matrix` grün + `briefing_mail_validator` Exit 0 gegen echt zugestellte Mail; die 5 Golden-HTML-Fixtures sind einmalig regeneriert und ihr Diff zeigt AUSSCHLIESSLICH km-Zeilen-Änderungen (keine #1306-Regression).
  - Test: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py -v` grün, danach `uv run python3 .claude/hooks/briefing_mail_validator.py` Exit 0 gegen `gregor-test@henemm.com` (Stalwart-Test-Postfach); anschließend `uv run python tests/golden/email/regenerate.py` einmalig ausführen und `git diff tests/golden/email/*.txt` manuell auf ausschließlich km-Zeilen prüfen, danach `uv run pytest tests/golden/email/` zweimal hintereinander grün (Byte-Stabilität).

## Known Limitations

- **Zweites Golden-Refreeze kurz nach #1306:** Die 5 HTML-Golden-Fixtures
  wurden bereits im Rahmen von #1306 neu eingefroren. Diese Spec erzwingt ein
  weiteres Refreeze — Diff-Review MUSS strikt auf km-Zeilen begrenzt bleiben,
  damit sich keine #1306-Regression einschleicht.
- **Telegram/SMS unberührt:** Diese Spec betrifft ausschließlich die
  HTML-Segment-Header (Desktop + Mobile) und die Plain-Text-Konsolidierung.
  Telegram-Kurzstil (`telegram_style`) und SMS-Renderer sind nicht Teil
  dieser Änderung.
- **Alert-Deviation-Labels unberührt:** `helpers.py::build_segment_label()`
  (Z.901-935, Alert-/Change-Pfad #397/#816/#832) bleibt unangetastet — andere
  Formatierungsregel (`.0`-Strip via `_fmt_km`), anderer Zweck (Abweichungs-
  Hinweise, nicht Segment-Header). Keine Zusammenlegung, siehe ADR.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Formatierungs-Entscheidung im Rahmen von #574,
  keine neue Systemarchitektur)
- **Rationale:**
  1. **#574-Format ersetzt bewusst das #956-Zwischenformat.** Das Segment-
     Header-Format `km X.X–Y.Y` (diese Spec) ersetzt das bisherige
     `X.X km - Y.Y km` (festgeschrieben in
     `docs/specs/modules/issue_956_email_format.md`, dort als Zwischenstand
     dokumentiert) — PO-Entscheid #1310. Das Datenmodell (kumulierte
     `distance_km`-Laufsumme aus #956 Teil B, `html.py:947-956`) bleibt
     unverändert; nur die Textdarstellung ändert sich. Diese Spec supersedet
     `issue_956_email_format.md` an genau dieser Stelle (Segment-Header-
     Format), alle übrigen #956-Festlegungen (Ziel-Block-Struktur,
     Laufsummen-Berechnung) bleiben unberührt gültig.
  2. **`build_segment_label()` (Alert-Pfad) bleibt bewusst getrennt.**
     `helpers.py:901-935` formatiert Kilometer für Abweichungs-/Change-
     Zeilen mit `_fmt_km()` (Z.896-898, strippt `.0`: `12.0` → `"12"`) — ein
     anderes Anzeigeziel (kompakte Alert-Texte) als der Segment-Header
     (immer eine Nachkommastelle, auch bei `.0`, für visuelle
     Tabellen-Konsistenz). Verworfene Alternative: `_fmt_km()` um einen
     `strip: bool`-Parameter erweitern und für beide Fälle wiederverwenden —
     verworfen, weil das zwei fachlich unterschiedliche Formatierungs-
     Verträge (Alert-Kompaktheit vs. Header-Konsistenz) künstlich in einer
     Funktion vermischt und Regressionsrisiko für den bereits stabilen
     Alert-Pfad (#397/#816/#832) schafft. Eine neue, kleine, eigenständige
     Funktion (`_km_range`) ist die sauberere Trennung.

## Changelog

- 2026-07-19: Initial spec erstellt — Issue #574, PO-bestätigt via #1310,
  verifiziert durch Kontextanalyse in
  `docs/context/feat-574-segment-km-header.md`.
