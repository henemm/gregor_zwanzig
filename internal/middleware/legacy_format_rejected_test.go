package middleware

// TDD RED — Issue #2262: Rückbau des Alt-Format-Übergangs-Zweigs (ADR-0060).
// Spec: docs/specs/modules/session_allowlist.md, AC-19.
//
// Ziel-Zustand nach der Implementierung: ein Anmelde-Merkmal im alten
// dreiteiligen Format wird wie ein unbekanntes Cookie behandelt (401), ohne
// stille Hebung. Dieser Test schlägt VOR der Implementierung fehl, weil der
// Legacy-Zweig das Merkmal heute noch annimmt und upgraded — siehe
// TestLegacyCookie_AcceptedAndUpgradedToFourPart in session_allowlist_test.go,
// der bis zur Implementierung grün bleibt und dort zusammen mit dem
// Legacy-Zweig entfernt wird (AC-10 entfällt laut Spec).

import (
	"net/http"
	"testing"
	"time"
)

// AC-19 (a), Go-Dienst: Ein gültig signiertes, junges Alt-Merkmal wird nach
// dem Rückbau abgewiesen — ohne Sonderbehandlung, ohne Set-Cookie-Hebung.
//
// Positivkontrolle zuerst: ein per echtem (neuem) Format ausgestelltes
// Merkmal muss am selben Endpunkt weiterhin durchgehen — sonst bewiese ein
// 401 nur einen kaputten Endpunkt, nicht die gezielte Ablehnung des
// Alt-Formats.
func TestLegacyCookie_RejectedAfterRueckbau(t *testing.T) {
	dataDir := t.TempDir()
	seedUserRecord(t, dataDir, "alice")

	writeAllowlist(t, dataDir, "alice", "sess-ac19-ctrl")
	control := makeNewSessionCookie("alice", "sess-ac19-ctrl", time.Now().Unix(), testSecret)
	if rr := authProbe(t, dataDir, testSecret, control); rr.Code != http.StatusOK {
		t.Fatalf("AC-19 Positivkontrolle: neues Format muss weiterhin gültig sein, bekommen %d", rr.Code)
	}

	// Alt-Format: gültig signiert, jünger als 24h — nach der VORHERIGEN Regel
	// wäre das angenommen und gehoben worden.
	legacy := makeSessionCookie("alice", time.Now().Unix(), testSecret)
	rr := authProbe(t, dataDir, testSecret, legacy)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("AC-19: Alt-Format-Merkmal muss nach dem Rückbau abgewiesen werden, bekommen %d", rr.Code)
	}
	if up := upgradedCookie(rr); up != "" {
		t.Errorf("AC-19: keine stille Hebung mehr erwartet, aber Set-Cookie mit %q gefunden", up)
	}
}
