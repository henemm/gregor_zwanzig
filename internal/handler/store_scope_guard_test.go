package handler

// Issue #1396 Scheibe S2 — Waechter gegen den geteilten Store-Parameter.
//
// Spec: docs/specs/modules/fix_1396_s2_store_scope_guard.md
//
// S1 hat 25 Stellen in diesem Paket von "s = s.WithUser(...)" auf ":=" gestellt.
// "=" schreibt in die von allen gleichzeitigen Anfragen GETEILTE Closure-
// Variable (Begruendung ausfuehrlich in trip.go:10-28). Dieser Waechter liest
// jede *.go-Datei dieses Verzeichnisses als Syntaxbaum und meldet jede
// Zuweisung an einen aeusseren Funktionsparameter innerhalb einer Closure —
// unabhaengig von Variablenname und aufgerufener Methode. Eine Textsuche nach
// "s = s.WithUser(middleware." uebersaehe die Zwischenvariablen-Form (Analyse
// docs/context/fix-1396-store-race-handler.md, Risiko 2).
//
// Der Scan-Kern (ssgScan) nimmt Quelltext entgegen, keine Dateipfade — die
// Fixture-Tests rufen ihn direkt auf, OHNE zur Testzeit "git show" oder einen
// anderen Prozess zu starten (Vorbild internal/mail/recipient_parity_test.go).
// Die Fixtures sind String-Konstanten, keine echten Dateien: der Waechter
// scannt auch _test.go und wuerde sich sonst selbst rot melden.

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"regexp"
	"sort"
	"strings"
	"testing"
)

const (
	ssgAusnahmeMarke   = "gz-closure-param-write:"
	ssgMinBegruendung  = 15
	ssgMindestDateien  = 50 // heute 106; ein Absturz darunter heisst: Pfad verloren
	ssgVorlagenVerweis = "internal/handler/trip.go:10-28"
)

var ssgNichtWortRe = regexp.MustCompile(`[^\p{L}\p{N}]+`)

type ssgBefund struct {
	Bezeichnung string
	Zeile       int
	Parameter   string
}

type ssgSchatten struct {
	name     string
	von, bis token.Pos
}

type ssgKandidat struct {
	name string
	pos  token.Pos
	// huelle ist der aeusserste FuncLit zwischen Kandidat und aeusserer
	// Funktion — an ihm haengt die Frage, ob die Closure entkommt.
	huelle ast.Node
}

// ssgScan liefert alle Funde in einem beliebigen Go-Quelltext. Ein Parse-Fehler
// wird zurueckgegeben und NIE verschluckt (AC-8) — eine uebersprungene Datei
// waere ein stilles Gruen.
func ssgScan(bezeichnung string, quelle []byte) ([]ssgBefund, error) {
	fset := token.NewFileSet()
	datei, err := parser.ParseFile(fset, bezeichnung, quelle, parser.ParseComments)
	if err != nil {
		return nil, fmt.Errorf("%s ist kein gueltiges Go: %w", bezeichnung, err)
	}

	kommentare := map[int]string{}
	for _, gruppe := range datei.Comments {
		for _, k := range gruppe.List {
			kommentare[fset.Position(k.Pos()).Line] = k.Text
		}
	}

	gefunden := map[string]ssgBefund{}
	// Jede FuncDecl UND jede FuncLit ist eine moegliche "aeussere" Funktion F:
	// auch eine Zwischenebene (Wrapper, der selbst eine FuncLit nimmt) hat
	// Parameter, die sich alle Anfragen teilen.
	ast.Inspect(datei, func(n ast.Node) bool {
		switch f := n.(type) {
		case *ast.FuncDecl:
			if f.Body != nil {
				ssgPruefeFunktion(fset, bezeichnung, ssgParamNamen(f.Recv, f.Type), f.Body, kommentare, gefunden)
			}
		case *ast.FuncLit:
			ssgPruefeFunktion(fset, bezeichnung, ssgParamNamen(nil, f.Type), f.Body, kommentare, gefunden)
		}
		return true
	})

	funde := make([]ssgBefund, 0, len(gefunden))
	for _, b := range gefunden {
		funde = append(funde, b)
	}
	sort.Slice(funde, func(i, j int) bool {
		if funde[i].Bezeichnung != funde[j].Bezeichnung {
			return funde[i].Bezeichnung < funde[j].Bezeichnung
		}
		return funde[i].Zeile < funde[j].Zeile
	})
	return funde, nil
}

