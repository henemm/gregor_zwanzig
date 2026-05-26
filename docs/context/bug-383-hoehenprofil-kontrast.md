# Context: bug-383-hoehenprofil-kontrast

## Request Summary
Die Höhenprofil-Datenkurven (SVG `<polyline>`) in zwei Komponenten verwenden `stroke="var(--g-ink-faint)"` (#9c9a90 = 2.82:1 auf weiß), das unter dem WCAG §1.4.11 Non-Text-Kontrast-Minimum von 3:1 liegt. Ziel: Token auf einen WCAG-konformen Wert anheben + Test in contrast-audit.test.ts ergänzen.

## Betroffene Dateien

| Datei | Stelle | Problem |
|------|---------|---------|
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte:167` | `<polyline stroke="var(--g-ink-faint)">` | bedeutungstragende Datenkurve, 2.82:1 → FAIL §1.4.11 |
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte:80` | `<polyline stroke="var(--g-ink-faint)">` | bedeutungstragende Datenkurve, 2.82:1 → FAIL §1.4.11 |
| `frontend/src/lib/contrast-audit.test.ts` | kein §1.4.11-Test vorhanden | neuer Test für SVG stroke FAIL-Token |

## Nicht betroffene Profile-Komponenten
- `FullProfile.svelte` — `stroke="currentColor"` + CSS `color: var(--g-ink)` → 17.43:1 ✓
- `ElevSparkline.svelte` — `stroke={stroke}` prop mit default `'currentColor'` → erbt korrekt ✓

## Dekorative Elemente (§1.4.11-exempt)
In `ProfileEditor.svelte` gibt es 3 horizontale Gitternetz-Linien mit:
- `stroke="var(--g-ink-faint)"` + `stroke-dasharray="2,4"` + `stroke-width="0.5"`
- Diese sind rein dekorativ (kein Datenbezug) → §1.4.11-exempt
- Nach Fix: `// audit:exempt — dekorativ` Kommentar ergänzen, damit der neue Test sie überspringt

## Design-Token-Werte (aus app.css)

| Token | Wert | Kontrast auf #fff | Eignung |
|-------|------|-------------------|---------|
| `--g-ink-faint` | #9c9a90 | 2.82:1 | **FAIL** (aktuell, falsch) |
| `--g-ink-3` | #6b675c | 5.65:1 | AA-text ✓ |
| `--g-ink-muted` | #5c5a52 | 6.91:1 | AA-text ✓ (Empfehlung) |

Empfehlung: `--g-ink-muted` — höherer Puffer über 3:1, semantisch passend für "muted" Datenkurve (visuell untergeordnet gegenüber den schwarzen Pins).

## Existing Patterns
- `contrast-audit.test.ts` prüft bereits `--g-ink-faint` als **Textfarbe** (CSS color:, Tailwind text-[], style-Binding). SVG `stroke` ist **nicht** abgedeckt → Erweiterungsbedarf.
- `audit:exempt` Kommentar-Muster bereits etabliert (z.B. `BrandWordmark.svelte` Punkt-Glyph).
- Neue Test-Funktion analog zu `textColorOffenders()` aber für SVG `stroke=` Attribute.

## Fix-Umfang (sehr klein)
1. `ProfileEditor.svelte:167` — `stroke="var(--g-ink-faint)"` → `stroke="var(--g-ink-muted)"`
2. `ProfileChart.svelte:80` — `stroke="var(--g-ink-faint)"` → `stroke="var(--g-ink-muted)"`
3. `ProfileEditor.svelte:140/149/158` — Gridlines: `// audit:exempt — dekorativ` Kommentar ergänzen
4. `contrast-audit.test.ts` — neuer Test: `stroke="var(--g-ink-faint)"` ohne `audit:exempt` → 0 Funde

## Dependencies
- `app.css` definiert `--g-ink-faint` (#9c9a90) und `--g-ink-muted` (#5c5a52) — keine Änderung nötig
- Token-Bridge (#369) noch nicht gemergt, aber `--g-ink-muted` ist bereits in beiden Systemen vorhanden → kein Blocking

## Risiken
- **Gering:** Rein visueller Fix (CSS-Token-Tausch), keine Logik-Änderung
- **Gridlines:** Müssen als `audit:exempt` markiert werden, sonst schlägt der neue Test an; korrekt weil dekorativ
