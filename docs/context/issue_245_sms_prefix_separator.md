# Context: Issue #245 — SMS-Vorschau: Leerzeichen vor Prefix-Separator

## Request Summary
Stage-Namen mit Doppelpunkt (z.B. `"Tag 1: von Valldemossa nach Deià"`) erzeugen nach `.replace(":", "")` trailing Whitespace, der nach 10-Char-Truncation in der SMS-Vorschau sichtbar bleibt (`"Tag 1 von : N-..."`).

## Related Files
| Datei | Relevanz |
|-------|----------|
| `src/services/preview_service.py:148` | Fundstelle: `clean_stage = (stage_name or "Etappe").replace(":", "")` — hier fehlt `.strip()` |
| `src/output/tokens/builder.py:26-28` | `_sanitize_stage_name`: Umlaut-Ersatz dann `[:10]` — Truncation schneidet trailing Space nicht weg |
| `tests/tdd/test_epic_140_preview_endpoints.py:199` | Existierender Test prüft `": "` im token_line — kein Test für Stage-Namen mit Doppelpunkt |
| `tests/unit/test_sms_trip.py` | SMS-Trip-Tests, kein Colon-in-stage_name-Case |

## Bestehende Patterns
- `preview_service.py` bereinigt Stage-Namen vor Übergabe an `SMSTripFormatter`
- `_sanitize_stage_name` im builder.py macht Umlaut-Ersatz + `[:10]` Truncation, kein Strip
- Kommentar in Zeile 146-147 erklärt die Intent der `:` Bereinigung korrekt

## Ursache (präzise)
```
"Tag 1: von Valldemossa nach Deià"
  → .replace(":", "")  →  "Tag 1 von Valldemossa nach Deià"   ← Space bleibt!
  → _sanitize_stage_name → [:10]  →  "Tag 1 von "             ← Trailing Space!
  → token_line: "Tag 1 von : N- D- ..."                        ← Sichtbar vor ":"
```

## Fix (1 Zeile)
`src/services/preview_service.py:148`:
```python
# vorher:
clean_stage = (stage_name or "Etappe").replace(":", "")
# nachher:
clean_stage = (stage_name or "Etappe").replace(":", "").strip()
```

## Dependencies
- Upstream: `stage_name` kommt aus `self._build_report()` → Trip-Daten
- Downstream: `SMSTripFormatter.format_sms()` → `build_token_line()` → `_sanitize_stage_name()`

## Risks & Considerations
- Minimaler Fix, kein Seiteneffekt: `.strip()` entfernt nur leading/trailing Whitespace nach dem Replace
- Kein Schema-Rework, keine Daten-Migration nötig
- Bestehender Test `test_ac1_token_line_contains_stage_colon_prefix` deckt den Fall nicht ab → neuen Test hinzufügen
