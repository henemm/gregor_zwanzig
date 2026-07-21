# Spec: Wetter-Metriken-Tab v2 (Desktop) — #587

**Status:** Entwurf (wartet auf PO-Freigabe der ACs)
**Created:** 2026-06-06
**Issue:** #587 (Teil von Epic #575 / Paket „Trip bearbeiten")
**Quelle:** `body-23-config-change-flow.md`, `screen-trip-edit-v2-weather.jsx`
**Modell-Entscheidung (PO Henning, 2026-06-06):** zwei Zustände `spalte`/`aus`, zwei Modi
`raw`/`indicator`, **keine Detail-Zeile** (`secondary` entfällt), **kein Signal**, Telegram-Limit 8.

## Problem

Der „Wetter"-Tab im Trip-Bearbeiten-Screen (`TripEditView.svelte`) zeigt nur eine Read-Only-Karte
(`WeatherSummaryCard`). Der Nutzer kann dort nichts konfigurieren und sieht keinen Zusammenhang
zwischen Einstellung und erzeugter E-Mail (PO-Feedback 2026-06-05).

## Scope

**In Scope (Desktop, Frontend):**
- „Wetter"-Tab wird zum **4-Abschnitte-Editor + Live-Mail-Vorschau rechts (sticky)**.
- Modell-Vereinfachung: `secondary`/Detail-Bucket entfällt im Frontend (`metricsEditor.ts`,
  `OutputLayoutEditor`, `ChannelPreviewBlock` und abhängige Molecules). Jede ausgewählte Metrik
  ist **Spalte** (geordnet) oder **aus**.
- Telegram-Budget im Frontend `CHANNEL_COL_BUDGET.telegram` 7 → 8.
- Verlustfreie Migration bestehender `display_config`: Metriken im alten `secondary`-Bucket
  werden zu `spalte` (Spalten), hinter die bisherigen primary einsortiert (read-modify-write).

**Out of Scope (eigene Slices/Folge):**
- Tab-Umbenennung auf kanonischen Satz „Übersicht · … · Wetter-Metriken · Briefing-Zeitplan · Alerts" (#616)
- Kanal-Verkettung Zeitplan/Alerts (#617)
- Mobile-Ansicht (#618)
- Backend-Renderer/`channel_layout.py`: `secondary`/Detail-Zeile + `signal` entfernen, `_PRIMARY_SLOTS 5→8` (#610 Schritt 2/2 + Backend-Koordination) — kein Nutzer betroffen, nicht blockierend.

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet den Trip-Bearbeiten-Screen und wählt den Wetter-Tab,
When die Seite lädt, Then erscheinen vier Abschnitte (Profil · Grundauswahl · Reihenfolge &
Darstellung · Kanäle) links und eine Live-Mail-Vorschau rechts — **nicht** die bisherige
Read-Only-Karte.

**AC-2:** Given der Wetter-Tab ist offen, When der Nutzer eine Metrik aktiviert/deaktiviert, die
Reihenfolge ändert, den Modus Roh/Einfach umschaltet oder das Preset wechselt, Then aktualisiert
sich die Live-Mail-Vorschau rechts **sofort** und die betroffene Stelle wird sichtbar
hervorgehoben (Diff-Highlight: moved/added/removed/mode/preset).

**AC-3:** Given der Abschnitt „Reihenfolge & Darstellung", When er gerendert wird, Then zeigt er
eine nummerierte Liste der ausgewählten Metriken mit ▲/▼ (Reihenfolge), Roh/Einfach-Umschalter
(nur bei Metriken mit Indikator-Mapping, sonst nur „Roh") und „Entfernen" — und **keinen**
„→ Detail"-Knopf und **keine** separate Detail-Zeile.

**AC-4:** Given mehr als 8 Spalten sind ausgewählt und Telegram ist aktiv, When der Abschnitt
„Reihenfolge & Darstellung" und die Telegram-Vorschau gerendert werden, Then erscheint nach
Position 8 eine orange gestrichelte Schnittlinie („ab hier bei Telegram abgeschnitten") und die
Telegram-Vorschau zeigt nur die ersten 8 Spalten plus eine Erklärung, dass der Rest abgeschnitten ist.

**AC-5:** Given irgendein Kanal-, Budget- oder Vorschau-Element im Wetter-Tab, When es gerendert
oder typgeprüft wird, Then erscheint ausschließlich Email · Telegram · SMS (kein Signal) und
`CHANNEL_COL_BUDGET.telegram` ist 8; `npm run check` und der Build sind grün.

**AC-6:** Given die Live-Mail-Vorschau, When der Nutzer zwischen den Kanal-Tabs wechselt, Then
zeigt Email eine HTML-Tabelle (Kopf + Segment-Zeilen), Telegram eine Mono-Bubble mit
Schnitt-Erklärung und SMS eine Token-Zeile mit Zeichen-Zähler.

**AC-7:** Given ein bestehender Trip, dessen `display_config` Metriken im alten `secondary`-Bucket
hatte, When der Trip im Wetter-Tab geladen und ohne weitere Änderung gespeichert wird, Then bleiben
diese Metriken erhalten (als Spalten einsortiert) — keine Metrik geht verloren, alle übrigen Felder
der `display_config` bleiben unverändert (read-modify-write).

**AC-8:** Given die Optik des Wetter-Tabs, When ein Screenshot gegen die SOLL-Vorlage verglichen
wird, Then liegt die Pixel-Differenz unter der #603-Schwelle (Hard-Gate); Inline-Styles und Tokens
folgen `var(--g-*)` gemäß JSX.

**AC-9:** Given die bestehende Frontend-Test-Suite, When sie nach der Änderung läuft, Then sind alle
Tests grün; Erwartungen, die noch einen `secondary`/Detail-Bucket annahmen, sind auf das
Spalte/aus-Modell angepasst.

## Verifikation (mock-frei)
- Playwright-E2E gegen Staging als eingeloggter Nutzer: Wetter-Tab öffnen (AC-1), Änderung →
  Live-Mail-Update + Highlight (AC-2), Schnittlinie/Telegram-Vorschau (AC-4), Kanal-Tabs (AC-6).
- `npm run check` + Build grün (AC-5).
- Roundtrip-Test display_config: laden → speichern → laden, Metrik-Counts identisch (AC-7).
- Pixel-Diff-Tool gegen SOLL (AC-8). Frontend-Test-Suite grün (AC-9).

## Datenmodell (Frontend, vereinfacht)
```typescript
type Mode = 'raw' | 'indicator';
interface MetricColumn { id: string; order: number; mode: Mode; }   // nur Spalten
interface WeatherConfig {
  preset_id: string;
  columns: MetricColumn[];                 // ausgewählte Metriken, geordnet (kein secondary)
  channels: { email: boolean; telegram: boolean; sms: boolean };
  dirty: boolean;
}
// Migration: alt {primary[], secondary[], off[]} → columns = primary ++ secondary (order beibehalten)
```

## Hinweis JSX-Divergenz
Die gelieferten JSX (`screen-trip-edit-v2-weather.jsx`) enthalten noch `secondary`/„→ Detail".
**Maßgeblich ist die PO-Entscheidung „keine Detail-Zeile".** JSX-Bereinigung läuft separat über
Claude Design und blockiert diese Umsetzung nicht. Optik (Abstände, Tokens, Layout) bleibt 1:1 nach JSX.
