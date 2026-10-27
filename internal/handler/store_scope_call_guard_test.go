package handler

// Issue #2156 (Epic #2138) — Waechter gegen Handler, die eine nutzergebundene
// Store-Methode aufrufen, ohne den Store vorher per WithUser zu binden.
// ADR-0003 (Mandantentrennung) wurde bisher nur durch Review-Disziplin
// getragen, nicht maschinell geprueft.
//
// Spec: docs/specs/modules/store_scope_call_guard.md (v2.0)
//
// Bauprinzip wie internal/handler/store_scope_guard_test.go (ssgScan): reiner
// Testcode, go/parser + go/ast, keine externen Prozesse zur Testzeit,
// Fixtures als String-Konstanten (sonst scannt der Waechter sich selbst).
// Anders als dort ist der Befundtyp hier eine REIHENFOLGE-Verletzung
// (Store-Aufruf VOR der WithUser-Bindung), keine geteilte Closure-Variable —
// ein eigenstaendiger Waechter mit eigener Traversierung (Entscheidung
// Phase 2: kein Ausbau von ssgScan, siehe Spec "Entscheidungen").
//
// Scope-Entscheidung (Abweichung von der Spec-Formulierung "der Waechter
// scannt alle *.go in internal/handler/, _test.go eingeschlossen"): Der
// Provenance-Lauf (AC-1/AC-3) scannt NUR Nicht-Test-Dateien. Testdateien
// binden den Store ueberwiegend direkt per store.New(dir, "alice") (Fixture-
// Aufbau, kein Auth-Kontext-Pfad aus middleware.UserIDFromContext) und rufen
// danach ohne WithUser Trigger-Methoden wie SaveTrip/LoadTrips auf (gemessen:
// >100 Stellen in *_test.go). Ein Scan inklusive _test.go meldete dort
// hunderte Funde, die Phase 6 NICHT beheben wuerde (Phase 6 setzt Marker nur
// in internal/store/*.go) — der Waechter waere nach der Lieferung dauerhaft
// rot statt bei AC-8 auf 0 Befunde zu stehen. Gemessen: 31 Nicht-Test-Dateien
// in internal/handler/ (Vorbild ssgMindestDateien bezog sich auf 106
// inklusive Tests desselben Pakets — nicht uebertragbar).

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"testing"
)

const (
	sscgMarkerExempt   = "gz-store-scope-exempt:"
	sscgMarkerRequired = "gz-store-scope-required:"
	sscgMarkerCall     = "gz-store-scope-call:"
	sscgMinBegruendung = 15

	// Selbstschutz (AC-5): heute liefert die requireUser()-Ableitung 25
	// Methoden (Vorbild ssgMindestDateien-Idee: Absturz darunter heisst Pfad
	// verloren, nicht Regression im Store).
	sscgMindestRequireUser = 25
	// Heute 31 Nicht-Test-Dateien in internal/handler/ (Scope-Entscheidung
	// oben) — Marge nach unten gegen "Verzeichnis vertauscht/leer".
	sscgMindestHandlerDateien = 25

	sscgHandlerVerzeichnis = "."
	sscgStoreVerzeichnis   = "../store"
)

var sscgNichtWortRe = regexp.MustCompile(`[^\p{L}\p{N}]+`)

// sscgStichprobe: fest kodierte Mindest-Assertion (AC-5b), KEINE
// Ausnahme-/Ergaenzungsliste — die Auslöser- und Ausnahmemenge selbst kommen
// ausschliesslich aus dem Quelltext (Marker-Konvention, Spec).
var sscgStichprobe = []string{"LoadTrip", "SaveTrip", "LoadLocations", "LoadComparePresets"}

func sscgBegruendungGueltig(begruendung string) bool {
	return len([]rune(sscgNichtWortRe.ReplaceAllString(begruendung, ""))) >= sscgMinBegruendung
}

// --- Store-Seite: Marker-Ableitung + Klassifikations-Grundlage ------------

type sscgMarkerBefund struct {
	Datei   string
	Zeile   int
	Meldung string
}

// sscgStoreKlassifikation ist das aggregierte Ergebnis ueber alle Dateien von
// internal/store/*.go (ohne _test.go).
type sscgStoreKlassifikation struct {
	RequireUserMethoden map[string]bool   // AST: Koerper ruft s.requireUser() strukturell auf
	Exempt              map[string]string // Methode -> Begruendung (gz-store-scope-exempt)
	Required            map[string]string // Methode -> Begruendung (gz-store-scope-required)
	AlleMethoden        map[string]bool   // jede EXPORTIERTE *Store-Methode (Grundlage der Klassifikations-Pflicht)
	Befunde             []sscgMarkerBefund
}

