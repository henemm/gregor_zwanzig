---
entity_id: feat_1349_telegram_unavailable
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [telegram, official-alerts, unavailable, issue-1349, issue-1348]
---

<!-- Issue #1349 — Scheibe 2 (Telegram): Hinweis "amtliche Warnungen nicht abrufbar". Folge von #1348. -->

# Scheibe 2 (Telegram) — Hinweis "amtliche Warnungen nicht abrufbar"

## Approval

- [x] Approved (PO „go" 2026-07-23)

## Purpose

Das Telegram-Trip-Briefing ("rich") zeigt — analog zur E-Mail (#1348) und SMS (Scheibe 1) —
eine sichtbare Hinweiszeile "amtliche Warnungen aktuell nicht abrufbar", wenn für mindestens
ein Segment `SegmentWeatherData.official_alerts_unavailable=True` ist. Kein Zeichen-Limit →
volle Hinweiszeile über den geteilten Baustein aus `unavailable_hint.py` (kein neuer Text,
kein Kürzel).

## Source

- **File:** `src/output/renderers/narrow.py` (MODIFY, ~+6 LoC) — in `render_telegram_bubbles()` nach dem Kopf-Bubble eine Hinweis-Bubble bei gesetztem Flag
- **File:** `tests/tdd/test_telegram_trip_unavailable_hint.py` (CREATE, ~+30 LoC)

Schicht: **Python-Core / Domain-Backend** (`src/output/...`). Kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~+36
- **Files:** 2 (1 MODIFY + 1 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SegmentWeatherData.official_alerts_unavailable` | intern | Quelle des Flags (#1348, Scheduler) |
| `any_official_alerts_unavailable` / `render_official_alerts_unavailable_plain` (`unavailable_hint.py`) | intern | GETEILTE Anzeige-Bausteine — Wiederverwendung Pflicht (kein Nachbau) |
| `TelegramBubble` / `_esc` (`narrow.py`) | intern | Bubble-Struktur + Telegram-Escaping |

## Implementation Details

```
render_telegram_bubbles(...):
    ... bubbles.append(head bubble) ...
    if any_official_alerts_unavailable(segments):
        bubbles.append(TelegramBubble(
            text=_esc(render_official_alerts_unavailable_plain(ascii_safe=False))
        ))
    ... _official_alert_bubble ... (bestehend)
```

## Expected Behavior

- **Input:** Segmentliste, davon ≥1 mit `official_alerts_unavailable=True`.
- **Output:** Eine der Telegram-Bubbles enthält den Text "…nicht abrufbar".
- **Side effects:** Keine.

## Acceptance Criteria

- **AC-1:** Given ein Telegram-Trip-Briefing, bei dem ≥1 Segment
  `official_alerts_unavailable=True` hat / When die Bubbles gerendert werden / Then enthält
  mindestens eine Bubble den Hinweistext "nicht abrufbar".
  - Test: `render_telegram_bubbles(...)` mit Flag → eine Bubble enthält "nicht abrufbar".

- **AC-2:** Given ein Telegram-Trip-Briefing, bei dem KEIN Segment das Flag gesetzt hat /
  When die Bubbles gerendert werden / Then erscheint KEIN Nicht-abrufbar-Hinweis und die
  Anzahl/der Inhalt der Bubbles ist unverändert gegenüber heute.
  - Test: identische Segmente ohne Flag → kein "nicht abrufbar", Bubble-Liste == Baseline.

- **AC-3:** Given der Hinweis wird angezeigt / When der geteilte Baustein genutzt wird /
  Then stammt der Text aus `render_official_alerts_unavailable_plain` (kein neuer, eigener
  Telegram-Textbaustein) — geprüft am gerenderten Ergebnis, das den Baustein-Text trägt.
  - Test: die Hinweis-Bubble enthält exakt den Baustein-Text (inkl. ⚠️-Prefix bzw. dessen escapte Form).

- **AC-4:** Given das Flag stammt vom ECHTEN Fail-soft-Pfad (Quelle liefert `[]` ohne zu
  werfen) / When die Segmente in den Telegram-Renderer fließen / Then erscheint der Hinweis —
  der Regressionswächter benutzt KEIN werfendes Double.
  - Test: Fixture setzt das Flag über `get_official_alerts_with_status` mit geblockter echter Quelle.

## Known Limitations

- Kurzform-Telegram (`report.sms_text`) erbt den `W?`-Marker aus Scheibe 1 und ist hier NICHT betroffen.
- Ein Segment ohne das Attribut zählt per `getattr`-Default als verfügbar (kein Fehlalarm).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kanal-Ausweitung eines entschiedenen Features (#1348); keine neue Entscheidungsfläche.

## Changelog

- 2026-07-23: Initial spec created (Scheibe 2 Telegram von #1349)
