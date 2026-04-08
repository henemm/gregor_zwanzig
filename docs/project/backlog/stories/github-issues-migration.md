# Plan: Backlog-Migration zu GitHub Issues

**Erstellt:** 2026-04-08
**Status:** Draft

## Ziel

Die gesamte Projekt-Planung von Markdown-Dateien auf GitHub Issues umstellen, damit:
- Backlog in der Standard-GitHub-UI sichtbar und filterbar ist
- Issues direkt in PRs verlinkt und automatisch geschlossen werden koennen
- Keine Parallel-Pflege von Markdown + Code noetig ist
- Fortschritt ueber GitHub Project Boards trackbar wird

## Ist-Zustand

### Markdown-Dateien die heute das Backlog bilden

| Datei | Inhalt | Issues daraus |
|---|---|---|
| `backlog/ACTIVE-roadmap.md` | Feature-Tabelle (55 Zeilen), Sprint-Planung, Known Bugs | ~12 offene Features + 7 Migration-Tasks |
| `backlog/epics.md` | 9 Epics mit Stories | Werden zu GitHub Milestones |
| `project/known_issues.md` | 1 offener Bug (BUG-TZ-01) | 1 Bug-Issue |
| `project/strategic-directions.md` | Feature-Priorisierung, Entscheidungen | Kein Issue — bleibt als Doku |
| `backlog/stories/*.md` | 4 Story-Dokumente | Referenz in Issue-Body |
| `backlog/features/*.md` | 2 Feature-Briefs | Referenz in Issue-Body |
| `project/backlog.md` | Alte PO-Ansicht | Obsolet nach Migration |

### Was NICHT migriert wird

- **Done-Features** — 43 erledigte Features bleiben nur im Markdown-Archiv
- **Obsolete Features** (MET Norway, MOSMIX) — werden nicht als Issues angelegt
- **Specs** (`docs/specs/modules/*.md`, 58 Dateien) — bleiben im Repo, werden aus Issues verlinkt

## Ziel-Struktur auf GitHub

### Labels

| Label | Farbe | Zweck |
|---|---|---|
| `priority: high` | rot | HIGH-Priority Features |
| `priority: medium` | gelb | MEDIUM-Priority Features |
| `priority: low` | gruen | LOW-Priority Features |
| `type: feature` | blau | Neues Feature |
| `type: bug` | rot | Bug |
| `type: migration` | lila | Tech-Stack-Migration |
| `category: core` | grau | Core/Infrastruktur |
| `category: provider` | grau | Weather Provider |
| `category: risk-engine` | grau | Risiko-Bewertung |
| `category: formatter` | grau | Report-Generierung |
| `category: channel` | grau | Versand (Email/SMS/Signal) |
| `category: webui` | grau | Frontend |
| `category: ops` | grau | Operations |

### Milestones (aus Epics)

| Milestone | Quelle | Offene Issues |
|---|---|---|
| Low-Connectivity Delivery | Epic: Low-Connectivity Delivery | F1, F9 |
| Enhanced Trip Reports | Epic: Enhanced Trip Reports | F4, F5 |
| Asynchrone Trip-Steuerung | Epic: Asynchrone Trip-Steuerung | F6 |
| Advanced Risk & Terrain | Epic: Advanced Risk & Terrain | F10 |
| Tech Stack Migration | Epic: Tech Stack Migration | M1-M7 |

### Issues (aus offenen Features)