func ssgParamNamen(recv *ast.FieldList, typ *ast.FuncType) map[string]bool {
	namen := map[string]bool{}
	fuer := func(liste *ast.FieldList) {
		if liste == nil {
			return
		}
		for _, feld := range liste.List {
			for _, name := range feld.Names {
				if name.Name != "_" {
					namen[name.Name] = true
				}
			}
		}
	}
	fuer(recv)
	fuer(typ.Params)
	// Ein benannter Rueckgabewert liegt im selben Gueltigkeitsbereich wie die
	// Parameter — eine Closure, die ihn per "=" mutiert, schreibt in dieselbe
	// geteilte Variable.
	fuer(typ.Results)
	return namen
}

// ssgPruefeFunktion durchlaeuft den Rumpf EINER aeusseren Funktion, sammelt
// dabei alle inneren Verdeckungen (":=", "var", FuncLit-Parameter, range), die
// lokalen Deklarationen der Ebene 0, alle Zuweisungskandidaten innerhalb
// verschachtelter FuncLits und die Closures, die die Funktion per "return"
// verlassen.
func ssgPruefeFunktion(
	fset *token.FileSet, bezeichnung string, ebene0 map[string]bool,
	rumpf *ast.BlockStmt, kommentare map[int]string, gefunden map[string]ssgBefund,
) {
	if rumpf == nil {
		return
	}
	var schatten []ssgSchatten
	var kandidaten []ssgKandidat
	var stapel []ast.Node
	lokale := map[string]bool{}      // Ebene 0, aber nicht Teil der Signatur
	entkommt := map[ast.Node]bool{}  // FuncLits, die die Funktion verlassen
	haelt := map[string][]ast.Node{} // Variable -> darin abgelegte FuncLits
	rueckgabe := map[string]bool{}   // Namen, die in einem "return" vorkommen

	merke := func(namen []*ast.Ident, von, bis token.Pos, lokal bool) {
		for _, id := range namen {
			if id == nil || id.Name == "_" {
				continue
			}
			// Eine Deklaration DIREKT im Rumpf der aeusseren Funktion verdeckt
			// nichts — sie IST Ebene 0. Nur der Rumpf selbst endet auf
			// rumpf.End(), jeder innere Block frueher.
			if lokal && ssgBereichsEnde(stapel) == rumpf.End() {
				lokale[id.Name] = true
				continue
			}
			schatten = append(schatten, ssgSchatten{id.Name, von, bis})
		}
	}
	// merkeHuelle haelt fest, welche Variable einen FuncLit traegt: wird sie
	// spaeter zurueckgegeben, entkommt er (Form "inner := func...; return inner()").
	// Der FuncLit darf in einer DIREKTEN Umhuellung stecken — einem Aufruf mit
	// genau EINEM Argument ("h = http.HandlerFunc(func...)"), syntaktisch eine
	// Typumwandlung. Ein mehrargumentiger Aufruf ("reduce(werte, func...)")
	// reicht die Closure nur hinein und liefert etwas anderes zurueck; ihn zu
	// durchsuchen war ein Fehlalarm (AC-13).
	merkeHuelle := func(ziele, werte []ast.Expr) {
		for i, z := range ziele {
			id, ok := z.(*ast.Ident)
			if !ok || i >= len(werte) {
				continue
			}
			wert := werte[i]
			for {
				ruf, ok := wert.(*ast.CallExpr)
				if !ok || len(ruf.Args) != 1 {
					break
				}
				wert = ruf.Args[0]
			}
			if lit, ok := wert.(*ast.FuncLit); ok {
				haelt[id.Name] = append(haelt[id.Name], lit)
			}
		}
	}

	ast.Inspect(rumpf, func(n ast.Node) bool {
		if n == nil {
			stapel = stapel[:len(stapel)-1]
			return false
		}
		switch k := n.(type) {
		case *ast.FuncLit:
			for name := range ssgParamNamen(nil, k.Type) {
				schatten = append(schatten, ssgSchatten{name, k.Pos(), k.End()})
			}
		case *ast.ReturnStmt:
			// Nur die "return" der AEUSSEREN Funktion zaehlen — eines innerhalb
			// einer Closure verlaesst nur diese.
			if ssgAeussereHuelle(stapel) == nil {
				for _, e := range k.Results {
					ast.Inspect(e, func(m ast.Node) bool {
						switch x := m.(type) {
						case *ast.FuncLit:
							entkommt[x] = true
						case *ast.Ident:
							rueckgabe[x.Name] = true
						}
						return true
					})
				}
			}
		case *ast.RangeStmt:
			if k.Tok == token.DEFINE {
				merke(ssgIdents(k.Key, k.Value), k.Pos(), k.End(), false)
			}
		case *ast.GenDecl:
			if k.Tok == token.VAR {
				for _, spec := range k.Specs {
					if v, ok := spec.(*ast.ValueSpec); ok {
						merke(v.Names, k.End(), ssgBereichsEnde(stapel), true)
						for i, nm := range v.Names {
							if i < len(v.Values) {
								merkeHuelle([]ast.Expr{nm}, []ast.Expr{v.Values[i]})
							}
						}
					}
				}
			}
		case *ast.AssignStmt:
			merkeHuelle(k.Lhs, k.Rhs)
			if k.Tok == token.DEFINE {
				merke(ssgIdents(k.Lhs...), k.End(), ssgBereichsEnde(stapel), true)
				break
			}
			// Bewusst nur Einzelzuweisungen (Spec "Known Limitations").
			if k.Tok == token.ASSIGN && len(k.Lhs) == 1 {
				if huelle := ssgAeussereHuelle(stapel); huelle != nil {
					if id, ok := k.Lhs[0].(*ast.Ident); ok {
						kandidaten = append(kandidaten, ssgKandidat{id.Name, k.Pos(), huelle})
					}
				}
			}
		}
		stapel = append(stapel, n)
		return true
	})

	for name := range rueckgabe {
		for _, lit := range haelt[name] {
			entkommt[lit] = true
		}
	}

	for _, kand := range kandidaten {
		// Fund nur, wenn der Name zur Ebene 0 gehoert (Signatur ODER lokale
		// Deklaration des Rumpfes) UND die schreibende Closure die Funktion per
		// "return" verlaesst, also dauerhaft geteilt wird. Das "entkommt"-Gate
		// gilt fuer BEIDE Klassen gleich — sonst meldete der Waechter zwei
		// verbreitete, harmlose Idiome: den Akkumulator ("zaehler = zaehler + 1"
		// in einer nur oertlich benutzten Closure) und das Panik-Auffang-Idiom
		// ("defer func(){ err = ... }()", Adversary-Befund F004), das per
		// Sprachdesign in einen benannten Rueckgabewert schreibt.
		if !(ebene0[kand.name] || lokale[kand.name]) || !entkommt[kand.huelle] {
			continue
		}
		if ssgVerdeckt(schatten, kand.name, kand.pos) {
			continue
		}
		zeile := fset.Position(kand.pos).Line
		if ssgAusnahmeGueltig(kommentare[zeile]) {
			continue
		}
		gefunden[fmt.Sprintf("%d|%s", zeile, kand.name)] = ssgBefund{bezeichnung, zeile, kand.name}
	}
}

