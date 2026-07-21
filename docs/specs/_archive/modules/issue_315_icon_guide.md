---
entity_id: issue_315_icon_guide
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, lucide, icons, design-system, documentation, conventions, issue-315]
---

# Issue #315 — Icon-Leitfaden: Lucide-Icon-Standard und Alias-Konvention

## Approval

- [ ] Approved

## Purpose

Das Frontend nutzt Lucide-Icons (`@lucide/svelte`) ohne dokumentierten Standard: Welches Icon steht für welche Aktion, und wie wird der Import-Alias benannt? Das führt dazu, dass dasselbe Icon in verschiedenen Dateien unter verschiedenen Alias-Namen importiert wird (z. B. `Pencil` vs. `PencilIcon`). Dieses Modul schafft zwei Liefergegenstände: (1) eine verbindliche `## Icons (Lucide)`-Sektion in `docs/reference/sveltekit_best_practices.md` als einzige schreibende Autorität für Icon-Auswahl und Alias-Namensgebung, und (2) die mechanische Bereinigung aller 7 betroffenen Svelte-Dateien, die von der neuen Konvention abweichen — ausschließlich Alias-Umbenennungen ohne Logik-Änderungen.

> **Schicht-Hinweis:** Alle Code-Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Die Dokumentations-Ergänzung liegt in `docs/reference/`. Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`) + Projekt-Dokumentation (`docs/reference/`)
- **Scope:** 1 Dokumentationsdatei (Ergänzung), 7 Svelte-Dateien (Alias-Umbenennungen)

### Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `docs/reference/sveltekit_best_practices.md` | Neue `## Icons (Lucide)`-Sektion ergänzen |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | `Pencil → PencilIcon`, `Check → CheckIcon`, `X → XIcon` |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte` | `Check → CheckIcon`, `X → XIcon` |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | `X → XIcon` |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | `Trash2 → Trash2Icon` |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | `Plus → PlusIcon` |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | `Upload → UploadIcon` |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | `Archive → ArchiveIcon` |
| `frontend/src/routes/_design/+page.svelte` | `Pencil → PencilIcon` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `@lucide/svelte` | npm-Paket (vorhanden) | Lucide-Icon-Bibliothek; tiefe Import-Pfade (`@lucide/svelte/icons/<name>`) sind bereits in Teilen der Codebase genutzt |
| `frontend/src/lib/components/ui/wicon` | Svelte-Komponente (vorhanden) | Wetter-Icon-System (`WIcon`) — ausdrücklich NICHT von diesem Leitfaden abgedeckt, aber referenziert in der Dokumentation als Abgrenzung |
| `docs/reference/sveltekit_best_practices.md` | Dokumentationsdatei (vorhanden) | Erhält die neue Icon-Sektion; enthält bereits Best-Practices zu Komponenten, Typen, State |
| AP-009 (no-emoji-Regel) | Design-System-Anti-Pattern | Kreuzreferenz in der Dokumentation: Emojis als Icons sind verboten, stattdessen Lucide verwenden |
| AP-005 (no-icon-soup) | Design-System-Anti-Pattern | Kreuzreferenz in der Dokumentation: nicht jede Zeile braucht ein Icon |

## Implementation Details

### Phase A — Dokumentation (keine LoC-Grenze, es ist Markdown)

In `docs/reference/sveltekit_best_practices.md` einen neuen Abschnitt `## Icons (Lucide)` ergänzen. Der Abschnitt enthält vier Teile:

**1. Import-Pfad-Regel**

```markdown
Immer tiefen Import-Pfad verwenden, niemals den Barrel-Import:

```svelte
<!-- Korrekt -->
import PencilIcon from '@lucide/svelte/icons/pencil';
import Trash2Icon from '@lucide/svelte/icons/trash-2';

<!-- Verboten — lädt die gesamte Bibliothek -->
import { Pencil, Trash2 } from '@lucide/svelte';
```
```

**2. Alias-Namens-Regel**

Kurze oder mehrdeutige Icon-Namen erhalten das Suffix `Icon`. Mehrsilbige, selbsterklärende Namen bleiben ohne Suffix:

| Kategorie | Beispiele mit Suffix | Beispiele ohne Suffix |
|-----------|---------------------|----------------------|
| Kurz/mehrdeutig | `PencilIcon`, `Trash2Icon`, `XIcon`, `CheckIcon`, `PlusIcon`, `UploadIcon`, `ArchiveIcon`, `BellIcon`, `SearchIcon` | — |
| Mehrsilbig/selbsterklärend | — | `GripVertical`, `ChevronDown`, `ChevronUp`, `LayoutDashboard`, `GitCompare`, `LogOut`, `EllipsisVertical`, `CloudSun`, `MapPin`, `Loader2` |

