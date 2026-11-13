package model

// Issue #2961 (ADR-0116, F004): gemeinsame Wahrheitstabelle der
// Schreibweisen, gelesen auch vom Python-Test
// tests/tdd/test_premium_sms_nummer_normalform.py.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type nummernTabelle struct {
	Gruppen []struct {
		Normalform    string   `json:"normalform"`
		Schreibweisen []string `json:"schreibweisen"`
	} `json:"gruppen"`
	Leer []string `json:"leer"`
}

func TestNormalizePremiumSmsNumberGemeinsameTabelle(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "tests", "fixtures", "premium_sms_nummern_normalform.json"))
	if err != nil {
		t.Fatal(err)
	}
	var tab nummernTabelle
	if err := json.Unmarshal(raw, &tab); err != nil {
		t.Fatal(err)
	}
	gesehen := map[string]bool{}
	for _, g := range tab.Gruppen {
		if gesehen[g.Normalform] {
			t.Fatalf("Normalform %q doppelt in der Tabelle", g.Normalform)
		}
		gesehen[g.Normalform] = true
		for _, s := range g.Schreibweisen {
			if got := NormalizePremiumSmsNumber(s); got != g.Normalform {
				t.Errorf("%q -> %q, erwartet %q", s, got, g.Normalform)
			}
		}
	}
	for _, s := range tab.Leer {
		if got := NormalizePremiumSmsNumber(s); got != "" {
			t.Errorf("%q -> %q, erwartet leer", s, got)
		}
	}
}
