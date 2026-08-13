# Nächstes Ticket (`/next-ticket`)

Beantwortet am Ende einer Session eine einzige Frage, direkt in DIESEM Terminalfenster/Tab:
**Welches Ticket starte ich hier als Nächstes?** Kein Dashboard, keine Artifact-Seite —
reine Chat-Antwort für die laufende Session. Ergänzt `/radar` (Gesamtüberblick über alle
Tabs für den PO), ersetzt es nicht: `/radar` plant über alle Fenster hinweg, `/next-ticket`
beantwortet nur "und HIER, jetzt?".

**Wann ausführen:** auf Zuruf — typischerweise wenn diese Session ihr Issue gerade fertig
gemeldet hat (`workflow.py finish`) und in genau diesem Tab weitergemacht werden soll.
Nicht automatisch.

## Schritt 1: Diesen Tab identifizieren

```bash
pwd
git branch --show-current
python3 /home/hem/agent-os-openspec/core/hooks/workflow.py list 2>&1 | grep '\*$'
```

Ergebnis: Name/Issue des gerade abgeschlossenen oder noch aktiven Workflows in diesem Tab
(falls vorhanden). Nur zur Einordnung — dieser Tab braucht KEINE Bindung an sein bisheriges
Thema, er kann komplett wechseln.

## Schritt 2: Was arbeiten die ANDEREN Tabs gerade — Ausschlussliste

Gleiche Erkennung wie `/radar` Schritt 2 (Worktree = Tab, Ordnername ist KEIN verlässlicher
Hinweis auf das Issue — der `*`-markierte Workflow pro Worktree ist die Wahrheit), aber nur
um "belegt" zu markieren, nicht um ein volles Dashboard zu bauen:

```bash
cd /home/hem/gregor_zwanzig
for d in .claude/worktrees/*/; do
  name=$(basename "$d")
  [ "$d" -ef "<Pfad dieses Tabs>" ] && continue
  branch=$(git -C "$d" branch --show-current 2>/dev/null)
  echo "=== $name | branch=$branch ==="
  ( cd "$d" && python3 /home/hem/agent-os-openspec/core/hooks/workflow.py list 2>&1 | grep '\*$' )
done
```

Nur echte Worktrees zählen (`git worktree list` im Hauptrepo gegenprüfen — verwaiste Ordner
ohne gültiges `.git` sehen wie ein Tab aus, sind aber keiner). Jede Issue-Nummer, die dort
als aktiv erkannt wird → aus der Kandidatenliste ausschließen. Workflows mit sehr altem
Stand und/oder bereits `gh issue view <N> --json state` CLOSED zählen nicht als belegt.

