# Design-Request: Frischer SOLL für Compare-Detail-Hub `/compare/[id]`

**Auslöser:** Issue #643 (Paket 2 von #582, Epic #575) — als „überholt" geschlossen, weil
JSX-Vorlage und SOLL-Screenshot den Live-Stand nicht mehr abbilden.
**Tracking der Folge-Umsetzung:** Issue #646 (blockiert bis dieser Design-Request geliefert ist).

## Problem mit dem aktuellen Handoff

Der Compare-Detail-Hub ist bereits live als **Tab-Hub** (Kontext-Header → Status-Streifen →
Tab-Leiste Übersicht/Orte/Idealwerte/Layout/Versand/Vorschau), Signal-frei, ausgeliefert
unter #582 (`8dd45ccd`) + Folge-Fixes #589/#590/#591/#601/#609.

Die Handoff-Quellen widersprechen diesem Live-Stand:

| Quelle | Problem |
|--------|---------|
| `jsx/screen-compare-detail.jsx` | enthält noch **Signal** (Z. 19/242/266) — entfernt per #610 |
| `soll/G-compare-detail.png` | zeigt **altes Einseiten-Layout OHNE Tab-Leiste** (Header → Status-Streifen → Ranking-Liste) + Kanal „Email · **Signal**" + Demo-Daten „Skitouren Hochkönig" |

Ein „1:1"-Nachbau wäre eine **Regression**: er holte Signal und das überholte
Einseiten-Layout zurück.

## Bitte um frischen SOLL

Für eine künftige echte Fidelity-Prüfung des **aktuellen Tab-Hubs** wird benötigt:

1. **Aktualisierte JSX** `screen-compare-detail.jsx` ohne Signal (Kanäle nur Email · Telegram · SMS).
2. **Frischer SOLL** `G-compare-detail.png`, gerendert vom aktuellen Tab-Hub
   (Kontext-Header mit Status-Pill + „Region · Profil · N Orte", Status-Streifen,
   **Tab-Leiste**, dann Übersicht-Tab-Inhalt) — kein Einseiten-Layout, kein Signal.

Danach kann ein neues Fidelity-Issue mit Pixel-Diff-Gate `G-compare-detail` aufgesetzt werden.

## Hinweis Diff-Tool

`design_fidelity_diff.py` mappt `G-compare-detail` aktuell auf `/compare` statt `/compare/[id]`
(braucht Pre-Action „erste Vergleichs-Kachel klicken"). Erst beim neuen Fidelity-Issue
relevant, dann mitziehen.
