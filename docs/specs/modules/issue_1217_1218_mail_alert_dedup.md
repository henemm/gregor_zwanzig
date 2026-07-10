---
entity_id: issue_1217_1218_mail_alert_dedup
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [bug, official-alerts, email-renderer, dedup, bundle-G-mail-darstellung]
---

<!-- Issues #1217 + #1218 — Amtliche Warnungen in Mails doppelt + Segment-Bezug fehlt -->

# Issues 1217+1218 — Amtliche-Warnung-Dedup vereinheitlichen + Segment-Bezug im Briefing

## Approval

- [x] Approved (PO 2026-07-10 — „go"; Segment-Bezug wie #1200, eine gemeinsame Compare-Dedup-Quelle)

## Purpose

Amtliche Warnungen erscheinen in Mails **doppelt** (Compare-Übersicht #1218: Hitze/Gewitter doppelt;
Trip-Briefing #1217: doppelt), und dem Trip-Briefing fehlt die **Segment-Zuordnung**. Ursache: drei
divergierende Dedup-/Gruppierungs-Strategien. Ziel: alle Mail-Pfade auf **einen** robusten Dedup-Helfer
(`dedupe_official_alerts`) konsolidieren und den Segment-Bezug (wie Warn-Mail #1200) auch im Trip-Briefing
rendern. PO-Entscheidungen 2026-07-10: (a) Segment-Bezug wie #1200, (b) eine gemeinsame Dedup-Quelle im Compare.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` — `dedupe_official_alerts` (kanonisch),
  `collect_trip_alert_entries` (abzulösen), `render_official_alerts_html` (um Segment-Bezug erweitern),
  `format_segment_reference` (Baustein #1200). Python-Core / Domain-Backend.
- **File:** `src/output/renderers/email/html.py:1412-1413` — Trip-Briefing.
- **File:** `src/output/renderers/email/compare_html.py` — `_render_warn_cell` (:244 roher Input),
  `_dedup_alerts` (:182 dritter Schlüssel).

## Estimated Scope

- **LoC:** ~+90/−70 · **Files:** ~5 (3 src, 2+ Tests) · **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dedupe_official_alerts` | Vorbild | `(region_label, hazard)`, höchste Stufe, Segment-Union — die kanonische Quelle |
| `format_segment_reference` (#1200) | Baustein | Segment-Bezug-Text, wiederverwenden |
| Renderer-Mailgate #811 | Gate | Commit auf Mail-Inhalts-Dateien → Validator-Nachweise Pflicht |

## Implementation Details

**Konsolidierung auf eine Dedup-Quelle:**
```
# official_alerts.py — collect_trip_alert_entries wird auf dedupe_official_alerts-Semantik gehoben
#   (bzw. der Briefing-Pfad ruft dedupe_official_alerts direkt): Gruppe (region_label, hazard),
#   höchste Stufe, Segment-ID-Union. Liefert (alert, segment_ids)-Tupel.

# render_official_alerts_html: nimmt künftig Segment-IDs je Alert an und rendert den Segment-Bezug
#   (format_segment_reference) im Badge — analog zum Plain-Notice (#1200 render_official_alert_notice_plain:166).

# compare_html.py:244 — _render_warn_cell bekommt deduplizierten Input (gemeinsamer Helfer).
# compare_html.py:182 — _dedup_alerts wird durch den gemeinsamen Helfer ersetzt/zurückgeführt
#   (Streifen + Chips nutzen dieselbe eine Quelle → nie wieder divergent).
```

## Expected Behavior

- **Input:** Segmente/Orte mit `official_alerts` (ggf. dieselbe Warnung mehrfach über Segmente/Stufen).
- **Output:** Je `(region_label, hazard)` **ein** Eintrag (höchste Stufe); Trip-Briefing zeigt den
  Segment-Bezug; Compare-Übersichts-Chips und Pro-Ort-Streifen zeigen identisch entdoppelte Warnungen.
- **Side effects:** reine Präsentation; keine Datenpfade.

## Acceptance Criteria

- **AC-1:** Given ein Ort mit derselben Warnung mehrfach (gleiche `(region_label, hazard)`, z.B. Hitze
  über zwei Segmente) / When die **Compare-Übersichtstabelle** gerendert wird / Then erscheint der
  Warn-Chip **genau einmal** (nicht doppelt). — #1218
  - Test: `render_compare_html` mit dupliziertem Hitze-Alert → `_render_warn_cell`-Chip „Hitze" genau 1×.

- **AC-2:** Given derselbe Ort / When Übersichts-Chip UND Pro-Ort-Streifen gerendert werden / Then
  zeigen **beide** dieselbe entdoppelte Menge (identische Dedup-Quelle).
  - Test: Anzahl Chips == Anzahl Streifen-Badges für denselben Input.

- **AC-3:** Given ein Trip mit derselben Warnung über mehrere Etappen / When das **Trip-Briefing**
  gerendert wird / Then erscheint die Warnung **genau einmal** (höchste Stufe je `(region_label, hazard)`). — #1217
  - Test: Briefing-HTML mit Duplikat über 2 Segmente → Warnung-Label genau 1×.

- **AC-4:** Given eine Trip-Warnung, die bestimmte Etappen/Segmente betrifft / When das Trip-Briefing
  gerendert wird / Then nennt der Badge den **Segment-Bezug** (via `format_segment_reference`, Format wie
  Warn-Mail #1200). — #1217 „Segment-Zuordnung fehlt"
  - Test: Briefing-HTML enthält den Segment-Bezug-Text der betroffenen Segmente.

- **AC-5:** Given verschiedene Warnungen (unterschiedliche hazards/Regionen) / When gerendert wird / Then
  werden sie **nicht** fälschlich kollabiert (kein Over-Dedup).
  - Test: zwei verschiedene hazards an einem Ort → zwei Einträge; zwei Regionen gleicher hazard → zwei Einträge.

- **AC-6:** Given der Fix / When die Test-Suite läuft / Then keine Regression an #1200 (Warn-Mail
  Segment-Bezug), #1172 (Dedup-Info), #1056 (Farb-Skala), #1134 (Zeitfenster/Metrik-Zellen).
  - Test: bestehende Suiten grün.

- **AC-7:** Given dieselbe Massiv-Sperre (`hazard=access_ban`, `region_label=None`), deren Stufe
  während der Tour eskaliert (z.B. Niveau 3 „eingeschränkt" → Niveau 4 „gesperrt", also mit
  UNTERSCHIEDLICHEM `label`-Text über zwei Segmente) / When Trip-Briefing bzw. Compare gerendert
  werden / Then erscheint die Sperre **genau einmal** (höchste Stufe). Der Dedup muss eine
  **stufen-unabhängige, stabile Massiv-Identität** nutzen, nicht den level-behafteten Label-Text.
  — F001 (Adversary), PO-Scope-Freigabe 2026-07-10 „jetzt mitfixen".
  - Test: zwei `access_ban`-Alerts desselben Massivs, Niveau 3 und 4, verschiedene Labels →
    genau EIN Eintrag (Niveau 4) im Briefing und im Compare-Übersichts-Chip.

- **AC-8:** Given zwei GENUIN verschiedene Warnungen, bei denen der `region_label`-Wert der einen
  zufällig dem `label`-Wert der anderen gleicht (gleicher hazard) / When dedupliziert wird / Then
  werden sie NICHT kollabiert (Fallback-Schlüssel ist quellen-namespaced). — F002 (Adversary).
  - Test: `dedupe_official_alerts` mit dieser Konstellation → zwei Einträge.

## Known Limitations

- `collect_trip_alert_entries` bleibt bestehen, dedupliziert aber jetzt selbst über `dedupe_official_alerts`
  (drei Trip-Renderer: `html.py` nutzt einen eigenen dedupe-Pfad MIT Segment-Bezug; `plain.py`/`compact.py`
  nutzen `collect_trip_alert_entries`). Die #1087-Tests rufen `collect_trip_alert_entries` weiter direkt auf.
- Segment-Bezug im HTML-Badge erfordert Signaturerweiterung von `render_official_alerts_html`
  (Segment-IDs je Alert) — Golden-/Byte-Tests (#1087) ggf. nachziehen (bewusst).
- **Segment-Bezug ist bewusst HTML-only** (Trip-Briefing `full`, HTML-Teil). Die Text-Renderer
  `plain.py` (Textteil der `full`-Mail) und `compact.py` (`compact`-Body) **deduplizieren korrekt**
  (AC-3/AC-7, keine Doppelung), zeigen aber **keinen** per-Segment-Bezug — `compact` ist bewusst terse und
  ASCII-transliteriert (Emoji/En-Dash aus `format_segment_reference` passen dort nicht). AC-4 ist daher
  HTML-scoped. Nachrüstung des Text-Segment-Bezugs wäre ein eigenes Folge-Thema.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Konsolidierung auf bestehenden Helfer (Prinzip „eine Quelle, Rest Thin-Wrapper"),
  keine neue Struktur. Beseitigt Divergenz statt sie zu erweitern.

## Changelog

- 2026-07-10: Initial spec (Issues #1217 + #1218, gebündelt).
- 2026-07-10: Scope-Erweiterung nach Adversary-Runde 1 (AMBIGUOUS). PO-Freigabe „jetzt mitfixen":
  AC-7 (Massiv-Sperren-Eskalation, F001) + AC-8 (Fallback-Key-Kollision, F002). Neu betroffen:
  `src/services/official_alerts/models.py` (additives, optionales Identitätsfeld auf `OfficialAlert`),
  `src/services/official_alerts/massif_closure.py` (setzt die stabile Massiv-Identität).
