package i18n

// doc-compliance-test: Ratsche, kein Verhaltenstest.
//
// i18n-Ratsche Go (G5, Issue #2679, Epic #2644, ADR-0104). Meldet deutsche
// Nutzertexte als String-Literale in den Go-API-Verzeichnissen, damit sie
// nicht still an der englischen Sprachfassung vorbeigehen. Altbestand steht
// in hardcode_allowlist.json (Verzeichnis endet auf "/", sonst exakte Datei)
// und darf nur schrumpfen: ein Eintrag ohne Befund ist rot.
//
// Spec: docs/specs/modules/i18n_g5_ratsche_go_2679.md
// Startstand messen: GZ_I18N_GUARD_PRINT=1 go test -run TestKeineHartkodierten -v ./internal/i18n/

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"testing"
)

type finding struct {
	File string
	Line int
	Text string
}

var (
	hgScanDirs    = []string{"internal/handler", "internal/mail", "internal/notify", "internal/store", "internal/middleware", "internal/resolver"}
	hgUmlaut      = regexp.MustCompile(`[äöüÄÖÜß]|&(auml|ouml|uuml|Auml|Ouml|Uuml|szlig);`)
	hgSignalwort  = regexp.MustCompile(`(?i)\b(nicht|fehlt|bitte|hallo|ignoriere|bestaetig\w*|zurueck\w*|abgelaufen|fehlgeschlagen)\b`)
	hgMindestDats = 80 // heute 92 Nicht-Test-Dateien; darunter ist der Messaufbau kaputt
)

const hgMarker = "i18n-log"

// hgAusgenommenerAufruf: log.*, slog.*, fmt.Errorf, errors.New.
func hgAusgenommenerAufruf(call *ast.CallExpr) bool {
	sel, ok := call.Fun.(*ast.SelectorExpr)
	if !ok {
		return false
	}
	pkg, ok := sel.X.(*ast.Ident)
	if !ok {
		return false
	}
	switch pkg.Name {
	case "log", "slog":
		return true
	case "fmt":
		return sel.Sel.Name == "Errorf"
	case "errors":
		return sel.Sel.Name == "New"
	}
	return false
}

func hgAusgenommen(lit *ast.BasicLit, stack []ast.Node) bool {
	for i := len(stack) - 1; i >= 0; i-- {
		switch n := stack[i].(type) {
		case *ast.ImportSpec:
			return true
		case *ast.Field:
			if n.Tag == lit {
				return true
			}
		case *ast.CallExpr:
			if hgAusgenommenerAufruf(n) {
				return true
			}
		}
	}
	return false
}

func scanSource(filename string, src []byte) ([]finding, error) {
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, filename, src, parser.ParseComments)
	if err != nil {
		return nil, err
	}
	markerZeilen := map[int]bool{}
	for _, cg := range file.Comments {
		for _, c := range cg.List {
			if strings.Contains(c.Text, hgMarker) {
				z := fset.Position(c.Pos()).Line
				markerZeilen[z], markerZeilen[z+1] = true, true
			}
		}
	}
	var bereiche [][2]token.Pos
	for _, d := range file.Decls {
		if fd, ok := d.(*ast.FuncDecl); ok && fd.Doc != nil && strings.Contains(fd.Doc.Text(), hgMarker) {
			bereiche = append(bereiche, [2]token.Pos{fd.Pos(), fd.End()})
		}
	}
	var out []finding
	var stack []ast.Node
	ast.Inspect(file, func(n ast.Node) bool {
		if n == nil {
			stack = stack[:len(stack)-1]
			return true
		}
		defer func() { stack = append(stack, n) }()
		lit, ok := n.(*ast.BasicLit)
		if !ok || lit.Kind != token.STRING {
			return true
		}
		text, err := strconv.Unquote(lit.Value)
		if err != nil || !(hgUmlaut.MatchString(text) || hgSignalwort.MatchString(text)) {
			return true
		}
		zeile := fset.Position(lit.Pos()).Line
		if markerZeilen[zeile] || hgAusgenommen(lit, stack) {
			return true
		}
		for _, b := range bereiche {
			if lit.Pos() >= b[0] && lit.End() <= b[1] {
				return true
			}
		}
		out = append(out, finding{File: filename, Line: zeile, Text: text})
		return true
	})
	return out, nil
}

func hgRepoRoot(t *testing.T) string {
	t.Helper()
	_, self, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller fehlgeschlagen")
	}
	return filepath.Join(filepath.Dir(self), "..", "..")
}