Faustformel: Ein Name, der als JavaScript-Bezeichner allein stehend wie eine Variable aussieht (`X`, `Check`, `Plus`), bekommt `Icon` als Suffix. Namen, die eindeutig ein visuelles Konzept beschreiben (`ChevronDown`, `GripVertical`), bleiben wie sie sind.

**3. Genehmigte Aktions-Icons**

| Aktion | Lucide-Icon | Import-Alias |
|--------|-------------|--------------|
| Bearbeiten | `pencil` | `PencilIcon` |
| Löschen | `trash-2` | `Trash2Icon` |
| Schließen / Dialog-X | `x` | `XIcon` |
| Entfernen aus Liste | `x` | `XIcon` |
| Hinzufügen / Neu | `plus` | `PlusIcon` |
| Bestätigen / Speichern | `check` | `CheckIcon` |
| Suche | `search` | `SearchIcon` |
| Drag-Handle | `grip-vertical` | `GripVertical` |
| Kebab-Menü | `ellipsis-vertical` | `EllipsisVertical` |
| Laden / Spinner | `loader-2` | `Loader2` |
| Hochladen / Import | `upload` | `UploadIcon` |
| Archivieren | `archive` | `ArchiveIcon` |
| Alarm / Benachrichtigung | `bell` | `BellIcon` |

**4. Wetter-Icons — Abgrenzung**

```markdown
**Wichtig:** Für Wetter-Icons (Sonne, Regen, Schnee, Gewitter usw.) ausschließlich
`<WIcon kind="..." />` aus `$lib/components/ui/wicon` verwenden. Lucide-Wetter-Icons
(`Cloud`, `Sun`, `CloudRain`, …) dürfen in der App-UI NICHT direkt importiert werden.
WIcon ist in `docs/specs/modules/issue_322_wicon_komponente.md` spezifiziert.

Kreuzreferenz: AP-009 (Emojis als Icons verboten), AP-005 (kein Icon-Überfluss).
```

### Phase B — Alias-Bereinigung (~22 LoC)

Reine mechanische Umbenennung in 7 Dateien. Import-Pfade bleiben unverändert; nur der lokale Alias-Name wird angepasst, und alle Nutzungsstellen derselben Datei werden synchron mitgeändert.

| Datei | Vorher | Nachher |
|-------|--------|---------|
| `WaypointCard.svelte` | `import Pencil from '…/pencil'` | `import PencilIcon from '…/pencil'` |
| `WaypointCard.svelte` | `import Check from '…/check'` | `import CheckIcon from '…/check'` |
| `WaypointCard.svelte` | `import X from '…/x'` | `import XIcon from '…/x'` |
| `WaypointRow.svelte` | `import Check from '…/check'` | `import CheckIcon from '…/check'` |
| `WaypointRow.svelte` | `import X from '…/x'` | `import XIcon from '…/x'` |
| `TopAppBar.svelte` | `import X from '…/x'` | `import XIcon from '…/x'` |
| `StageRow.svelte` | `import Trash2 from '…/trash-2'` | `import Trash2Icon from '…/trash-2'` |
| `Step2Stages.svelte` | `import Plus from '…/plus'` | `import PlusIcon from '…/plus'` |
| `Step1Profile.svelte` | `import Upload from '…/upload'` | `import UploadIcon from '…/upload'` |
| `BottomNav.svelte` | `import Archive from '…/archive'` | `import ArchiveIcon from '…/archive'` |
| `_design/+page.svelte` | `import Pencil from '…/pencil'` | `import PencilIcon from '…/pencil'` |

In jeder Datei: nach Import-Umbenennung alle `<Pencil`, `<Check`, `<X`, `<Trash2`, `<Plus`, `<Upload`, `<Archive` im Template-Teil ebenfalls umbenennen (schließende Tags eingeschlossen). Die Komponenten-Verwendung selbst (Props, Events) bleibt unverändert.

### Umsetzungsreihenfolge

1. `docs/reference/sveltekit_best_practices.md` — Icon-Sektion (keine Code-Abhängigkeiten)
2. Alias-Umbenennungen in allen 7 Svelte-Dateien (reihenfolgeunabhängig, da isolierte Dateien)

### LoC-Budget

