---
entity_id: fix_1396_s2_store_scope_guard
type: module
created: 2026-08-01
updated: 2026-08-01
status: implemented
version: "1.0"
tags: [go-api, multi-user, tenant-isolation, ratchet, regression-guard]
---

<!-- Issue #1396 — Scheibe S2 von 2. S1 (Reparatur + Verhaltensnachweis) ist
     ausgeliefert (Commit e03fde9d). Diese Scheibe sichert das Ergebnis von S1
     strukturell ab, statt es erneut zu belegen. -->

# Fix #1396 S2 — Wächter gegen den geteilten Store-Parameter

## Approval

- [x] Approved — PO-go 2026-08-01 (8 ACs freigegeben; LoC-Budget auf 500
  angehoben, weil der Scan-Kern mit Scope-Auflösung ~230 Zeilen braucht)

## Purpose

S1 hat 25 Stellen in `internal/handler/` repariert, an denen ein Handler die
Nutzerkennung per `s = s.WithUser(...)` in eine von allen gleichzeitigen
Anfragen **geteilte** Closure-Variable schrieb — ein Cross-User-Datenleck über
`data/users/<user_id>/`. Diese Scheibe verhindert den Rückfall: ein Go-Test
liest `internal/handler/*.go` über `go/parser`+`go/ast` und meldet jede
Zuweisung an einen äußeren Funktionsparameter innerhalb einer Closure — egal
mit welchem Variablennamen und welcher aufgerufenen Methode. Ohne diese Scheibe
schützt nur die Sorgfalt der nächsten Änderung, nicht die Struktur.

## Source

- **File:** `internal/handler/store_scope_guard_test.go` (NEU) — der Wächter
- **Identifier:** `go/ast`-Analyse — Fund ist jede `ast.AssignStmt` mit
  `Tok == token.ASSIGN` (also `=`, **nicht** `token.DEFINE`/`:=`), deren linke
  Seite ein einfacher `*ast.Ident` ist, der (a) zur **Ebene 0** der äußeren
  `ast.FuncDecl`/`ast.FuncLit` gehört (s. u.), (b) die Zuweisung innerhalb eines
  verschachtelten `ast.FuncLit` liegt und (c) an dieser Stelle nicht durch eine
  zwischenzeitliche eigene `:=`-Deklaration desselben Namens verdeckt ist
- **Ebene 0 — zwei Klassen, eine gemeinsame Bedingung:**
  - **Signatur** (Receiver, Parameter, **benannter Rückgabewert**)
  - **Lokale Deklaration direkt im Rumpf** der äußeren Funktion (`:=` **und**
    `var`)

  Für **beide** Klassen gilt dieselbe zusätzliche Bedingung: Fund nur, wenn die
  schreibende Closure die äußere Funktion **per `return` verlässt** — also der
  `ast.FuncLit` selbst in einem `ast.ReturnStmt` der äußeren Funktion vorkommt
  oder in einer Variablen liegt, die dort zurückgegeben wird
  (`inner := func…; return inner()`). Begründung unter „Implementation
  Details" → *Warum die `return`-Bedingung, und warum für beide Klassen*.
- **Vorlage:** `internal/handler/trip.go:10-28` (Erklärkommentar aus #1395 S2,
  Ziel der Fehlermeldung); `internal/mail/recipient_parity_test.go` (einziger
  vorhandener Ratschen-Test in Go — Aufbau, Fehlermeldungsstil, Ausnahme-Ventil
  mit Mindest-Begründungslänge; bewusst **ohne** `exec.Command`/`git show` zur
  Testzeit — Vorbild für die Fixture-Führung dieser Spec)

Schicht: **Go-API** (`internal/`). Kein Python-Core, kein Frontend beteiligt.

## Estimated Scope

- **LoC:** 691 (added), 1 CREATE, 0 MODIFY am Produktionscode. Aufteilung:
  ~250 Scan-Kern samt Scope- und `return`-Auflösung, der Rest Fixture-
  Konstanten und Tests (AC-2/AC-3 brauchen je einen wörtlichen Auszug, die
  Herkunfts-Klassen je eine eigene Fixture samt Abgrenzung)
- **Files:** 1 CREATE (`internal/handler/store_scope_guard_test.go`)
- **Effort:** low (Muster durch S1 und `recipient_parity_test.go` bereits
  erprobt, keine Reparatur an Produktionscode nötig — der ist seit S1 sauber)

