# Context: Issue #581 — Trip-Detail 1:1 nach JSX

## Request Summary
Beide Trip-Detail-Screens (Ansicht + Bearbeiten) sollen 1:1 mit den JSX-Designvorlagen
übereinstimmen. Aktuell weichen Layout, Übersichts-Tab-Inhalt und Statistik-Karte
deutlich von den Soll-Vorgaben ab.

## JSX-Quelldateien (bindend)
| Datei | Screen |
|-------|--------|
| `claude-code-handoff/current/jsx/screen-trip-detail.jsx` | Ansicht (6 Tabs) |
| `claude-code-handoff/current/jsx/screen-trip-edit-tabs.jsx` | Bearbeiten (5 Tabs) |
| `claude-code-handoff/current/jsx/atoms.jsx` | Atom-Referenz |
| `claude-code-handoff/current/jsx/molecules.jsx` | Molecule-Referenz |
| `claude-code-handoff/current/jsx/tokens.css` | Token-Referenz |

## SOLL-Screenshots
`claude-code-handoff/current/soll/F-trip-detail-*.png` (5 Bilder — zeigen Edit-View)
- `F-trip-detail-overview.png`: Edit-View, Etappen-Tab aktiv, horizontaler EtappenStrip
- `F-trip-detail-reports-collapsed.png`: Reports-Tab (Morgen/Abend/Kanäle-Form)
- `F-trip-detail-reports-expanded.png`: Alarmregeln-Liste
- `F-trip-detail-wetter.png`: Alarmregeln-Formular (Add/Edit-State)
- `F-trip-detail-editor-top.png`: Voller Etappen-Editor (viele Stages)

## Related Files

### View-Screen (screen-trip-detail.jsx)
| Datei | Relevanz |
|-------|---------|
| `frontend/src/routes/trips/[id]/+page.svelte` | Main-View-Page — Container, TripHeader + TripTabs |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Breadcrumb + H1 + Status + Hero |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Navigation (6 Tabs, Segmented-basiert) |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Übersicht-Tab: aktuell 4 DetailCards |
| `frontend/src/lib/components/trip-detail/FullProfile.svelte` | SVG-Höhenprofil (existiert, korrekt) |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | StatusBadge-Atom |

### Edit-Screen (screen-trip-edit-tabs.jsx)
| Datei | Relevanz |
|-------|---------|
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Edit-Page (delegiert an TripEditView) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Hauptkomponente Edit-View |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Horizontaler Stage-Strip (vorhanden, noch nicht in Edit-View) |

### Shared/Existierende Atoms & Molecules
| Datei | Zweck |
|-------|-------|
| `frontend/src/lib/components/atoms/TopoBg.svelte` | Topografischer Hintergrund |
| `frontend/src/lib/components/atoms/Card.svelte` | Karten-Container |
| `frontend/src/lib/components/atoms/Pill.svelte` | Status-Pill |
| `frontend/src/lib/components/atoms/Switch.svelte` | Toggle-Switch |
| `frontend/src/lib/components/atoms/SectionH.svelte` | Abschnitts-Header mit Eyebrow |
| `frontend/src/lib/components/atoms/Btn.svelte` | Buttons |
| `frontend/src/lib/components/atoms/Eyebrow.svelte` | Eyebrow-Label |
| `frontend/src/lib/components/molecules/AlertRow.svelte` | Alert-Zeile mit Icon/Dot |

## Ist-Zustand vs. Soll (Hauptabweichungen)

