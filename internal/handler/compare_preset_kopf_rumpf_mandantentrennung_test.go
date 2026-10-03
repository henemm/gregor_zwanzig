package handler

// Issue #2284 Scheibe S1, AC-11 (Spec: docs/specs/modules/feat_2284_s1_subscription_header.md)
//
// Regressionswaechter, heute gruen by design: Der neue Hub-Kopf-Baustein
// schickt ueber die Seite nur den minimalen Rumpf ({"name": ...}). Der
// bestehende TestComparePresetPutServerFields_TenantIsolation deckt nur den
// Spiegelfall mit VOLLEM Rumpf ab (A schreibt, Bs gleichnamige Datei bleibt).
// Hier: B schickt genau den Kopf-Rumpf an As ID, B hat unter dieser ID NICHTS.
// As Datei muss byte-gleich bleiben. Welchen Status B bekommt, ist nicht Teil
// der Zusicherung.
//
// Positivkontrolle im selben Test: A schickt denselben minimalen Rumpf und
// bekommt 200 mit geaendertem Namen. Ohne sie waere ein Router, der jedem 404
// liefert, ebenfalls gruen (vakuum-gruen).
//
// Ausfuehrung:
//   go test ./internal/handler -run TestComparePresetKopfRumpf -v

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestComparePresetKopfRumpf_FremderNutzerAendertNichts(t *testing.T) {
	s := newTestStore(t)
	id := "cp-2284-kopf-rumpf"
	sA := s.WithUser("usera")

	if err := sA.SaveComparePreset(comparePresetPutBodyStruct(id, "usera")); err != nil {
		t.Fatalf("seed A: %v", err)
	}
	pathA := filepath.Join(sA.BriefingsDir(), id+".json")
	before, err := os.ReadFile(pathA)
	if err != nil {
		t.Fatalf("As Datei vor dem PUT lesen: %v", err)
	}

	r := briefingVergleichEtagRouter(s)

	// B schickt exakt den Kopf-Rumpf an As ID.
	wB := doReq(r, http.MethodPut, "/api/compare/presets/"+id, `{"name":"fremd"}`, "", "userb")
	t.Logf("B erhielt HTTP %d (Status nicht Teil der Zusicherung)", wB.Code)

	after, err := os.ReadFile(pathA)
	if err != nil {
		t.Fatalf("As Datei nach Bs PUT lesen: %v", err)
	}
	if string(before) != string(after) {
		t.Fatalf("As Datei durch Bs PUT veraendert (Mandantentrennung verletzt).\nvorher:  %s\nnachher: %s", before, after)
	}

	// A liest weiter seinen alten Namen.
	wGet := doReq(r, http.MethodGet, "/api/compare/presets/"+id, "", "", "usera")
	if wGet.Code != http.StatusOK {
		t.Fatalf("GET durch A: expected 200, got %d: %s", wGet.Code, wGet.Body.String())
	}
	if strings.Contains(wGet.Body.String(), `"fremd"`) {
		t.Fatalf("A liest Bs Namen: %s", wGet.Body.String())
	}

	// Positivkontrolle: A aendert mit demselben minimalen Rumpf.
	wA := doReq(r, http.MethodPut, "/api/compare/presets/"+id, `{"name":"A neu"}`, "", "usera")
	if wA.Code != http.StatusOK {
		t.Fatalf("Positivkontrolle: A-PUT expected 200, got %d: %s", wA.Code, wA.Body.String())
	}
	stored, err := os.ReadFile(pathA)
	if err != nil {
		t.Fatalf("As Datei nach eigenem PUT lesen: %v", err)
	}
	if !strings.Contains(string(stored), `"A neu"`) {
		t.Fatalf("Positivkontrolle: As Name nicht gespeichert: %s", stored)
	}
	// Merge-Vertrag (#2285): fehlende Felder bleiben unveraendert.
	if !strings.Contains(string(stored), `"loc-1"`) {
		t.Fatalf("Positivkontrolle: location_ids durch minimalen Rumpf verloren: %s", stored)
	}
}