// scanTree scannt dirs unter root; Messaufbau leer (Verzeichnis ohne Go-Datei
// oder weniger als mindest Dateien insgesamt) ist ein Fehler, kein Gruen.
func scanTree(root string, dirs []string, mindest int) ([]finding, error) {
	var out []finding
	dateien := 0
	for _, dir := range dirs {
		jeDir := 0
		err := filepath.WalkDir(filepath.Join(root, dir), func(p string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				if d.Name() == "testdata" {
					return filepath.SkipDir
				}
				return nil
			}
			if !strings.HasSuffix(p, ".go") || strings.HasSuffix(p, "_test.go") {
				return nil
			}
			src, err := os.ReadFile(p)
			if err != nil {
				return err
			}
			rel, _ := filepath.Rel(root, p)
			bs, err := scanSource(filepath.ToSlash(rel), src)
			if err != nil {
				return err
			}
			jeDir++
			out = append(out, bs...)
			return nil
		})
		if err != nil {
			return nil, fmt.Errorf("Scan %s: %w", dir, err)
		}
		if jeDir == 0 {
			return nil, fmt.Errorf("Messaufbau leer: keine Go-Datei in %s", dir)
		}
		dateien += jeDir
	}
	if dateien < mindest {
		return nil, fmt.Errorf("Messaufbau leer: nur %d Dateien gescannt (erwartet >= %d)", dateien, mindest)
	}
	return out, nil
}

func scanRepo(t *testing.T) []finding {
	t.Helper()
	out, err := scanTree(hgRepoRoot(t), hgScanDirs, hgMindestDats)
	if err != nil {
		t.Fatal(err)
	}
	return out
}

func loadAllowlist(t *testing.T) []string {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(hgRepoRoot(t), "internal", "i18n", "hardcode_allowlist.json"))
	if err != nil {
		t.Fatalf("Allowlist lesen: %v", err)
	}
	var list []string
	if err := json.Unmarshal(raw, &list); err != nil {
		t.Fatalf("Allowlist ist kein JSON-Array von Strings: %v", err)
	}
	return list
}

func hgDeckt(eintrag, datei string) bool {
	if strings.HasSuffix(eintrag, "/") {
		return strings.HasPrefix(datei, eintrag)
	}
	return eintrag == datei
}

// hgPruefe liefert die Meldungen beider Ratschen-Richtungen; der echte Lauf
// (hgEchterLauf) und der Selbsttest gehen durch dieselbe Routine.
func hgPruefe(allow []string, befunde []finding) (ungedeckt, veraltet []string) {
	for _, b := range befunde {
		gedeckt := false
		for _, e := range allow {
			gedeckt = gedeckt || hgDeckt(e, b.File)
		}
		if !gedeckt {
			ungedeckt = append(ungedeckt, fmt.Sprintf("%s:%d: %q (Nutzertext über i18n-Katalog/WriteError ausgeben oder Log mit // i18n-log markieren)", b.File, b.Line, b.Text))
		}
	}
	for _, e := range allow {
		genutzt := false
		for _, b := range befunde {
			genutzt = genutzt || hgDeckt(e, b.File)
		}
		if !genutzt {
			veraltet = append(veraltet, "Eintrag veraltet, bitte entfernen: "+e)
		}
	}
	return ungedeckt, veraltet
}

func hgEchterLauf(t *testing.T) (ungedeckt, veraltet []string) {
	t.Helper()
	befunde := scanRepo(t)
	if os.Getenv("GZ_I18N_GUARD_PRINT") == "1" {
		set := map[string]bool{}
		for _, b := range befunde {
			set[b.File] = true
		}
		var dateien []string
		for f := range set {
			dateien = append(dateien, f)
		}
		sort.Strings(dateien)
		j, _ := json.MarshalIndent(dateien, "", "  ")
		t.Logf("Startstand (%d Befunde):\n%s", len(befunde), j)
	}
	return hgPruefe(loadAllowlist(t), befunde)
}

func TestKeineHartkodiertenNutzertexte(t *testing.T) {
	if ungedeckt, _ := hgEchterLauf(t); len(ungedeckt) > 0 {
		t.Error("\n" + strings.Join(ungedeckt, "\n"))
	}
}

func TestAllowlistHatKeineVeralteten(t *testing.T) {
	if _, veraltet := hgEchterLauf(t); len(veraltet) > 0 {
		t.Error("\n" + strings.Join(veraltet, "\n"))
	}
}

