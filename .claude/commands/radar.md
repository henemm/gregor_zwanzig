# Werkstatt-Radar (`/radar`)

Erzeugt/aktualisiert das PO-Dashboard "Werkstatt-Radar" (Artifact): eine einfache Liste
pro aktivem Arbeits-Tab, was als Nächstes zu starten ist. Zielgruppe ist der PO
(Geschäftsführer, kein Techniker) — siehe `feedback_no_tech_jargon` und
`feedback_radar_tab_plan_format` im Auto-Memory. Das Endergebnis ist bewusst simpel;
die Recherche dahinter ist es nicht.

**Wann ausführen:** auf Zuruf ("aktualisiere den Radar" o. ä.), nicht automatisch.

## Schritt 1: Backlog erfassen

```bash
gh issue list --repo henemm/gregor_zwanzig --state open --json number,title,labels,body,updatedAt --limit 300
```

Damit auch: Duplikate/Themen-Nähe über Titel+Labels grob vorsortieren (nur Vorstufe,
kein Endergebnis — siehe Schritt 3).

## Schritt 2: Echte Tabs erkennen (PFLICHT — nicht überspringen)

Ein "Tab" ist ein Worktree unter `.claude/worktrees/` (nicht die alten `gz-workspace`-
Klone unter `/home/hem/gz-workspaces/`, die sind meist Altlasten). Der Ordnername eines
Worktrees ist **kein verlässlicher Hinweis** darauf, an welchem Issue er gerade arbeitet
(z. B. kann ein Worktree `intake-965` heißen, aber inzwischen an #1223 arbeiten) — die
Wahrheit steht im `*`-markierten Workflow pro Worktree:

```bash
cd /home/hem/gregor_zwanzig
for d in .claude/worktrees/*/; do
  name=$(basename "$d")
  branch=$(git -C "$d" branch --show-current 2>/dev/null)
  uncommitted=$(git -C "$d" status --porcelain 2>/dev/null | wc -l)
  lastcommit=$(git -C "$d" log -1 --format=%ar 2>/dev/null)
  echo "=== $name | branch=$branch | uncommitted=$uncommitted | zuletzt=$lastcommit ==="
  ( cd "$d" && python3 /home/hem/agent-os-openspec/core/hooks/workflow.py list 2>&1 | grep '\*$' )
done
```

Ergebnis pro Tab: die Zeile mit `*` ist der gerade aktive Workflow dieses Tabs. Kein `*`
→ Tab ist idle/zwischen Aufgaben (in der Ausgabe weglassen oder explizit als frei markieren).
Workflow-Name auf Issue-Nummer(n) mappen (z. B. `rework-1209-config-resolver-b` → #1209).
Bei Unsicherheit: `GZ_ACTIVE_WORKFLOW=<name> OPENSPEC_ACTIVE_WORKFLOW=<name> python3 .../workflow.py status`
innerhalb des jeweiligen Worktrees für Details.

Worktrees mit sehr altem `zuletzt`-Datum (>2 Tage) und/oder deren Issue bereits
`gh issue view <N> --json state` CLOSED ist: als verwaist markieren, nicht als aktiven Tab zählen.

## Schritt 3: Rest des Backlogs einordnen

Für alle offenen Issues, die NICHT bereits einem aktiven Tab zugeordnet sind:

- **Bündeln:** kleine, inhaltlich zusammengehörige Issues (gleicher Bereich, gleiche
  Fehlerklasse, einer referenziert den anderen im Body) proaktiv zu einem Schritt
  zusammenfassen — nicht nachfragen (`feedback-bundle-small-issues-proactively`).
- **Abhängigkeiten:** Issue-Bodies nach Signalwörtern absuchen ("Folge zu #X", "aus #X",
  "Scheibe N von #X", "Voraussetzung", "blockt") — daraus die Reihenfolge INNERHALB eines
  Tabs ableiten.
- **Konfliktfreiheit zwischen Tabs:** bei Unsicherheit, ob zwei Issues an derselben Stelle
  im Code arbeiten würden, einen Fork mit Auftrag "gh issue view + Code-Grep +
  Kollisionsmatrix" spawnen (Vorgehen und Fallstricke: Memory
  `reference-werkstatt-radar-artifact`). Titel-/Label-Ähnlichkeit allein reicht NICHT als
  Nachweis.
- Große, unklare oder blockierte Posten (Epics ohne Slice-Zerlegung, `status:blocked-po`,
  reine Konzept-Issues ohne Code) NICHT in die Tab-Liste zwingen — eigene "Wartet"-Zeile.

## Schritt 4: Ausgabe — EXAKTES Format, nicht abweichen

Zielformat ist vom PO festgelegt (Memory `feedback_radar_tab_plan_format`). Kurzfassung:

- So viele Tabs wie tatsächlich aktive Worktrees aus Schritt 2 (nicht künstlich auf eine
  feste Zahl auffüllen oder kürzen) — plus ggf. einen neuen Tab-Vorschlag, falls ein
  besonders wichtiges Issue sonst gar nicht abgedeckt wäre.
- Pro Tab: kurzer Themenname (Klartext, z. B. "Warn-Mail", nicht der Workflow-Name) +
  nummerierte Liste `#<Nummer> <Klartext-Titel>`. Erster Eintrag, falls durch Schritt 2
  bestätigt aktiv: Markierung "läuft schon".
- Gebündelte Punkte als `#A + #B (gebündelt)` in einer Zeile.
- **VERBOTEN im sichtbaren Ergebnis:** Dateipfade, Workflow-/Branch-Namen, Phasen-
  Bezeichnungen ("TDD RED" etc.), Kollisionsmatrizen, "Blast-Radius"/"SOLO"-Jargon,
  mehrsätzige Begründungen. Höchstens ein kurzer Halbsatz Warum, in Geschäftssprache
  (Auswirkung fürs Produkt, nicht Code-Ursache).
- Abschluss-Abschnitt **"Noch nicht gestartet"** (NICHT "Wartet, bis ein Tab frei wird" — trifft
  nicht auf jeden Eintrag zu, manche könnten sofort in einem neuen Tab starten; PO-Korrektur
  2026-07-11) für Großes/Blockiertes. Jede Zeile trägt ihren eigenen Halbsatz-Grund.
- Ein Schlusssatz, dass die Tabs sich nicht gegenseitig blockieren (nur wenn durch
  Schritt 3 auch tatsächlich geprüft — sonst weglassen statt zu behaupten).

## Schritt 5: Artifact veröffentlichen

Gleiche Artifact-URL weiterverwenden (Memory `reference-werkstatt-radar-artifact` für die
aktuelle URL und die Falle mit "deleted/no write access" bei alten URLs). Design: schlicht,
warme dunkle/helle Palette, keine dichten Tabellen — reines Karten-Layout pro Tab.

## Nicht vergessen

- Nach dem Update: kurze Chat-Zusammenfassung (2-3 Sätze) + Link, nicht die ganze Liste
  nochmal im Chat wiederholen, wenn sie schon auf der Seite steht.
- Bei neuen, im Zuge der Recherche entdeckten Erkenntnissen (z. B. ein Tab arbeitet an
  etwas anderem als der Ordnername vermuten lässt, ein Workflow ist verwaist): das kurz
  als Memory-Update festhalten, nicht nur einmalig im Chat erwähnen.
