package handler

// Issue #2961 (Spec AC-21): die Premium-SMS-Ratebremse warnt bei
// Erschoepfung genau einmal je Erschoepfungsphase im Log — nicht vorher und
// nicht bei jedem weiteren abgewiesenen Vergleich; nach Ablauf des Fensters
// und erneuter Erschoepfung wieder.

import (
	"bytes"
	"log"
	"os"
	"strings"
	"testing"
	"time"
)

func TestPremiumSmsRatebremse_WarnLogGenauBeiErschoepfung(t *testing.T) {
	var buf bytes.Buffer
	log.SetOutput(&buf)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })

	uhr := time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)
	rl := NewPremiumSmsRateLimiter(10)
	rl.jetzt = func() time.Time { return uhr }
	warnungen := func() int { return strings.Count(buf.String(), "WARN: Ratebremse") }

	for i := 0; i < 10; i++ {
		if !rl.Allow() {
			t.Fatalf("Versuch %d vorzeitig gesperrt", i+1)
		}
		rl.RecordFailure()
	}
	if n := warnungen(); n != 0 {
		t.Fatalf("Warnung vor der Erschoepfung: %d", n)
	}
	for i := 0; i < 3; i++ {
		if rl.Allow() {
			t.Fatal("erschoepfte Bremse laesst Vergleich zu")
		}
	}
	if n := warnungen(); n != 1 {
		t.Fatalf("erwartet genau eine Warnung, gefunden %d: %q", n, buf.String())
	}
	uhr = uhr.Add(time.Hour + time.Second)
	for i := 0; i < 10; i++ {
		if !rl.Allow() {
			t.Fatalf("nach Fensterablauf Versuch %d gesperrt", i+1)
		}
		rl.RecordFailure()
	}
	rl.Allow()
	if n := warnungen(); n != 2 {
		t.Fatalf("nach erneuter Erschoepfung erwartet zwei Warnungen, gefunden %d", n)
	}
}