| Scope | Δ LoC | Zählt |
|-------|--------|-------|
| `docs/reference/sveltekit_best_practices.md` | ~+60 | nein (Markdown) |
| 7 Svelte-Dateien (Alias-Renames) | ~+0 netto (1:1-Ersatz) | ja |
| **Gesamt Code-Delta** | **~0 netto** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Codebase mit inkonsistenten Lucide-Alias-Namen in 7 Svelte-Dateien
- **Output (Dokumentation):** `docs/reference/sveltekit_best_practices.md` enthält eine vollständige `## Icons (Lucide)`-Sektion mit Import-Regel, Alias-Konvention, Aktions-Icon-Tabelle und WIcon-Abgrenzung
- **Output (Code):** Alle kurzen/mehrdeutigen Lucide-Imports in den 7 Dateien tragen das `Icon`-Suffix; kein `<Pencil`, `<Check`, `<X`, `<Trash2`, `<Plus`, `<Upload`, `<Archive` mehr ohne Suffix
- **Side effects:** Keine Verhaltensänderung zur Laufzeit — Lucide-Komponenten sind Wrapper um SVG; Alias-Umbenennung ändert nur den Bezeichner im lokalen Scope, nicht die gerenderte Ausgabe

## Acceptance Criteria

- **AC-1:** Given `docs/reference/sveltekit_best_practices.md` / When ein Entwickler nach dem Icon für "Bearbeiten", "Löschen" oder "Hinzufügen" sucht / Then findet er in der `## Icons (Lucide)`-Sektion den genehmigten Lucide-Namen und den korrekten Import-Alias in unter 10 Sekunden — ohne die Codebase durchsuchen zu müssen.
  - Test: (populated after /tdd-red)

- **AC-2:** Given zwei verschiedene Seiten mit einem "Bearbeiten"-Button (z. B. WaypointCard und _design) / When die Import-Zeilen der jeweiligen Svelte-Dateien verglichen werden / Then verwenden beide `PencilIcon` als Alias — kein `Pencil` ohne Suffix mehr vorhanden.
  - Test: `grep -rn "import Pencil " frontend/src/` → 0 Treffer

- **AC-3:** Given alle Svelte-Dateien im `frontend/src/`-Verzeichnis / When ein Grep auf bare kurze Icon-Aliases (`import X `, `import Check `, `import Trash2 `, `import Plus `, `import Upload `, `import Archive `, `import Pencil `) ausgeführt wird / Then liefert jede dieser Suchen 0 Treffer — alle kurzen/mehrdeutigen Lucide-Imports tragen das `Icon`-Suffix.
  - Test: `grep -rn "import \(X\|Check\|Trash2\|Plus\|Upload\|Archive\|Pencil\) " frontend/src/` → 0 Treffer

- **AC-4:** Given die `## Icons (Lucide)`-Sektion in `docs/reference/sveltekit_best_practices.md` / When nach dem Wort "WIcon" oder "Wetter" gesucht wird / Then enthält die Sektion einen expliziten Hinweis, dass Wetter-Icons ausschließlich über `<WIcon>` aus `$lib/components/ui/wicon` einzubinden sind und Lucide-Wetter-Icons (Cloud, Sun, CloudRain …) direkt verboten sind.
  - Test: `grep -n "WIcon" docs/reference/sveltekit_best_practices.md` → mindestens 1 Treffer

## Known Limitations

- Die Bereinigung erfasst ausschließlich die 7 in der Analyse identifizierten Dateien. Zukünftige Entwickler können die Konvention verletzen — die einzige Durchsetzung ist der Leitfaden selbst. Ein automatisierter Lint-Check (`eslint-plugin-import` o. ä.) ist bewusst out of scope.
- Mehrsilbige, unambige Icons ohne `Icon`-Suffix (z. B. `GripVertical`, `ChevronDown`) sind eine Ermessensentscheidung. Die Grenze zwischen "mehrdeutig" und "selbsterklärend" ist in der Dokumentation durch Beispiele definiert, nicht durch eine mechanisch prüfbare Regel.
- `AddReportCard.svelte` und `EditRouteSection.svelte` sind bereits konform (`PlusIcon` bzw. `UploadIcon`) — diese Dateien brauchen keine Änderung.

## Out of Scope

- Keine Änderung an der WIcon-Komponente oder ihrem Dokumentation (`issue_322_wicon_komponente.md`)
- Kein ESLint-Plugin oder CI-Check zur Durchsetzung der Konvention
- Keine Überprüfung von Test-Dateien (`*.test.ts`, `*.spec.ts`) auf Icon-Importe
- Kein Barrel-Import-Refactoring bei Icons, die bereits korrekt benannt sind

## Changelog

- 2026-05-26: Initial spec created (Issue #315 — Icon-Leitfaden)