func ssgIdents(ausdruecke ...ast.Expr) []*ast.Ident {
	var ids []*ast.Ident
	for _, a := range ausdruecke {
		if id, ok := a.(*ast.Ident); ok {
			ids = append(ids, id)
		}
	}
	return ids
}

// ssgBereichsEnde liefert das Ende des innersten Gueltigkeitsbereichs auf dem
// Stapel. Auch if/for/switch/select zaehlen: eine Deklaration in deren Init-
// Teil gilt bis zum Ende der ganzen Anweisung, nicht bis zum Blockende.
func ssgBereichsEnde(stapel []ast.Node) token.Pos {
	for i := len(stapel) - 1; i >= 0; i-- {
		switch k := stapel[i].(type) {
		case *ast.BlockStmt, *ast.CaseClause, *ast.CommClause, *ast.IfStmt,
			*ast.ForStmt, *ast.RangeStmt, *ast.SwitchStmt, *ast.TypeSwitchStmt,
			*ast.SelectStmt:
			return k.End()
		}
	}
	return token.Pos(0)
}

// ssgAeussereHuelle liefert den aeussersten FuncLit auf dem Stapel, also die
// Closure, die die aeussere Funktion verlassen koennte. nil heisst: die Stelle
// liegt direkt im Rumpf der aeusseren Funktion, in keiner Closure.
func ssgAeussereHuelle(stapel []ast.Node) ast.Node {
	for _, n := range stapel {
		if _, ok := n.(*ast.FuncLit); ok {
			return n
		}
	}
	return nil
}

