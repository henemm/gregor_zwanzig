# Context: Issue #681 — Compare-Editor Slice 4 (Layout + Versand)

## Request Summary
Tab-Inhalte „Layout" und „Versand" auf CE_-Fidelity bringen: Live-Vorschau je Kanal (Email-Tabelle, Telegram-Monospace, SMS-Fließtext) und Telegram-Überschuss-Pill (`↳ Detail`, orange) wenn mehr als 8 Spalten gewählt. Versand-Tab erhält Versandzeit-Kacheln + Aktivierungs-Banner. Aktions-Button „Briefing aktivieren" im Header — disabled bis Versand besucht.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Haupt-Shell mit Tab-Routing; Header für „Briefing aktivieren"-Button (AC-4) |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Zu erweitern: ↳ Detail-Pill (AC-2) + CE_LayoutPreview ersetzen ChannelPreviewBlock (AC-1/3) |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | Komplett-Rework nach CE_VersandTab: Kacheln + ChannelRow + Aktivierungs-Banner (AC-4) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Bestehend: channel_layouts RMW — kein Anpassungsbedarf (AC-5) |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` | versandVisited-Logik für AC-4 |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | State: channelLayouts, sendEmail/Telegram/Sms, schedule, timeWindow, forecastHours |
| `claude-code-handoff/.../jsx/screen-compare-editor.jsx` | Design-Quelle: CE_LayoutTab (Z.364), CE_LayoutPreview (Z.440), CE_VersandTab (Z.520), CE_CHANNELS (Z.22) |
| `frontend/src/lib/types.ts` | ComparePreset, ChannelLayouts |

## CE_CHANNELS (aus JSX, Z.22)
```
{ id: "email",    label: "Email",    maxCols: Infinity, hint: "alles · Empfehlung + Tabelle + Detail" }
{ id: "telegram", label: "Telegram", maxCols: 8,        hint: "max 8 Spalten" }
{ id: "sms",      label: "SMS",      maxCols: 0,        hint: "flach · ≤ 140 Zeichen" }
```

## Bestehende Patterns
- **CE_Fidelity-Rework-Pattern** (Slices 1–3): existierende Step-Komponenten werden erweitert/ersetzt, keine neuen Routen
- **ChannelPreviewBlock** in Step4Layout → soll durch CE_LayoutPreview (echte Live-Vorschau) ersetzt werden
- **OutputLayoutEditor** in Step4Layout bleibt erhalten für Drag-Sort + Toggle — wird ergänzt um ↳ Detail-Pill
- **versandVisited** in CompareEditor.svelte steuert schon `done.has('versand')` — wird für AC-4 genutzt
- **buildComparePresetSavePayload**: channel_layouts via RMW bereits implementiert
- **CompareWizardState.save()**: POST/PUT mit vollem Payload inkl. display_config — kein Backend-Änderungsbedarf

## Was existiert vs. was fehlt

### Step4Layout (existiert → ergänzen)
| Feature | Status |
|---------|--------|
| Channel-Tabs (Email/Telegram/SMS) | ✓ vorhanden (ohne ∞/8/— Anzeige) |
| OutputLayoutEditor (Drag-Sort, Toggle, Buckets) | ✓ vorhanden |
| ↳ Detail-Pill für Telegram-Overflow (AC-2) | ✗ fehlt |
| ∞/8/— Max-Cols-Indikator im Channel-Tab | ✗ fehlt |
| Live-Vorschau CE_ (Email-Tabelle, Telegram-Monospace, SMS-Fließtext) | ✗ nur ChannelPreviewBlock-Chips |

### Step5Versand (existiert → Rework)
| Feature | Status |
|---------|--------|
| Kanal-Toggles (Email/Telegram/SMS) | ✓ vorhanden |
| Zeitfenster-Inputs | ✓ vorhanden |
| Schedule-Buttons | ✓ vorhanden |
| Versandzeit-Kacheln (Versand · Zeitfenster · Horizont) | ✗ fehlt |
| Kanal-Sub-Label (z.B. „Layout · 8 Spalten") | ✗ fehlt |
| Aktivierungs-Banner (dunkel/grün) | ✗ fehlt |

### CompareEditor Header
| Feature | Status |
|---------|--------|
| „Briefing aktivieren"-Button (Create-Modus) | ✗ fehlt (AC-4: disabled bis versandVisited) |

## Dependencies
- **Upstream**: OutputLayoutEditor (existiert), CompareWizardState, compareEditorSave, compareEditorLogic
- **Downstream**: Playwright E2E gegen Staging

## Risks & Considerations
- Step4Layout ist komplex (async mount, channelBuckets-State, $effect Sync). Pill-Logik muss NACH dem existing $effect-Sync eingefügt werden, ohne Timing-Bugs.
- CE_LayoutPreview nutzt Mock-Daten im JSX (MOCK_LOCATIONS/MOCK_COMPARE_ROWS). In Svelte: Placeholder-Daten aus dem Wizard-State ableiten (pickedIds → Ort-Namen) — oder statischen Preview-Platzhalter.
- AC-4 „Briefing aktivieren": in CompareEditor.svelte bereits Header; braucht den versandVisited-Flag + Aufruf von wiz.save().
- AC-5 Spalten-Reihenfolge pro Kanal: channelBuckets ist bereits per-Kanal getrennt — kein Änderungsbedarf, nur Verify.
- Drag-Sort-Persistenz ist laut Issue Out-of-Scope V1 (UI zeigt Reihenfolge, aber RMW-Sync schon aktiv).
