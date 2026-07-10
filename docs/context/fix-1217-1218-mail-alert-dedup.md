# Context/Analyse: fix-1217-1218-mail-alert-dedup

## Request Summary
Amtliche Warnungen erscheinen in Mails **doppelt**: im Orts-Vergleich (#1218: Hitze/Gewitter
doppelt) und im Trip-Briefing (#1217: doppelt + fehlende Segment-Zuordnung). Ursache: drei
divergierende Dedup-/Gruppierungs-Strategien. Ziel: Konsolidierung auf einen robusten Helfer +
einheitliches Segment-Rendering. Gebündelt (`bundle:G-mail-darstellung`, gemeinsame Ursache).

## Kein Regress aus #1056
Der #1056-Fix (Farb-Vereinheitlichung) hat die Dedup-Funktionen nachweislich nicht angefasst
(Adversary bestätigt: zero changes an `dedupe_official_alerts`/`_dedup_alerts`/`collect_trip_alert_entries`).
Die Doppelung ist vorbestehend, dem PO jetzt aufgefallen (Screenshots in #1217/#1218).

## Root Cause — drei divergierende Strategien
| Pfad | Funktion (Datei:Zeile) | Schlüssel / Verhalten | Problem |
|------|------------------------|------------------------|---------|
| Trip-**Briefing**-Badge | `collect_trip_alert_entries` (`official_alerts.py:178`) | Gruppe nach `region_label or label`, LISTE je Gruppe, `alert not in group` (Objekt-Eq); **keine** Segment-IDs | #1217: Fast-Duplikate durch; Segment-Bezug fehlt |
| Trip-**Warn-Mail** (#1200) | `dedupe_official_alerts` (`official_alerts.py:120`) | `(region_label, hazard)`, höchste Stufe, **Segment-Union** | **robust** — Vorbild |
| **Compare**-Streifen | `_dedup_alerts` (`compare_html.py:182`) | `(hazard, level, label)` | dritter Schlüssel |
| **Compare**-Übersichts-Chips | `_render_warn_cell(loc.official_alerts)` (`compare_html.py:244`) | **KEIN Dedup** (roher Input) | #1218: Chips doppelt |

## Affected Files (voraussichtlich)
| Datei | Change | Beschreibung |
|-------|--------|--------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `collect_trip_alert_entries` auf `dedupe_official_alerts`-Semantik heben (region_label+hazard, höchste Stufe, Segment-Union) ODER Briefing direkt auf `dedupe_official_alerts` umstellen; Segment-Rendering im Badge/Notice |
| `src/output/renderers/email/html.py:1412-1413` | MODIFY | Trip-Briefing: robuster Dedup + Segment-Bezug (analog Warn-Mail #1200) |
| `src/output/renderers/email/compare_html.py:244` | MODIFY | Übersichts-Chips: Input deduplizieren (gemeinsamer Helfer statt roh) |
| `src/output/renderers/email/compare_html.py:182` | MAYBE | `_dedup_alerts` durch gemeinsamen Helfer ersetzen (eine Quelle) |
| Tests (tdd) | CREATE/MODIFY | Repro: doppelte Alerts → EIN Eintrag je (region_label,hazard); Segment-Bezug im Briefing sichtbar |

## Scope Assessment
- Files: ~4-6 · Est. LoC: +80/−60 (Konsolidierung) · Risk: **MEDIUM** (geteilter Mail-Renderer, beide Mail-Typen, Mailgate #811)

## Technical Approach (Empfehlung)
**Konsolidieren auf `dedupe_official_alerts` als einzige Quelle** (Prinzip „eine Quelle, Rest Thin-Wrapper"):
1. Trip-Briefing (`html.py`) nutzt `dedupe_official_alerts` (statt `collect_trip_alert_entries`) → robuste Dedup + Segment-IDs; Badge/Notice rendert den Segment-Bezug (Baustein aus #1200 wiederverwenden, `format_segment_reference`).
2. Compare-Übersichts-Chips (`_render_warn_cell`) bekommen deduplizierten Input.
3. `_dedup_alerts` (compare) und `collect_trip_alert_entries` → auf den gemeinsamen Helfer zurückführen oder entfernen (Divergenz beseitigen).

## Repro-Artefakt
Während der #1056-E2E wurde eine echte Test-Briefing-Mail an `gregor-test@henemm.com` gesendet — in
der Analyse-/RED-Phase als realer Doppelungs-Beleg heranziehbar (IMAP).

## Open Questions
- [ ] Segment-Zuordnung im Trip-**Briefing**: gleiche Darstellung wie in der Warn-Mail (#1200 `format_segment_reference`) — Format vom PO bestätigen lassen?
- [ ] Compare: sollen Übersichts-Chip und Pro-Ort-Streifen künftig identisch deduplizieren (empfohlen: ja)?
