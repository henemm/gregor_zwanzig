---
entity_id: issue_284_alert_rules_restyle
type: module
created: 2026-05-21
updated: 2026-05-21
status: implemented
version: "1.0"
tags: [frontend, design-system, alert-rules-editor, ui-restyle, css-tokens, svelte, issue-284]
---

# Issue #284 — AlertRulesEditor + ModeCard: Full Restyle against Brand Tokens

## Approval

- [x] Approved

## Purpose

Der AlertRulesEditor und seine Unterkomponenten verwenden derzeit ad-hoc HTML-Buttons und eigene CSS-Klassen statt der etablierten Design-System-Komponenten `Btn` und `Pill`. Dieses Modul vereinheitlicht alle drei Komponenten des alert-rules-editor mit den Brand-Tokens: Buttons werden durch `<Btn>`-Komponenten ersetzt, Severity-Pills erhalten deutsche Labels und eine outlined Variante, die ModeCard-Beispieltexte wechseln zur Mono-Schrift, und die Zeilen-Darstellung des `AlertRuleRow` erhält eine Tabellen-ähnliche Hairline-Trennlinie statt individueller Card-Borders. Das Ergebnis ist eine visuell konsistente Darstellung, die vollständig aus den Design-Token der `app.css` aufgebaut ist.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 5 Dateien

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/app.css` | Outlined Pill-Variante ergänzen |
| `frontend/src/lib/utils/alertMetricLabels.ts` | `SEVERITY_LABEL_DE`-Konstante ergänzen |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | `.example`-Style: italic → Mono-Schrift |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | View-Mode + Edit-Mode komplett restyled |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Card-Wrapper + Ghost-Add-Button |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/btn` | Svelte-Komponente (vorhanden) | Ersetzt alle ad-hoc `<button>`-Elemente; Varianten: primary, ghost, outline, secondary, destructive, link; Größen: xs, sm, md, lg |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Svelte-Komponente (vorhanden) | Rendert Severity-Badges; leitet `...rest`-Props an den DOM weiter, so dass `data-outlined` das DOM-Element erreicht |
| `frontend/src/lib/utils/alertMetricLabels.ts` | Utility-Datei (vorhanden) | Enthält bereits `ALERT_SEVERITY_TONE`; wird um `SEVERITY_LABEL_DE` ergänzt |
| `frontend/src/app.css` | CSS-Datei (vorhanden) | Single Source of Truth für Design-Token; erhält neue Outlined-Pill-Regeln |
| `frontend/e2e/alert-rules-editor.spec.ts` | Playwright-Test (vorhanden) | AC-2 prüft `[data-slot="pill"][data-tone="warning"]` — `data-tone` muss erhalten bleiben |

## Implementation Details

### 1. `app.css` — Outlined Pill-Variante

Direkt nach den bestehenden `[data-slot="pill"]` Tone-Regeln einfügen:

```css
[data-slot="pill"][data-outlined] {
  background: transparent;
  border: 1px solid currentColor;
}
[data-slot="pill"][data-outlined][data-tone="warning"]  { color: var(--g-warning); }
[data-slot="pill"][data-outlined][data-tone="danger"]   { color: var(--g-danger); }
[data-slot="pill"][data-outlined][data-tone="info"]     { color: var(--g-info); }
[data-slot="pill"][data-outlined][data-tone="default"]  { color: var(--g-ink-muted); }
```

Die Outlined-Variante ist additiv — bestehende Filled-Pills bleiben unberührt, da `data-outlined` als extra Attribut gesetzt wird.

### 2. `alertMetricLabels.ts` — Deutsche Severity-Labels

Am Ende der Datei ergänzen (nach vorhandenem `ALERT_SEVERITY_TONE`):

```typescript
export const SEVERITY_LABEL_DE: Record<AlertSeverity, string> = {
  info: 'Info',
  warning: 'Warnung',
  critical: 'Kritisch'
};
```

### 3. `ModeCard.svelte` — Mono-Schrift für `.example`

Den bestehenden `.example`-CSS-Block in der Komponente anpassen:

```css
.example {
  font-family: var(--g-font-data);
  font-size: 11px;
  font-style: normal;
  letter-spacing: 0;
  color: var(--g-ink-faint);
}
```

Konkret: `font-style: italic` entfernen, `font-family: var(--g-font-data)` und `letter-spacing: 0` setzen.

### 4. `AlertRuleRow.svelte` — View-Mode Restyle

**Import-Ergänzungen am Dateianfang:**

```svelte
import Btn from '$lib/components/ui/btn';
import { SEVERITY_LABEL_DE } from '$lib/utils/alertMetricLabels';
```

**Zeilen-Layout:** Individuelle Card-Border/Background der View-Zeile durch Hairline-Trennlinie ersetzen:

