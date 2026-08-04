---
entity_id: feat_1481b_pendant_gate
type: module
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [gate, dry, commit-hook]
---

# Spec: Commit-Gate „Pendant-Sperre"

- **Issue:** #1481 Scheibe B
- **Workflow:** `feat-1481-pendant-sperre`
- **created:** 2026-08-04
- **Kontext & Messungen:** `docs/context/feat-1481-pendant-sperre.md`
- **Status:** Entwurf — wartet auf PO-Freigabe der Acceptance Criteria

## Zweck in einem Satz

Eine **neu angelegte** Datei in einem einseitigen Bereich (nur Vergleich **oder** nur Trip)
blockiert den Commit, außer sie liegt in einem geteilten Bereich oder trägt eine Begründungszeile
`gz-eigenstaendig: <fachlicher Grund>` im Kopf.

## Warum

CLAUDE.md verlangt seit langem „möglichst viel Code zwischen Trip und Ortsvergleich teilen" —
bisher eine reine Textregel. Bei #1459 D3 hätte dort stehen müssen „zwei getrennte Felder, weil
sonst die Go-Seite mit angefasst werden müsste"; genau dieser Satz blieb unausgesprochen, und die
Doppelung fiel erst Wochen später auf. Vier Paare existieren heute bereits doppelt
(`compare-new/CompareNewEditor.svelte` ↔ `trip-new/TripNewEditor.svelte`,
`compare-new/compareNewLogic.ts` ↔ `trip-new/tripNewLogic.ts`,
`compare/CompareTabs.svelte` ↔ `trip-detail/TripTabs.svelte`,
`renderers/email/compare_html.py` ↔ `renderers/email/html.py` — im Code selbst dokumentiert:
`compare_html.py:3` „analog zu ``html.py`` (Trip-Mail)"). Zwölf Paritäts-Tests im Bestand
bewachen genau solche Paare, nachdem sie bereits doppelt existierten — der Beleg, dass die
Textregel allein nicht wirkt. Der Ausweg verhindert nichts, er macht die Entscheidung im
Änderungssatz zitierbar.

Verwandter Wächter: `.claude/hooks/touched_tests_gate.py` (Scheibe A, gleicher Verdrahtungstyp,
gleiche Fail-open-Regel). Nächstes Vorbild dem Umfang nach: `.claude/hooks/test_naming_gate.py`
(52 Zeilen, sperrt ebenfalls nur neue Dateien nach Pfadmuster, mit Prüfdatum und fail-open).

## Zuschnitt

**Einseitige Bereiche** (neue Dateien hier brauchen einen Ausweg):
- `frontend/src/lib/components/compare/**` und `compare-new/**` (Vergleichs-Seite)
- `frontend/src/lib/components/trip-detail/**` und `trip-new/**` (Trip-Seite)
- `src/output/renderers/**/{compare_*,trip_*}.py` — **rekursiv**, nicht nur oberste Ebene

**Ausweg-Bereiche** (neue Dateien hier lösen die Sperre nie aus):
- `frontend/src/lib/components/shared/**`
- Renderer ohne `compare_`/`trip_`-Präfix

**Gestrichen gegenüber dem Ticket: `frontend/src/lib/components/edit/**`.** Nachgemessen: die 16
Nicht-Testdateien dort sind durchweg Etappen-, Routen- und Kartenwerk (`EditStagesSection.svelte`,
`EditRouteSection.svelte`, `StageDateField.svelte`, `MapControl.svelte`). Kein Bauteil unter
`compare/` importiert daraus, und laut CLAUDE.md darf Compare-eigen ohnehin nur Orte-Tab,
transponierte Übersicht und Compare-Mail-Muster sein — Etappen sind dort nicht vorgesehen. Ein
Pendant kann hier strukturell nicht entstehen; die Sperre erzeugte reines Rauschen.

**Erweitert gegenüber dem Ticket: Renderer rekursiv statt nur oberste Ebene.** Das Muster aus dem
Issue (`src/output/renderers/{compare_*,trip_*}.py`) verfehlt ausgerechnet den bestbelegten Fall
— `email/compare_html.py` liegt eine Ebene tiefer.

## Acceptance Criteria

**AC-1: Neue Datei im einseitigen Bereich ohne Begründung blockiert den Commit**
Given eine neu erstellte Datei liegt in `compare/**`, `trip-detail/**` oder einem
`compare_`/`trip_`-Renderer und trägt keine Begründungszeile im Kopf
When `git commit` diese Datei als Neuanlage ausführt
Then bricht der Commit ab (Exit-Code 2), und die Meldung nennt Datei und Bereich.
- Test: Wegwerf-Repo, echte neue Datei ohne Begründung committen, Exit-Code 2 gemessen.

**AC-2: Begründungszeile lässt den Commit durch**
Given dieselbe neue Datei trägt im Dateikopf `gz-eigenstaendig: <Grund mit >=15 sinnvollen
Zeichen>` innerhalb der ersten 20 Zeilen
When `git commit` ausgeführt wird
Then läuft der Commit ohne Rückfrage durch (Exit-Code 0).
- Test: identisches Wegwerf-Repo, Kopf um die Begründungszeile ergänzt, Exit-Code 0 gemessen.

**AC-3: Zu kurze oder inhaltsleere Begründung blockiert weiterhin**
Given die Begründungszeile enthält nur Satzzeichen oder weniger als 15 sinnvolle Zeichen (nach
Entfernen aller Nicht-Wortzeichen)
When `git commit` ausgeführt wird
Then bricht der Commit weiterhin ab (Exit-Code 2), unabhängig von der Zeilenlänge insgesamt.
- Test: Wegwerf-Repo mit `gz-eigenstaendig: ...` und mit `gz-eigenstaendig: kurz`, beide
  Exit-Code 2.

**AC-4: Der geteilte Bereich lässt jede neue Datei durch**
Given eine neue Datei liegt unter `shared/**` oder ist ein Renderer ohne
`compare_`/`trip_`-Präfix
When `git commit` ausgeführt wird
Then läuft der Commit ohne Begründungszeile durch (Exit-Code 0).
- Test: Wegwerf-Repo, neue Datei unter `shared/`, kein Kopfkommentar, Exit-Code 0 gemessen.

**AC-5: Nur neu angelegte Dateien werden geprüft, der Bestand ist frei**
Given eine bereits vorhandene Datei im einseitigen Bereich wird inhaltlich geändert, nicht neu
angelegt
When `git commit` ausgeführt wird
Then läuft der Commit unabhängig vom Inhalt durch (Exit-Code 0).
- Test: Wegwerf-Repo, Bestandsdatei ändern und committen ohne jede Begründungszeile, Exit-Code 0
  gemessen.

**AC-6: Testdateien sind über ihre Endung ausgenommen, unabhängig vom Ablageort**
Given eine neue Testdatei liegt DIREKT im einseitigen Bereich statt in einem `__tests__/`-Ordner
— gemessen liegt rund die Hälfte der Testdateien dort (`compare/channelChipCount.test.ts`), eine
reine Ordnerregel würde sie also massenhaft blockieren
When `git commit` mit `compare/fooBar.test.ts` ohne Begründungszeile ausgeführt wird
Then läuft der Commit durch (Exit-Code 0), weil die Ausnahme an der Endung hängt
(`.test.ts`/`.spec.ts`/`.test.js`) und zusätzlich an den Ordnern `tests/**` und `__tests__/**`.
- Test: Wegwerf-Repo, neue `compare/fooBar.test.ts` NEBEN einem `__tests__/`-Ordner → Exit-Code 0;
  Gegenprobe `compare/fooBar.ts` (gleicher Ort, keine Testendung) → Exit-Code 2. Die Gegenprobe
  ist der eigentliche Nachweis: ohne sie wäre die Ausnahme auch dann grün, wenn sie alles
  durchließe.

**AC-7: Verschiebung in den geteilten Bereich lässt immer durch, auch unter der Ähnlichkeitsschwelle**
Given eine Datei wandert von einem einseitigen Bereich nach `shared/**`, und die Änderung ist so
groß, dass Git daraus Löschen+Neuanlegen macht statt einer erkannten Umbenennung
When `git commit` ausgeführt wird
Then läuft der Commit durch (Exit-Code 0), weil das Ziel geteilt ist — unabhängig von der
Erkennungsschwelle für Renames.
- Test: Wegwerf-Repo, Datei nach `shared/` verschieben und Inhalt so stark ändern, dass Git keine
  Rename erkennt, Exit-Code 0 gemessen.

**AC-8: Reine Umbenennung innerhalb derselben Seite blockiert nicht**
Given eine Datei wird innerhalb desselben einseitigen Bereichs umbenannt (z.B. `compare/` bleibt
`compare/`, kein Seitenwechsel) **und ihr Inhalt bleibt dabei praktisch unverändert** (von git
gemeldete Ähnlichkeit >= 95 %)
When `git commit` ausgeführt wird
Then läuft der Commit durch (Exit-Code 0), ohne Begründungszeile.
- Test: Wegwerf-Repo, `compare/Old.svelte` zu `compare/New.svelte` umbenennen und committen,
  Exit-Code 0 gemessen. Gegenprobe: dieselbe Umbenennung mit stark umgeschriebenem Inhalt →
  Exit-Code 2 (bewusster Fehlalarm, s. „Nicht in dieser Scheibe").

**Messreihe zur Grenze von 95 %** (Adversary-Fund F007, gemessen mit `git diff --cached
--name-status -M`):

| unverwandtes Paar (8 Zeilen, N gemeinsam) | git meldet | echte Umbenennung (40 Zeilen, k geändert) | git meldet |
|---|---|---|---|
| 1–4 gemeinsam | `D`+`A` | k=0 | `R100` |
| 5 gemeinsam | `R051` | k=1 | `R096` |
| 6 gemeinsam | `R061` | k=2 | `R093` |
| 7 gemeinsam | `R076` | k=4 | `R087` |
| | | k=8 | `R076` |

Die beiden Reihen **überlappen** bei `R076`: eine echte Umbenennung mit 8 geänderten Zeilen ist
von einem unverwandten Paar mit gemeinsamem Gerüst nicht unterscheidbar. Deshalb 95 % — damit
kommen `R100` und `R096` durch, das gesamte Zufallsband (bis `R076`) nicht.

**AC-9: Verschiebung von der Gegenseite oder aus dem geteilten Bereich in einen einseitigen Bereich braucht Begründung**
Given eine Datei wandert aus `trip-detail/**` oder `shared/**` neu nach `compare/**` (oder
umgekehrt) — der bequemste Weg an der Sperre vorbei, den das Issue nicht nennt
When `git commit` ohne Begründungszeile ausgeführt wird
Then bricht der Commit ab (Exit-Code 2), genauso wie bei einer komplett neuen Datei.
- Test: Wegwerf-Repo, Datei von `trip-detail/` nach `compare/` verschieben, Exit-Code 2 ohne
  Begründung, Exit-Code 0 mit Begründungszeile.

**AC-10: Drei Kommentarformen werden erkannt, im Fenster der ersten 20 Zeilen**
Given die Begründungszeile steht als `#`-Kommentar, als `//`-Kommentar (TS/Svelte) oder als
bloße Zeile innerhalb eines Python-Moduls-Docstrings — die Python-Renderer haben gemessen
überhaupt keine `#`-Kommentare im Kopf, nur `"""…"""`-Docstrings (`trip_metric_ids.py:1`,
`trip_report.py:1`), ein reiner `#`-Ausdruck würde dort nie greifen
When `git commit` ausgeführt wird
Then läuft der Commit für alle drei Formen gleichermaßen durch (Exit-Code 0), solange die Zeile
innerhalb der ersten 20 Zeilen steht (längster gemessener Kopf-Docstring: 13 Zeilen).
- Test: drei Wegwerf-Dateien (`.py` mit `#`, `.ts` mit `//`, `.py` mit reiner Docstring-Zeile
  ohne `#`) — alle Exit-Code 0; vierte Variante mit Begründung erst ab Zeile 21 → Exit-Code 2.

**AC-11: Der Wächter erkennt Commits an der Aufrufform, nicht am Wortlaut**
Given ein Commit über `git -C <pfad> commit`, verkettet (`cd /tmp && git -C <pfad> commit`) oder
in mehrzeiliger Form ausgeführt wird, sowie ein Nicht-Commit-Aufruf wie
`grep -rn "git commit" …`
When der Bash-Aufruf geprüft wird
Then greift der Wächter bei allen drei Commit-Formen und NICHT beim grep-Aufruf.
- Test: erweitert die bestehende `tests/tdd/test_commit_gate_invocation_forms.py` um den neuen
  Wächter als parametrisierten Fall (keine neue Testdatei) — Exit-Code 2/0 je nach Aufrufform,
  am Wegwerf-Repo gemessen.

**AC-12: Der Wächter prüft seinen eigenen Ordner und sagt, wenn er nicht zuständig ist**
*(neu gefasst 2026-08-04 nach Adversary-Fund F010 — die frühere Fassung „liest den Vormerk-Stand
dort" ist zurückgebaut.)*
Given der Commit-Befehl trägt ein Anzeichen dafür, dass er einen **anderen** Projektordner meint
When der Wächter läuft
Then prüft er **nicht** dort, sondern lässt den Commit durch (Exit-Code 0) und **benennt** die
Auslassung („Der Commit zielt auf einen anderen Ordner — hier wurde nicht geprüft"). Ohne ein
solches Anzeichen prüft er unverändert das Verzeichnis, in dem er läuft.

Die Anzeichen sind ein **abgeschlossener, dokumentierter Satz** — keine Liste von
Hilfsprogrammen, keine Pfad-Auflösung: `-C` als eigenes Token · `--git-dir` · `--work-tree` ·
`GIT_DIR=` · `GIT_WORK_TREE=` · `cd` als Befehlswort. Sie zählen nur in einem Kommando-Abschnitt,
der auch wirklich `git` aufruft; was **vor** `git` steht (`sudo`, `timeout`, `xargs`, …), ist
gleichgültig. Damit endet die Liste, die kein Ende hatte. Die Zerlegung stammt aus `hook_utils`
(`_git_segments`) und wird **nicht nachgebaut** (#1431); fehlt sie, läuft der Commit ungeprüft
durch statt geraten zu werden.

- Test: die fünf gemessenen Wege in einen anderen Ordner (`git -C B commit` · `cd B && git
  commit` · `git --git-dir=… --work-tree=… commit` · `GIT_DIR=… GIT_WORK_TREE=… git commit` ·
  `(cd B && git commit)`) → jeweils Exit-Code 0 **und** eine Meldung, die den anderen Ordner
  benennt. Der Rückgabewert allein unterscheidet die benannte Grenze nicht von der Umgehung,
  deshalb wird die Meldung mitgeprüft.
- Test (Gegenprobe, acht Spielarten): schlichter Commit · `-C` im Text der Commit-Nachricht ·
  `git -c user.name=x commit` · `grep -C 3 muster datei && git commit` · `git commit -am` ·
  `git commit --amend` · `grep -C 3 muster datei ; timeout 30 git commit` · `sudo git commit`
  → alle Exit-Code 2. Ohne diese Gegenprobe wäre ein Wächter grün, der schlicht nichts mehr
  prüft.
- Test: `git commit -C HEAD` (git-eigenes Flag zum Übernehmen einer Nachricht, **kein**
  Verzeichnis) → Exit-Code 0 mit Benennung, statt `HEAD` als Pfad zu deuten.

**AC-13: Eigene Störung des Wächters blockiert nie**
Given der Wächter selbst scheitert (Zeitüberschreitung, `git diff --cached` nicht aufrufbar,
defekter Bestand, **nicht auflösbares Werkzeug-Paket `hook_utils`**, unerwarteter Fehler an
einer Stelle ohne eigenen Störungszweig)
When `git commit` ausgeführt wird
Then läuft der Commit durch (Exit-Code 0), und die Störung wird sichtbar gemeldet. Fehlt das
Werkzeug-Paket, wird **nicht geraten**: kein Rückfall auf eine Wortlaut-Prüfung
(`"git commit" in befehl`) — das wäre eine Zweitfassung des Defekts aus #1431 —, sondern
durchlassen und sagen.
- Test: Wegwerf-Repo mit erzwungenem internem Fehler im Wächter, Exit-Code 0 trotz einseitiger
  Neuanlage ohne Begründung. Zusätzlich (Adversary-Funde F001/F004): Wächter-Kopie ohne
  `hook_utils` und mit leerem `HOME` → Exit-Code 0; Wächter-Kopie mit künstlicher Störung
  mitten im Zuschnitt → Exit-Code 0. Der zweite Test ist der Wächter über das äußerste
  Sicherheitsnetz selbst: es ließ sich zuvor ersatzlos entfernen, ohne dass ein Test rot wurde.

**AC-14: Nach dem Prüfdatum schaltet sich der Wächter selbst ab**
Given das Systemdatum liegt nach dem 2026-11-03
When `git commit` mit einer neuen einseitigen Datei ohne Begründung ausgeführt wird
Then läuft der Commit durch (Exit-Code 0), und die Meldung weist auf das abgelaufene Prüfdatum
hin.
- Test: Wegwerf-Repo mit vorgetäuschtem Systemdatum nach 2026-11-03, Exit-Code 0 gemessen.

**AC-15: Die Blockade-Meldung nennt eine namensähnliche Datei auf der Gegenseite**
Given eine neue Datei `compare/CompareTabs.svelte` wird angelegt, während
`trip-detail/TripTabs.svelte` bereits existiert — nach Abschneiden des Seiten-Präfixes bleibt bei
beiden `Tabs.svelte` übrig
When der Commit blockiert
Then enthält die Meldung den Pfad des vermuteten Gegenstücks `trip-detail/TripTabs.svelte`, damit
die Begründung eine konkrete Frage beantwortet statt ins Leere zu schreiben.
- Test: Wegwerf-Repo mit vorbereitetem `trip-detail/TripTabs.svelte`, neue
  `compare/CompareTabs.svelte` committen → Ausgabe enthält `trip-detail/TripTabs.svelte`,
  Exit-Code 2. Gegenprobe: neue `compare/Ortsliste.svelte` ohne Gegenstück → Exit-Code 2, aber
  KEIN erfundener Pendant-Name in der Meldung. Ohne diese Gegenprobe wäre ein Wächter grün, der
  immer irgendetwas nennt.

**AC-16: Die Meldung nennt beide Auswege ausdrücklich**
Given ein Commit wird durch die Sperre blockiert
When die Meldung ausgegeben wird
Then nennt sie sowohl den geteilten Bereich als auch die Begründungszeile als Weg zum
Durchkommen.
- Test: Wegwerf-Repo, blockierter Commit, Prozess-Ausgabe enthält sowohl einen Hinweis auf
  `shared/` als auch auf `gz-eigenstaendig:`, Exit-Code 2.

## Nicht in dieser Scheibe

- **Fängt nur neue Dateien.** Nicht: neue Felder oder Codepfade in bestehenden Dateien, nicht
  identische Logik unter anderem Namen, nicht Doppelungen innerhalb einer Datei.
- **Go bleibt außen vor** — ausgerechnet #1459 D3, einer der beiden Anlassfälle, spielte auf der
  Go-Seite. Ein Go-Pendant der Sperre ist nicht Teil dieser Scheibe.
- **Unpräfigierte Trip-Gegenstücke sind mechanisch unerkennbar**: `src/output/renderers/email/html.py`
  ist das Pendant zu `compare_html.py`, trägt aber kein Präfix. Ein Namenskonventions-Problem, das
  dieser Wächter nicht löst.
- **Die Begründungspflicht prüft Länge, nicht Substanz.** `gz-eigenstaendig: aus Zeitgruenden
  getrennt gebaut` kommt durch. Das ist gewollt — der Ausweg soll nichts verhindern, sondern die
  Entscheidung zitierbar machen — bleibt aber eine bewusste Grenze, kein später nachzutragender
  Mangel. Gegengewicht ist AC-15 (der Wächter nennt das vermutete Gegenstück).
- **Umbenennen mit starkem Umschreiben verlangt eine Begruendung — bewusster Fehlalarm**
  (PO-Entscheidung 2026-08-04 nach Adversary-Fund F007). Der Waechter kann „aehnlicher Inhalt"
  nicht von „dasselbe Bauteil" unterscheiden; die Messreihe unter AC-8 zeigt, dass sich beide
  Reihen bei `R076` ueberschneiden. Waere die Ausnahme grosszuegig, liesse sich jede Neuanlage
  als Umbenennung tarnen: es genuegt, im selben Commit irgendeine Datei derselben Seite zu
  loeschen, deren Grundgeruest die neue teilt — und die Doppelung waere nie geprueft. Von den
  beiden Fehlerrichtungen ist der Fehlalarm die harmlose: er kostet eine Begruendungszeile, die
  Umgehung kostet die Wirkung des Waechters. Deshalb greift die Ausnahme nur bei praktisch
  unveraendertem Inhalt (>= 95 %). Der naheliegende Gegenentwurf — bei einer Neuanlage nach
  einer Loeschung im selben Bereich zu suchen — wurde verworfen: eine beliebige unabhaengige
  Loeschung im selben Bereich wuerde damit jede echte Neuanlage durchwinken.
- **Die Aehnlichkeits-Erkennung laeuft mit der git-Voreinstellung** (`-M`, 50 %). Die
  zwischenzeitliche Absenkung auf 25 % ist zurueckgenommen: sie erzeugte nur mehr zufaellige
  Umbenennungs-Meldungen, und seit die Ausnahme an der gemeldeten Aehnlichkeit haengt, aendert
  eine niedrigere Schwelle am Ergebnis nichts mehr.
- **Ein Commit in einen anderen Projektordner wird nicht geprüft — benannt, nicht
  stillschweigend.** Der Wächter prüft ausschließlich das Verzeichnis, in dem er läuft.
  Deutet ein Anzeichen auf einen anderen Ordner, lässt er durch und sagt es.

  **Begründung (vier Runden an derselben Stelle):** F002 (mehrere `-C` verketten relativ) →
  F006 (`-C` aus dem falschen Abschnitt) → F008 (Hilfsprogramm vor dem Commit) → F010. Jede
  Runde entstand aus „nur noch dieses eine Stück nachbessern", dieselbe Falle wie in #1431.
  Am Ende kannte der Wächter **einen von fünf** gemessenen Wegen in einen anderen Ordner:

  | Weg | erkannt? |
  |---|---|
  | `git -C B commit` | ja |
  | `cd B && git commit` | **nein** — der häufigste von allen |
  | `git --git-dir=B/.git --work-tree=B commit` | **nein** |
  | `GIT_DIR=B/.git GIT_WORK_TREE=B git commit` | **nein** |
  | `(cd B && git commit)` | **nein** |

  Die Frage „wo wird hier committet?" ist nicht zuverlässig zu beantworten — Aliase,
  Skripte, Schleifen, es kommen immer neue Wege dazu. Beantwortbar ist nur „bin ich hier
  zuständig?". Der Rückbau macht den Code **kürzer** (349 → 323 Zeilen) und ersetzt
  Pfad-Auflösung, Abschnitts-Filter und die geliehenen Namen `_git_lex`/`_token`/
  `_git_subcommand_of_segment` durch einen abgeschlossenen Anzeichen-Satz.
- **`cd` gilt immer als Anzeichen — auch innerhalb desselben Projektordners.** `cd frontend
  && git commit` würde also nicht geprüft, obwohl der Vormerk-Stand für den ganzen Ordner
  gilt und die Prüfung richtig gewesen wäre. Gemessen im gesamten Repo: **0** Vorkommen von
  `cd <unterordner> && git … commit`; die vier Vorkommen von `cd` vor einem git-Commit sind
  durchweg `cd /tmp && git -C <repo> commit` aus Testvorlagen, führen also gerade **nicht**
  in denselben Ordner. `cd frontend` kommt vor, aber ausschließlich für die Node-Werkzeuge
  (`npm ci`, `npx playwright`), die dieses Verzeichnis brauchen — git braucht es nie. Die
  beiden denkbaren Unterscheidungen (relativer gegen absoluten Pfad; obersten Ordner beider
  Orte vergleichen) führen zurück in genau die Pfad-Auflösung, an der vier Runden
  gescheitert sind. Die Auslassung ist damit bewusst und dokumentiert; sie kostet im
  schlimmsten Fall eine ungeprüfte Änderung **mit sichtbarem Hinweis**.
- **Kein Klon-Detektor (jscpd)** — laut Ticket erst, wenn diese Scheibe einen belegten Fang hat.
- **`frontend/src/lib/components/edit/**` ist bewusst ausgeschlossen** (siehe „Zuschnitt").
- **Der Abschluss-Hook nach dem PO-Kurzbefehl** wurde vom PO gestrichen (2026-08-04) und ist
  nicht Teil dieses Tickets mehr.

## Regel-Budget

Neues Gate → **Prüfdatum 2026-11-03**. Bis dahin muss ein belegter Fang vorliegen (mindestens ein
Commit, den es zu Recht blockiert hat), sonst Rückbau. AC-14 ersetzt den Rückbau **nicht** — es
sorgt nur dafür, dass ein vergessenes Gate ab dem Prüfdatum niemanden mehr behindert; das
Entfernen der Datei bleibt eine bewusste Entscheidung im Gate-Audit #1197. Bauform übernommen von
`test_naming_gate.py:19`. Bestand zum Vergleich: 31 Hooks in `.claude/hooks/`.

## Umfang

| Datei | Art | Zeilen (geschätzt) |
|---|---|---|
| `.claude/hooks/pendant_gate.py` | ANLEGEN | ~130 |
| `tests/tdd/test_pendant_gate.py` | ANLEGEN | ~250 |
| `.claude/settings.json` | ÄNDERN | ~8 |
| `tests/tdd/test_commit_gate_invocation_forms.py` | ERWEITERN | wenige Zeilen, kein neuer Testfile |

Gesamt ~400 Zeilen Code+Test — über dem Standard-Limit von 250. Anhebung auf 500 nötig, PO-Freigabe
noch einzuholen (analog zur Anhebung bei Scheibe A).

**`.claude/hooks/` ist geschützt** — das Anlegen von `pendant_gate.py` braucht die
Ausnahme-Freigabe zum aktiven Workflow `feat-1481-pendant-sperre` (Laufzeit 1 Stunde, an den
Workflow-Namen gebunden — der Vorgang darf danach nicht neu angelegt werden).

Risiko MITTEL: Die Kernlogik ist einfacher Pfadabgleich + Zeilensuche; das Risiko liegt im
Störungspfad und in der Verdrahtung — bei Scheibe A lagen dort alle drei kritischen
Adversary-Funde. Deshalb ist AC-13 (fail-open) nicht verhandelbar.

## Gemessene Grundlagen (Analyse, nicht Annahme)

**Vier heute doppelt existierende Paare:**

| Vergleichs-Seite | Trip-Seite | Beleg |
|---|---|---|
| `compare-new/CompareNewEditor.svelte` | `trip-new/TripNewEditor.svelte` | gleicher Name bis aufs Präfix |
| `compare-new/compareNewLogic.ts` | `trip-new/tripNewLogic.ts` | dito |
| `compare/CompareTabs.svelte` | `trip-detail/TripTabs.svelte` | dito |
| `renderers/email/compare_html.py` | `renderers/email/html.py` | im Code dokumentiert: `compare_html.py:3` „analog zu ``html.py`` (Trip-Mail)" |

**60-Tage-Messung:** ~120 neu angelegte Dateien in den einseitigen Bereichen, davon ~37 kein
Testcode → die Sperre feuert etwa alle 1,5 Tage.

**Zwölf Paritäts-Tests im Bestand** bewachen Paare, die bereits doppelt existieren — der Beleg,
dass die reine Textregel nicht wirkt.

**Bestand der Bereiche:** compare 79 · trip-detail 61 · compare-new 4 · trip-new 4 · shared 105.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Wächter setzt eine bereits in CLAUDE.md dokumentierte Konvention
  („Trip/Ortsvergleich-Code-Teilung") mechanisch um; er trifft keine neue Architekturentscheidung.

## Changelog

- 2026-08-04: Initial spec created
- 2026-08-04: Nach Adversary-Runde 4 (F010, CRITICAL) — **Rückbau statt Nachbesserung**:
  AC-12 neu gefasst („prüft den eigenen Ordner und sagt, wenn er nicht zuständig ist"),
  `_zielrepo()` samt Pfad-Auflösung ersatzlos gestrichen (349 → 323 Zeilen). F011 und F012
  fallen dadurch von selbst weg. Die vier zugehörigen Alt-Tests sind entfallen, weil sie ein
  absichtlich aufgegebenes Verhalten prüften.
- 2026-08-04: Nach Adversary-Runde 3 (F008, CRITICAL) — AC-12 um die benannte Grenze bei
  nicht zuordenbarem `-C` ergänzt; unter „Nicht in dieser Scheibe" die Entscheidung gegen
  eine Liste von Hilfsprogrammen festgehalten, mit F002/F006/F008 als Beleg.
- 2026-08-04: Nach Adversary-Runde 2 (erneut BROKEN) — AC-8 auf „Inhalt praktisch unverändert"
  verengt (F007, PO-Entscheidung: Fehlalarm statt Umgehung) samt Messreihe; AC-12 um die
  abschnittsweise `-C`-Auflösung ergänzt (F006).
- 2026-08-04: Nach Adversary-Lauf (VERDICT BROKEN) präzisiert — AC-12 um die Verkettung
  mehrerer `-C`, AC-13 um fehlendes Werkzeug-Paket und das äußerste Sicherheitsnetz; die
  Ähnlichkeitsschwelle der Umbenennungs-Erkennung und ihre Grenze unter „Nicht in dieser
  Scheibe" festgehalten.