func ssgVerdeckt(schatten []ssgSchatten, name string, pos token.Pos) bool {
	for _, s := range schatten {
		if s.name == name && pos >= s.von && pos < s.bis {
			return true
		}
	}
	return false
}

// ssgAusnahmeGueltig folgt dem Vorbild "# gz-main-path:" (CLAUDE.md, Pfadregel):
// die Begruendung steht AN der Zeile und braucht >= 15 sinnvolle Zeichen.
func ssgAusnahmeGueltig(kommentar string) bool {
	idx := strings.Index(kommentar, ssgAusnahmeMarke)
	if idx < 0 {
		return false
	}
	grund := kommentar[idx+len(ssgAusnahmeMarke):]
	return len([]rune(ssgNichtWortRe.ReplaceAllString(grund, ""))) >= ssgMinBegruendung
}

func ssgMeldung(funde []ssgBefund) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Geteilte Store-Variable: %d Zuweisung(en) an eine von allen "+
		"Anfragen geteilte Variable der aeusseren Funktion, innerhalb einer Closure.\n", len(funde))
	for _, f := range funde {
		fmt.Fprintf(&b, "  %s:%d — %q wird per \"=\" neu zugewiesen\n",
			f.Bezeichnung, f.Zeile, f.Parameter)
	}
	fmt.Fprintf(&b, "Alle gleichzeitigen Anfragen teilen sich diese Variable "+
		"(Cross-User-Datenleck ueber data/users/<user_id>/). Erwartete Reparatur: "+
		"\"=\" durch \":=\" ersetzen — anfragelokale Deklaration, rechte Seite meint "+
		"weiterhin die aeussere. Ausfuehrliche Begruendung: %s. Begruendete Ausnahme: "+
		"\"// %s <Begruendung>\" an der Fundzeile.", ssgVorlagenVerweis, ssgAusnahmeMarke)
	return b.String()
}

// --- AC-1 -------------------------------------------------------------------

func TestStoreScopeGuardHandlerPaketIstFrei(t *testing.T) {
	eintraege, err := os.ReadDir(".")
	if err != nil {
		t.Fatalf("Paketverzeichnis nicht lesbar: %v", err)
	}
	var alle []ssgBefund
	gescannt := 0
	for _, e := range eintraege {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") {
			continue
		}
		quelle, err := os.ReadFile(e.Name())
		if err != nil {
			t.Fatalf("%s nicht lesbar: %v", e.Name(), err)
		}
		funde, err := ssgScan(e.Name(), quelle)
		if err != nil {
			t.Fatalf("Waechter kann %s nicht pruefen und darf sie NICHT ueberspringen: %v", e.Name(), err)
		}
		gescannt++
		alle = append(alle, funde...)
	}
	if gescannt < ssgMindestDateien {
		t.Fatalf("Nur %d Dateien gescannt (erwartet >= %d) — der Waechter waere "+
			"stilles Gruen ohne echte Pruefung.", gescannt, ssgMindestDateien)
	}
	if len(alle) > 0 {
		t.Fatalf("%s", ssgMeldung(alle))
	}
}

// --- Fixtures aus der echten Historie (einmalig entnommen, nie zur Testzeit) --

// Woertlicher Auszug aus internal/handler/location.go im Stand e03fde9d~1
// (vor Fix #1396 S1): LocationsHandler samt der Direktaufruf-Zuweisungszeile.
const ssgFixtureLocationVorS1 = `package handler

func LocationsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		locations, err := s.LoadLocations()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(` + "`" + `{"error":"store_error"}` + "`" + `))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(locations)
	}
}
`