**Das Ergebnis ist eine Tatsache, kein Vorbehalt.** Genau dafür läuft dieser Schritt — damit
der User nicht selbst nachsehen muss, ob ein Kandidat gerade woanders läuft. Für JEDEN
Kandidaten, der es in Schritt 4 in die Empfehlung oder die Alternativen schafft, muss vorher
feststehen: frei oder belegt. Ließ sich das für einen Worktree technisch nicht prüfen (z. B.
nicht lesbar, `workflow.py` schlägt fehl): das ehrlich als Lücke benennen ("Tab X konnte
nicht geprüft werden") statt den Kandidaten trotzdem unter Vorbehalt weiterzureichen.

## Schritt 3: Backlog + echte Priorität, nicht nur das Label

```bash
gh issue list --repo henemm/gregor_zwanzig --state open --json number,title,labels,body,updatedAt --limit 300
```

`priority:`-Label ist ein Startpunkt, keine Antwort — siehe Memory
`project_khw_tour_priorisierung_2026_08` u. ä.: harte Termine, "Folge zu #X"/"Scheibe N von
#X"-Abhängigkeiten in den Issue-Bodies, vermutete Duplikate und die tatsächliche
Nutzerwirkung schlagen das Label. Bei Unsicherheit, ob ein Kandidat an derselben Stelle im
Code arbeiten würde wie ein GERADE in einem anderen Tab laufendes Issue (Schritt 2): kurzer
Fork mit `gh issue view` + Code-Grep, wie in `/radar` Schritt 3 — Titel-/Label-Ähnlichkeit
allein reicht nicht als Nachweis.

**Erst den eigenen Strang zu Ende prüfen, PFLICHT vor dem Rest des Backlogs.** Gehört das
zuletzt in diesem Tab bearbeitete Issue zu einer Kette (Epic-Bezug im Body, "Folge zu #X",
"Scheibe N von #X", gemeinsames `epic`-Label)? Wenn ja, ist das nächste offene Folge-Issue
im selben Strang der Standard-Kandidat — ein Themenwechsel kostet nach einem `/clear`
echten Aufwand (Domänenwissen, bereits gelesene Spec/Analyse geht verloren, wird andernorts
neu aufgebaut). Nur verdrängen, wenn ein anderer Punkt nachweislich dringender ist (harter
Termin, kritischer/produktionsrelevanter Bug, ausdrückliche PO-Vorgabe) — dann in der
Empfehlung kurz benennen, warum der Strang NICHT fortgesetzt wird. Existiert zur nächsten
Scheibe noch kein eigenes Issue (nur als Plan im Epic-Body vermerkt): das ausdrücklich so
ausweisen, nicht als startbares Ticket ausgeben.

## Schritt 4: Eine Antwort, keine Liste

Ausgabe NUR im Chat dieser Session, kein Artifact, kein Dashboard:

- **Empfehlung:** `#<Nummer> <Klartext-Titel>` + ein Halbsatz Warum, in Geschäftssprache
  (Auswirkung fürs Produkt/den Termin, nicht Code-Ursache) — kein Dateipfad, kein
  Workflow-/Branch-Name, kein Phasenbegriff.
- **Pflicht: die Issue-Nummer steht IMMER dabei.** Nie nur „Scheibe 2" oder „weiter mit dem
  Alarm-Strang" ohne Nummer nennen — die Antwort muss für sich stehen und auch nach einem
  `/clear` verständlich sein, ohne dass der bisherige Chatverlauf bekannt sein muss. Ist die
  Empfehlung die Folgescheibe eines Epics: **beide** Nummern nennen — Epic (`#<Epic-Nr>
  <Epic-Titel>`) UND das konkrete Folge-Issue (`#<Nummer> <Titel>`). Gibt es noch kein
  eigenes Issue für die nächste Scheibe, das ausdrücklich sagen ("kein Issue vorhanden —
  zuerst anlegen") statt es als startbar hinzustellen.
- Nur falls die Empfehlung unklar/knapp blockiert ist: 1–2 Alternativen darunter, kurz
  begründet, ebenfalls jeweils mit Issue-Nummer.
- **VERBOTEN: den Belegt-Status eines anderen Tabs als Bedingung an den User zurückgeben**
  — Formulierungen wie „falls #N gerade in einem anderen Fenster läuft" sind genau die
  Prüfung, die Schritt 2 abschließend übernehmen soll, nicht der User. Jede genannte
  Empfehlung/Alternative ist zum Ausgabezeitpunkt bereits als frei bestätigt. Konnte das für
  einen Kandidaten nicht geprüft werden, gehört er entweder gar nicht in die Antwort, oder es
  steht offen dabei "Tab X konnte nicht geprüft werden" — nie als stilles "falls". Erlaubt
  bleibt ausschließlich ein echter Ermessens-Vorbehalt, der beim User liegt (z. B. "falls du
  anders priorisieren willst").
- Keine Tab-Buchstaben, keine Nachrücker-Liste für andere Tabs — das bleibt `/radar`s
  Aufgabe. Wenn der Gesamtüberblick über alle Fenster gefragt ist, `/radar` vorschlagen
  statt hier nachzubauen.

## Nicht vergessen

Dieser Command liefert nur die Auswahl, keinen Freifahrtschein zum Loslegen — vor dem Start
des empfohlenen Tickets läuft der normale Workflow-Einstieg (`/00-intake` o. ä.).
