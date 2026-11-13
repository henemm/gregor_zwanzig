package handler

// Issue #2677 (Adversary F002): Fehlercodes an Nebenstellen der Handler waren
// nur ueber den HTTP-Status bewacht — ein "not_found" -> "gone" blieb gruen,
// obwohl der Client dann fehler.unbekannt sieht. Dieser Waechter liest die
// Handler-Quellen per go/parser, sammelt jedes String-Literal, das als Code an
// WriteError/WriteErrorWith/bailIf (oder einen Helfer, der seinen Parameter
// dorthin weiterreicht) geht, und verlangt fuer jeden Code einen Katalogtext
// in de UND en (fehler.*, auth.fehler.*, konto.fehler.*, fach.fehler.*).

import (
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/henemm/gregor-api/internal/i18n"
)

// fehlerPraefixe spiegelt die Suchkette von i18n.ErrorBody.
var fehlerPraefixe = []string{"fehler.", "auth.fehler.", "konto.fehler.", "fach.fehler."}

// fehlerSenken: Funktionsname -> Index des code-Arguments.
func fehlerSenken() map[string]int {
	return map[string]int{"WriteError": 3, "WriteErrorWith": 3, "bailIf": 4}
}

// codeFund: varianten sind die Werte von Args["variante"] (leer = keine);
// dynamisch heisst, die Variante ist kein Literal und kommt aus
// dynamischeVarianten.
type codeFund struct {
	code      string
	pos       string
	varianten []string
	dynamisch bool
}

// dynamischeVarianten: Codes, deren Variante zur Laufzeit gewaehlt wird, mit
// allen moeglichen Werten. Neue dynamische Variante => hier ergaenzen.
var dynamischeVarianten = map[string][]string{
	"quota_exceeded": {string(quotaTrips), string(quotaComparePresets), string(quotaLocations)},
	// Issue #2961: Mengenbremsen je Nutzer (nutzer_mengenbremse.go).
	"rate_limit_exceeded": {"aufloesen", "testnachricht", "versand", "abruf", "parallel", "gpx"},
}

// paketVars: paketweite var X = i18n.Args{...} fuer die Variantenaufloesung.
func paketVars(files []*ast.File) map[string]*ast.CompositeLit {
	m := map[string]*ast.CompositeLit{}
	for _, f := range files {
		for _, d := range f.Decls {
			g, ok := d.(*ast.GenDecl)
			if !ok || g.Tok != token.VAR {
				continue
			}
			for _, sp := range g.Specs {
				vs := sp.(*ast.ValueSpec)
				for i, n := range vs.Names {
					if i < len(vs.Values) {
						if cl, ok := vs.Values[i].(*ast.CompositeLit); ok {
							m[n.Name] = cl
						}
					}
				}
			}
		}
	}
	return m
}

// variante liest Args["variante"] aus dem args-Ausdruck: (wert, gefunden,
// literal).
func variante(arg ast.Expr, vars map[string]*ast.CompositeLit) (string, bool, bool) {
	cl, ok := arg.(*ast.CompositeLit)
	if id, isID := arg.(*ast.Ident); isID {
		cl, ok = vars[id.Name]
	}
	if !ok {
		return "", false, false
	}
	for _, el := range cl.Elts {
		kv, ok := el.(*ast.KeyValueExpr)
		if !ok {
			continue
		}
		k, ok := kv.Key.(*ast.BasicLit)
		if !ok || k.Value != `"variante"` {
			continue
		}
		if v, ok := kv.Value.(*ast.BasicLit); ok && v.Kind == token.STRING {
			s, _ := strconv.Unquote(v.Value)
			return s, true, true
		}
		return "", true, false
	}
	return "", false, false
}

func handlerQuellen(t *testing.T, fset *token.FileSet) []*ast.File {
	t.Helper()
	pfade, err := filepath.Glob("*.go")
	if err != nil {
		t.Fatal(err)
	}
	var files []*ast.File
	for _, p := range pfade {
		if strings.HasSuffix(p, "_test.go") {
			continue
		}
		f, err := parser.ParseFile(fset, p, nil, 0)
		if err != nil {
			t.Fatalf("parse %s: %v", p, err)
		}
		files = append(files, f)
	}
	if len(files) == 0 {
		t.Fatal("keine Handler-Quellen gefunden")
	}
	return files
}

func aufrufName(c *ast.CallExpr) string {
	if id, ok := c.Fun.(*ast.Ident); ok {
		return id.Name
	}
	return ""
}

// paramIndex liefert den Index des Parameters name in ft, sonst -1.
func paramIndex(ft *ast.FuncType, name string) int {
	i := 0
	for _, f := range ft.Params.List {
		if len(f.Names) == 0 {
			i++
			continue
		}
		for _, n := range f.Names {
			if n.Name == name {
				return i
			}
			i++
		}
	}
	return -1
}