// Selbsttest der Allowlist-Pruefung und des Messaufbaus ohne Repo-Dateien.
func TestWaechterPrueftAllowlistUndMessaufbau(t *testing.T) {
	befunde := []finding{{File: "internal/handler/a.go", Line: 1, Text: "x"}, {File: "internal/mail/b.go", Line: 2, Text: "y"}, {File: "internal/handler/neu.go", Line: 3, Text: "z"}}
	allow := []string{"internal/handler/a.go", "internal/mail/", "internal/handler/umgestellt.go", "internal/resolver/"}
	ungedeckt, veraltet := hgPruefe(allow, befunde)
	if len(ungedeckt) != 1 || !strings.HasPrefix(ungedeckt[0], "internal/handler/neu.go:3:") {
		t.Errorf("ungedeckt: got %v", ungedeckt)
	}
	if strings.Join(veraltet, "|") != "Eintrag veraltet, bitte entfernen: internal/handler/umgestellt.go|Eintrag veraltet, bitte entfernen: internal/resolver/" {
		t.Errorf("veraltet: got %v", veraltet)
	}

	root := t.TempDir()
	schreib := func(rel, inhalt string) {
		p := filepath.Join(root, rel)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(inhalt), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	schreib("a/x.go", "package a\nvar s = \"Nicht gefunden\"\n")
	schreib("a/x_test.go", "package a\nvar t = \"Nicht gefunden\"\n")
	schreib("a/testdata/y.go", "package a\nvar u = \"Nicht gefunden\"\n")
	schreib("b/nur_test.go", "package b\nvar v = \"Nicht gefunden\"\n")
	got, err := scanTree(root, []string{"a"}, 1)
	if err != nil || len(got) != 1 || got[0].File != "a/x.go" || got[0].Line != 2 {
		t.Errorf("scanTree: nur a/x.go:2 erwartet (ohne _test.go, ohne testdata/), got %+v, err %v", got, err)
	}
	if _, err := scanTree(root, []string{"a"}, 2); err == nil || !strings.Contains(err.Error(), "Messaufbau leer") {
		t.Errorf("Mindestdateizahl unterschritten: Messaufbau leer erwartet, got %v", err)
	}
	if _, err := scanTree(root, []string{"a", "b"}, 1); err == nil || !strings.Contains(err.Error(), "Messaufbau leer: keine Go-Datei in b") {
		t.Errorf("leeres Verzeichnis: Messaufbau leer erwartet, got %v", err)
	}
}

func TestWaechterErkenntNeueTexte(t *testing.T) {
	const kopf = "package x\n\n"
	faelle := []struct {
		name, src string
		zeile     int // 0 = kein Befund erwartet
	}{
		{"http.Error deutsch", kopf + "func h() {\n\thttp.Error(w, \"Nicht gefunden\", 404)\n}\n", 4},
		{"log.Printf", kopf + "func h() {\n\tlog.Printf(\"Datei nicht gefunden\")\n}\n", 0},
		{"Marker gleiche Zeile", kopf + "func h() {\n\tfoo(\"Datei nicht gefunden\") // i18n-log\n}\n", 0},
		{"Marker Zeile darüber", kopf + "func h() {\n\t// i18n-log\n\tfoo(\"Datei nicht gefunden\")\n}\n", 0},
		{"ae-Umschrift", kopf + "var s = \"Bitte bestaetige deine Adresse\"\n", 3},
		{"HTML-Entity", kopf + "var s = `Hallo,&nbsp;f&uuml;r dich`\n", 3},
		{"Entity ohne Signalwort", kopf + "var s = \"f&uuml;r dich\"\n", 3},
		{"Umlaut", kopf + "var s = \"Ungültig\"\n", 3},
		{"Doc-Kommentar i18n-log", kopf + "// BuildX baut die Betreiber-Mail. i18n-log\nfunc BuildX() string {\n\treturn \"Hallo Betreiber, für dich\"\n}\n", 0},
		{"Struct-Tag", kopf + "type T struct {\n\tA string `json:\"fehlt\"`\n}\n", 0},
		{"errors.New", kopf + "var e = errors.New(\"Datei fehlt\")\n", 0},
		{"fmt.Errorf verschachtelt", kopf + "func h() error {\n\treturn fmt.Errorf(\"%s\", g(\"Datei fehlt\"))\n}\n", 0},
		{"Importpfad", kopf + "import \"example.com/fehlt/nicht\"\n", 0},
		{"englisch", kopf + "var s = \"not found\"\n", 0},
		{"Wortteil kein Signalwort", kopf + "var s = \"nichts_wert\"\n", 0},
	}
	for _, f := range faelle {
		got, err := scanSource("x.go", []byte(f.src))
		if err != nil {
			t.Fatalf("%s: parse: %v", f.name, err)
		}
		switch {
		case f.zeile == 0 && len(got) != 0:
			t.Errorf("%s: unerwarteter Befund %+v", f.name, got)
		case f.zeile != 0 && (len(got) != 1 || got[0].Line != f.zeile || got[0].File != "x.go"):
			t.Errorf("%s: erwartet 1 Befund in x.go:%d, got %+v", f.name, f.zeile, got)
		}
	}
}
