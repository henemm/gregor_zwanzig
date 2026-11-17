# Context: feat-2984-regionszeile-ortsformatierer

## Request Summary
Issue #2984 (Paar P03 aus der Paritäts-Bestandsaufnahme #1986): Die Regionszeile im
Klartext-Block der amtlichen Warnung (`Region: Kärnten — Segment 3`) baut ihre
Ortsangabe direkt über `format_segment_reference`, während Betreff, Karten-Kopf
(`scope_label`) und alle anderen Alarmarten über die geteilte Auflösung
`segments.format_alert_location` gehen (inkl. gemessener km-Spanne, #2036).
Doppelung zu einem Baustein zusammenführen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/official_alerts.py:845-893` | `render_official_alert_notice_plain` — Regionszeile Z. 884-887 nutzt `format_segment_reference` direkt, kennt kein `segment_km` |
| `src/output/renderers/alert/official_alerts.py:2463-2473` | `_measured_km_span` — gemeinsame gemessene Spanne eines Bündels |
| `src/output/renderers/alert/official_alerts.py:2476-2560` | `build_official_alert_notices` — innere Funktion `_ort(sprache)` = die eigentliche Ortsauflösung der amtlichen Warnung (Spanne → `format_alert_location`, sonst `format_segment_reference` oder „unbekannt") |
| `src/output/renderers/alert/segments.py:32,94` | `format_segment_reference`, `format_alert_location` (DIE geteilte Auflösungsreihenfolge, #1744/#2036) |
| `src/services/notification_service.py:2050-2083` | `_dispatch_alert_message`: einziger Produktiv-Aufrufer; Z. 2069-2072 ruft `build_official_alert_notices(..., segment_km=_measured_event_km(alert_msg))` für HTML, Z. 2083 ruft den Plain-Renderer OHNE `segment_km` |
| `src/services/notification_service.py:497-510` | `_measured_event_km` — `{seg_id: (km_from, km_to)}` nur für gemessene Ereignisse |
| `tests/tdd/test_official_alert_location_parity.py` | bewachender Paritätstest (#2036 AC-3) — nur `scope_label`, nicht die Regionszeile |
| `tests/tdd/test_alert_location_vocabulary.py:273` | `test_alle_drei_alarmarten_bilden_denselben_ortstext` — Invariante nur am Betreff |

## Existing Patterns
- #2036 hat `build_official_alert_notices` additiv um `segment_km` (Default `None`) erweitert: ohne Eintrag byte-identisch „Segment N". Dasselbe Muster passt für den Plain-Renderer.
- Ortsauflösung ist per Teilungs-Invariante (#1744 AC-3) EINE Funktion; neue Ortssprache nie zweiter Pfad.

## Dependencies
- Upstream: `segments.format_alert_location`, `format_segment_reference`, i18n `t()` (`warnung.zeile.region`, `warnung.zeit.unbekannt`).
- Downstream: Klartext-Mailteil und Telegram-Text des Trip-Alarms mit eingebetteter amtlicher Warnung (`_dispatch_alert_message`). SMS bekommt diesen Text NICHT (eigener Pfad `render_alert_sms`). HTML nutzt `render_warn_block` (schon über `scope_label`).

## Tests, die die Regionszeile prüfen (müssen grün bleiben)
- `tests/tdd/test_alert_segment_reference.py` (:92, :103)
- `tests/test_amtliche_warnungen_zweisprachig.py` (:98, :296)
- `tests/tdd/test_issue_1172_official_alert_dedup_info.py` (:74, :96, :116)
- `tests/tdd/test_official_alert_warn_section.py` (:220, :237)
- `tests/tdd/test_official_alert_subject_label_fidelity.py` (:219)
- `tests/tdd/test_warnmail_official_alert_display.py` (:214 über Dispatch, :282)
- `tests/tdd/test_ampel_css_dots.py` (:105)

## Existing Specs
- `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` (AC-3, Fallback-Garantie AC-10)
- `docs/specs/modules/fix_1744_alarm_format_angleichen.md:156` (Zeilenangabe veraltet)
- `docs/specs/modules/warnmail_official_alert_display.md:99`

## Risks & Considerations
- **Sichtbare Änderung:** Mit gemessener Spanne zeigt die Regionszeile künftig `km 12-20` statt `Segment 3` — dann aber identisch zu Karten-Kopf und Betreff derselben Mail (heute widersprechen sich Kopf und Regionszeile). Ohne gemessene Spanne: byte-identisch.
- **Nicht-numerische Kennungen:** `format_alert_location` verwirft unbrauchbare Kennungen und fällt auf km zurück — die Regionszeile hat aber keine km. Lösung: nicht `format_alert_location` blind aufrufen, sondern die in `build_official_alert_notices` schon existierende Ortsauflösung (`_ort`) zu einer Modulfunktion herausziehen und an beiden Stellen nutzen.
- **Bündelung unterschiedlich:** Plain dedupliziert per `dedupe_official_alerts`, Notices bündeln zusätzlich per `_bundle_by_hazard_level`. Segmentliste je Warnung kann daher abweichen — nur die Ortsauflösung wird geteilt, nicht die Gruppierung.
- Renderer-Commit-Gate: Mail-Inhalt ändert sich → Modus-Matrix-Test und Mail-Validator müssen frisch grün sein.

## Analysis

### Type
Feature (Refactoring mit kleiner sichtbarer Angleichung; kein Ausfall)

### Ist-Befund (verifiziert am Code, 2026-11-17)
- `build_official_alert_notices` (official_alerts.py ~2518-2530) löst den Ort über die
  innere Funktion `_ort(sprache)` auf: gemessene Spanne (`_measured_km_span`) →
  `format_alert_location(None, ids, von, bis, km_measured=True)`, sonst
  `format_segment_reference(ids) or t("warnung.zeit.unbekannt")`.
- `render_official_alert_notice_plain` (Z. 884-887) hängt an die Regionszeile direkt
  `format_segment_reference(segment_ids)` an, kennt kein `segment_km`.
- `_dispatch_alert_message` (notification_service.py ~2069-2083) übergibt
  `segment_km=_measured_event_km(alert_msg)` nur dem HTML-Pfad, der Plain-/Telegram-Text
  bekommt ihn nicht. Folge: bei gemessener Spanne sagt der HTML-Kopf `km 12-20`,
  die Regionszeile im Klartext/Telegram derselben Nachricht `Segment 3`.
- Einziger Produktiv-Aufrufer des Plain-Renderers ist `_dispatch_alert_message`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Inneres `_ort` zu Modulfunktion `_official_alert_location(segment_ids, segment_km, lang) -> str` (leerer String bei leerer Segmentliste) herausziehen; `build_official_alert_notices` nutzt sie (plus eigener „unbekannt"-Rückfall, byte-identisch); `render_official_alert_notice_plain` bekommt additiven Keyword-Parameter `segment_km=None` und nutzt dieselbe Funktion für die Regionszeile |
| `src/services/notification_service.py` | MODIFY | Plain-Aufruf in `_dispatch_alert_message` erhält `segment_km=_measured_event_km(alert_msg)` (einmal berechnen, für HTML und Plain wiederverwenden) |
| `tests/tdd/test_official_alert_location_parity.py` (oder neue Datei) | MODIFY/CREATE | Paritätstest: Regionszeile == `scope_label` für gemessene Spanne, Segment-Fallback, nicht-numerische Kennungen, leere Liste; Durchstich über `_dispatch_alert_message` (Plain + Telegram enthalten `km 12-20`, wenn HTML-Kopf es tut) |
| `docs/specs/modules/...` | CREATE | Spec für #2984 |
| `docs/specs/modules/fix_1744_alarm_format_angleichen.md` | MODIFY | veraltete Zeilenangabe (Z. 156) nachziehen |

### Scope Assessment
- Files: 3-4 Code/Test + 1-2 Doku
- Estimated LoC: +60/-15 (davon Produktivcode ~ +20/-12)
- Risk Level: LOW — eine Ortsauflösung wird geteilt; ohne gemessene Spanne bleibt alles byte-identisch, die bestehenden Regionszeilen-Tests (Liste oben) müssen unverändert grün bleiben.

### Technical Approach
1. Gemeinsamer Baustein = die bereits bestehende amtliche Ortsauflösung (`_ort`), als
   Modulfunktion. NICHT `format_alert_location` direkt im Plain-Renderer aufrufen: dessen
   Stufe 3 verwirft nicht-numerische Kennungen (`_renderable_segment_ids`) und fiele dann
   auf km-Rückfall ohne km-Werte — die heutige Regionszeile zeigt solche Kennungen aber
   roh (#1965). Die Herausziehung erhält genau das Verhalten beider Stellen.
2. Leere Segmentliste: Plain lässt den Zusatz „ — …" weg (bleibt so); Notices setzen
   „unbekannt" (bleibt so) → der Baustein liefert `""`, der jeweilige Aufrufer
   entscheidet den Rückfall.
3. `segment_km` additiv mit Default `None` → alle Bestandsaufrufe/Tests byte-identisch
   (Muster #2036).
4. Gruppierung bleibt getrennt (Plain: nur `dedupe_official_alerts`; Notices zusätzlich
   `_bundle_by_hazard_level`) — geteilt wird nur die Ortsauflösung je Segmentliste.
5. Der Paritätstest bleibt als Regressionswächter und wird auf die Regionszeile erweitert.
6. Renderer-Commit-Gate: Mail-Inhalt (Klartext-Teil) ändert sich bei gemessener Spanne →
   Modus-Matrix-Test und Briefing-/Alarm-Mail-Validator vor dem Commit frisch grün.

### Dependencies
- Upstream: `segments.format_alert_location`, `segments.format_segment_reference`,
  `_measured_km_span`, i18n `t()` (`warnung.zeile.region`, `warnung.zeit.unbekannt`).
- Downstream: Klartext-Mailteil + Telegram-Text des Trip-Alarms mit eingebetteter
  amtlicher Warnung. SMS/Premium-SMS unberührt (eigener Pfad, `sms_scope` aus Notices).

### Nebenbefund (außerhalb Scope)
- `build_official_allclear_notices` (Entwarnung, ~Z. 2666) nutzt `format_segment_reference`
  direkt; Entwarnungen tragen keine km-Spanne — kein Widerspruch innerhalb derselben
  Nachricht bekannt, daher nicht Teil von #2984 (ggf. eigener Eintrag in der
  Paritäts-Bestandsaufnahme #1986).

### Open Questions
- keine (Produktverhalten folgt der bereits freigegebenen Entscheidung #2036: gemessene
  km-Spanne verdrängt die Segmentnummer, sonst Segment-Sprache).