func sscgLeeresErgebnis() sscgStoreKlassifikation {
	return sscgStoreKlassifikation{
		RequireUserMethoden: map[string]bool{},
		Exempt:              map[string]string{},
		Required:            map[string]string{},
		AlleMethoden:        map[string]bool{},
	}
}

func sscgVereinige(ziel, quelle sscgStoreKlassifikation) sscgStoreKlassifikation {
	for k := range quelle.RequireUserMethoden {
		ziel.RequireUserMethoden[k] = true
	}
	for k, v := range quelle.Exempt {
		ziel.Exempt[k] = v
	}
	for k, v := range quelle.Required {
		ziel.Required[k] = v
	}
	for k := range quelle.AlleMethoden {
		ziel.AlleMethoden[k] = true
	}
	ziel.Befunde = append(ziel.Befunde, quelle.Befunde...)
	return ziel
}

func sscgIstStoreReceiver(f *ast.FuncDecl) bool {
	if f.Recv == nil || len(f.Recv.List) == 0 {
		return false
	}
	star, ok := f.Recv.List[0].Type.(*ast.StarExpr)
	if !ok {
		return false
	}
	id, ok := star.X.(*ast.Ident)
	return ok && id.Name == "Store"
}

// sscgRuftRequireUserAuf prueft STRUKTURELL (kein Textsuche-Weg — ein
// Kommentar mit "requireUser()" erzeugte sonst einen Phantom-Treffer,
// gemessen in internal/store/store.go:25), ob der Koerper s.requireUser()
// aufruft.
func sscgRuftRequireUserAuf(body *ast.BlockStmt) bool {
	gefunden := false
	ast.Inspect(body, func(n ast.Node) bool {
		call, ok := n.(*ast.CallExpr)
		if !ok {
			return true
		}
		if sel, ok := call.Fun.(*ast.SelectorExpr); ok && sel.Sel.Name == "requireUser" {
			gefunden = true
		}
		return true
	})
	return gefunden
}

type sscgMarkerZeile struct {
	Art         string // "exempt" oder "required"
	Begruendung string
}

// sscgMarkerAusKommentar liest ALLE Markerzeilen (0, 1 oder 2 — 2 heisst
// doppelt markiert) aus einer Kommentargruppe.
func sscgMarkerAusKommentar(doc *ast.CommentGroup) []sscgMarkerZeile {
	if doc == nil {
		return nil
	}
	var treffer []sscgMarkerZeile
	for _, zeile := range doc.List {
		for marke, art := range map[string]string{sscgMarkerExempt: "exempt", sscgMarkerRequired: "required"} {
			if idx := strings.Index(zeile.Text, marke); idx >= 0 {
				treffer = append(treffer, sscgMarkerZeile{art, strings.TrimSpace(zeile.Text[idx+len(marke):])})
			}
		}
	}
	return treffer
}

// sscgScanStoreQuelle scannt EINE Datei aus internal/store/*.go.
func sscgScanStoreQuelle(bezeichnung string, quelle []byte) (sscgStoreKlassifikation, error) {
	erg := sscgLeeresErgebnis()
	fset := token.NewFileSet()
	datei, err := parser.ParseFile(fset, bezeichnung, quelle, parser.ParseComments)
	if err != nil {
		return erg, fmt.Errorf("%s ist kein gueltiges Go: %w", bezeichnung, err)
	}

	// Kommentargruppen, die als Doc EINER *Store-Methode erkannt wurden --
	// alles andere mit Markertext ist verwaist (haengt an nichts
	// Store-Foermigem, oder an gar keiner Deklaration).
	angehaengt := map[*ast.CommentGroup]bool{}

	for _, decl := range datei.Decls {
		f, ok := decl.(*ast.FuncDecl)
		if !ok {
			continue
		}
		marker := sscgMarkerAusKommentar(f.Doc)
		istStore := sscgIstStoreReceiver(f)
		if len(marker) > 0 {
			angehaengt[f.Doc] = true
		}
		zeile := fset.Position(f.Pos()).Line
		if f.Doc != nil {
			zeile = fset.Position(f.Doc.Pos()).Line
		}
		if !istStore {
			if len(marker) > 0 {
				erg.Befunde = append(erg.Befunde, sscgMarkerBefund{bezeichnung, zeile,
					fmt.Sprintf("verwaister Marker: %s ist keine *Store-Methode", f.Name.Name)})
			}
			continue
		}
		if ast.IsExported(f.Name.Name) {
			erg.AlleMethoden[f.Name.Name] = true
		}
		ruftAuf := f.Body != nil && sscgRuftRequireUserAuf(f.Body)
		if ruftAuf && ast.IsExported(f.Name.Name) {
			erg.RequireUserMethoden[f.Name.Name] = true
		}

		switch {
		case len(marker) >= 2:
			erg.Befunde = append(erg.Befunde, sscgMarkerBefund{bezeichnung, zeile,
				fmt.Sprintf("doppelt markiert: %s traegt mehr als einen Marker", f.Name.Name)})
		case len(marker) == 1:
			m := marker[0]
			if !sscgBegruendungGueltig(m.Begruendung) {
				erg.Befunde = append(erg.Befunde, sscgMarkerBefund{bezeichnung, zeile,
					fmt.Sprintf("Begruendung zu kurz (< %d Zeichen): %s", sscgMinBegruendung, f.Name.Name)})
			} else if m.Art == "exempt" {
				if ruftAuf {
					erg.Befunde = append(erg.Befunde, sscgMarkerBefund{bezeichnung, zeile,
						fmt.Sprintf("widerspruechlicher Marker: %s ist exempt, ruft aber requireUser() auf", f.Name.Name)})
				} else {
					erg.Exempt[f.Name.Name] = m.Begruendung
				}
			} else {
				erg.Required[f.Name.Name] = m.Begruendung
			}
		}
	}

	// Verwaiste Marker: Kommentartext mit Markermarke, der an KEINER
	// *Store-Methode als Doc-Kommentar haengt (z.B. freistehend nach einer
	// geloeschten Methode, oder vor einer var-/const-Deklaration).
	for _, gruppe := range datei.Comments {
		if angehaengt[gruppe] {
			continue
		}
		text := gruppe.Text()
		if strings.Contains(text, "gz-store-scope-exempt") || strings.Contains(text, "gz-store-scope-required") {
			erg.Befunde = append(erg.Befunde, sscgMarkerBefund{bezeichnung, fset.Position(gruppe.Pos()).Line,
				"verwaister Marker: keiner *Store-Methode direkt vorangestellt"})
		}
	}

	return erg, nil
}

