# Context: Issue #390 — Compare-Screen auf Atomic-Bibliothek migrieren

## Request Summary
Die Route `/compare` soll die drei Inline-Helper aus `screen-compare.jsx` durch kanonische Library-Bausteine ersetzen: `ChipBtn → Pill`, `CompareField → Field`, `FocusBadge → Pill tone="accent"`. Page-lokale Komposita (CompareMatrix, HourlyMatrix etc.) bleiben unangetastet.

## Aktueller Stand (was bereits OK ist)
- `LocationsRail.svelte` — verwendet bereits `Pill` für Gruppen- und Profil-Filter-Chips ✅
- Alle page-lokalen Komposita (`CompareMatrix`, `HourlyMatrix`, `RecommendationBanner` etc.) — bleiben unangetastet ✅

## Was migriert werden muss

### 1. Mobile Chip-Row (`+page.svelte`, Z. 299–306)
**Ist:** `<button class="shrink-0 rounded-full border border-border bg-muted px-3 py-1 text-xs">`  
**Soll:** `<Pill>` mit Toggle-Verhalten (ausgewählt = `tone="accent"` bzw. aktiver Stil, abwählen via onclick)  
**Import:** `Pill` aus `$lib/components/ui/pill/index.js` (bereits vorhanden für andere Zwecke)

### 2. PresetHeader — CompareField → Field
**Datei:** `frontend/src/lib/components/compare/PresetHeader.svelte`  
**Ist:** 5× raw `<div><label>…</label><input/><Select/></div>` ohne Field-Wrapper  
**Soll:** Jedes Label+Input/Select-Paar in `<Field label="…">…</Field>` einwickeln  
**Import:** `{ Field }` aus `$lib/components/molecules/index.js`

### 3. GroupSection — FocusBadge → Pill tone="accent"
**Datei:** `frontend/src/lib/components/compare/GroupSection.svelte`  
**Ist:** Location-Items zeigen nur Checkbox + Name + Wetter-Button (kein Profil-Badge)  
**Soll:** Kleines `<Pill tone="accent">` mit `profileSignature(loc.activity_profile).icon` pro Location, rechts neben dem Namen  
**Import:** `Pill` aus `$lib/components/ui/pill/index.js` (neu), `profileSignature` bereits importiert im Parent (muss in GroupSection ebenfalls rein)

## Soll-Screenshot Referenz
- `claude-code-handoff/screenshots/soll-flow3C-new-compare.png` — zeigt Vergleichsparameter-Card mit Field-Styling + Profil-Pill-Toggles
- `claude-code-handoff/screenshots/04-orts-vergleich.png` — Trip-Edit (nicht direkt relevant)
- `claude-code-handoff/screenshots/soll-flow5A-edit-compare.png` — Auto-Report Bearbeiten (Tabs)

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/compare/+page.svelte` | Hauptseite — Mobile-Chips migrieren (Z. 299–306) |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | CompareField → Field |
| `frontend/src/lib/components/compare/GroupSection.svelte` | FocusBadge → Pill tone="accent" |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Ziel-Atom — tone-basiert inkl. "accent" |
| `frontend/src/lib/components/molecules/Field.svelte` | Ziel-Molecule — Label+Hint-Wrapper |
| `frontend/src/lib/utils/profileSignature.ts` | Liefert icon + eyebrow pro ActivityProfile |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Bereits migriert — Muster für Pill-Nutzung |

## Existing Patterns
- Pill `tone="accent"` für aktiv/selektiert: siehe `LocationsRail.svelte` Z. 117
- Pill mit profileSignature-Dot: siehe `LocationsRail.svelte` Z. 134
- Field-Molecule als Label-Wrapper: siehe `PresetHeader` in trip-wizard-Step-Komponenten

## Dependencies
- Upstream: `Pill`, `Field`, `profileSignature` — alle vorhanden, kein Neubau
- Downstream: `CompareMatrix`, `HourlyMatrix` etc. — bleiben unverändert

## Risiken & Betrachtungen
- **Mobile-Chips**: `onclick={() => toggleLocation(loc.id)}` bleibt erhalten; nur Styling-Wrapper ändert sich
- **PresetHeader**: Rein visuell — keine Logik-Änderungen; `$bindable`-State bleibt
- **GroupSection**: FocusBadge ist additiv (bisher fehlend) — kein Breaking Change
- **Kontrast**: `contrast-audit.test.ts` muss nach Migration grün bleiben
- **LoC-Limit**: Scope klein (~30–50 LoC Netto-Änderung), unter 250 LoC-Limit
