# Context: feat-1348-warn-unavailable-hint (letzter Rest #1348 — Briefing-Hinweis)

## Request Summary
Wenn amtliche Warnungen NICHT ABRUFBAR sind (≠ „keine Warnungen"), zeigt das
E-Mail-Trip-Briefing einen sichtbaren Hinweis statt still „alles ruhig" zu wirken
(#1346-Sicherheitsprinzip).

## Kernbefund
`base.py:get_official_alerts_for_location` gibt bei Fehler UND bei leer identisch
`[]` zurück — kein „unavailable"-Signal. `source.covers(lat,lon)` sagt, ob eine
Quelle den Ort abdeckt.

## Design (Spec: warn_unavailable_hint.md)
- Neue `get_official_alerts_with_status() -> (alerts, unavailable)`; alte Funktion
  bleibt Wrapper (37 Bestandsaufrufer unberührt).
- **unavailable = covering > 0 and failed >= 1** (PO-Entscheid 2026-07-23: STRENG
  — schon eine ausgefallene abdeckende Quelle genügt).
- Flag über `SegmentWeatherData.official_alerts_unavailable` bis in die Renderer.
- Sichtbarer Hinweis in E-Mail full (HTML+Plain) + compact; rote Danger-Box, NIE
  `G_INK_FAINT` (Lesbarkeits-Leitprinzip).

## Scope
- NUR E-Mail-Trip-Briefing. SMS/Telegram/Compare = Folge-Scheiben.
- Renderer-Mail-Gate #811 Pflicht (test_issue_811_mode_matrix grün +
  briefing_mail_validator-Lauf).
- Regressionsarm: „keine Warnungen"/„Warnungen vorhanden" byte-identisch.

## Render-Stellen
`output/renderers/alert/official_alerts.py` (geteilter Baustein),
`output/renderers/email/{html,plain,compact}.py`. Byte-Gleichheits-Anforderungen
compare↔trip nicht brechen.