func sscgStoreBaumEinlesen(t *testing.T, verzeichnis string) sscgStoreKlassifikation {
	t.Helper()
	eintraege, err := os.ReadDir(verzeichnis)
	if err != nil {
		t.Fatalf("Store-Verzeichnis nicht lesbar: %v", err)
	}
	erg := sscgLeeresErgebnis()
	gescannt := 0
	for _, e := range eintraege {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") || strings.HasSuffix(e.Name(), "_test.go") {
			continue
		}
		quelle, err := os.ReadFile(filepath.Join(verzeichnis, e.Name()))
		if err != nil {
			t.Fatalf("%s nicht lesbar: %v", e.Name(), err)
		}
		einzel, err := sscgScanStoreQuelle(e.Name(), quelle)
		if err != nil {
			t.Fatalf("Waechter kann %s nicht pruefen und darf sie NICHT ueberspringen: %v", e.Name(), err)
		}
		erg = sscgVereinige(erg, einzel)
		gescannt++
	}
	if gescannt == 0 {
		t.Fatalf("Kein Store-Quelltext gescannt -- Pfad verloren?")
	}
	return erg
}

// --- Handler-Seite: Provenance-Lauf + Aufruf-Inventar ----------------------

type sscgCallBefund struct {
	Datei      string
	Zeile      int
	Bezeichner string
	Methode    string
	Meldung    string // gesetzt statt Bezeichner/Methode fuer Nicht-Provenance-Funde (z.B. verwaister Call-Marker)
}

func sscgFormatiereCallFunde(funde []sscgCallBefund) string {
	var b strings.Builder
	for _, f := range funde {
		if f.Meldung != "" {
			fmt.Fprintf(&b, "  %s:%d — %s\n", f.Datei, f.Zeile, f.Meldung)
			continue
		}
		fmt.Fprintf(&b, "  %s:%d — %s.%s() ohne vorherige WithUser-Bindung\n", f.Datei, f.Zeile, f.Bezeichner, f.Methode)
	}
	return b.String()
}

