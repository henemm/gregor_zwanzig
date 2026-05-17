---
entity_id: issue_245_sms_prefix_separator
type: bugfix
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [sms, preview, formatting]
---

# SMS-Vorschau: Leerzeichen vor Prefix-Separator (Issue #245)

## Approval

- [ ] Approved

## Purpose

Stage-Namen mit Doppelpunkt (z.B. `"Tag 1: von Valldemossa nach Deià"`) erzeugen nach `.replace(":", "")` ein Leerzeichen an der Position des ehemaligen Doppelpunkts. Nach 10-Char-Truncation in `_sanitize_stage_name` bleibt dieses Leerzeichen als trailing Space erhalten und erscheint in der SMS-Vorschau sichtbar als `"Tag 1 von : N-..."`.

## Source

- **File:** `src/services/preview_service.py`
- **Identifier:** `PreviewService.render_sms_preview()` — Zeile mit `clean_stage =`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/tokens/builder._sanitize_stage_name` | intern | Umlaut-Ersatz + `[:10]` Truncation — kein Strip |
| `src/formatters/sms_trip.SMSTripFormatter.format_sms` | intern | Empfänger von `clean_stage` |

## Implementation Details

```python
# Vorher (fehlerhaft):
clean_stage = (stage_name or "Etappe").replace(":", "")

# Nachher (korrekt):
clean_stage = (stage_name or "Etappe").replace(":", "").strip()
```

`.strip()` entfernt leading/trailing Whitespace, der nach `.replace(":", "")` entstehen kann, wenn ein Doppelpunkt am Anfang, Ende oder direkt neben einem Leerzeichen steht. Hat null Seiteneffekt auf normale Stage-Namen.

## Expected Behavior

- **Input:** `stage_name = "Tag 1: von Valldemossa nach Deià"`
- **Output:** `clean_stage = "Tag 1 von "`.strip() → `"Tag 1 von"` (kein trailing Space)
- **SMS-Prefix:** `"Tag 1 von: N- ..."` statt `"Tag 1 von : N- ..."`

## Acceptance Criteria

**AC-1:** Given `stage_name = "Tag 1: von Valldemossa nach Deià"` / When `render_sms_preview()` aufgerufen / Then enthält `token_line` keinen Space direkt vor dem Separator-Doppelpunkt (`" :"` ist verboten).
- Test: (populated after /tdd-red)

**AC-2:** Given `stage_name = "Normalname"` (ohne Doppelpunkt) / When `render_sms_preview()` aufgerufen / Then ändert sich das Verhalten gegenüber vorher nicht (kein Regressions-Effekt).
- Test: (populated after /tdd-red)

## Known Limitations

- Fix betrifft nur `preview_service.py`. Falls Stage-Namen mit Doppelpunkt auch an anderen Stellen in die SMS-Pipeline gelangen (z.B. direkter CLI-Aufruf), wäre dort ein separater Fix nötig — aktuell nicht betroffen.

## Changelog

- 2026-05-17: Initial spec created (Issue #245)