const ssgFixtureLocationZeile = 5

// Woertlicher Auszug aus internal/handler/compare_preset.go im Stand
// 7e0b7415~1 — Zwischenvariablen-Form "s = s.WithUser(userID)", dort Zeile 183.
// ABWEICHUNG VON DER SPEC: die Spec nennt e03fde9d~1, dort trug die Datei aber
// bereits ":=" (Commit 7e0b7415, #1395 S6, hatte sie vorab repariert; siehe
// Commit-Text von e03fde9d). 7e0b7415~1 ist der letzte Stand mit "=".
// Rumpf nach der Decode-Pruefung abgeschnitten, Klammern geschlossen.
const ssgFixtureComparePresetVorS6 = `package handler

// POST /api/compare/presets
func CreateComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		s = s.WithUser(userID)

		var preset model.ComparePreset
		if err := json.NewDecoder(r.Body).Decode(&preset); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}
	}
}
`

const ssgFixtureComparePresetZeile = 7

func ssgScanOhneFehler(t *testing.T, bezeichnung, quelle string) []ssgBefund {
	t.Helper()
	funde, err := ssgScan(bezeichnung, []byte(quelle))
	if err != nil {
		t.Fatalf("%s liess sich nicht parsen: %v", bezeichnung, err)
	}
	return funde
}

func ssgErwarteGenauEinenFund(t *testing.T, funde []ssgBefund, zeile int, param string) {
	t.Helper()
	if len(funde) != 1 {
		t.Fatalf("Erwartet: genau 1 Fund, gemessen: %d (%+v)", len(funde), funde)
	}
	if funde[0].Zeile != zeile || funde[0].Parameter != param {
		t.Fatalf("Erwartet Fund an Zeile %d fuer Parameter %q, gemessen: %+v", zeile, param, funde[0])
	}
}

// --- AC-2 / AC-3 ------------------------------------------------------------

func TestStoreScopeGuardErkenntDirektaufrufForm(t *testing.T) {
	funde := ssgScanOhneFehler(t, "location.go@e03fde9d~1", ssgFixtureLocationVorS1)
	ssgErwarteGenauEinenFund(t, funde, ssgFixtureLocationZeile, "s")
}

func TestStoreScopeGuardErkenntZwischenvariablenForm(t *testing.T) {
	funde := ssgScanOhneFehler(t, "compare_preset.go@7e0b7415~1", ssgFixtureComparePresetVorS6)
	ssgErwarteGenauEinenFund(t, funde, ssgFixtureComparePresetZeile, "s")
}

// --- AC-4 -------------------------------------------------------------------

// Vorlage fuer synthetische Quelltexte: Parametername (1), aufgerufene Methode
// (2) und ein Zeilenzusatz (3, fuer das Ausnahme-Ventil in AC-5) sind variabel.
// Die Fundzeile ist immer Zeile 5.
const ssgVorlage = `package handler

func H(%[1]s *ablage) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		%[1]s = %[1]s.%[2]s(kennungAus(r))%[3]s
	})
}
`

const ssgVorlageZeile = 5

func TestStoreScopeGuardHaengtNichtAnNamenUndMethode(t *testing.T) {
	for _, f := range []struct{ param, methode string }{
		{"store", "ForTenant"},
		{"db", "Scoped"},
	} {
		quelle := fmt.Sprintf(ssgVorlage, f.param, f.methode, "")
		ssgErwarteGenauEinenFund(t, ssgScanOhneFehler(t, f.param+".go", quelle), ssgVorlageZeile, f.param)
	}
}

// AC-4 deckt ab, dass der Waechter nicht am Namen haengt. Die folgenden Faelle
// erweitern das auf die HERKUNFT der Variable: nicht nur Parameter existieren
// genau einmal je registrierter Route, sondern auch ein benannter
// Rueckgabewert und — sofern die schreibende Closure die Funktion per "return"
// verlaesst — eine lokale Variable ihres Rumpfes.

