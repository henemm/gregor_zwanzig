# Context: Issue #287 — Orts-Vergleich Polish

## Request Summary

Der Orts-Vergleich-Screen (Compare) braucht UI-Token-Korrekturen: Profile-Indikatoren auf Emoji-Basis ersetzen, Einstellungen-Card aufpolieren, Auto-Report-Cards redesignen und Sektion-Divider tokenisieren.

## Ist-Zustand (was bereits gut ist)

- `LocationsRail.svelte`: Verwendet bereits `<Checkbox>` und `<Pill>` — keine nativen Checkboxen mehr.
- `PresetHeader.svelte`: Verwendet bereits `<Select>`, `<Btn variant="accent">` (Vergleich starten), `<Btn variant="outline">` (Auto-Briefing speichern).
- `CompareSubscriptionsPanel.svelte`: Grundstruktur vorhanden, "Aktuellen Vergleich speichern" als `<Btn variant="outline">`.

## Was noch fehlt / geändert werden muss

### 1. LocationsRail — Profile-Emoji → ProfileChip (Dot)
- `sig.icon` (Unicode-Emoji) wird in Gruppen-Items und ungrouped-Items als `<span>` gerendert.
- Emoji variiert zwischen OS → ersetzen durch `[data-slot="dot"]` mit `--g-profile-*`-Token.
- Profil-Filter-Pills zeigen ebenfalls `{sig.icon} {sig.eyebrow}` → Icon durch Dot ersetzen.
- Border-Divider: `border-r` (kein Token) → `border-r border-[var(--g-ink-faint)]/40` oder inline-style.

### 2. PresetHeader — Button-Varianten
- "Preset laden": `variant="outline" disabled` → `variant="ghost" disabled` (bewusst visuell leiser).
- Datum-Input: kein Mono-Styling → `font-mono` o.ä. für konsistente Zahlendarstellung.

### 3. CompareSubscriptionsPanel — Auto-Report Cards Redesign
- Status-Dot: `bg-green-500` / `bg-gray-300` → `[data-slot="dot"]` mit Design-Token.
- Status-Badges ("ok"/"Fehler"): raw Tailwind-Klassen → `<Pill>` Komponente.
- Fehlendes "Bearbeiten"-Affordance (PencilIcon-Button) in Card-Header.
- Card-Hover-Effekt fehlt.

### 4. Section Divider
- `border-r` in LocationsRail ohne Token → `style="border-right: 1px solid color-mix(in srgb, var(--g-ink-faint) 40%, transparent);"` oder Tailwind-Equivalent.

## Vorhandene Komponenten (wiederverwendbar)

| Komponente | Pfad | Verwendung |
|-----------|------|-----------|
| `<Btn>` | `ui/btn/Btn.svelte` | variant: accent, outline, ghost, icon-sm |
| `<Pill>` | `ui/pill/Pill.svelte` | tone: success, danger, default |
| `<Select>` | `ui/select/Select.svelte` | Bereits eingebunden |
| `<Checkbox>` | `ui/checkbox/Checkbox.svelte` | Bereits eingebunden |
| `[data-slot="dot"]` | app.css:350 | data-size: xs/sm/md, data-tone: rain/sun/... |
| `profileSignature()` | `utils/profileSignature.ts` | Liefert accent (CSS-Var) + eyebrow |

## Design-Tokens (relevant)

```
--g-profile-wandern:          #3a7d44
--g-profile-wintersport:      #4a7fb5
--g-profile-summer-trekking:  #c45a2a
--g-profile-allgemein:        #6b675c
--g-ink-faint:                (app.css)
```

## Betroffene Dateien

| Datei | Änderungsumfang |
|-------|----------------|
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Mittel — Profile-Emoji → Dot, Divider |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | Klein — Btn-Variante, Datum-Mono |
| `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` | Mittel — Dots, Pills, Bearbeiten-Button |

## Abhängigkeiten

- Issue #277 (CSS Variable Fallbacks) — bereits erledigt, Tokens sind definiert.
- Kein Backend-Einfluss — rein presentational.

## Risiken

- `ProfileChip` ist neu zu erstellen als kleine Inline-Komponente oder direkt inline in LocationsRail.
- `[data-slot="dot"]` hat nur Wx-Tones in app.css; für Profile-Farben muss `style="background: var(--g-profile-...)"` inline genutzt werden.
