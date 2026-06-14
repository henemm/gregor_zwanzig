---
entity_id: issue_810_raw_format_ampel
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [bug, email, briefing, format-mode]
---

# Issue #810 — Format-Modus 'Roh' respektieren für Wind/Böen/Regen im HTML-Briefing

## Approval

- [ ] Approved

## Purpose

Der per-Metrik-Format-Schalter „Roh" (`use_friendly_format=false`) muss im HTML-Briefing
auch für **Wind, Böen, Regen und Regenwahrscheinlichkeit** greifen. Aktuell überschreiben
die 4-stufigen Ampelpunkte (eingeführt #759) den Schalter unbedingt — „Roh" zeigt trotzdem
🟢🟡🟠🔴 statt der Zahl.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `fmt_val` (Keys `wind`, `gust`, `precip`, `pop`)

Schicht: **Python-Backend** (E-Mail-Renderer). Kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~3 (drei `if html:` → `if html and use_friendly:`)
- **Files:** 1 (Quelle) + 1 Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ampel_dot` | Helper | 4-stufiger Ampelpunkt (bleibt für „Einfach") |
| `use_friendly` (Z.428) | Lokale Variable | Bereits korrekt berechnet, nur nicht konsultiert |
| `cloud`/`sunshine`/`cape` (selbes File) | Korrekt-Vorbild | `if not use_friendly:` zuerst |

## Implementation Details

```python
# wind/gust (Z.446):
if html and use_friendly:
    metric_id = _AMPEL_KEY_TO_METRIC_ID[key]
    return ampel_dot(val, get_metric(metric_id).display_thresholds)
# sonst fällt es auf den existierenden raw-Pfad: s = f"{val:.0f}" (+ Kompass bei wind)

# precip (Z.459):
if html and use_friendly:
    return ampel_dot(val, get_metric("precipitation").display_thresholds)
# sonst: return f"{val:.1f}"

# pop (Z.500):
if html and use_friendly:
    return ampel_dot(val, get_metric("rain_probability").display_thresholds)
# sonst: return f"{val:.0f}"
```

Plain-Part (`html=False`) ist bereits raw und bleibt unverändert.

## Expected Behavior

- **Input:** `fmt_val(key, val, html=True, format_modes={key: "raw"})` für wind/gust/precip/pop.
- **Output:** rohe Zahl (z.B. `"33"`, `"2.4"`, `"60"`), kein Ampel-Emoji.
- **Side effects:** keine. Bei `format_modes={key: "indicator"/"simplified"}` oder
  `friendly_keys`-Mitgliedschaft bleibt der Ampelpunkt erhalten.

## Acceptance Criteria

- **AC-1:** Given Wind/Böen auf Format „Roh" / When die HTML-Briefing-Zelle gerendert wird /
  Then enthält die Zelle die rohe km/h-Zahl und KEINEN Ampelpunkt (🟢🟡🟠🔴).
  - Test: `fmt_val("wind", 33, html=True, format_modes={"wind": "raw"})` → Ergebnis enthält
    `"33"` und keines der vier Ampel-Emojis. Analog `gust`.

- **AC-2:** Given Regen auf Format „Roh" / When die HTML-Zelle gerendert wird / Then zeigt sie
  die rohe mm-Zahl ohne Ampelpunkt.
  - Test: `fmt_val("precip", 2.4, html=True, format_modes={"precip": "raw"})` → enthält `"2.4"`,
    kein Ampel-Emoji.

- **AC-3:** Given Regenwahrscheinlichkeit auf „Roh" / When die HTML-Zelle gerendert wird / Then
  zeigt sie die rohe Prozentzahl ohne Ampelpunkt.
  - Test: `fmt_val("pop", 60, html=True, format_modes={"pop": "raw"})` → enthält `"60"`,
    kein Ampel-Emoji.

- **AC-4 (Regress-Schutz):** Given Wind/Regen auf Format „Einfach"/indicator (Default) / When
  die HTML-Zelle gerendert wird / Then bleibt der 4-stufige Ampelpunkt erhalten (Verhalten #759
  unverändert).
  - Test: `fmt_val("wind", 33, html=True, format_modes={"wind": "indicator"})` → Ergebnis ist
    genau einer von 🟢🟡🟠🔴. Analog precip/pop.

- **AC-5 (Plain-Gegenprobe):** Given irgendein Modus / When der Plain-Part gerendert wird
  (`html=False`) / Then erscheint nie ein Ampel-Emoji (war schon so, bleibt so).
  - Test: `fmt_val("wind", 33, html=False, format_modes={"wind": "indicator"})` → keine
    Ampel-Emojis.

- **AC-6 (E2E echte Mail):** Given ein Trip mit wind/precip-Metrik auf „Roh" / When eine echte
  Briefing-Mail gerendert + per `build_mime_message` serialisiert wird / Then enthält der
  HTML-Part rohe Zahlen statt Ampelpunkten für diese Metriken, und `briefing_mail_validator`
  bleibt Exit 0.
  - Test: Mail rendern → MIME bauen → HTML-Part dekodieren → assert keine Ampel-Emojis in den
    wind/precip-Zellen.

## Known Limitations

- Andere Metriken mit eigenem Emoji/Ampel-Pfad (cloud, sunshine, cape, visibility) sind bereits
  korrekt und nicht Teil dieses Fixes.

## Changelog

- 2026-06-14: Initial spec created (Issue #810)