### View-Screen (`+page.svelte`)
| Bereich | Ist | Soll (JSX) |
|---------|-----|------------|
| Layout-Wrapper | `container mx-auto max-w-5xl p-4` (eingeschränkt) | Full-Width, padding: 40px sides, max-width: 1480px |
| Hintergrund | keiner | `TopoBg opacity={0.14}` |
| Breadcrumb-Bar | Im TripHeader eingebettet | Separate Bar: `padding: 16px 40px, borderBottom, space-between` |
| Breadcrumb-Inhalt | "MEINE TRIPS › SHORTCODE" | "Trips / shortName" mit Aktions-Buttons rechts |
| Aktions-Buttons | Danger-Zone unten (Pausieren/Archivieren) | Top-Bar: "Pausieren", "Archivieren", "Test-Briefing senden" |
| Hero H1 | `font-size: var(--g-text-3xl)` | `fontSize: 38, letterSpacing: -0.02em` |
| Übersichts-Tab | 4 DetailCards (2×2 Grid, Issue #487) | FullProfile + StageRows + MetricsPreview (links) + 3 Cards rechts |
| Zeitplan-Tab | BriefingsTab (umfangreiche Form) | 4 HubScheduleCards mit Switch |

### Edit-Screen (`TripEditView.svelte`)
| Bereich | Ist | Soll (JSX) |
|---------|-----|------------|
| Layout-Wrapper | `max-w-5xl mx-auto p-4` | Full-Width, padding: 40px sides |
| Breadcrumb | "MEINE TRIPS · TRIP BEARBEITEN" | "Trips / shortName / Bearbeiten" |
| H1 | Nur trip.name | shortcode + name (mit Monospace shortcode) |
| Stats-Karte | Flache Text-Zeile | GESAMT/ZEITRAUM zwei-spaltige Header-Struktur |
| Tab-Badges | Inline-Text "Etappen & Wegpunkte 13" | Separate Pill-Badges |
| Etappen-Tab-Inhalt | `EditStagesPanelNew` (vertikal) | `EtappenStrip` (horizontal, wie in SOLL-Screenshot) |

## Neue Komponenten (müssen erstellt werden)

| Komponente | Ort | Beschreibung |
|------------|-----|-------------|
| `HubOverview.svelte` | trip-detail/ | Ersetzt TripOverview: FullProfile + StageRow-Liste + MetricsPreview (links) + 3 Cards (rechts) |
| `TripStageRow.svelte` | trip-detail/ | Klickbare Etappen-Zeile: Code + Titel + Zusammenfassung + Risiko-Pill (für View, nicht Edit) |
| `MetricsPreview.svelte` | trip-detail/ | Chip-Liste aktiver Metriken (read-only, verlinkt in Metriken-Tab) |
| `ReportLine.svelte` | trip-detail/ | Dot + Label + Zeit + Kanal-Dots (für HubOverview-rechte-Karte) |
| `ChannelDot.svelte` | trip-detail/ | Kleines Kanal-Icon (✉/▲/·) in einem 18×18px Square |
| `HubSchedule.svelte` | trip-detail/ | 4 HubScheduleCards mit Switch (Briefing-Zeitplan-Tab) |

## Existing Patterns
- **TopoBg**: `<TopoBg opacity={0.14}/>` als absolut positionierter Hintergrund
- **Full-Width-Layout**: Siehe `screen-compare-wizard.jsx` oder andere Screens
- **Tab underline**: TripTabs überschreibt bereits Segmented-Styles für Unterstreichungs-Tabs
- **EtappenStrip**: Wird in `EditStagesPanelNew.svelte` bereits verwendet (korrekte API)
- **StageCard**: In `waypoints/StageCard.svelte`, wird von EtappenStrip verwendet

## Dependencies
- **Upstream**: FullProfile, EtappenStrip, AlertRow, Card, Pill, Switch, SectionH, Btn, Eyebrow, TopoBg
- **Downstream**: Tests in `TripOverview.issue487.test.ts`, `TripOverview.issue504.test.ts`, `issue_516_ia_navigation.test.ts`

## Existing Specs
- `docs/specs/modules/issue_302_trip_detail_page.md` — Basis-Spec Trip-Detail (Tabs, Danger-Zone)
- `docs/specs/modules/issue_487_trip_detail_overview_cards.md` — Bisheriges 4-Karten-Layout (wird ersetzt)
- `docs/specs/modules/issue_389_trip_detail_atomic.md` — Atomic-Migration Spec

## Risks & Considerations
- TripOverview.issue487.test.ts prüft das 4-Karten-Layout → Tests müssen aktualisiert werden
- TripOverview.issue504.test.ts prüft Alerts-Karte → ebenfalls anpassen
- issue_516_ia_navigation.test.ts prüft Tab-Navigation → sollte kompatibel bleiben (gleiche Tab-IDs)
- BriefingsTab (funktionale Implementierung) bleibt erhalten — HubSchedule ist ein anderes Layout, nicht die Form
- Die HubSchedule-Karten sind READ-ONLY-Darstellung (wie im JSX: `const [enabled, setEnabled] = React.useState(!!on)`) aber ohne Backend-Anbindung für den Toggle im Übersichts-Tab