// sscgScanHandlerQuelle liefert (a) Provenance-Funde (Auslöser-Aufruf vor
// Bindung, plus verwaiste gz-store-scope-call-Marker) und (b) die Menge der
// aus dieser Datei aufgerufenen, EXPORTIERT wirkenden Methodennamen (Rohmenge
// fuer die Klassifikations-Pflicht — gegen AlleMethoden zu filtern, ein
// gleichnamiger Methodenname auf einem anderen Typ ist sonst ein
// Fehlalarm).
func sscgScanHandlerQuelle(bezeichnung string, quelle []byte, auslöser map[string]bool) ([]sscgCallBefund, map[string]bool, error) {
	fset := token.NewFileSet()
	datei, err := parser.ParseFile(fset, bezeichnung, quelle, parser.ParseComments)
	if err != nil {
		return nil, nil, fmt.Errorf("%s ist kein gueltiges Go: %w", bezeichnung, err)
	}

	kommentareInZeile := map[int]string{}
	for _, gruppe := range datei.Comments {
		for _, k := range gruppe.List {
			kommentareInZeile[fset.Position(k.Pos()).Line] = k.Text
		}
	}
	gueltigerMarkerInZeile := func(zeile int) bool {
		text := kommentareInZeile[zeile]
		idx := strings.Index(text, sscgMarkerCall)
		return idx >= 0 && sscgBegruendungGueltig(text[idx+len(sscgMarkerCall):])
	}

	var funde []sscgCallBefund
	aufgerufen := map[string]bool{}
	verwaisteCallMarker := map[int]bool{}

	// verarbeite laeuft EINEN Funktionskoerper (FuncDecl oder FuncLit) fuer
	// sich — verschachtelte FuncLits werden NICHT mitgenommen (return false),
	// sondern vom aeusseren ast.Inspect separat als eigener Aufruf
	// verarbeitet (Vorbild-Dispatch wie ssgScan).
	verarbeite := func(body *ast.BlockStmt) {
		if body == nil {
			return
		}
		// gebunden haelt je Bezeichner die FRUEHESTE Position einer
		// ":="/"="-Bindung "<id> = <expr>.WithUser(...)" in diesem Koerper.
		gebunden := map[string]token.Pos{}
		ast.Inspect(body, func(n ast.Node) bool {
			if _, ok := n.(*ast.FuncLit); ok {
				return false
			}
			assign, ok := n.(*ast.AssignStmt)
			if !ok {
				return true
			}
			for i, rhs := range assign.Rhs {
				call, ok := rhs.(*ast.CallExpr)
				if !ok {
					continue
				}
				sel, ok := call.Fun.(*ast.SelectorExpr)
				if !ok || sel.Sel.Name != "WithUser" || i >= len(assign.Lhs) {
					continue
				}
				id, ok := assign.Lhs[i].(*ast.Ident)
				if !ok || id.Name == "_" {
					continue
				}
				if pos, schon := gebunden[id.Name]; !schon || assign.End() < pos {
					gebunden[id.Name] = assign.End()
				}
			}
			return true
		})

		ast.Inspect(body, func(n ast.Node) bool {
			if _, ok := n.(*ast.FuncLit); ok {
				return false
			}
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			sel, ok := call.Fun.(*ast.SelectorExpr)
			if !ok {
				return true
			}
			id, ok := sel.X.(*ast.Ident)
			if !ok {
				return true
			}
			methode := sel.Sel.Name
			if ast.IsExported(methode) {
				aufgerufen[methode] = true
			}
			if !auslöser[methode] {
				return true
			}
			zeile := fset.Position(call.Pos()).Line
			bindung, hatBindung := gebunden[id.Name]
			istGebunden := hatBindung && bindung <= call.Pos()
			hatMarker := gueltigerMarkerInZeile(zeile - 1)

			if !istGebunden {
				if !hatMarker {
					funde = append(funde, sscgCallBefund{Datei: bezeichnung, Zeile: zeile, Bezeichner: id.Name, Methode: methode})
				}
			} else if hatMarker {
				verwaisteCallMarker[zeile-1] = true
			}
			return true
		})
	}

	ast.Inspect(datei, func(n ast.Node) bool {
		switch f := n.(type) {
		case *ast.FuncDecl:
			verarbeite(f.Body)
		case *ast.FuncLit:
			verarbeite(f.Body)
		}
		return true
	})

	for markerZeile := range verwaisteCallMarker {
		funde = append(funde, sscgCallBefund{Datei: bezeichnung, Zeile: markerZeile, Meldung: "verwaister gz-store-scope-call Marker (Aufrufstelle ohnehin gebunden)"})
	}
	sort.Slice(funde, func(i, j int) bool { return funde[i].Zeile < funde[j].Zeile })

	return funde, aufgerufen, nil
}

func sscgHandlerBaumEinlesen(t *testing.T, verzeichnis string, auslöser map[string]bool) ([]sscgCallBefund, map[string]bool, int) {
	t.Helper()
	eintraege, err := os.ReadDir(verzeichnis)
	if err != nil {
		t.Fatalf("Handler-Verzeichnis nicht lesbar: %v", err)
	}
	var alleFunde []sscgCallBefund
	aufgerufen := map[string]bool{}
	gescannt := 0
	for _, e := range eintraege {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") || strings.HasSuffix(e.Name(), "_test.go") {
			continue
		}
		quelle, err := os.ReadFile(filepath.Join(verzeichnis, e.Name()))
		if err != nil {
			t.Fatalf("%s nicht lesbar: %v", e.Name(), err)
		}
		funde, methoden, err := sscgScanHandlerQuelle(e.Name(), quelle, auslöser)
		if err != nil {
			t.Fatalf("Waechter kann %s nicht pruefen und darf sie NICHT ueberspringen: %v", e.Name(), err)
		}
		alleFunde = append(alleFunde, funde...)
		for m := range methoden {
			aufgerufen[m] = true
		}
		gescannt++
	}
	return alleFunde, aufgerufen, gescannt
}

