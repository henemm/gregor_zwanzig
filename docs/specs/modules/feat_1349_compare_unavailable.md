---
entity_id: feat_1349_compare_unavailable
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [compare, official-alerts, unavailable, issue-1349, issue-1348]
---

<!-- Issue #1349 — Scheibe 3 (Compare): Banner "amtliche Warnungen nicht abrufbar". Folge von #1348. -->

# Scheibe 3 (Compare) — Banner "amtliche Warnungen nicht abrufbar"

## Approval

- [x] Approved (PO „go" 2026-07-23)

## Purpose

Die Orts-Vergleich-Mail zeigt — analog zu Trip-E-Mail (#1348), SMS (Scheibe 1) und Telegram
(Scheibe 2) — einen Banner "amtliche Warnungen aktuell nicht abrufbar", wenn für mindestens
einen verglichenen Ort eine abdeckende amtliche Quelle beim Fetch ausgefallen ist. Im
Compare-Pfad fehlt das Ausfall-Flag heute komplett; es wird über dieselbe Erkennung wie im
Trip-Pfad (`get_official_alerts_with_status`) eingezogen. Geteilter Baustein aus
`unavailable_hint.py` (kein Nachbau).

## Source

- **File:** `src/app/user.py` (MODIFY, ~+2 LoC) — `LocationResult.official_alerts_unavailable: bool = False`
- **File:** `src/services/comparison_engine.py` (MODIFY, ~+8 LoC) — `get_official_alerts_with_status` statt `get_official_alerts_for_location`, Flag durchreichen
- **File:** `src/output/renderers/email/compare_html.py` (MODIFY, ~+6 LoC) — Unavailable-Banner in `render_compare_html`
- **File:** `tests/tdd/test_compare_unavailable_hint.py` (CREATE, ~+45 LoC)

Schicht: **Python-Core / Domain-Backend** (`src/app`, `src/services`, `src/output`). Kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~+70
- **Files:** 4 (3 MODIFY + 1 CREATE)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `get_official_alerts_with_status` (`services/official_alerts/base.py`) | intern | Erkennung `(alerts, unavailable)` — geteilt mit Trip-Pfad (#1348) |
| `LocationResult` (`src/app/user.py`) | intern | Träger des neuen Flags im Compare-Pfad |
| `any_official_alerts_unavailable` / `render_official_alerts_unavailable_html` (`unavailable_hint.py`) | intern | GETEILTE Anzeige-Bausteine — Wiederverwendung Pflicht |
| Renderer-Mail-Gate #811 Compare-Pfad (`email_spec_validator.py`) | Gate | Nachweis gegen echt zugestellte Compare-Mail (X-GZ-Mail-Type: compare) |

## Implementation Details

```
1. user.py: LocationResult
   official_alerts_unavailable: bool = False   (additiv)

2. comparison_engine.py (official_alerts_enabled-Zweig):
   alerts, unavailable = get_official_alerts_with_status(loc.lat, loc.lon)
   # except -> alerts=[], unavailable=False (bzw. True bei unerwartetem Fehler,
   #           sicherheitsseitig wie trip_report_scheduler.py:810-812)
   # official_alerts_enabled=False -> alerts=[], unavailable=False
   LocationResult(..., official_alerts=alerts, official_alerts_unavailable=unavailable)

3. compare_html.render_compare_html:
   unavailable_banner_html = (
       render_official_alerts_unavailable_html()
       if any_official_alerts_unavailable(locations) else ""
   )
   # in body_html-Reihung neben warn_banner_html (nur nicht-leere Blöcke)
```

## Expected Behavior

- **Input:** `ComparisonResult` mit ≥1 `LocationResult`, davon ≥1 mit `official_alerts_unavailable=True`.
- **Output:** Die Compare-HTML-Mail enthält den Danger-Box-Banner "…nicht abrufbar".
- **Side effects:** Keine (reiner Lese-/Renderpfad; Fetch-Aufruf getauscht, Verhalten bei Erfolg identisch).

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich, bei dem für ≥1 Ort das Flag
  `official_alerts_unavailable=True` ist / When die Compare-Mail gerendert wird / Then
  enthält die HTML-Mail einen sichtbaren Hinweis "…nicht abrufbar".
  - Test: `render_compare_html(result, ...)` mit einem LocationResult-Flag=True → HTML enthält "nicht abrufbar".

- **AC-2:** Given ein Orts-Vergleich, bei dem KEIN Ort das Flag gesetzt hat / When die
  Compare-Mail gerendert wird / Then ist die HTML-Ausgabe byte-identisch zur heutigen und
  enthält KEINEN Nicht-abrufbar-Banner.
  - Test: identischer Result einmal ohne Flag → Ausgabe == Baseline, "nicht abrufbar" nicht enthalten.

- **AC-3:** Given der Compare-Fetch läuft am ECHTEN Fail-soft-Pfad (`get_official_alerts_with_status`,
  Quelle liefert `[]` ohne zu werfen) / When `comparison_engine` einen Ort auswertet / Then
  ist `LocationResult.official_alerts_unavailable=True` — der Regressionswächter benutzt KEIN
  werfendes Double.
  - Test: comparison_engine mit geblockter echter Quelle → LocationResult-Flag True; kein `raise`-Double.

- **AC-4:** Given der Hinweis wird angezeigt / When der geteilte Baustein genutzt wird / Then
  stammt der Banner aus `render_official_alerts_unavailable_html` (kein neuer Compare-Textbaustein),
  hochkontrastig (G_DANGER, kein G_INK_FAINT).
  - Test: der gerenderte Banner trägt den Baustein-Text + G_DANGER, nicht G_INK_FAINT.

- **AC-5:** Given ein Ort mit echter amtlicher Warnung UND ein anderer Ort mit gesetztem
  Ausfall-Flag / When die Compare-Mail gerendert wird / Then erscheinen BEIDE (bestehender
  Warn-Banner und Nicht-abrufbar-Banner) — die Infos sind orthogonal.
  - Test: Mischfall → sowohl Warn-Banner-Inhalt als auch "nicht abrufbar" im HTML.

## Known Limitations

- `compare_official_alert.py` (Alert-Abweichungs-Pfad #1258) bleibt unberührt; der Hinweis fließt über comparison_engine → LocationResult → compare_html.
- Strenge Regel wie #1348: EINE ausgefallene abdeckende Quelle je Ort genügt für das Flag dieses Orts.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kanal-Ausweitung eines entschiedenen Features (#1348) mit Wiederverwendung der bestehenden Erkennung; keine neue Entscheidungsfläche. Trip/Compare-Teilung (geteilte Erkennung + geteilter Anzeige-Baustein) wird eingehalten.

## Changelog

- 2026-07-23: Initial spec created (Scheibe 3 Compare von #1349)
