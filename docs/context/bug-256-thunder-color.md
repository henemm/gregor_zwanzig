# Context: Bug #256 — --g-weather-thunder Farbkonflikt

## Request Summary

`--g-wx-thunder` in `frontend/src/app.css` steht auf violett (`#5a3a7a`), aber semantisch gehört Gewitter zur Alarm-/Gefahr-Palette (rot, wie `--g-danger: #b33a2a`). Der Wert muss auf `#c43a2a` (rot) korrigiert und in `design_tokens.py` ergänzt werden.

## Befund

| Datei | Token | Aktueller Wert | Problem |
|-------|-------|----------------|---------|
| `frontend/src/app.css:80` | `--g-wx-thunder` | `#5a3a7a` (violett) | **Single Source of Truth — falsch** |
| `docs/reference/design_system_tokens.css:51` | `--g-weather-thunder` | `#c43a2a` (rot) | Archiv-Referenz — korrekter Wert |
| `src/output/renderers/email/design_tokens.py` | (fehlt) | — | **Lücke** — kein Thunder-Token im Mail-Renderer |
| `docs/reference/design_system.md:320-325` | Konflikt-Dokumentation | beide erwähnt | Muss nach Fix aktualisiert werden |

## Entscheidung

**Rot (`#c43a2a`)** ist korrekt:
- Passt zu `--g-danger: #b33a2a` (gleiche Alarm-Hue)
- Semantisch: Gewitter = Gefahr = Rot; Violett hat keinen Bezug zum Gefahren-System
- `design_system_tokens.css` hatte den richtigen Wert

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `frontend/src/app.css` | Zeile 80: `#5a3a7a` → `#c43a2a` |
| `src/output/renderers/email/design_tokens.py` | Neuer Eintrag `G_WX_THUNDER = "#c43a2a"` |
| `docs/reference/design_system.md` | Konflikt-Abschnitt: „gelöst durch Issue #256" |
| `docs/reference/design_system_tokens.css` | Zeile 51: Wert bleibt, Kommentar aktualisieren |

## Tests

- `tests/tdd/test_issue_254_email_template_vorarbeit.py::test_ac1_design_system_md_references_thunder_bug` — prüft Konflikt-Erwähnung; bleibt grün solange `weather-thunder` + `Bug` im Content (Erwähnung „gelöst" ist OK)
- Keine bestehenden Tests für Farbwerte → neue Tests für AC erforderlich

## Risiken

- `frontend/src/app.css` hat ca. 6 weitere `--g-wx-*`-Tokens — nur thunder ändern, Rest unberührt
- `design_tokens.py` darf nur ergänzt werden (kein Refactor bestehender Einträge)