// --- Klassifikations-Pflicht (AC-3) -- reine Funktion ueber bereits
// abgeleitete Mengen, entkoppelt von der AST-Traversierung. -----------------

func sscgKlassifikationsPflicht(aufgerufen, auslöser, exempt map[string]bool) []string {
	var unklassifiziert []string
	for m := range aufgerufen {
		if auslöser[m] || exempt[m] {
			continue
		}
		unklassifiziert = append(unklassifiziert, m)
	}
	sort.Strings(unklassifiziert)
	return unklassifiziert
}

// --- Selbstschutz (AC-5) -- reine Funktionen, einzeln testbar. -------------

func sscgSelbstschutzMindestzahl(auslöserRequireUser map[string]bool) error {
	if len(auslöserRequireUser) < sscgMindestRequireUser {
		return fmt.Errorf("nur %d requireUser()-Methoden abgeleitet (erwartet >= %d) -- Pfad verloren?",
			len(auslöserRequireUser), sscgMindestRequireUser)
	}
	return nil
}

func sscgSelbstschutzStichprobe(auslöserRequireUser map[string]bool) error {
	var fehlend []string
	for _, name := range sscgStichprobe {
		if !auslöserRequireUser[name] {
			fehlend = append(fehlend, name)
		}
	}
	if len(fehlend) > 0 {
		return fmt.Errorf("Stichprobe fehlt in der Ableitung: %v", fehlend)
	}
	return nil
}

func sscgSelbstschutzDateizahl(gescannt int) error {
	if gescannt < sscgMindestHandlerDateien {
		return fmt.Errorf("nur %d Handler-Dateien gescannt (erwartet >= %d) -- Pfad verloren?",
			gescannt, sscgMindestHandlerDateien)
	}
	return nil
}

// ============================================================================
// Zentraler Lauf gegen den ECHTEN Baum (AC-1, AC-3, AC-4, AC-5, AC-8)
// ============================================================================
//
// Dieser Test ist HEUTE bewusst rot: 24 Marker fehlen noch in
// internal/store/*.go (Phase 6). Rot erwartet: "Klassifikations-Pflicht
// (AC-3) verletzt: N unklassifizierte Methode(n)" mit N > 0 (heute u.a. alle
// 23 zu markierenden gz-store-scope-exempt-Methoden + WithUser + LockBriefing
// ohne gz-store-scope-required). Gruen erwartet: AC-1 (Provenance) UND
// Marker-Hygiene (AC-4) sind bereits heute sauber -- nur die Klassifikation
// fehlt.

func TestStoreScopeCallGuardGegenEchtenBaum(t *testing.T) {
	store := sscgStoreBaumEinlesen(t, sscgStoreVerzeichnis)

	if err := sscgSelbstschutzMindestzahl(store.RequireUserMethoden); err != nil {
		t.Fatalf("Selbstschutz (AC-5a): %v", err)
	}
	if err := sscgSelbstschutzStichprobe(store.RequireUserMethoden); err != nil {
		t.Fatalf("Selbstschutz (AC-5b): %v", err)
	}
	if len(store.Befunde) > 0 {
		var b strings.Builder
		for _, f := range store.Befunde {
			fmt.Fprintf(&b, "  %s:%d — %s\n", f.Datei, f.Zeile, f.Meldung)
		}
		t.Errorf("Marker-Hygiene (AC-4) verletzt im echten Baum, %d Fund(e):\n%s", len(store.Befunde), b.String())
	}

	auslöser := map[string]bool{}
	for m := range store.RequireUserMethoden {
		auslöser[m] = true
	}
	for m := range store.Required {
		auslöser[m] = true
	}

	callFunde, aufgerufenRoh, gescannt := sscgHandlerBaumEinlesen(t, sscgHandlerVerzeichnis, auslöser)
	if err := sscgSelbstschutzDateizahl(gescannt); err != nil {
		t.Fatalf("Selbstschutz (AC-5c): %v", err)
	}

	aufgerufen := map[string]bool{}
	for m := range aufgerufenRoh {
		if store.AlleMethoden[m] {
			aufgerufen[m] = true
		}
	}
	exempt := map[string]bool{}
	for m := range store.Exempt {
		exempt[m] = true
	}
	unklassifiziert := sscgKlassifikationsPflicht(aufgerufen, auslöser, exempt)

	if len(callFunde) > 0 {
		t.Errorf("Store-Aufruf vor WithUser-Bindung (AC-1), %d Fund(e):\n%s", len(callFunde), sscgFormatiereCallFunde(callFunde))
	}
	if len(unklassifiziert) > 0 {
		t.Errorf("Klassifikations-Pflicht (AC-3) verletzt: %d unklassifizierte Methode(n) -- "+
			"tragen weder requireUser() noch einen gz-store-scope-*-Marker: %v", len(unklassifiziert), unklassifiziert)
	}
}

