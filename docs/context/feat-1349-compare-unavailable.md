# Context: feat-1349-compare-unavailable (Scheibe 3 von #1349, größte Scheibe)

## Request Summary
Die Orts-Vergleich-Mail (`compare_html.py`, X-GZ-Mail-Type: compare) soll — analog zu
E-Mail-Trip (#1348), SMS (Scheibe 1) und Telegram (Scheibe 2) — einen Banner "amtliche
Warnungen aktuell nicht abrufbar" zeigen, wenn für mindestens einen Ort eine abdeckende
amtliche Quelle ausgefallen ist. Im Compare-Pfad FEHLT das Flag noch komplett — es muss
neu eingezogen werden (derselbe Stillschweig-Bug-Typ wie #1348).

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/user.py:117` | `LocationResult` — braucht additives Feld `official_alerts_unavailable: bool = False` (neben `official_alerts`, Zeile 160) |
| `src/services/comparison_engine.py:221-232` | ruft heute `get_official_alerts_for_location(loc.lat, loc.lon)` OHNE Status — auf `get_official_alerts_with_status` umstellen, Flag auf LocationResult durchreichen |
| `src/output/renderers/email/compare_html.py:982-1089` | `render_compare_html`; Banner-Reihung bei 1046/1085 — hier den Unavailable-Banner einhängen. `_render_warn_banner` (526) ist der Nachbar |
| `src/output/renderers/email/unavailable_hint.py` | GETEILTE Bausteine `any_official_alerts_unavailable`, `render_official_alerts_unavailable_html` — Wiederverwendung Pflicht |

## Existing Patterns
- `any_official_alerts_unavailable(items)` liest `getattr(item, "official_alerts_unavailable", False)` — funktioniert duck-typed auch auf `LocationResult`, sobald das Feld existiert (kein Compare-eigener Aggregator).
- `render_official_alerts_unavailable_html()` ist der geteilte Danger-Box-Baustein (schon in der Trip-Mail live).
- Banner-Reihung in `render_compare_html`: nur nicht-leere Blöcke werden gejoint (Anti-Erosion #1034) → Banner nur bei gesetztem Flag.
- Trip nutzt `get_official_alerts_with_status()` (liefert `(alerts, unavailable)`) — Compare zieht denselben Aufruf ein (Trip/Compare-Teilung: gleiche Erkennung, kein zweiter Pfad).

## Analysis

### Type
Feature (Kanal-Ausweitung + Flag-Neueinführung im Compare-Pfad).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/user.py` | MODIFY (~+2 LoC) | `LocationResult.official_alerts_unavailable: bool = False` |
| `src/services/comparison_engine.py` | MODIFY (~+8 LoC) | `get_official_alerts_with_status`; Flag im Erfolgs-/Fehlerzweig setzen und an LocationResult übergeben |
| `src/output/renderers/email/compare_html.py` | MODIFY (~+6 LoC) | Unavailable-Banner in `render_compare_html` (nur bei `any_official_alerts_unavailable(locations)`) |
| `tests/tdd/test_compare_unavailable_hint.py` | CREATE (~+45 LoC) | Kern-Tests am echten Fail-soft-Pfad |

### Scope Assessment
- Files: 4 (3 MODIFY + 1 CREATE)
- Estimated LoC: +60/+90
- Risk Level: MEDIUM — berührt den Erfolgspfad von comparison_engine (Fetch-Aufruf getauscht); Byte-Identität der Compare-Mail OHNE Flag ist Pflicht-Regressionsschutz.

### Technical Approach
1. `LocationResult` bekommt das additive bool-Feld (Default False → Bestandsobjekte/Serialisierung unverändert).
2. `comparison_engine`: `get_official_alerts_with_status(loc.lat, loc.lon)` statt `get_official_alerts_for_location`; das `unavailable`-Flag im `official_alerts_enabled`-Zweig mitführen. Bei `except`/`official_alerts_enabled=False`: Flag False (bzw. bei unerwartetem Fehler sicherheitsseitig True — wie Trip-Pfad #1348, `trip_report_scheduler.py:810-812`).
3. `compare_html.render_compare_html`: `unavailable_banner_html = render_official_alerts_unavailable_html() if any_official_alerts_unavailable(locations) else ""`, in die `body_html`-Reihung neben `warn_banner_html`.
4. Ohne gesetztes Flag: Compare-Mail byte-identisch.

### Dependencies
- Upstream: `get_official_alerts_with_status` (base.py, schon vorhanden aus #1348).
- Downstream: Compare-Mail-Renderer; Renderer-Mail-Gate #811 Compare-Pfad (`email_spec_validator.py`, X-GZ-Mail-Type: compare).
- `compare_official_alert.py` (Alert-Abweichungs-Pfad #1258) bleibt UNBERÜHRT — der Hinweis fließt über comparison_engine → LocationResult → compare_html, nicht über den Alert-Notice-Pfad.

### Open Questions
- Keine PO-Frage offen (Wortlaut = geteilter Baustein, Banner-Position = neben bestehendem Warn-Banner).
