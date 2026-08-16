# Nächstes Ticket (`/next-ticket`)

Beantwortet am Ende einer Session eine einzige Frage, direkt in DIESEM Terminalfenster/Tab:
**Welches Ticket starte ich hier als Nächstes?** Kein Dashboard, keine Artifact-Seite —
reine Chat-Antwort für die laufende Session. Ergänzt `/radar` (Gesamtüberblick über alle
Tabs für den PO), ersetzt es nicht: `/radar` plant über alle Fenster hinweg, `/next-ticket`
beantwortet nur "und HIER, jetzt?".

**Wann ausführen:** auf Zuruf — typischerweise wenn diese Session ihr Issue gerade fertig
gemeldet hat (`workflow.py finish`) und in genau diesem Tab weitergemacht werden soll.
Nicht automatisch.

## Schritt 0: Kurzzeit-Cache prüfen — Pflicht vor jedem teuren Schritt

Zwei Aufrufe kurz hintereinander (selbe Sitzung ohne `/clear`, oder ein zweiter Aufruf
innerhalb weniger Minuten) dürfen NICHT zweimal denselben vollen Backlog neu einlesen und
neu bewerten:

- **Innerhalb derselben Sitzung:** Stehen Ergebnisse aus Schritt 2/3 bereits im
  Gesprächsverlauf dieser Sitzung (kein `/clear` dazwischen, keine `workflow.py finish`
  seither), diese direkt wiederverwenden statt die Befehle erneut auszuführen.
- **Über Sitzungsstarts hinweg (Cache-Datei):** `docs/artifacts/next_ticket_cache.json`
  (worktree-lokal, gitignored) prüfen. Ist die Datei jünger als 5 Minuten:
  ```bash
  gh issue list --repo henemm/gregor_zwanzig --state open --json number,updatedAt --limit 300 \
    | sha256sum
  ```
  Stimmt diese Kurz-Prüfsumme (billig: keine Issue-Bodies) mit der im Cache hinterlegten
  überein, ist der Backlog seit dem Cache-Schreiben unverändert — die zwischengespeicherte
  Analyse aus Schritt 3 direkt weiterverwenden, Schritt 3 nicht erneut ausführen. Weicht sie
  ab oder ist die Datei älter als 5 Minuten oder fehlt: normal weiter mit Schritt 1, und am
  Ende von Schritt 3 die neue Prüfsumme + die daraus abgeleitete Analyse in die Cache-Datei
  schreiben (überschreiben, keine Historie).
- Der Belegt-Check aus Schritt 2 (Ausschlussliste anderer Tabs) wird von diesem Cache NICHT
  erfasst — der ist lokal/kostenlos (kein `gh`-Aufruf, reine Dateisystem-/Git-Befehle) und
  läuft bei jedem Aufruf frisch, weil er sich schneller ändert als der Backlog selbst.

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
zuletzt in diesem Tab bearbeitete Issue zu einer Kette? In diesem Repo tatsächlich verwendete
Schreibweisen dafür, alle gleichwertig erkennen (Vielfalt ist Bestand, keine davon ist
"falsch"): **"Folge zu #X"**, **"Scheibe N von #X"**, **"Nachzug zu #X"**, **"Teil von #X"**,
**"S<N>[a-z]? zu/von #X"** (z. B. "S2-Nachzug zu #1457"), sowie ein **Issue-Titel-Präfix**
`#<Epic-Nr> S<N>[a-z]?:` (z. B. "#1676 S2b: ..." — die Epic-Nummer steht dabei VOR dem
Doppelpunkt, nicht als Fließtext-Referenz). Gemeinsames `epic`-Label zählt zusätzlich als
Hinweis, ersetzt aber keine der Textformen. Steht KEINE dieser Formen im Titel/Body, gilt das
Issue als eigenständig — nicht aktiv nach einer Kette suchen, die nirgends benannt ist.
Trifft eine der Formen zu, ist das nächste offene Folge-Issue im selben Strang der
Standard-Kandidat — ein Themenwechsel kostet nach einem `/clear`
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
- **VERBOTEN: unaufgefordert erklären, was NICHT vorgeschlagen wurde und warum.** Weder
  "thematisch naheliegende, aber ausgeschlossene" Kandidaten noch die Rechercheschritte
  dahinter gehören in die Standardausgabe — das ist Prozess-Transparenz, die niemand
  angefordert hat, kein Teil der Antwort. Die Recherche (Schritt 2/3) bleibt vollständig
  Voraussetzung für die Empfehlung, taucht aber nicht im sichtbaren Ergebnis auf. Fragt der
  User gezielt nach ("warum nicht #N?"), das im Chat beantworten — nicht proaktiv voranstellen.

## Nicht vergessen

Dieser Command liefert nur die Auswahl, keinen Freifahrtschein zum Loslegen — vor dem Start
des empfohlenen Tickets läuft der normale Workflow-Einstieg (`/00-intake` o. ä.).