// AC-2/AC-8: LockBriefing muss ueber gz-store-scope-required in der
// Auslösermenge stehen (nicht weil ihr Name im Testcode steht). Heute (vor
// Phase 6) fehlt der Marker im Quelltext -- bewusst rot, wird durch das
// Setzen des Markers in briefing_lock.go gruen.
func TestStoreScopeCallGuardLockBriefingBrauchtNochDenRequiredMarker(t *testing.T) {
	store := sscgStoreBaumEinlesen(t, sscgStoreVerzeichnis)
	if _, ok := store.Required["LockBriefing"]; !ok {
		t.Errorf("AC-2/AC-8: LockBriefing (internal/store/briefing_lock.go) traegt noch keinen " +
			"gz-store-scope-required Marker -- wird in Phase 6 gesetzt")
	}
}

// --- AC-1 -------------------------------------------------------------------

const sscgFixtureAufrufVorBindung = `package handler

func H(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		_, _ = s.LoadTrips()
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
	}
}
`

func TestStoreScopeCallGuardMeldetAufrufVorBindung(t *testing.T) {
	auslöser := map[string]bool{"LoadTrips": true}
	funde, _, err := sscgScanHandlerQuelle("h.go", []byte(sscgFixtureAufrufVorBindung), auslöser)
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if len(funde) != 1 || funde[0].Methode != "LoadTrips" {
		t.Fatalf("erwartet genau 1 Fund fuer LoadTrips (Aufruf vor Bindung), gemessen: %+v", funde)
	}
}

const sscgFixtureUsBindungGebunden = `package handler

func H(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		us := s.WithUser(middleware.UserIDFromContext(r.Context()))
		_, _ = us.LoadTrips()
	}
}
`

func TestStoreScopeCallGuardErkenntUsAlsGueltigeBindung(t *testing.T) {
	auslöser := map[string]bool{"LoadTrips": true}
	funde, _, err := sscgScanHandlerQuelle("h.go", []byte(sscgFixtureUsBindungGebunden), auslöser)
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if len(funde) != 0 {
		t.Fatalf("\"us :=\" haette als gueltige Bindung erkannt werden muessen (kein Namens-Whitelisting), gemessen: %+v", funde)
	}
}

// --- AC-2 -------------------------------------------------------------------

const sscgFixtureRequireUserNurImKommentar = `package store

// Diese Methode ruft NICHT requireUser() auf -- der Name steht nur hier im
// Kommentartext (Phantomtreffer-Test, vgl. internal/store/store.go:25).
func (s *Store) Phantom() error {
	return nil
}
`

func TestStoreScopeCallGuardIgnoriertRequireUserImKommentar(t *testing.T) {
	erg, err := sscgScanStoreQuelle("phantom.go", []byte(sscgFixtureRequireUserNurImKommentar))
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if erg.RequireUserMethoden["Phantom"] {
		t.Fatalf("Eine Kommentar-Erwaehnung von requireUser() darf keinen Treffer erzeugen (kein Textsuche-Weg)")
	}
}

const sscgFixtureMarkerRequiredOhneRequireUserAufruf = `package store

// gz-store-scope-required: baut den Schluessel direkt aus s.UserID, kein requireUser
func (s *Store) SperrenOhneRequireUser(id string) func() {
	return func() {}
}
`

func TestStoreScopeCallGuardMarkerRequiredLandetInAuslösermenge(t *testing.T) {
	erg, err := sscgScanStoreQuelle("marker.go", []byte(sscgFixtureMarkerRequiredOhneRequireUserAufruf))
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if _, ok := erg.Required["SperrenOhneRequireUser"]; !ok {
		t.Fatalf("Der Marker-Pfad haette die Methode in die Auslösermenge aufnehmen muessen, gemessen Required: %+v", erg.Required)
	}
	if erg.RequireUserMethoden["SperrenOhneRequireUser"] {
		t.Fatalf("Die Methode ruft requireUser() strukturell NICHT auf -- der AST-Pfad darf sie nicht faelschlich zeigen")
	}
}

// --- AC-3 -------------------------------------------------------------------

func TestStoreScopeCallGuardKlassifikationsPflichtMeldetUnbekannteMethode(t *testing.T) {
	aufgerufen := map[string]bool{"GeisterMethode": true, "Bekannt": true}
	auslöser := map[string]bool{"Bekannt": true}
	unklassifiziert := sscgKlassifikationsPflicht(aufgerufen, auslöser, map[string]bool{})
	if len(unklassifiziert) != 1 || unklassifiziert[0] != "GeisterMethode" {
		t.Fatalf("erwartet genau [\"GeisterMethode\"], gemessen: %v", unklassifiziert)
	}
}