| # | Titel | Labels | Milestone | Quelle |
|---|---|---|---|---|
| 1 | SMS-Kanal (F1) | `type: feature`, `priority: high`, `category: channel` | Low-Connectivity Delivery | Roadmap |
| 2 | Trip-Briefing Kompakt-Tabelle (F4) | `type: feature`, `priority: medium`, `category: formatter` | Enhanced Trip Reports | Roadmap |
| 3 | Biwak-/Zelt-Modus (F5) | `type: feature`, `priority: medium`, `category: core` | Enhanced Trip Reports | Roadmap |
| 4 | Trip-Umplanung per Kommando (F6) | `type: feature`, `priority: medium`, `category: core` | Asynchrone Trip-Steuerung | Roadmap |
| 5 | Satellite Messenger / Garmin inReach (F9) | `type: feature`, `priority: low`, `category: channel` | Low-Connectivity Delivery | Roadmap |
| 6 | Lawinen-Integration SLF/EAWS (F10) | `type: feature`, `priority: low`, `category: provider` | Advanced Risk & Terrain | Roadmap |
| 7 | Versandweg-Auswahl Channel-Switch (F12) | `type: feature`, `priority: high`, `category: webui` | — | Roadmap |
| 8 | Multi-User mit Login (F13) | `type: feature`, `priority: high`, `category: core` | Tech Stack Migration | Roadmap |
| 9 | Subscription Metriken-Auswahl Model+UI (F14a) | `type: feature`, `priority: high`, `category: webui` | — | Roadmap |
| 10 | Subscription Metriken-Auswahl Renderer (F14b) | `type: feature`, `priority: high`, `category: formatter` | — | Roadmap |
| 11 | Logging/Rotation (OPS-02) | `type: feature`, `priority: low`, `category: ops` | — | Roadmap |
| 12 | Timezone Mismatch BUG-TZ-01 | `type: bug`, `priority: high`, `category: formatter` | — | known_issues.md |
| 13 | Migration: Go-Backend Setup (M1) | `type: migration`, `priority: high`, `category: core` | Tech Stack Migration | Roadmap |
| 14 | Migration: Provider portieren (M2) | `type: migration`, `priority: high`, `category: provider` | Tech Stack Migration | Roadmap |
| 15 | Migration: Risk Engine portieren (M3) | `type: migration`, `priority: high`, `category: risk-engine` | Tech Stack Migration | Roadmap |
| 16 | Migration: Formatter portieren (M4) | `type: migration`, `priority: high`, `category: formatter` | Tech Stack Migration | Roadmap |
| 17 | Migration: Frontend Setup (M5) | `type: migration`, `priority: high`, `category: webui` | Tech Stack Migration | Roadmap |
| 18 | Migration: Frontend Pages (M6) | `type: migration`, `priority: high`, `category: webui` | Tech Stack Migration | Roadmap |
| 19 | Migration: Cutover (M7) | `type: migration`, `priority: high`, `category: core` | Tech Stack Migration | Roadmap |

### Issue-Body Template

Jedes Issue enthaelt:

```markdown
## Beschreibung
[Was und warum]

## Betroffene Systeme
[Aus Roadmap: Affected Systems]

## Aufwand
[Simple / Medium / Large]

## Abhaengigkeiten
[Andere Issues die vorher fertig sein muessen]

## Referenzen
- Spec: `docs/specs/modules/[name].md` (falls vorhanden)
- Story: `docs/project/backlog/stories/[name].md` (falls vorhanden)
- Feature-Brief: `docs/project/backlog/features/[name].md` (falls vorhanden)
```

## Durchfuehrung

### Schritt 1: Labels anlegen (13 Labels)

Alle Labels aus der Tabelle oben auf GitHub erstellen.

### Schritt 2: Milestones anlegen (5 Milestones)

Aus der Milestone-Tabelle oben.

### Schritt 3: Issues anlegen (19 Issues)

Jedes Issue mit korrektem Titel, Labels, Milestone und Body.

### Schritt 4: Markdown-Dateien aktualisieren

| Datei | Aktion |
|---|---|
| `backlog/ACTIVE-roadmap.md` | Hinweis ergaenzen: "Offene Features → GitHub Issues" |
| `backlog/epics.md` | Hinweis ergaenzen: "Epics → GitHub Milestones" |
| `project/known_issues.md` | Hinweis ergaenzen: "Bugs → GitHub Issues" |
| `project/backlog.md` | Als obsolet markieren |

### Schritt 5: CLAUDE.md anpassen

Workflow-Referenzen auf GitHub Issues umstellen, damit kuenftige Claude-Sessions Issues statt Markdown pflegen.

## Was sich danach aendert

| Vorher (Markdown) | Nachher (GitHub Issues) |
|---|---|
| Feature-Status in Roadmap-Tabelle pflegen | Issue oeffnen/schliessen |
| Sprint-Planung in Markdown editieren | GitHub Project Board mit Spalten |
| Bug in known_issues.md dokumentieren | Issue mit `type: bug` Label |
| Neues Feature → `/feature` Command → Markdown | Issue erstellen → Spec schreiben → PR verlinkt Issue |
| Fortschritt: Markdown lesen | Milestone-Fortschritt in GitHub UI |

## Nicht-Ziele

- Kein GitHub Projects Board (Kanban) in diesem Schritt — kann spaeter ergaenzt werden
- Keine Automatisierung (GitHub Actions die Issues aktualisieren) — erstmal manuell
- Done-Features werden NICHT nachtraeglich als geschlossene Issues angelegt