// Lokale Variable, von der ZURUECKGEGEBENEN Closure eingefangen: kein
// Parameter, strukturell trotzdem dieselbe dauerhaft geteilte Variable.
const ssgFixtureLokaleVariable = `package handler

func Build(sIn *ablage) http.HandlerFunc {
	s := sIn
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(kennungAus(r))
	}
}
`

// Dieselbe Bauart mit "var" statt ":=" — die Deklarationsform darf nichts
// aendern, die Closure entkommt genauso.
const ssgFixtureLokaleVariableVarForm = `package handler

func Build(sIn *ablage) http.HandlerFunc {
	var s = sIn
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(kennungAus(r))
	}
}
`

// Abgrenzung: dieselbe Bauart, aber die Closure verlaesst die Funktion NICHT.
// Ein gewoehnlicher Akkumulator — ohne diese Abgrenzung meldete der Waechter
// eines der haeufigsten harmlosen Go-Idiome und waere Laerm.
const ssgFixtureOertlicheClosure = `package handler

func Summe(werte []int) int {
	zaehler := 0
	addiere := func() { zaehler = zaehler + 1 }
	for range werte {
		addiere()
	}
	return zaehler
}
`

// Zwischenstufe: die entkommende Closure wird von einer zweiten geliefert, die
// selbst nur ueber eine Variable im "return" auftaucht.
const ssgFixtureZwischenstufe = `package handler

func Build(sIn *ablage) http.HandlerFunc {
	s := sIn
	inner := func() http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			s = s.WithUser(kennungAus(r))
		}
	}
	return inner()
}
`

// Benannter Rueckgabewert, von der verschachtelten Closure per "=" mutiert.
// Teil der Signatur, und die Closure entkommt: sie steckt in "h", das die
// Funktion zurueckgibt — die Umhuellung "http.HandlerFunc(...)" aendert daran
// nichts.
const ssgFixtureBenannterRueckgabewert = `package handler

func Build(s *ablage) (h http.HandlerFunc) {
	h = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h = umhuellen(h, kennungAus(r))
	})
	return h
}
`

func TestStoreScopeGuardErkenntLokaleVariableEntkommenderClosure(t *testing.T) {
	for _, f := range []struct {
		name, quelle string
		zeile        int
	}{
		{"kurzform", ssgFixtureLokaleVariable, 6},
		{"var-form", ssgFixtureLokaleVariableVarForm, 6},
		{"zwischenstufe", ssgFixtureZwischenstufe, 7},
	} {
		t.Run(f.name, func(t *testing.T) {
			ssgErwarteGenauEinenFund(t, ssgScanOhneFehler(t, f.name+".go", f.quelle), f.zeile, "s")
		})
	}
}

func TestStoreScopeGuardSchweigtBeiNurOertlichBenutzterClosure(t *testing.T) {
	funde := ssgScanOhneFehler(t, "oertlich.go", ssgFixtureOertlicheClosure)
	if len(funde) != 0 {
		t.Fatalf("Eine Closure, die die Funktion nie verlaesst, teilt nichts dauerhaft "+
			"und darf kein Fund sein, gemessen: %+v", funde)
	}
}

func TestStoreScopeGuardErkenntBenanntenRueckgabewert(t *testing.T) {
	funde := ssgScanOhneFehler(t, "rueckgabe.go", ssgFixtureBenannterRueckgabewert)
	ssgErwarteGenauEinenFund(t, funde, 5, "h")
}

// Abgrenzung zum vorigen Fall (Adversary-Befund F004): das von Go selbst
// empfohlene Panik-Auffang-Idiom schreibt per Sprachdesign in einen benannten
// Rueckgabewert. Die Closure laeuft beim Ruecksprung ab und verlaesst die
// Funktion nie — sie teilt nichts dauerhaft und darf kein Fund sein.
const ssgFixtureDeferAufBenanntenRueckgabewert = `package handler

func Tun(s *ablage) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("Panik: %v", r)
		}
	}()
	return s.Arbeite()
}
`

func TestStoreScopeGuardSchweigtBeiDeferAufBenanntemRueckgabewert(t *testing.T) {
	funde := ssgScanOhneFehler(t, "defer.go", ssgFixtureDeferAufBenanntenRueckgabewert)
	if len(funde) != 0 {
		t.Fatalf("Ein \"defer\", das beim Ruecksprung ablaeuft, verlaesst die Funktion "+
			"nicht und darf kein Fund sein, gemessen: %+v", funde)
	}
}

