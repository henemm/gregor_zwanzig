# Context: Issue #427 — GitHub Labels & Issues aufräumen

## Request Summary
GitHub-Labels im Repo `henemm/gregor_zwanzig` enthalten redundante und inkonsistente
Einträge (doppelte Bug-/Feature-Labels, gemischtes `type:`-Präfix-Schema). Offene Issues
sollen korrekt gelabelt sein.

## Ist-Zustand: Label-Redundanzen

| Problem | Labels | Nutzung |
|---------|--------|---------|
| Doppeltes Bug-Label | `bug` (kein Präfix) vs. `type:bug` | 50 vs. 38 Issues |
| Dreifaches Feature-Label | `feature` + `enhancement` + `type:feature` | 21 + 117 + 12 Issues |
| Fehlende Beschreibung | `priority:critical`, `area:*` (meiste) | — |

**Standard-Schema im Repo:** `type:bug`, `type:feature`, `type:infra`, `type:rework`, `type:docs`
→ `bug`, `feature`, `enhancement` sind Legacy-Labels ohne `type:`-Präfix.

## Offene Issues mit Labeling-Mängeln

### Kein `type:`-Label (11 Issues):
- `#438–#443` (Orts-Vergleich Epic + Steps): haben `feature`, fehlt `type:feature`
- `#416` Mobile Trip-Detail: hat `enhancement`, fehlt `type:feature`
- `#368` Epic Atomic-Design: kein `type:`-Label
- `#351`, `#349` Backend-Bugs: kein `type:`-Label (sollten `type:bug` bekommen)
- `#246` Epic Orts-Vergleich: kein `type:`-Label (sollte `epic` behalten + `type:feature`)

### Doppelt gelabelte Issues (4 Issues):
- `#426` Alternative Login: `feature` + `type:feature` + `enhancement` (alle drei!)
- `#425` Alternative Signup: `enhancement` + `type:feature`

## Labels — vollständige Liste

```
Aktive Labels (Stand 2026-05-29):
accessibility, area:alerts, area:cockpit, area:compare, area:components,
area:editor, area:home, area:output, area:reports, area:sidebar, area:tokens,
area:trips, area:weather, backend-coordination, breaking-change, bug,
data-loss, design-compliance, enhancement, epic, feature, for:claude-design,
foundation, frontend, mobile, priority:critical, priority:high, priority:low,
priority:medium, status:deferred, type:bug, type:docs, type:feature,
type:infra, type:rework, ux
```

**Zu löschende Legacy-Labels (nach Migration):**
- `bug` → Merge in `type:bug`
- `feature` → Merge in `type:feature`
- `enhancement` → Merge in `type:feature` (oder in eigenes `type:enhancement` umbenennen)

## Entscheidung erforderlich

Zwei Optionen für `enhancement` vs. `type:feature`:

**Option A:** `enhancement` → `type:feature` (einheitliches `type:`-Schema)
- Pro: konsistent, GitHub-Standard wird ersetzt
- Con: `enhancement` (117 Issues!) muss komplett migriert werden

**Option B:** `enhancement` behalten, `feature` + `type:feature` löschen
- Pro: weniger Migrationsaufwand (nur 33 Issues)
- Con: gemischtes Schema (`type:bug` aber kein `type:feature`)

## Keine Code-Änderungen

Dieses Issue betrifft ausschließlich GitHub-Metadaten (Labels + Issue-Tags).
Keine `src/`, `frontend/`, `api/`-Dateien werden geändert.
Alle Aktionen laufen via `gh label` + `gh issue edit` CLI.

## Risiken & Überlegungen

- Label-Löschung ist **reversibel** (neu anlegen ist jederzeit möglich)
- Issue-Label-Änderungen sind **reversibel** (gh issue edit --add-label / --remove-label)
- Closed Issues müssen mitbereinigt werden, damit historische Konsistenz erhalten bleibt
- Geringer Aufwand, hohes Signal-to-Noise-Verhältnis für zukünftige Arbeit
