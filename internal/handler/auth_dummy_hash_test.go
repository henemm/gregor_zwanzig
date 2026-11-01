package handler

// TDD RED — Issue #2163 Scheibe 1, AC-10 (Stufe 2: neues Symbol).
// Spec: docs/specs/modules/auth_haertung_go_2163.md
//
// Festgelegtes Symbol (package handler, unexportiert):
//
//	func dummyPasswordHash() []byte
//
// Liefert den prozessweit EINMAL (sync.Once) erzeugten bcrypt-Dummy-Hash, gegen
// den alle Login-/Forgot-Nicht-Treffer-Zweige vergleichen. Cost aus
// bcrypt.DefaultCost (dieselbe Quelle wie router.go beim Speichern), nicht hart
// kodiert.
//
// RED-Beleg: Build-Fehler "undefined: dummyPasswordHash" — dieser Test bricht
// bis zur Umsetzung das Testbinary des ganzen Pakets internal/handler.

import (
	"bytes"
	"testing"

	"golang.org/x/crypto/bcrypt"
)

func TestDummyPasswordHash_CostIstDefaultCost_EinmalErzeugt_AC10(t *testing.T) {
	h1 := dummyPasswordHash()
	cost, err := bcrypt.Cost(h1)
	if err != nil {
		t.Fatalf("AC-10: Dummy-Hash ist kein gueltiger bcrypt-Hash: %v (%q)", err, h1)
	}
	if cost != bcrypt.DefaultCost {
		t.Errorf("AC-10: Dummy-Hash-Cost erwartet bcrypt.DefaultCost (%d), bekommen %d", bcrypt.DefaultCost, cost)
	}

	h2 := dummyPasswordHash()
	if !bytes.Equal(h1, h2) {
		t.Errorf("AC-10: zwei Zugriffe muessen denselben Hash liefern (sync.Once) — bcrypt salzt zufaellig, "+
			"ein zweiter Hash belegt eine Neuerzeugung: %q != %q", h1, h2)
	}
}
