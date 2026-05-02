# Backlog Structure

Dieses Verzeichnis enthaelt Planungs-Dokumente fuer das Projekt. **Tracking
selbst (Status, Prioritaet, Status-Uebergaenge) findet komplett auf GitHub
Issues statt** — siehe https://github.com/henemm/gregor_zwanzig/issues.

## Directory Structure

```
backlog/
├── README.md                          # Diese Datei
├── completed-features-archive.md      # Historisches Archiv (stillgelegt 2026-05-02, Issue #114)
├── epics.md                           # Epic-Tracking (grosse Initiativen, optional)
├── stories/                           # User-Story-Dokumente (Detail-Planung)
│   └── [story-name].md
└── features/                          # Feature-Briefs (Detail-Planung)
    └── [feature-name].md
```

## Hierarchy

```
Epic (months)
  └─ User Story (weeks)
      └─ Feature (days)
          └─ Tasks (hours)
```

## Tracking-Quelle

| Was | Wo |
|---|---|
| Offene Features / Bugs | GitHub Issues (open) |
| In Arbeit | GitHub Issue mit Label `in-progress` oder verlinktem PR |
| Erledigt | GitHub Issue closed + zugehoeriger PR merged |
| Historisches Archiv (vor 2026-05-02) | `completed-features-archive.md` (read-only) |

Der frueher hier dokumentierte Status-Workflow (`open → spec_ready → in_progress → done`)
ist 1:1 ueber GitHub-Labels und Issue-State abbildbar:
- `open` = GitHub Issue open, noch keine Spec
- `spec_ready` = Issue open, Spec im Repo, Label `spec_ready`
- `in_progress` = Issue open, Workflow gestartet, ggf. Label `in-progress`
- `done` = Issue closed
- `blocked` = Issue open, Label `blocked`

## Documents Explained

### completed-features-archive.md

**Status:** Stillgelegt seit 2026-05-02 (Issue #114). Read-only, nur Historie
(Features VOR diesem Datum). Neue Eintraege gehoeren ins jeweilige GitHub Issue.

### epics.md

**Purpose:** Tracking grosser, mehrwoechiger Initiativen mit mehreren Stories.
Wird manuell gepflegt, wenn die Granularitaet von GitHub-Issues nicht reicht.

### stories/[story-name].md

**Purpose:** Detail-Dokument zu einer User Story. Wird vom `/user-story` Skill
angelegt. Enthaelt Acceptance Criteria, Feature-Breakdown mit Prioritaeten,
Implementierungs-Reihenfolge, Effort-Schaetzung. Verweist auf die zugehoerigen
GitHub Issues.

### features/[feature-name].md

**Purpose:** Detail-Brief zu einem einzelnen Feature. Wird vom `/0-feature`
Skill angelegt. Enthaelt Scoping (Files/LOC), Dependencies, Naechste Schritte.
Verweist auf das zugehoerige GitHub Issue.

## Workflows

### Grosser Bedarf (User Story)

1. User beschreibt: "Als Weitwanderer moechte ich SMS-Berichte..."
2. `/user-story "..."` → user-story-planner agent erstellt:
   - `stories/sms-berichte.md`
   - **Pro Feature ein eigenes GitHub Issue** mit Label `enhancement`
   - Optional: Epic-Eintrag in `epics.md`
3. User waehlt erstes Feature → `/0-feature "SMS Channel Integration"`
4. feature-planner agent erstellt `features/sms-channel-integration.md` und
   verlinkt das GitHub Issue.
5. Workflow: `/2-analyse → /3-write-spec → approve → /5-implement → /6-validate → /7-deploy`
6. Nach Abschluss: `gh issue close <n>` mit Kommentar; PR-Merge dokumentiert die Aenderung.

### Einzelnes Feature

1. `/0-feature "HTML Tables in Email Formatter"`
2. feature-planner agent erstellt Feature-Brief + GitHub Issue.
3. Workflow durchlaufen.
4. Issue schliessen.

## Scoping Limits

Pro Feature:
- Max 4-5 Dateien geaendert
- Max ±250 LoC

Wenn groesser → in mehrere Issues aufteilen.

## Related Commands

| Command | Purpose | Creates |
|---------|---------|---------|
| `/0-user-story` | Grosse User Need planen | Story-Doc + GitHub Issues |
| `/0-feature` | Einzelnes Feature planen | Feature-Brief + GitHub Issue |
| `/0-bug` | Bug analysieren | Bug-Report (+ optional GitHub Issue) |
| `/workflow` | Workflow-Status verwalten | - |

## Maintenance

- **Wartung der GitHub Issues:** Labels aktuell halten, geschlossene Issues
  ggf. mit Verweis auf den umsetzenden PR/Commit kommentieren.
- **`epics.md`:** Manuell pflegen, wenn ein Epic startet/endet.
- **`completed-features-archive.md`:** **NICHT mehr aendern** — historisches
  Read-only-Dokument.