const sscgFixtureStoreUnmarkierteMethode = `package store

func (s *Store) UnmarkierteMethode() error {
	return nil
}
`

const sscgFixtureHandlerRuftUnmarkierteMethodeAuf = `package handler

func H(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		_ = s.UnmarkierteMethode()
	}
}
`

func TestStoreScopeCallGuardKlassifikationsPflichtEndToEnd(t *testing.T) {
	storeErg, err := sscgScanStoreQuelle("unmarkiert.go", []byte(sscgFixtureStoreUnmarkierteMethode))
	if err != nil {
		t.Fatalf("Store-Fixture liess sich nicht parsen: %v", err)
	}
	_, aufgerufenRoh, err := sscgScanHandlerQuelle("h.go", []byte(sscgFixtureHandlerRuftUnmarkierteMethodeAuf), map[string]bool{})
	if err != nil {
		t.Fatalf("Handler-Fixture liess sich nicht parsen: %v", err)
	}
	aufgerufen := map[string]bool{}
	for m := range aufgerufenRoh {
		if storeErg.AlleMethoden[m] {
			aufgerufen[m] = true
		}
	}
	auslöser := map[string]bool{}
	for m := range storeErg.RequireUserMethoden {
		auslöser[m] = true
	}
	for m := range storeErg.Required {
		auslöser[m] = true
	}
	exempt := map[string]bool{}
	for m := range storeErg.Exempt {
		exempt[m] = true
	}

	unklassifiziert := sscgKlassifikationsPflicht(aufgerufen, auslöser, exempt)
	if len(unklassifiziert) != 1 || unklassifiziert[0] != "UnmarkierteMethode" {
		t.Fatalf("erwartet Fund fuer UnmarkierteMethode (weder requireUser() noch Marker), gemessen: %v", unklassifiziert)
	}
}

// --- AC-4 -------------------------------------------------------------------

const sscgFixtureDoppeltMarkiert = `package store

// gz-store-scope-exempt: Kennung kommt als Parameter herein, siehe Signatur
// gz-store-scope-required: baut den Schluessel direkt aus s.UserID selbst
func (s *Store) Doppelt(id string) error {
	return nil
}
`

const sscgFixtureWiderspruechlich = `package store

// gz-store-scope-exempt: Kennung kommt angeblich als Parameter herein
func (s *Store) Widerspruch(id string) error {
	if err := s.requireUser(); err != nil {
		return err
	}
	return nil
}
`

const sscgFixtureVerwaisterMarkerAmDateiende = `package store

func (s *Store) OhneMarker() error {
	return nil
}

// gz-store-scope-exempt: haengt an keiner Methode mehr, sie wurde geloescht
var _ = 1
`

const sscgFixtureKurzeBegruendung = `package store

// gz-store-scope-exempt: passt
func (s *Store) KurzBegruendet() error {
	return nil
}
`

func TestStoreScopeCallGuardMarkerHygiene(t *testing.T) {
	faelle := []struct {
		name            string
		quelle          string
		erwMeldungsTeil string
	}{
		{"doppelt markiert", sscgFixtureDoppeltMarkiert, "doppelt markiert"},
		{"widerspruechlicher Marker", sscgFixtureWiderspruechlich, "widerspruechlich"},
		{"verwaister Marker -- Name existiert nicht", sscgFixtureVerwaisterMarkerAmDateiende, "verwaist"},
		{"Begruendung unter 15 Zeichen", sscgFixtureKurzeBegruendung, "zu kurz"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			erg, err := sscgScanStoreQuelle(f.name+".go", []byte(f.quelle))
			if err != nil {
				t.Fatalf("Fixture liess sich nicht parsen: %v", err)
			}
			if len(erg.Befunde) != 1 {
				t.Fatalf("erwartet genau 1 Fund, gemessen: %+v", erg.Befunde)
			}
			if !strings.Contains(erg.Befunde[0].Meldung, f.erwMeldungsTeil) {
				t.Fatalf("Meldung enthaelt nicht %q: %q", f.erwMeldungsTeil, erg.Befunde[0].Meldung)
			}
		})
	}
}

const sscgFixtureVerwaisterCallMarker = `package handler

func H(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		// gz-store-scope-call: bewusste Ausnahme, obwohl hier eigentlich gebunden ist
		_, _ = s.LoadTrips()
	}
}
`

func TestStoreScopeCallGuardVerwaisterCallMarkerAnGebundenerAufrufstelle(t *testing.T) {
	auslöser := map[string]bool{"LoadTrips": true}
	funde, _, err := sscgScanHandlerQuelle("h.go", []byte(sscgFixtureVerwaisterCallMarker), auslöser)
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if len(funde) != 1 || !strings.Contains(funde[0].Meldung, "verwaist") {
		t.Fatalf("erwartet genau 1 Fund ueber den verwaisten Call-Marker, gemessen: %+v", funde)
	}
}

