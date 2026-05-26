---
entity_id: bug_383_hoehenprofil_kontrast
type: bugfix
created: 2026-05-26
updated: 2026-05-26
status: active
version: "1.0"
tags: [bugfix, accessibility, wcag, contrast, svg, design-system, elevation-profile, issue-383]
---

<!-- Issue #383 — WCAG §1.4.11 Non-Text-Kontrast: SVG-Höhenprofil-Datenkurven zu hell -->

# Issue #383 — Bug-Fix: Höhenprofil-Datenkurven auf WCAG §1.4.11-konformes Token anheben

## Approval

- [ ] Approved

## Zweck

Zwei SVG-`<polyline>`-Elemente in `ProfileEditor.svelte` und `ProfileChart.svelte` verwenden `stroke="var(--g-ink-faint)"` (#9c9a90, Kontrastverhältnis 2.82:1 auf Weiß). WCAG §1.4.11 (Non-Text Contrast, Level AA) fordert mindestens 3:1 für bedeutungstragende grafische Elemente — die Höhenprofil-Datenkurve ist ein bedeutungstragendes UI-Element, das Tourenentscheidungen beeinflusst. Das Token wird auf `--g-ink-muted` (#5c5a52, 6.91:1) angehoben, das die §1.4.11-Grenze deutlich übersteigt. Dekorative Gitternetz-Linien in `ProfileEditor.svelte` sind von der Anforderung ausgenommen und werden mit `audit:exempt`-Kommentaren gekennzeichnet.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` Zeile 167 — `stroke="var(--g-ink-faint)"` → `stroke="var(--g-ink-muted)"` (Datenkurve)
- `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` Zeilen 140/149/158 — drei dekorative Gitternetz-Linien mit `stroke-dasharray` erhalten `<!-- audit:exempt — dekorativ -->` Kommentar
- `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte` Zeile 80 — `stroke="var(--g-ink-faint)"` → `stroke="var(--g-ink-muted)"` (Datenkurve)

**Neue Test-Ergänzung:**
- `frontend/src/lib/contrast-audit.test.ts` — neuer Test-Block prüft per Source-Inspection, dass keine `.svelte`-Datei `stroke="var(--g-ink-faint)"` enthält, ohne dass die Zeile oder der umliegende Kontext einen `audit:exempt`-Kommentar trägt

**NICHT ändern:** `FullProfile.svelte` (stroke=currentColor, color: --g-ink = 17.43:1 ✓), `ElevSparkline.svelte` (stroke prop default currentColor ✓) — beide sind bereits konform.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/lib/...`, SvelteKit). Python-Backend und Go-API sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für Design-Tokens; definiert `--g-ink-faint: #9c9a90` (2.82:1, FAIL) und `--g-ink-muted: #5c5a52` (6.91:1, PASS) |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` | Svelte-Komponente | Höhenprofil-Editor im Trip-Detail-View; enthält die betroffene Datenkurve (Zeile 167) und drei dekorative Grid-Linien (Zeilen 140/149/158) |
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte` | Svelte-Komponente | Höhenprofil-Anzeige im Trip-Wizard; enthält die zweite betroffene Datenkurve (Zeile 80) |
| `frontend/src/lib/contrast-audit.test.ts` | Test-Datei | Source-Inspection-Tests für WCAG-Compliance; erhält neuen Test-Block für SVG-stroke §1.4.11 |

## Implementation Details

### 1. `ProfileEditor.svelte` — Datenkurve (Zeile 167)

Token-Austausch auf der `<polyline>`, die das Höhenprofil zeichnet:

```
Vorher:
<polyline stroke="var(--g-ink-faint)" ...>

Nachher:
<polyline stroke="var(--g-ink-muted)" ...>
```

### 2. `ProfileEditor.svelte` — Gitternetz-Linien (Zeilen 140/149/158)

Drei dekorative `<line>`-Elemente mit `stroke-dasharray` sind §1.4.11-exempt (rein dekorativ, kein Informationsgehalt). Jede Zeile erhält einen Inline-Kommentar direkt davor oder dahinter:

```svelte
<!-- audit:exempt — dekorativ -->
<line stroke-dasharray="..." ... />
```

### 3. `ProfileChart.svelte` — Datenkurve (Zeile 80)

Identischer Token-Austausch wie in Schritt 1:

```
Vorher:
<polyline stroke="var(--g-ink-faint)" ...>

Nachher:
<polyline stroke="var(--g-ink-muted)" ...>
```

### 4. `contrast-audit.test.ts` — neuer Test-Block

Source-Inspection analog zum bestehenden `textColorOffenders`-Pattern. Der neue Test scanrt alle `.svelte`-Dateien auf `stroke="var(--g-ink-faint)"` und prüft, ob im Kontext-Fenster (±60 Zeichen) kein `audit:exempt`-Kommentar steht:

```typescript
test('AC-1 §1.4.11: --g-ink-faint nirgends als SVG stroke ohne audit:exempt', () => {
  const offenders: string[] = [];
  for (const f of FILES.filter(f => f.endsWith('.svelte'))) {
    const content = readFileSync(f, 'utf-8');
    const re = /stroke="var\(--g-ink-faint\)"/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(content)) !== null) {
      const ctx = content.slice(Math.max(0, m.index - 60), m.index + 120);
      if (/audit:exempt/.test(ctx)) continue;
      const line = content.slice(0, m.index).split('\n').length;
      offenders.push(`${f}:${line}`);
    }
  }
  assert.equal(
    offenders.length,
    0,
    `stroke="var(--g-ink-faint)" ohne audit:exempt (§1.4.11 FAIL):\n  ${offenders.join('\n  ')}`
  );
});
```

### 5. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `ProfileEditor.svelte` | +3 / -1 (1 Token-Tausch + 3 Kommentare) | ja |
| `ProfileChart.svelte` | +1 / -1 (Token-Tausch) | ja |
| `contrast-audit.test.ts` | +18 | ja |
| **Gesamt (zählend)** | **~22** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine Laufzeit-Eingabe — alle Änderungen sind statische SVG-Attribut-Werte
- **Output:** Beide Datenkurven-`<polyline>`-Elemente rendern mit `--g-ink-muted` (#5c5a52, 6.91:1 auf Weiß); WCAG §1.4.11 AA ist erfüllt
- **Side effects:** Visuell sichtbare Änderung: Höhenprofil-Kurven erscheinen etwas dunkler/klarer. Dekorative Gitternetz-Linien bleiben mit `--g-ink-faint` (kein Kontrast-Anforderung für dekorative Elemente); der `audit:exempt`-Kommentar dokumentiert die Ausnahme für zukünftige Audits.

## Acceptance Criteria

- **AC-1:** Given alle `.svelte`-Quelldateien im Frontend / When ein Source-Inspection-Test auf `stroke="var(--g-ink-faint)"` ohne `audit:exempt`-Kontext sucht / Then gibt es exakt 0 Treffer (kein unkennzeichnetes FAIL-Token als SVG-Datenkurven-stroke)
  - Test: `contrast-audit.test.ts` — neuer Test-Block `AC-1 §1.4.11`

- **AC-2:** Given `ProfileEditor.svelte` wird in einem Browser gerendert / When das Höhenprofil mit Wegpunkten angezeigt wird / Then hat die `<polyline>`-Datenkurve den Stroke-Wert `var(--g-ink-muted)` und nicht mehr `var(--g-ink-faint)`
  - Test: Source-Inspection via AC-1-Test (indirekt: 0 unkennzeichnete `--g-ink-faint`-stroke-Treffer beweisen den Token-Tausch)

- **AC-3:** Given `ProfileChart.svelte` im Trip-Wizard-Step / When das Höhenprofil gerendert wird / Then hat die `<polyline>`-Datenkurve den Stroke-Wert `var(--g-ink-muted)` und nicht mehr `var(--g-ink-faint)`
  - Test: Source-Inspection via AC-1-Test (identischer Mechanismus wie AC-2)

- **AC-4:** Given die drei dekorativen Gitternetz-`<line>`-Elemente in `ProfileEditor.svelte` (Zeilen 140/149/158 mit `stroke-dasharray`) / When der contrast-audit.test.ts läuft / Then werden diese Zeilen nicht als Verstöße gezählt, weil jede einen `audit:exempt`-Kommentar trägt
  - Test: AC-1-Test — audit:exempt-Guard verhindert Fehlalarm für dekorative Linien

- **AC-5:** Given der bestehende contrast-audit.test.ts mit seinen 4 bestehenden Tests / When der neue §1.4.11-Test-Block hinzugefügt wird / Then laufen alle 5 Tests grün (kein Regressionsbruch bestehender Checks)
  - Test: `cd frontend && node --experimental-strip-types --test src/lib/contrast-audit.test.ts`

## Known Limitations

- **Kein Browser-Pixel-Test:** Der Kontrast-Nachweis erfolgt per Source-Inspection (Token-Name), nicht durch pixelgenaue Browser-Messung. Dies ist konsistent mit dem bestehenden contrast-audit.test.ts-Pattern und hinreichend, da `--g-ink-muted` in `app.css` definiert und stabil ist.
- **§1.4.11-Audit anderer SVG-Elemente:** Dieser Fix begrenzt sich auf die zwei identifizierten `<polyline>`-Kurven. Weitere SVG-Elemente (Achsen, Pins) sind separat zu prüfen — nicht Teil dieses Scopes.

## Out of Scope

- Änderungen an `FullProfile.svelte` oder `ElevSparkline.svelte` (bereits konform)
- Änderungen an Design-Token-Werten in `app.css`
- §1.4.3-Compliance (Text-Kontrast) — bereits durch bestehende contrast-audit.test.ts abgedeckt

## Changelog

- 2026-05-26: Initial spec erstellt. Behebt WCAG §1.4.11 Non-Text-Kontrast-Verstoß an SVG-Datenkurven in ProfileEditor.svelte und ProfileChart.svelte: Token `--g-ink-faint` (2.82:1) → `--g-ink-muted` (6.91:1); dekorative Grid-Linien mit audit:exempt gekennzeichnet; neuer Source-Inspection-Test in contrast-audit.test.ts.