Budget-Verlauf: 250 → 500 (PO-go 2026-08-01, Scan-Kern mit Scope-Auflösung)
→ **700 nötig**, nachdem der Adversary-Lauf zwei Lücken (lokale Variable der
äußeren Funktion, benannter Rückgabewert) und die dafür erforderliche
`return`-Auflösung samt Abgrenzungs-Testfällen nachgezogen hat. Stand nach der
zweiten Adversary-Runde (F004): **691 von 700**.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go/parser`, `go/ast`, `go/token` (Standardbibliothek) | intern | liest Quelltext als Syntaxbaum, statt ihn zu durchsuchen — Grund: Risiko 2 der Analyse, eine Textsuche nach `s = s.WithUser(middleware.` übersähe die Zwischenvariablen-Form |
| Fix #1396 S1 (Commit e03fde9d) | Vorbedingung | stellt den Ausgangszustand her, an dem der Wächter grün ist (0 Treffer in allen 106 Dateien von `internal/handler/`); außerdem Quelle der AC-2/AC-3-Fixture-Auszüge über `e03fde9d~1` |
| `internal/handler/trip.go:10-28` | Referenz | Ziel, auf das die Fehlermeldung des Wächters verweist, wenn er rot wird |
| `internal/mail/recipient_parity_test.go` | Vorbild | Bauform für Ausnahme-Ventil mit Mindest-Begründungslänge, Fehlermeldungsstil, Prüfung erzeugter Meldungstexte statt Datei-String-Suche; bewusst kein `exec.Command`/`git show` zur Testzeit |
| `docs/specs/modules/fix_1396_store_scope_race.md` (S1) | Vorgänger-Spec | Quelle der 6 Beispieldateien und der Analyse-Risiken, auf die diese Spec aufbaut |

## Implementation Details

**Reichweite (Tech-Lead-Entscheidung):** Der Wächter prüft **jede Funktion**
in `internal/handler/`, nicht nur Konstruktoren mit Rückgabetyp
`http.HandlerFunc`. Ein neuer Zugriffsweg, der die Handler-Form leicht
abwandelt (anderer Rückgabetyp, zusätzliche Zwischenebene), würde bei einer
engeren Prüfung unbemerkt durchrutschen — und genau der Rückfall über eine
Kopiervorlage ist der Grund, warum dieser Wächter existiert.

```
für jede *.go-Datei in internal/handler/:
    Baum = go/parser.ParseFile(...)   // Parse-Fehler ⇒ t.Fatalf, NICHT überspringen
    für jede ast.FuncDecl/FuncLit F im Baum:
        Signatur(F) = Receiver + Parameter + benannte Rückgabewerte von F
        Lokale(F)   = Namen aus :=/var DIREKT im Rumpf von F
        Entkommend(F) = FuncLits in einem return von F, plus FuncLits, die in
                        einer dort zurückgegebenen Variablen liegen. Beim
                        Zuweisungs-Weg zählt nur eine DIREKTE Umhüllung: ein
                        Aufruf mit GENAU EINEM Argument ("http.HandlerFunc(func…)",
                        syntaktisch eine Typumwandlung), beliebig geschachtelt.
                        Ein Aufruf mit mehreren Argumenten ("reduce(werte, func…)")
                        wird NICHT durchsucht — er reicht die Closure nur hinein.
        für jedes verschachtelte ast.FuncLit L innerhalb von F:
            für jede ast.AssignStmt A innerhalb von L:
                wenn A.Tok != token.ASSIGN: weiter          // := bleibt stumm
                für jede linke Seite lhs von A:
                    wenn lhs kein einfacher *ast.Ident: weiter
                    wenn lhs.Name weder in Signatur(F) noch in Lokale(F): weiter
                    wenn äußerstes L NICHT in Entkommend(F): weiter
                    wenn lhs.Name seit F.Body-Anfang bis zu A
                         durch eine :=-Deklaration verdeckt: weiter
                    wenn Zeile von A ein gültiges
                         "// gz-closure-param-write: <Begründung>"
                         trägt (>= 15 sinnvolle Zeichen, Buchstaben/Ziffern
                         gezählt wie in recipient_parity_test.go): weiter
                    sonst: melde Fund mit Bezeichnung, Zeile, Parametername
```

**Warum die `return`-Bedingung, und warum für beide Klassen.** Der Fehler aus S1
entsteht dadurch, dass ein Konstruktor einen **dauerhaft registrierten**
Zugriffsweg zurückgibt und die zurückgegebene Closure in eine Variable schreibt,
die es nur einmal gibt. Ob diese Variable ein Parameter oder eine lokale
Variable des Rumpfes ist, macht dabei keinen Unterschied — die Zwischenform

```go
func Build(sIn *store.Store) http.HandlerFunc {
	s := sIn                    // lokal, kein Parameter
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
	}
}
```

ist derselbe Fehler. Lokale Variablen **ohne** die `return`-Bedingung mitzuzählen
wäre aber zu grob: Es träfe eines der häufigsten harmlosen Go-Idiome —

```go
zaehler := 0
addiere := func() { zaehler = zaehler + 1 }   // verlässt die Funktion nie
```

— strukturell identisch, aber ungefährlich, weil die Closure die Funktion nie
verlässt und nirgends dauerhaft gehalten wird. **Gemessen:** die grobe Fassung
meldete auf dem echten Stand von `internal/handler/` **12 Funde**, alle in
`_test.go`-Dateien (aufzeichnende Fake-Server wie `lastURL = r.URL.RequestURI()`
und der Wächter selbst), **keinen einzigen** im Produktionscode — also
ausschließlich Lärm. Ein Wächter, der so etwas anmeckert, wird abgeschaltet und
schützt dann gar nichts mehr. Mit der `return`-Bedingung: **0 Funde** auf
demselben Stand.

Dieselbe Bedingung gilt **auch für die Signatur-Klasse** — anfangs galt sie dort
nicht, weil eine Zuweisung an einen Parameter aus einer Closure heraus „unter
keinen Umständen richtig" schien. Der Adversary-Lauf (Befund F004) hat das
widerlegt: Das von Go selbst empfohlene Panik-Auffang-Idiom schreibt per
Sprachdesign in einen benannten Rückgabewert, und zwar aus einer Closure heraus.

```go
func DoSomething() (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic: %v", r)   // richtig, aber wurde gemeldet
		}
	}()
	...
}
```

Diese Closure läuft beim Rücksprung ab und verlässt die Funktion nie — die
`return`-Bedingung trennt sie sauber von dem Fall, in dem ein benannter
Rückgabewert **herausgereicht** wird (AC-11). Für Receiver und Parameter kostet
die Vereinheitlichung nichts: Ein Handler-Konstruktor gibt seinen Zugriffsweg
zurück, damit greift die Bedingung dort ohnehin.

Das Ausnahme-Ventil `// gz-closure-param-write: <Begründung>` folgt dem
Vorbild `# gz-main-path:` aus `tests/tdd/test_repo_path_hardcoding_ratchet.py`
(dokumentiert in CLAUDE.md, Abschnitt „Pfadregel"): eine begründete Ausnahme
steht **an der Zeile** des Fundes, nicht in einer separaten Liste, und eine zu
kurze oder fehlende Begründung zählt nicht als Ausnahme. Heute existiert
**keine** solche Ausnahme in `internal/handler/` — das Register startet leer.

**Scan-Kern ist quelltextbasiert, nicht dateipfadbasiert.** Die eigentliche
Prüffunktion nimmt einen beliebigen Go-Quelltext (`[]byte`/`string`) plus eine
Bezeichnung für Fehlermeldungen entgegen und liefert eine Liste von Funden.
`go test` ruft sie für jede echte Datei in `internal/handler/` auf; die Tests
für AC-2 bis AC-5 rufen dieselbe Funktion direkt mit Fixture-Quelltext auf,
**ohne** zur Testzeit `git show` oder einen anderen Prozess auszuführen — ein
Test, der an Repo-Historie und Arbeitsbaum hängt, bricht im Worktree oder in
einem flachen Klon (Vorbild `recipient_parity_test.go`: keine
`exec.Command`-Aufrufe dort).

**Fixtures sind String-Konstanten, keine übersetzbaren Dateien im gescannten
Verzeichnis.** Der Wächter scannt alle `*.go` in `internal/handler/`,
`_test.go` eingeschlossen. Lägen die Fixtures für AC-2 bis AC-5 dort als echte
Go-Dateien, meldete der Wächter sich selbst rot. Sie gehören deshalb
ausschließlich als String-Konstanten in die Testdatei (oder alternativ unter
`testdata/`, das Go grundsätzlich nicht übersetzt — für diese Scheibe nicht
nötig, String-Konstanten reichen und halten das LoC-Budget klein).

Für AC-2 und AC-3 werden die Fixture-Konstanten **einmalig** von Hand aus den
echten Vor-S1-Fassungen gewonnen (`git show
e03fde9d~1:internal/handler/location.go` bzw. `...compare_preset.go`,
außerhalb des Tests ausgeführt) — jeweils **nur die betroffene Handler-
Funktion samt ihrer Zuweisungszeile**, nicht die ganze Datei (258 bzw. 663
Zeilen im Vor-S1-Stand, das würde das LoC-Limit sprengen). Jede dieser beiden
Konstanten trägt einen Kommentar mit dem Herkunfts-Commit.

Die Fehlermeldung eines Fundes nennt Bezeichnung, Zeile, Parametername und
verweist wörtlich auf `internal/handler/trip.go:10-28` sowie auf die
Ersetzung `=` durch `:=` als erwartete Reparatur — nach dem Vorbild der
Fehlermeldungen in `recipient_parity_test.go` (z. B.
`TestAC7FehlendeFalltabelleBrichtLautAb`), die stets erklären, *warum* etwas
ein Fund ist und was zu tun ist.

## Expected Behavior

- **Input:** der Inhalt aller `*.go`-Dateien unter `internal/handler/`
  (Produktions- und `_test.go`-Dateien gemeinsam gescannt, wie in der
  Ausgangsmessung), zur Testzeit über `go test` gelesen
- **Output:** `go test` grün bei 0 Funden; bei ≥1 Fund `t.Fatalf` mit einer
  Liste `Bezeichnung:Zeile — Parametername` und dem Verweis auf `trip.go:10-28`
- **Side effects:** keine. Der Wächter ändert nichts an Produktionscode, keine
  Migration, kein Datenschema betroffen.

## Acceptance Criteria

- **AC-1:** Given der Stand nach Fix #1396 S1 (Commit e03fde9d) / When der
  Wächter gegen `internal/handler/` läuft / Then meldet er 0 Funde und der
  Test ist grün.
  - Test: `go test -run TestStoreScopeGuard ./internal/handler/...` gegen den
    aktuellen Arbeitsstand, Exit 0.

- **AC-2:** Given ein wörtlicher Auszug (Handler-Funktion samt der
  betroffenen Zuweisungszeile, nicht die ganze Datei) aus der echten Vor-S1-
  Fassung von `internal/handler/location.go` mit der Direktaufruf-Form
  `s = s.WithUser(middleware.UserIDFromContext(r.Context()))` innerhalb einer
  Closure / When der Scan-Kern des Wächters auf diesen Auszug angewendet wird
  / Then meldet er genau diese Zuweisung mit der Zeilennummer, an der sie
  **im Auszug** steht.
  - Test: der Auszug wird **einmalig** aus `git show
    e03fde9d~1:internal/handler/location.go` entnommen (nicht zur Testzeit
    ausgeführt) und als String-Fixture-Konstante mit Kommentar zum
    Herkunfts-Commit in der Testdatei abgelegt; der Scan-Kern meldet einen
    Fund an der erwarteten Zeile des Fixtures.

- **AC-3:** Given ein ebenso gewonnener, wörtlicher Auszug aus der echten
  Vor-S1-Fassung von `internal/handler/compare_preset.go` mit der
  Zwischenvariablen-Form `s = s.WithUser(userID)` (Zeile 183 im
  Ursprungsstand) / When der Scan-Kern darauf angewendet wird / Then meldet
  er auch diese Stelle — der Punkt, an dem eine reine Textsuche nach
  `s = s.WithUser(middleware.` versagt hätte.
  - Test: derselbe Entnahmeweg (`git show e03fde9d~1:...`, einmalig, als
    String-Fixture-Konstante mit Herkunfts-Kommentar), Scan-Kern meldet einen
    Fund an der erwarteten Zeile des Fixtures. Zusammen mit AC-2 belegt dies:
    **beide** Formen werden erkannt. Vollständigkeit über alle 25
    Produktionsstellen ist bereits durch die Ausgangsmessung (0 Treffer nach
    S1) abgedeckt und ist nicht Gegenstand dieses ACs.

- **AC-4:** Given zwei synthetische Fixture-Quelltexte (String-Konstanten),
  die dasselbe Muster mit unterschiedlichem Variablennamen und
  unterschiedlicher aufgerufener Methode nachbilden (z. B.
  `store = store.ForTenant(id)` statt `s = s.WithUser(userID)`) / When der
  Scan-Kern darüber läuft / Then meldet er beide — der Wächter hängt am
  Muster „Zuweisung an äußeren Parameter innerhalb einer Closure", nicht an
  `s` oder an `WithUser`.
  - Test: zwei Fixture-Quelltexte mit variierten Namen, beide erzeugen einen
    Fund am Scan-Kern.
  - Erweiterung auf die **Herkunft** der Variable (Adversary-Nachtrag, gleiche
    Stoßrichtung: der Wächter hängt am Muster, nicht an der Schreibweise):
    `TestStoreScopeGuardErkenntLokaleVariableEntkommenderClosure` (lokale
    Variable per `:=`, per `var`, und über eine Zwischenstufe),
    `TestStoreScopeGuardErkenntBenanntenRueckgabewert` sowie als Abgrenzung
    `TestStoreScopeGuardSchweigtBeiNurOertlichBenutzterClosure`.

- **AC-5:** Given eine Fund-Zeile trägt den Kommentar
  `// gz-closure-param-write: <Begründung mit mindestens 15 sinnvollen
  Zeichen>` / When der Scan-Kern darüber läuft / Then meldet er diese Zeile
  nicht. Given dieselbe Zeile trägt keinen oder einen zu kurzen Kommentar
  (unter 15 sinnvollen Zeichen) / When der Scan-Kern darüber läuft / Then
  meldet er sie wie jeden anderen Fund.
  - Test: drei Fixture-Varianten derselben Fund-Zeile (ohne Kommentar, mit
    zu kurzem Kommentar, mit ausreichendem Kommentar) am Scan-Kern; nur die
    dritte bleibt unentdeckt.

- **AC-6:** Given ein Fixture-Quelltext mit einem echten Fund (z. B. der
  Auszug aus AC-2) / When der Scan-Kern läuft und daraus die Fehlermeldung
  erzeugt wird / Then enthält die **tatsächlich erzeugte** Meldung
  Bezeichnung, Zeilennummer und Parametername des Fundes, den Verweis auf
  `internal/handler/trip.go:10-28` sowie den Hinweis auf die erwartete
  Reparatur (`=` → `:=`) — geprüft an der erzeugten Meldung selbst, nicht an
  einer Zeichenkette in der Testdatei.
  - Test: Assertion auf den vom Scan-Kern zurückgegebenen bzw. daraus
    formatierten Meldungstext, der alle genannten Bestandteile prüft.

- **AC-7:** Given eine Zeile mit anfragelokaler Deklaration `s := s.WithUser(
  ...)` (`token.DEFINE`, das reparierte Muster aus S1) / When der Wächter
  darüber läuft / Then meldet er sie nicht — sonst wäre der Wächter direkt
  nach S1 rot und damit als Ratsche unbrauchbar.
  - Test: Fixture mit `:=`-Form am Scan-Kern, 0 Funde.

- **AC-8:** Given eine Datei in `internal/handler/` lässt sich nicht als
  gültiges Go parsen (Syntaxfehler) / When der Wächter läuft / Then bricht er
  mit einem klaren `t.Fatalf` ab, statt die Datei stillschweigend zu
  überspringen und grün zu melden.
  - Test: Fixture mit absichtlich ungültigem Go-Quelltext, `go/parser`-Fehler
    führt zu explizitem Testfehlschlag, nicht zu 0 Funden.

Die folgenden drei Kriterien sind aus dem Adversary-Lauf vom 2026-08-01
hinzugekommen (Verdict BROKEN, Befunde F001/F002).

- **AC-9:** Given ein Konstruktor legt die geteilte Variable als **lokale**
  Deklaration an (`s := sIn` oder `var s = sIn`) statt sie als Parameter zu
  führen, und die zurückgegebene Closure überschreibt sie per `=` / When der
  Wächter darüber läuft / Then meldet er den Fund — der Schaden ist derselbe
  wie beim Parameter-Fall, nachgewiesen unter `go test -race` mit 80
  gleichzeitigen Anfragen zweier Nutzer, in einer Variante mit tatsächlichem
  Cross-User-Treffer.
  - Test: `TestStoreScopeGuardErkenntLokaleVariableEntkommenderClosure` —
    Fixtures für beide Deklarationsformen, je ein Fund an der erwarteten
    Zeile. Zusätzlich an echtem Code gegengeprobt: `LocationsHandler` in
    `internal/handler/location.go` versuchsweise auf diese Form umgebaut →
    Fund an `location.go:32`, danach zurückgebaut.

- **AC-10:** Given eine Closure beschreibt eine lokale Variable der äußeren
  Funktion, **verlässt diese aber nie** (kein `return`, nur örtlicher Aufruf —
  das gewöhnliche Zähler-Idiom) / When der Wächter darüber läuft / Then meldet
  er sie **nicht**. Ohne diese Abgrenzung wäre die Verschärfung aus AC-9 nicht
  tragfähig: Sie träfe verbreiteten, harmlosen Code, und ein Wächter, der
  grundlos meldet, wird abgeschaltet.
  - Test: `TestStoreScopeGuardSchweigtBeiNurOertlichBenutzterClosure` —
    dieselbe Zuweisungsform wie in AC-9, Closure jedoch ohne `return`,
    0 Funde.

- **AC-11:** Given die geteilte Variable ist ein **benannter Rückgabewert** der
  äußeren Funktion, den eine verschachtelte, per `return` herausgereichte
  Closure per `=` überschreibt / When der Wächter darüber läuft / Then meldet er
  den Fund — benannte Rückgabewerte gehören zur Signatur und existieren wie
  Parameter genau einmal je Aufruf.
  - Test: `TestStoreScopeGuardErkenntBenanntenRueckgabewert` — Fixture mit
    benanntem Rückgabewert, ein Fund an der erwarteten Zeile.

Das folgende Kriterium ist aus der zweiten Adversary-Runde vom 2026-08-01
hinzugekommen (Befund F004).

- **AC-12:** Given eine Closure schreibt in einen **benannten Rückgabewert**,
  wird aber per `defer` registriert und läuft damit beim Rücksprung ab, ohne die
  Funktion je zu verlassen (das von Go empfohlene Panik-Auffang-Idiom) / When
  der Wächter darüber läuft / Then meldet er sie **nicht**. Ohne dieses
  Kriterium schlüge der Wächter auf korrektem, verbreitetem Code an; die
  Abgrenzung zu AC-11 leistet die `return`-Bedingung, die jetzt für Signatur-
  und lokale Namen gleichermaßen gilt.
  - Test: `TestStoreScopeGuardSchweigtBeiDeferAufBenanntemRueckgabewert` —
    Fixture mit `defer func(){ err = fmt.Errorf(...) }()` und benanntem
    Rückgabewert `err`, 0 Funde.

Das folgende Kriterium ist aus der dritten Adversary-Runde vom 2026-08-01
hinzugekommen (Befund F005).

- **AC-13:** Given eine Closure wird einem Hilfsaufruf mit **mehreren
  Argumenten** übergeben (`summe := reduce(werte, func(acc int) int { … })`),
  der sie nur synchron benutzt und etwas anderes als die Closure zurückgibt,
  und das Ergebnis dieses Aufrufs steht in einem `return` / When der Wächter
  darüber läuft / Then meldet er sie **nicht** — zurückgegeben wird das
  Ergebnis, nicht die Closure. Die Entkommens-Erkennung schält deshalb nur
  Aufrufe mit genau einem Argument ab (Typumwandlungen wie
  `http.HandlerFunc(func…)`), keine mehrargumentigen.
  - Test: `TestStoreScopeGuardSchweigtBeiMehrargumentigemHilfsaufruf` — Fixture
    mit `reduce(werte, func…)`, 0 Funde. Gegenprobe gemessen: mit der vorherigen
    Tiefensuche über den zugewiesenen Ausdruck lieferte dieselbe Fixture 1 Fund.

## Known Limitations

- **Vier Muster werden bewusst nicht erkannt** (an synthetischen Beispielen
  gemessen, kein Fund heute in `internal/handler/`):
  - Mehrfachzuweisung `x, s = 1, s.WithUser(u)` — die linke Seite hat mehr
    als ein Ziel, das Muster prüft nur Einzelzuweisungen.
  - Zuweisung über einen Zeiger `*s = ...` — die linke Seite ist ein
    `*ast.StarExpr`, kein einfacher `*ast.Ident`.
  - Zuweisung an ein Feld `wr.Store = ...` — die linke Seite ist ein
    `*ast.SelectorExpr`, kein einfacher `*ast.Ident`.
  - Weitergabe an eine Hilfsfunktion, die per Zeiger mutiert
    (`helperMutate(&s)`) — das ist überhaupt keine `ast.AssignStmt`, sondern
    ein Funktionsaufruf; der Wächter prüft keine Aufrufe.

  Diese vier Formen sind bewusst nicht abgedeckt: Sie kommen in
  `internal/handler/` heute nachweislich nicht vor (0 Treffer bei der
  Gegenprobe), und ihre Abdeckung würde den Wächter deutlich komplexer machen,
  ohne einen heute bestehenden Fehler zu fangen. Wer sie später braucht, weiß
  durch diesen Absatz wenigstens, dass sie fehlen.

- **Fünf Fluchtwege sieht der Wächter nicht, weil er nur `return` kennt.** Die
  `return`-Bedingung gilt seit Befund F004 einheitlich für **alle** Klassen
  (Receiver, Parameter, benannter Rückgabewert, lokale Deklaration). Eine
  Closure, die die äußere Funktion auf einem anderen Weg verlässt, bleibt damit
  unbemerkt — sie ist genauso langlebig und genauso gefährlich:
  - **Zuweisung an eine Paket-Variable** — `globalerHandler = func(){ s = … }`.
  - **Closure direkt als Argument** — `mux.HandleFunc("/x", func(w, r){ s = … })`;
    die Closure wird registriert, ohne je zurückgegeben zu werden.
  - **Ablage in einem Struct-Feld** — `srv.Handler = func(){ s = … }`.
  - **Versand über einen Kanal** — `auftraege <- func(){ s = … }`.
  - **`defer`-Registrierung mit Weiterreichung** — anders als das reine
    Panik-Auffang-Idiom aus AC-12, das nur beim Rücksprung abläuft.

  **Warum das offen bleibt — der Weg ist versperrt, nicht bloß ungeprüft.** Die
  naheliegende Gegenmaßnahme (Beweislast umkehren: alles gilt als entkommend,
  was nicht nachweislich örtlich bleibt) wurde gebaut und **gemessen**.
  Ergebnis: **11 Funde** auf echtem Code, davon **4 Fehlalarme im Wächter
  selbst**, weil ein Rückruf an eine synchron abarbeitende Funktion
  (`ast.Inspect`, `sort.Slice`, `filepath.Walk`) syntaktisch nicht von einer
  dauerhaft registrierten Closure zu unterscheiden ist: `ast.Inspect(x, f)` und
  `mux.HandleFunc(p, f)` haben dieselbe Form. Eine Namensliste synchroner
  Standardfunktionen wäre nie vollständig — jede fremde Bibliothek und jeder
  eigene Helfer müssten hinein. Eine tragfähige Abdeckung bräuchte
  Datenfluss-Analyse (Escape-Analyse) statt einer rein syntaktischen Prüfung;
  das sprengt Zuschnitt und Budget dieser Scheibe.

  **Heute ist die Grenze keine reale Lücke.** Alle Zugriffswege werden über
  `return` registriert: `internal/router/router.go` folgt durchgehend dem Muster
  `r.Get("/api/x", handler.XHandler(deps.Store))`, der Konstruktor
  `XHandler` gibt seine `http.HandlerFunc` also zurück — genau die Form, die der
  Wächter erkennt. Kommt später ein Zugriffsweg dazu, der seine Closure
  registriert statt sie zurückzugeben, fällt er durch dieses Raster; dann ist
  dieser Absatz der Einstiegspunkt.

- **Ein Akkumulator in einer zurückgegebenen Closure wird gemeldet — gewollt.**
  Wer in einer Hilfsfunktion eine Closure baut, die eine lokale Variable
  fortschreibt (`summe = summe + v`), und diese Closure **zurückgibt**, bekommt
  einen Fund, obwohl weder Handler noch Nebenläufigkeit im Spiel sind. Das ist
  die bewusst in Kauf genommene Folge der Reichweite: syntaktisch ist dieser
  Fall von der gefährlichen Form nicht zu unterscheiden, und die zurückgegebene
  Closure teilt die Variable tatsächlich über alle ihre Aufrufe hinweg. Der Weg
  ist dann das Ausnahme-Ventil `// gz-closure-param-write: <Begründung>` an der
  Fundzeile, nicht das Verengen des Musters. Bleibt die Closure dagegen
  innerhalb ihrer Funktion, schweigt der Wächter (Testfall
  `TestStoreScopeGuardSchweigtBeiNurOertlichBenutzterClosure`).

- **Ein einargumentiger Hilfsaufruf, der die Closure nur synchron benutzt,
  erzeugt weiterhin einen Fehlalarm.** AC-13 hat die Entkommens-Erkennung auf
  Umhüllungen mit **genau einem** Argument verengt und damit die häufige Form
  `reduce(werte, func…)` entschärft. Wer dieselbe Closure aber an einen Helfer
  mit nur einem Parameter gibt (`ergebnis := jedesElement(func(x int) int { s =
  … })`) und `ergebnis` zurückgibt, bekommt einen Fund, obwohl die Closure die
  Funktion nie verlässt. Die Verengung **verkleinert** die Fehlalarm-Klasse, sie
  beseitigt sie nicht. Der Grund ist derselbe wie bei der weiter oben
  verworfenen Beweislast-Umkehr: syntaktisch ist „gibt die Closure weiter" nicht
  von „benutzt sie synchron" zu unterscheiden — `http.HandlerFunc(f)` und
  `jedesElement(f)` haben dieselbe Form. Eine saubere Trennung bräuchte
  Datenfluss-Analyse. Der Weg im Einzelfall ist das Ausnahme-Ventil
  `// gz-closure-param-write: <Begründung>` an der Fundzeile.

- **Der Wächter belegt Vollständigkeit der Form, nicht Korrektheit des
  Verhaltens.** Dass eine `:=`-Deklaration unter echter Gleichzeitigkeit
  tatsächlich trägt, weist S1s AC-1/AC-2 nach
  (`store_scope_race_test.go`, Wettlauf-Detektor). Dieser Wächter stellt nur
  sicher, dass die reparierte *Form* nicht wieder in die geteilte Form
  zurückfällt.

- **Prüfdatum nach Regel-Budget (CLAUDE.md „Regel-Budget"): 2026-10-29.**
  S2 ist ein neuer Pflicht-Wächter. Kein nachweisbarer Fang (kein verhinderter
  echter Rückfall) bis zu diesem Datum ⇒ Rückbau.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche berührt. Die Mandantentrennung über
  `s.WithUser(middleware.UserIDFromContext(r.Context()))` ist in CLAUDE.md
  bereits als verbindlich festgehalten; dieser Wächter sichert den in S1
  hergestellten Zustand strukturell ab, trifft aber keine neue Entscheidung.

## Changelog

- 2026-08-01: Initial spec created (Scheibe S2 von 2 zu Issue #1396)
- 2026-08-01: AC-2/AC-3 auf wörtliche, einmalig entnommene Auszüge umgestellt
  (kein `git show` zur Testzeit, keine ganzen Dateien); AC-6 von Text-Check zu
  Verhaltensprüfung der tatsächlich erzeugten Meldung umformuliert; Fixtures
  explizit als String-Konstanten festgeschrieben, niemals als übersetzbare
  Dateien im gescannten Verzeichnis; Estimated Scope angepasst
  (PO-Feedback über Team-Lead)
- 2026-08-01: Adversary-Verdict BROKEN nachgezogen — Ebene 0 um **benannte
  Rückgabewerte** (unbedingt) und **lokale Deklarationen des Funktionsrumpfes**
  (`:=` und `var`, nur bei per `return` entkommender Closure) erweitert; beide
  Formen waren zuvor blinde Flecken. Die `return`-Bedingung stammt aus der
  Messung auf echtem Code: ohne sie 12 Funde, sämtlich Lärm in Testdateien;
  mit ihr 0. Known Limitations um die nicht-`return`-Entkommenswege und um den
  gewollt gemeldeten Akkumulator in zurückgegebenen Closures ergänzt.
  Verdeckungslogik unverändert — die Erweiterung hat sie nicht verlangt.
- 2026-08-01 (zweite Adversary-Runde, Befund F004): Die `return`-Bedingung gilt
  jetzt für **alle** Klassen, Signatur eingeschlossen — zuvor war sie nur für
  lokale Deklarationen aktiv, wodurch der Wächter das von Go empfohlene
  Panik-Auffang-Idiom (`defer func(){ err = … }()` auf benanntem Rückgabewert)
  meldete. Neu: **AC-12** mit Abgrenzungstest; **AC-11** auf „per `return`
  herausgereichte Closure" präzisiert. Dabei fiel eine Lücke der
  Entkommens-Erkennung auf: ein FuncLit in einer Umhüllung
  (`h = http.HandlerFunc(func…)`) galt nicht als entkommend, wodurch AC-11 still
  wurde; die Erkennung durchsucht den zugewiesenen Ausdruck jetzt genauso wie
  die `return`-Ergebnisse. Known Limitations um die **fünf Fluchtwege** und die
  **Messung der verworfenen Beweislast-Umkehr** ergänzt (11 Funde, davon 4
  Fehlalarme im Wächter selbst — `ast.Inspect(x, f)` ist syntaktisch nicht von
  `mux.HandleFunc(p, f)` zu unterscheiden). Gemessen: weiterhin **0 Funde** auf
  echtem Code, alle 12 Tests grün.
- 2026-08-01 (dritte Adversary-Runde, Befund F005): Die in der zweiten Runde
  eingeführte Umhüllungs-Suche war zu weit — sie durchsuchte den zugewiesenen
  Ausdruck **beliebig tief** und ließ damit jede Closure als entkommend gelten,
  sobald die Zielvariable irgendwo zurückgegeben wurde, auch wenn nur ihr
  *Ergebnis* zurückgeht (`summe := reduce(werte, func…); return summe`). Das war
  dieselbe Fehlerklasse wie bei der verworfenen Beweislast-Umkehr, über die
  AC-11-Erweiterung zurückgekehrt. Neu: Abgeschält werden nur noch Aufrufe mit
  **genau einem** Argument (Typumwandlungen, beliebig geschachtelt); ein nackter
  FuncLit als rechte Seite bleibt unverändert erfasst. **AC-13** mit
  Abgrenzungstest ergänzt, Pseudocode `Entkommend(F)` präzisiert, Known
  Limitations um den verbleibenden **einargumentigen** Fehlalarm ergänzt.
  Gemessen: weiterhin **0 Funde** auf echtem Code (107 Dateien), alle 13 Tests
  grün, AC-11 unverändert grün. Gegenprobe: mit der alten Tiefensuche lieferte
  die AC-13-Fixture 1 Fund. Datei jetzt **724 Zeilen** — über dem
  Workflow-Budget von 700, Anhebung liegt beim Product Owner.