const sscgFixtureGueltigerCallMarker = `package handler

func H(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// gz-store-scope-call: kontouebergreifender Sonderfall, siehe requireLocalOnly
		_, _ = s.LoadTrips()
	}
}
`

func TestStoreScopeCallGuardGueltigerCallMarkerUnterdrueckt(t *testing.T) {
	auslöser := map[string]bool{"LoadTrips": true}
	funde, _, err := sscgScanHandlerQuelle("h.go", []byte(sscgFixtureGueltigerCallMarker), auslöser)
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if len(funde) != 0 {
		t.Fatalf("ein gueltiger gz-store-scope-call Marker haette den Fund unterdruecken muessen: %+v", funde)
	}
}

// --- AC-5 -------------------------------------------------------------------

func TestStoreScopeCallGuardSelbstschutzMindestzahlSchlaegtBeiGeleerterAuslösermengeFehl(t *testing.T) {
	// Rueckdreh-Gegenprobe (AC-7): eine kuenstlich geleerte Auslösermenge
	// muss den Selbstschutz ROT machen, nicht einen Nulldurchlauf ergeben
	// (Lehre #2151 C, "vakuum-gruen").
	if err := sscgSelbstschutzMindestzahl(map[string]bool{}); err == nil {
		t.Fatalf("Mindestzahl-Assertion haette bei einer leeren Auslösermenge fehlschlagen muessen")
	}
}

func TestStoreScopeCallGuardSelbstschutzStichprobeSchlaegtBeiFehlenderMethodeFehl(t *testing.T) {
	unvollstaendig := map[string]bool{"LoadTrip": true, "SaveTrip": true, "LoadLocations": true}
	// LoadComparePresets fehlt bewusst.
	if err := sscgSelbstschutzStichprobe(unvollstaendig); err == nil {
		t.Fatalf("Stichprobenpruefung haette bei fehlender LoadComparePresets fehlschlagen muessen")
	}
}

func TestStoreScopeCallGuardSelbstschutzDateizahlSchlaegtBeiWenigenDateienFehl(t *testing.T) {
	if err := sscgSelbstschutzDateizahl(1); err == nil {
		t.Fatalf("Dateizahl-Assertion haette bei 1 gescannter Datei fehlschlagen muessen")
	}
}

// --- AC-7 (weitere Mutations-Gegenproben, ueber AC-1/AC-4 hinaus) ----------

const sscgFixtureOhneWithUserUeberhaupt = `package handler

func H(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		_, _ = s.LoadTrips()
	}
}
`

func TestStoreScopeCallGuardMutationOhneWithUserUeberhaupt(t *testing.T) {
	auslöser := map[string]bool{"LoadTrips": true}
	funde, _, err := sscgScanHandlerQuelle("h.go", []byte(sscgFixtureOhneWithUserUeberhaupt), auslöser)
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	if len(funde) != 1 {
		t.Fatalf("ein Handler ganz ohne WithUser haette genau 1 Fund liefern muessen, gemessen: %+v", funde)
	}
}

const sscgFixtureMitExemptMarker = `package store

// gz-store-scope-exempt: Kennung kommt als Parameter herein, kein WithUser noetig
func (s *Store) ParamKennung(id string) error {
	return nil
}
`

const sscgFixtureOhneMarkerMehr = `package store

func (s *Store) ParamKennung(id string) error {
	return nil
}
`

func TestStoreScopeCallGuardMarkerEntfernenMachtKlassifikationRot(t *testing.T) {
	mit, err := sscgScanStoreQuelle("mit.go", []byte(sscgFixtureMitExemptMarker))
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}
	ohne, err := sscgScanStoreQuelle("ohne.go", []byte(sscgFixtureOhneMarkerMehr))
	if err != nil {
		t.Fatalf("Fixture liess sich nicht parsen: %v", err)
	}

	aufgerufen := map[string]bool{"ParamKennung": true}
	auslöserLeer := map[string]bool{}

	mitExempt := map[string]bool{}
	for m := range mit.Exempt {
		mitExempt[m] = true
	}
	if u := sscgKlassifikationsPflicht(aufgerufen, auslöserLeer, mitExempt); len(u) != 0 {
		t.Fatalf("mit Marker haette 0 Funde liefern muessen, gemessen: %v", u)
	}

	ohneExempt := map[string]bool{}
	for m := range ohne.Exempt {
		ohneExempt[m] = true
	}
	if u := sscgKlassifikationsPflicht(aufgerufen, auslöserLeer, ohneExempt); len(u) != 1 || u[0] != "ParamKennung" {
		t.Fatalf("ohne Marker haette ParamKennung als unklassifiziert gemeldet werden muessen, gemessen: %v", u)
	}
}