```css
.alert-rule-view {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) auto auto auto auto auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: none;
  border-bottom: 1px solid var(--g-ink-faint);
  border-radius: 0;
  background: transparent;
  font-size: var(--g-text-sm);
}
.alert-rule-view:hover { background: var(--g-surface-2); }
.alert-rule-view:last-child { border-bottom: none; }
```

**Threshold-Wert:** Mono-Schrift ergänzen (Farbe bleibt wie bisher):

```css
.threshold {
  font-family: var(--g-font-data);
  font-variant-numeric: tabular-nums;
}
```

**Severity-Pill:** Outlined + Deutsche Labels:

```diff
- <Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
+ <Pill tone={ALERT_SEVERITY_TONE[rule.severity]} data-outlined>{SEVERITY_LABEL_DE[rule.severity]}</Pill>
```

**Kind-Pill:** Ebenfalls outlined:

```diff
- <Pill tone="default">{rule.kind}</Pill>
+ <Pill tone="default" data-outlined>{rule.kind}</Pill>
```

**Edit/Delete-Buttons:** Durch `<Btn>`-Komponente ersetzen:

```diff
- <button onclick={startEdit}>Bearbeiten</button>
- <button onclick={deleteRule}>Löschen</button>
+ <Btn variant="ghost" size="sm" onclick={startEdit}>Bearbeiten</Btn>
+ <Btn variant="ghost" size="sm" onclick={deleteRule}>Löschen</Btn>
```

### 5. `AlertRuleRow.svelte` — Edit-Mode Restyle

**Speichern/Abbrechen-Buttons:**

```diff
- <button class="btn-primary" onclick={saveEdit}>Speichern</button>
- <button class="btn-secondary" onclick={cancelEdit}>Abbrechen</button>
+ <Btn variant="primary" size="sm" onclick={saveEdit} data-testid="alert-rule-save">Speichern</Btn>
+ <Btn variant="ghost" size="sm" onclick={cancelEdit} data-testid="alert-rule-cancel">Abbrechen</Btn>
```

Lokale CSS-Klassen `.field`, `.btn-primary`, `.btn-secondary` aus dem Scoped-Style-Block entfernen.

### 6. `AlertRulesEditor.svelte` — Card-Wrapper + Ghost-Add-Button

**Import ergänzen:**

```svelte
import Btn from '$lib/components/ui/btn';
```

**Struktur:** Liste der Alert-Regeln und den Add-Button in einen Card-Div mit Border und Border-Radius einschließen. Add-Button durch `<Btn>` ersetzen:

```diff
- <button class="add-button" onclick={addRule}>+ Regel hinzufügen</button>
+ <Btn variant="ghost" size="sm" onclick={addRule} data-testid="alert-rules-editor-add">+ Regel hinzufügen</Btn>
```

Der Card-Wrapper erhält `border: 1px solid var(--g-ink-faint)` und `border-radius: var(--g-radius-md)`. Der Add-Button sitzt innerhalb des Cards am unteren Rand, nach der Regel-Liste.

### Umsetzungsreihenfolge

1. `app.css` — Outlined-Pill-Regeln (keine Abhängigkeiten)
2. `alertMetricLabels.ts` — `SEVERITY_LABEL_DE` (keine Abhängigkeiten)
3. `ModeCard.svelte` — `.example`-Style (unabhängig)
4. `AlertRuleRow.svelte` — View-Mode + Edit-Mode (benötigt Schritt 1 + 2)
5. `AlertRulesEditor.svelte` — Card-Wrapper + Add-Button (benötigt Schritt 1)

### Kritische Nebenbedingung

Der Playwright-Test `frontend/e2e/alert-rules-editor.spec.ts` prüft in AC-2:

```javascript
row.first().locator('[data-slot="pill"][data-tone="warning"]')
```

