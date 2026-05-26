# Context: Issue #315 — Icon-Leitfaden (Lucide)

## Request Summary

Es gibt keine verbindliche Zuordnung „welches Lucide-Icon für welche Aktion". Das führt zu inkonsistenter Verwendung in der Codebase (z. B. `Pencil` vs. `PenLine` für „Bearbeiten"). Ziel: Entscheidung treffen, in `sveltekit_best_practices.md` dokumentieren, dann bestehende Inkonsistenzen bereinigen.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `docs/reference/sveltekit_best_practices.md` | Zieldokument für den neuen Icon-Leitfaden-Abschnitt |
| `frontend/src/routes/trips/+page.svelte` | Pencil, Trash2, Search, EllipsisVertical |
| `frontend/src/routes/locations/+page.svelte` | Pencil, Trash2, Search |
| `frontend/src/routes/subscriptions/+page.svelte` | Pencil, Trash2, Search |
| `frontend/src/routes/account/+page.svelte` | Pencil, Trash2, X (Check) |
| `frontend/src/lib/components/ui/dialog/dialog-content.svelte` | X (Dialog schließen) |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Pencil, X, Check |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte` | X (entfernen), Check |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | Trash2, GripVertical |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Plus |
| `frontend/src/lib/components/compare/AddReportCard.svelte` | PlusIcon |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | X (Menü schließen) |

## Ist-Bestand der verwendeten Icons

### Eindeutig (konsistent)
| Aktion | Icon | Dateien |
|--------|------|---------|
| Bearbeiten | `Pencil` | trips, locations, subscriptions, account, WaypointCard, _design |
| Löschen | `Trash2` | trips, locations, subscriptions, StageRow, account |
| Suche | `Search` | trips, locations, subscriptions |
| Hinzufügen | `Plus` | Step2Stages, AddReportCard |
| Drag & Drop | `GripVertical` | StageRow |
| Kebab-Menü (vertikal) | `EllipsisVertical` | trips/+page |
| Speichern / Bestätigen | `Check` | WaypointCard, WaypointRow, account |

### Inkonsistent (mehrere Icons für gleiche Aktion)
| Aktion | Icons | Kontext |
|--------|-------|---------|
| Dialog/Panel schließen | `X` (dialog-content, TopAppBar) + `X` (WaypointRow: „entfernen") | Funktional verschieden! X = schließen, X = entfernen |
| Löschen vs. Entfernen | `Trash2` (persistentes Löschen) vs. `X` (aus Liste entfernen) | Unterschied ist fachlich korrekt — braucht Dokumentation |

### Nicht vorhanden (laut Issue, aber nicht in Codebase gefunden)
- `PenLine`, `Edit` (für Bearbeiten) — war anscheinend nie im Code
- `XCircle` — nicht in Codebase
- `PlusCircle` — nicht in Codebase
- `ChevronUp/Down` für Verschieben — nicht in Codebase (nur ChevronDown/Up für Expand/Collapse)
- `ArrowUp/Down` — nicht in Codebase
- `MoreHorizontal` — nicht in Codebase
- `AlertTriangle`, `AlertCircle` — nicht in Codebase
- `ExternalLink` — nicht in Codebase
- `ArrowLeft`, `ChevronLeft` für Navigation zurück — nicht in Codebase

## Bestehende Muster

- Import-Stil: `import PencilIcon from '@lucide/svelte/icons/pencil'` (Tree-Shaking, kein Wildcard)
- Alias-Inkonsistenz: Manche importieren `Pencil`, andere `PencilIcon` — kein Standard
- `sveltekit_best_practices.md` hat noch keinen Icon-Abschnitt

## Risiken & Überlegungen

- Keine inhaltliche Inkonsistenz gefunden (Pencil = Bearbeiten überall konsistent); das Issue beschreibt Befürchtungen, die in der Codebase nicht so schlimm sind wie erwartet
- `X` hat zwei semantisch verschiedene Rollen: „Dialog schließen" und „Element entfernen" — das ist korrekt, braucht aber explizite Dokumentation
- Import-Alias-Inkonsistenz (`Pencil` vs. `PencilIcon`) ist das eigentliche kosmetische Problem
- Cleanup-Scope ist gering (Icons sind schon fast konsistent)

## Scope

1. Abschnitt in `sveltekit_best_practices.md` schreiben: verbindliche Icon-Tabelle + Import-Konvention
2. Import-Aliase vereinheitlichen (kein `Icon`-Suffix)
3. `X` vs. `Trash2` Semantik klarstellen
