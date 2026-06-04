# Context: Issue #578 — Molecules + Organisms 1:1 nach molecules.jsx / organisms.jsx

## Request Summary
Alle Moleküle, Organismen und die Sidebar pixelgenau aus der bindenden JSX-Vorlage (`molecules.jsx`, `organisms.jsx`, `sidebar.jsx`) neu implementieren bzw. bestehende Divergenzen korrigieren. Dies ist Phase 1 [C] des Epic #575 und Voraussetzung für die Screen-Issues #579–#588.

## Bindende Quellen
| Datei | Inhalt |
|-------|--------|
| `claude-code-handoff/current/jsx/molecules.jsx` (1574 Z.) | Alle Molecule-Komponenten inkl. Compare-Domain |
| `claude-code-handoff/current/jsx/organisms.jsx` (1341 Z.) | WeatherMetricsTab, PresetRail, MetricOffShelf, ContextBar |
| `claude-code-handoff/current/jsx/sidebar.jsx` (27 Z.) | Thin Wrapper um BrandSidebar |

## Bestandsaufnahme: Molecules

### Vollständig implementiert ✅ (kein Handlungsbedarf)
| Komponente | Pfad |
|-----------|------|
| Field | `molecules/Field.svelte` |
| DetailRow | `molecules/DetailRow.svelte` |
| StagePill | `molecules/StagePill.svelte` |
| ChannelRow | `molecules/ChannelRow.svelte` |
| ChannelChip + channelGlyph | `molecules/ChannelChip.svelte` |
| BriefingScheduleRow | `molecules/BriefingScheduleRow.svelte` |
| ThresholdRow | `molecules/ThresholdRow.svelte` |
| Stat | `molecules/Stat.svelte` |
| AlertRow | `molecules/AlertRow.svelte` |
| CompareStatusPill | `compare/CompareStatusPill.svelte` |
| CompareTile | `compare/CompareTile.svelte` |
| CompareKebab | `compare/CompareKebab.svelte` |
| CompareLocationRow | `molecules/CompareLocationRow.svelte` |
| CompareIdealRow | `molecules/CompareIdealRow.svelte` |
| CompareLayoutRow | `molecules/CompareLayoutRow.svelte` |
| StageDateField | `edit/StageDateField.svelte` (andere Signatur, aber funktional) |

### Divergenzen — müssen korrigiert werden ⚠️
| Komponente | Divergenz (IST → SOLL) |
|-----------|----------------------|
| **BriefingTimelineRow** | "geplant"-Farbe: `--g-ink-3` → `--g-ink-4` (laut JSX) |
| **QuickAction** | JSX: `<button onClick>` + `boxShadow` + `--g-rule` Border + sub-Text MONO/UPPERCASE; Svelte: `<a href>`, kein Shadow, `--g-rule-soft`, sub-Text plain. SVG-Icons OK (via #577). |
| **SetupResumeCard** | JSX: `borderLeft: accent ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)"` + `boxShadow` + Schritte als Chips-Reihe + Footer-Leiste mit "Weiter bei:"; Svelte: `--g-rule-soft` Border, kein Shadow, Schritte als Liste |
| **CompareStatusRow** | Empfänger-Pille-Platzierung inkonsistent (QA V6) — prüfen gegen JSX |

### Fehlen komplett — müssen neu erstellt werden ❌
| Komponente | Verwendung |
|-----------|-----------|
| **StageCascadeNotice** | Waypoint-Editor — Folge-Etappen-Verschiebe-Hinweis |
| **HorizonChips** | In WeatherMetricsTab (JSX definiert, Svelte-Version in ui/horizon-chip/ hat andere API) |
| **ScoreToggle** | In MetricEditorRow |
| **CompareChannelSwitch** | Compare-Detail/Hub — Kanal-Umschalter |
| **CompareBriefingPreview** | Compare-Hub Tab Vorschau |
| **CompareChatBubble** | Signal/Telegram-Bubble |
| **CompareSmsPreview** | SMS-Flat-Format |
| **ComparePreviewMissing** | Fallback-Platzhalter in Preview |

## Bestandsaufnahme: Organisms

### Implementiert (über trip-detail/) ✅
| Organism | Export-Pfad |
|---------|-----------|
| WeatherMetricsTab | `organisms/index.ts` → `trip-detail/WeatherMetricsTab.svelte` |
| MetricGroup | `organisms/index.ts` → `trip-detail/MetricGroup.svelte` |
| ChannelPreviewBlock | `organisms/index.ts` → `trip-detail/ChannelPreviewBlock.svelte` |
| ChannelPreviewCard | `organisms/index.ts` → `trip-detail/ChannelPreviewCard.svelte` |
| MetricCheckbox | `organisms/index.ts` → `trip-detail/MetricCheckbox.svelte` |
| TripHeader, TripWizardShell, AlertRulesEditor, OutputLayoutEditor | `organisms/index.ts` |

### Fehlen komplett — müssen neu erstellt werden ❌
| Organism | Quelle | Verwendung |
|---------|--------|-----------|
| **PresetRail** | `organisms.jsx` | Preset-Liste im Metrics-Editor |
| **MetricOffShelf** | `organisms.jsx` | „Nicht im Briefing"-Aufklappsection |
| **MetricsEditorContextBar** | `organisms.jsx` | Header im Metrics-Editor |
| **HomeHeroTrip** | `screen-home.jsx` | Cockpit-Hero Trip-Modus |
| **HomeHeroCompare** | `screen-home.jsx` | Cockpit-Hero Compare-Modus |
| **OutboxCard** | `screen-home.jsx` (als HomeOutboxCard) | „Was geht raus"-Sektion |
| **AlertsCard** | `screen-home.jsx` (inline) | Alerts-letzte-24h-Sektion |

## SOLL-Screenshots (Verifikation nach Implementierung)
- `claude-code-handoff/current/soll/D-home-trip.png` — HomeHeroTrip, OutboxCard, AlertsCard, QuickAction
- `claude-code-handoff/current/soll/D-home-compare.png` — HomeHeroCompare, CompareStatusRow
- `claude-code-handoff/current/soll/F-trip-detail-wetter.png` — WeatherMetricsTab (PresetRail, MetricOffShelf, ContextBar)

## Abhängigkeiten
- **Upstream:** Atoms (#577 ✅), Tokens (#576 ✅)
- **Downstream:** Alle Screen-Issues #579–#588 warten auf #578

## Dokumentierte FAIL-Kriterien (aus D-home-VISUAL-QA.md)
- V4: QuickAction muss SVG-Icons haben (behoben in #577)
- V2: HomeHeroTrip: Pills → Titel → Subtitel → Balken+Label → Footer-Leiste
- V3: Kanäle im Footer, nicht orphaned im Body
- V5: „Außerdem beobachtet" braucht Card-Wrapper + Header
- V6: CompareStatusRow konsistente Empfänger-Pille-Platzierung

## Risiken
1. **Scope**: 8 fehlende Molecules + 7 fehlende Organisms = große Implementierung
2. **QuickAction `<button>` vs `<a href>`**: JSX verwendet onClick/button; Svelte verwendet href. Da Navigation über href sicherer und semantisch korrekter ist, bleibt `<a href>` — aber Shadow + Border-Token müssen auf JSX angepasst werden.
3. **HomeHeroTrip/Compare sind in screen-home.jsx, nicht in organisms.jsx**: Trotzdem als Svelte-Organisms in `organisms/` erstellen, damit #579 sie importieren kann.