Das Attribut `data-tone` MUSS erhalten bleiben. Die Outlined-Variante wird durch `data-outlined` als zusätzliches Attribut gesteuert — `data-tone` wird nicht ersetzt.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/app.css` | +8 | ja |
| `frontend/src/lib/utils/alertMetricLabels.ts` | +6 | ja |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | ~+3 | ja |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | ~+15 / -10 | ja |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | ~+10 / -5 | ja |
| **Gesamt** | **~+27 netto** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Bestehende Alert-Regeln eines Trips (Severity: info/warning/critical, Kind: Metrik-Typ, Schwellwert, Cooldown)
- **Output (visuell):**
  - Severity-Pills sind outlined (transparenter Hintergrund, farbige Border) mit deutschen Labels ("Info", "Warnung", "Kritisch")
  - Kind-Pills sind ebenfalls outlined mit `--g-ink-muted` als Farbe
  - Threshold-Werte erscheinen in `--g-font-data` (JetBrains Mono) mit tabular-nums
  - Zeilen sind durch Hairlines (`1px solid var(--g-ink-faint)`) getrennt, kein individuelles Card-Border pro Zeile
  - Hover einer Zeile zeigt `--g-surface-2` als Hintergrund
  - ModeCard-Beispieltexte erscheinen in Mono-Schrift statt kursiver Schrift
  - Alle Buttons (Bearbeiten, Löschen, Speichern, Abbrechen, Hinzufügen) nutzen die `<Btn>`-Komponente mit korrekter Variante und Größe
  - Die gesamte Regel-Liste ist von einem Card mit Border und Border-Radius eingeschlossen
- **Side effects:** Die Outlined-Pill-Regeln in `app.css` wirken global auf alle Pill-Nutzer, die `data-outlined` setzen — aktuell ausschließlich AlertRuleRow; andere Pill-Nutzer (StageStrip, LocationsRail, TripStatusBadge) sind nicht betroffen, da diese `data-outlined` nicht setzen

## Acceptance Criteria

**AC-1:** Given der AlertRulesEditor mit mindestens einer Regel mit `severity: "warning"` / When die Alerts-Tab-Ansicht im Trip-Detail gerendert wird / Then zeigt die Severity-Pill den deutschen Text "Warnung", hat transparenten Hintergrund und eine farbige Border in `--g-warning`, und behält das Attribut `data-tone="warning"` im DOM.
  - Test: (populated after /tdd-red)

**AC-2:** Given der Playwright-Test `frontend/e2e/alert-rules-editor.spec.ts` / When `npx playwright test alert-rules-editor` ausgeführt wird / Then laufen alle Tests durch (Exit 0) — insbesondere der `data-tone="warning"`-Selektor schlägt nicht fehl.
  - Test: Playwright-Testsuite — bestehende Tests dürfen nicht brechen

**AC-3:** Given eine Alert-Regel-Zeile im View-Modus / When die Zeile gerendert wird / Then hat die Zeile keine eigene Card-Border (`border: none`), keinen Card-Radius (`border-radius: 0`) und keinen eigenen Hintergrund (`background: transparent`), sondern nur eine untere Hairline-Trennlinie (`border-bottom: 1px solid var(--g-ink-faint)`). Die letzte Zeile hat keine Hairline.
  - Test: (populated after /tdd-red)

**AC-4:** Given die Bearbeiten- und Löschen-Buttons im View-Modus einer Regel / When der Quelltext von `AlertRuleRow.svelte` auf `<button` geprüft wird / Then ist kein nacktes `<button`-Element mehr vorhanden — alle Buttons sind `<Btn>`-Komponenten.
  - Test: `grep -c "<button" frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` → `0`

**AC-5:** Given der Speichern-Button im Edit-Modus einer Regel / When eine Regel bearbeitet und gespeichert wird / Then hat der Speichern-Button das Attribut `data-testid="alert-rule-save"` und der Abbrechen-Button `data-testid="alert-rule-cancel"`.
  - Test: (populated after /tdd-red)

**AC-6:** Given der Add-Button im AlertRulesEditor / When der Alerts-Tab gerendert wird / Then hat der Button `data-testid="alert-rules-editor-add"`, ist eine `<Btn variant="ghost">`-Komponente, und ist innerhalb eines Card-Wrappers mit Border und Border-Radius positioniert.
  - Test: (populated after /tdd-red)

**AC-7:** Given der ModeCard-Beispieltext (`.example`) / When die ModeCard-Komponente gerendert wird / Then ist der Text nicht mehr kursiv (`font-style: normal`) und verwendet `var(--g-font-data)` (JetBrains Mono).
  - Test: (populated after /tdd-red)

**AC-8:** Given alle anderen Pill-Nutzer im Frontend (LocationsRail, StageStrip, TripStatusBadge, StageDetailRow) / When die jeweiligen Seiten nach dem Restyle gerendert werden / Then zeigen diese Komponenten keine visuelle Regression — ihre Pills sind weiterhin filled (farbiger Hintergrund), da `data-outlined` nicht gesetzt ist.
  - Test: Manuelle Sichtprüfung auf `/compare` und Trip-Detail-Cockpit

## Known Limitations

- AC-8 ist eine visuelle Verifikation ohne automatisierten Playwright-Test — die Prüfung erfolgt durch manuelle Sichtprüfung auf den genannten Seiten.
- Die Outlined-Pill-Regel in `app.css` kennt nur `warning`, `danger`, `info`, `default` als Tone-Varianten für die Farbe. Wird `data-outlined` auf einer `tone="success"`- oder `tone="accent"`-Pill gesetzt, greift `currentColor` des Elements ohne explizite Token-Zuweisung — das ist für die aktuelle Nutzung im AlertRuleRow unproblematisch, da dort nur `warning`, `danger`, `info` und `default` vorkommen.
- Die `Pill`-Komponente muss `...rest`-Props an den DOM weiterleiten (spread), damit `data-outlined` das DOM-Element erreicht. Sollte dies in einer zukünftigen Überarbeitung der `Pill`-Komponente entfernt werden, muss `data-outlined` als explizites Prop ergänzt werden.

## Changelog

- 2026-05-21: Initial spec created (Issue #284 — AlertRulesEditor + ModeCard Full Restyle)