// --- AC-13 ------------------------------------------------------------------

// Abgrenzung (Adversary-Befund F005): ein mehrargumentiger Hilfsaufruf reicht
// die Closure nur hinein und liefert ein "int" zurueck. Die Closure verlaesst
// "Summe" nie — nur ihr Ergebnis tut es.
const ssgFixtureMehrargumentigerAufruf = `package handler

func Summe(sIn *ablage, werte []int) int {
	s := sIn
	summe := reduce(werte, func(acc int) int {
		s = s.WithUser("temp")
		return acc + 1
	})
	return summe
}
`

func TestStoreScopeGuardSchweigtBeiMehrargumentigemHilfsaufruf(t *testing.T) {
	funde := ssgScanOhneFehler(t, "reduce.go", ssgFixtureMehrargumentigerAufruf)
	if len(funde) != 0 {
		t.Fatalf("Eine Closure, die ein mehrargumentiger Hilfsaufruf nur synchron "+
			"benutzt, verlaesst die Funktion nicht und darf kein Fund sein, gemessen: %+v", funde)
	}
}

// --- AC-5 -------------------------------------------------------------------

func TestStoreScopeGuardAusnahmeVentilBrauchtEchteBegruendung(t *testing.T) {
	faelle := []struct {
		name    string
		zusatz  string
		erwFund bool
	}{
		{"ohne Kommentar", "", true},
		{"zu kurze Begruendung", " // " + ssgAusnahmeMarke + " passt", true},
		{"ausreichende Begruendung", " // " + ssgAusnahmeMarke +
			" Wrapper wird je Anfrage neu gebaut, kein geteilter Zustand", false},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			quelle := fmt.Sprintf(ssgVorlage, "store", "ForTenant", f.zusatz)
			funde := ssgScanOhneFehler(t, "ausnahme.go", quelle)
			if f.erwFund {
				ssgErwarteGenauEinenFund(t, funde, ssgVorlageZeile, "store")
				return
			}
			if len(funde) != 0 {
				t.Fatalf("Gueltige Ausnahme haette den Fund unterdruecken muessen: %+v", funde)
			}
		})
	}
}

// --- AC-6 -------------------------------------------------------------------

func TestStoreScopeGuardMeldungNenntFundUndReparatur(t *testing.T) {
	funde := ssgScanOhneFehler(t, "location.go@e03fde9d~1", ssgFixtureLocationVorS1)
	meldung := ssgMeldung(funde)
	for _, teil := range []string{
		"location.go@e03fde9d~1",
		fmt.Sprintf(":%d", ssgFixtureLocationZeile),
		`"s"`,
		ssgVorlagenVerweis,
		`":="`,
	} {
		if !strings.Contains(meldung, teil) {
			t.Errorf("Erzeugte Meldung nennt %q nicht:\n%s", teil, meldung)
		}
	}
}

// --- AC-7 -------------------------------------------------------------------

const ssgFixtureRepariert = `package handler

func LocationsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		s = s.WithUser("zweitmal")
		_ = s
	}
}
`

func TestStoreScopeGuardSchweigtBeiAnfragelokalerDeklaration(t *testing.T) {
	funde := ssgScanOhneFehler(t, "repariert.go", ssgFixtureRepariert)
	if len(funde) != 0 {
		t.Fatalf("Die reparierte \":=\"-Form haette 0 Funde liefern muessen, gemessen: %+v", funde)
	}
}

// --- AC-8 -------------------------------------------------------------------

func TestStoreScopeGuardParseFehlerWirdGemeldetStattUebersprungen(t *testing.T) {
	funde, err := ssgScan("kaputt.go", []byte("package handler\n\nfunc H(s *store.Store) {\n\ts = \n"))
	if err == nil {
		t.Fatalf("Ungueltiges Go haette einen Fehler liefern muessen, gemessen: %+v", funde)
	}
	if len(funde) != 0 {
		t.Fatalf("Bei Parse-Fehler duerfen keine Funde behauptet werden: %+v", funde)
	}
}
