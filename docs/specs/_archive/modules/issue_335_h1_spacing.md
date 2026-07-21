# Spec: issue_335_h1_spacing

- **Status:** Draft
- **Created:** 2026-05-25
- **Issue:** #335
- **Type:** Bug (Frontend-Kosmetik)

## Problem

Die H1 im Tour-Kopf (`/trips/[id]`) rendert Kürzel + Trenn-Mittelpunkt + Namen als
`"KHW ·Karnischer Höhenweg"` — das Leerzeichen **nach** dem Mittelpunkt fehlt. Svelte trimmt
das nachgestellte Leerzeichen des Text-Nodes `" · "` direkt vor dem `{/if}`-Block-Ende.

**Stelle:** `frontend/src/lib/components/trip-detail/TripHeader.svelte:69`

```svelte
{#if trip.shortcode}<span class="h1-shortcode">{trip.shortcode}</span> · {/if}{trip.name}
```

## Soll

`"KHW · Karnischer Höhenweg"` — Leerzeichen auf **beiden** Seiten des Mittelpunkts.
Fix: geschütztes Leerzeichen (`&nbsp;`) nach dem Mittelpunkt, damit Svelte es nicht trimmt.

## Scope

- **Nur** Zeile 69 (H1). Zeile 80 (meta-line) bleibt unangetastet — dort fängt der Flex-Gap
  des Containers `.meta-line` den Abstand ab, kein sichtbarer Bug.
- Keine Logik-, Backend- oder Style-Änderung. Reine Whitespace-Korrektur im Markup.

## Acceptance Criteria

**AC-1:** Given ein Trip mit gesetztem `shortcode` (z. B. `"KHW"`) und `name`
(z. B. `"Karnischer Höhenweg"`), When die `TripHeader`-H1 gerendert wird, Then enthält der
sichtbare H1-Text die Sequenz `"KHW · Karnischer Höhenweg"` mit genau einem Leerzeichen auf
beiden Seiten des Mittelpunkts (kein `"·Karnischer"` ohne Leerzeichen).

**AC-2:** Given ein Trip **ohne** `shortcode`, When die H1 gerendert wird, Then erscheint nur
der `name` ohne führenden Mittelpunkt und ohne führendes/zusätzliches Leerzeichen.

## Nicht-Ziele

- Keine Änderung an der Breadcrumb-Zeile (Zeile 58–66) oder der meta-line (Zeile 80).
- Keine Anpassung der CSS-Tokens / des `.h1-shortcode`-Stylings.