// weiterreicher erweitert senken um Helfer (benannte Funktionen und per :=
// gebundene Closures), die einen eigenen Parameter als Code weiterreichen.
func weiterreicher(files []*ast.File, senken map[string]int) {
	pruefe := func(name string, ft *ast.FuncType, body ast.Node) bool {
		if _, ok := senken[name]; ok || body == nil {
			return false
		}
		neu := false
		ast.Inspect(body, func(n ast.Node) bool {
			c, ok := n.(*ast.CallExpr)
			if !ok || neu {
				return !neu
			}
			idx, ok := senken[aufrufName(c)]
			if !ok || idx >= len(c.Args) {
				return true
			}
			if id, ok := c.Args[idx].(*ast.Ident); ok {
				if pi := paramIndex(ft, id.Name); pi >= 0 {
					senken[name] = pi
					neu = true
				}
			}
			return true
		})
		return neu
	}
	for geaendert := true; geaendert; {
		geaendert = false
		for _, f := range files {
			ast.Inspect(f, func(n ast.Node) bool {
				switch d := n.(type) {
				case *ast.FuncDecl:
					if d.Recv == nil && pruefe(d.Name.Name, d.Type, d.Body) {
						geaendert = true
					}
				case *ast.AssignStmt:
					if len(d.Lhs) == 1 && len(d.Rhs) == 1 {
						id, ok1 := d.Lhs[0].(*ast.Ident)
						fl, ok2 := d.Rhs[0].(*ast.FuncLit)
						if ok1 && ok2 && pruefe(id.Name, fl.Type, fl.Body) {
							geaendert = true
						}
					}
				}
				return true
			})
		}
	}
}

func sammleFehlercodes(t *testing.T) []codeFund {
	t.Helper()
	fset := token.NewFileSet()
	files := handlerQuellen(t, fset)
	senken := fehlerSenken()
	weiterreicher(files, senken)
	vars := paketVars(files)
	var funde []codeFund
	for _, f := range files {
		ast.Inspect(f, func(n ast.Node) bool {
			c, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			idx, ok := senken[aufrufName(c)]
			if !ok || idx >= len(c.Args) {
				return true
			}
			lit, ok := c.Args[idx].(*ast.BasicLit)
			if !ok || lit.Kind != token.STRING {
				return true
			}
			code, err := strconv.Unquote(lit.Value)
			if err != nil {
				t.Fatalf("Literal %s: %v", lit.Value, err)
			}
			fund := codeFund{code: code, pos: fset.Position(lit.Pos()).String()}
			if n := aufrufName(c); (n == "WriteError" || n == "WriteErrorWith") && idx+1 < len(c.Args) {
				if v, gef, isLit := variante(c.Args[idx+1], vars); gef && isLit {
					fund.varianten = []string{v}
				} else if gef {
					fund.varianten, fund.dynamisch = dynamischeVarianten[code], true
				}
			}
			funde = append(funde, fund)
			return true
		})
	}
	return funde
}

// englischerKatalog laedt nur die en-Dateien ueber i18n.NewCatalog; sie
// werden zusaetzlich als de-Bereich eingehaengt, damit Has (prueft de) die
// englischen Schluessel befragt.
func englischerKatalog(t *testing.T) *i18n.Catalog {
	t.Helper()
	wurzel := filepath.Join("..", "i18n", "messages", "en")
	mfs := fstest.MapFS{}
	err := fs.WalkDir(os.DirFS(wurzel), ".", func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		data, err := os.ReadFile(filepath.Join(wurzel, p))
		if err != nil {
			return err
		}
		mfs["messages/de/"+p] = &fstest.MapFile{Data: data}
		mfs["messages/en/"+p] = &fstest.MapFile{Data: data}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	c, err := i18n.NewCatalog(mfs)
	if err != nil {
		t.Fatal(err)
	}
	return c
}

func hatSchluessel(c *i18n.Catalog, code string) bool {
	for _, p := range fehlerPraefixe {
		if c.Has(p + code) {
			return true
		}
	}
	return false
}

// hatFehlertext spiegelt die Aufloesung von ErrorBody: <code>_<variante>,
// sonst <code>. Bei dynamischer Variante muss jede moegliche Variante tragen.
func hatFehlertext(c *i18n.Catalog, f codeFund) bool {
	if f.dynamisch && len(f.varianten) == 0 {
		return false
	}
	if len(f.varianten) == 0 {
		return hatSchluessel(c, f.code)
	}
	for _, v := range f.varianten {
		if !hatSchluessel(c, f.code+"_"+v) && !hatSchluessel(c, f.code) {
			return false
		}
	}
	return true
}

func TestFehlercodesDerHandlerStehenImKatalogDeUndEn(t *testing.T) {
	funde := sammleFehlercodes(t)
	if len(funde) < 50 {
		t.Fatalf("nur %d Fehlercode-Literale gefunden — Sammler kaputt?", len(funde))
	}
	en := englischerKatalog(t)
	var fehlend []string
	for _, f := range funde {
		if !hatFehlertext(i18n.Default, f) {
			fehlend = append(fehlend, f.pos+": "+strconv.Quote(f.code)+" fehlt in de")
		}
		if !hatFehlertext(en, f) {
			fehlend = append(fehlend, f.pos+": "+strconv.Quote(f.code)+" fehlt in en")
		}
	}
	sort.Strings(fehlend)
	if len(fehlend) > 0 {
		t.Errorf("Fehlercodes ohne Katalogtext (%d):\n%s", len(fehlend), strings.Join(fehlend, "\n"))
	}
}

// Sammler-Selbsttest: die Weiterreicher muessen erkannt werden, sonst fallen
// deren Codes unbemerkt aus der Pruefung.
func TestFehlercodeSammlerErkenntWeiterreicher(t *testing.T) {
	senken := fehlerSenken()
	weiterreicher(handlerQuellen(t, token.NewFileSet()), senken)
	for name, idx := range map[string]int{"smsFehler": 3, "fail": 1} {
		if got, ok := senken[name]; !ok || got != idx {
			t.Errorf("Weiterreicher %s: Index %d/%v, erwartet %d", name, got, ok, idx)
		}
	}
}
