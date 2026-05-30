package handler

// TDD RED — Issue #468 AAGUID-Labels.
// Tests MUST FAIL: aaguidToName does not exist yet.

import (
	"encoding/hex"
	"testing"
)

// iCloud Keychain AAGUID: fbfc3007-154e-4ecc-8cfb-6ef08c534b35
var iCloudAAGUIDHex = "fbfc3007154e4ecc8cfb6ef08c534b35"

// Windows Hello AAGUID: 08987058-cadc-4b81-b6e1-30de50dcbe96
var windowsHelloAAGUIDHex = "08987058cadc4b81b6e130de50dcbe96"

// Google Password Manager AAGUID: ee882879-721c-4913-9775-3dfcce97072a
var googlePMAAGUIDHex = "ee882879721c491397753dfcce97072a"

func mustDecodeHex(t *testing.T, s string) []byte {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatalf("hex decode %q: %v", s, err)
	}
	return b
}

// AC-1: Bekannte AAGUID → menschenlesbarer Name
func TestAaguidToName_KnownAAGUID_iCloudKeychain(t *testing.T) {
	// GIVEN: Die AAGUID von iCloud Keychain (fbfc3007-154e-4ecc-8cfb-6ef08c534b35)
	aaguid := mustDecodeHex(t, iCloudAAGUIDHex)

	// WHEN: aaguidToName aufgerufen wird
	got := aaguidToName(aaguid)

	// THEN: Gibt "iCloud Keychain" zurück
	if got != "iCloud Keychain" {
		t.Errorf("iCloud Keychain AAGUID: got %q, want %q", got, "iCloud Keychain")
	}
}

func TestAaguidToName_KnownAAGUID_WindowsHello(t *testing.T) {
	// GIVEN: Die AAGUID von Windows Hello (08987058-cadc-4b81-b6e1-30de50dcbe96)
	aaguid := mustDecodeHex(t, windowsHelloAAGUIDHex)

	// WHEN: aaguidToName aufgerufen wird
	got := aaguidToName(aaguid)

	// THEN: Gibt "Windows Hello" zurück
	if got != "Windows Hello" {
		t.Errorf("Windows Hello AAGUID: got %q, want non-empty name", got)
	}
}

// AC-2: Zero-AAGUID (alle Bytes 0x00) → leerer String
func TestAaguidToName_ZeroAAGUID(t *testing.T) {
	// GIVEN: Zero-AAGUID (alle 16 Bytes = 0x00, typisch für "none"-Attestation)
	zero := make([]byte, 16)

	// WHEN: aaguidToName aufgerufen wird
	got := aaguidToName(zero)

	// THEN: Gibt "" zurück (kein Name, kein Panic)
	if got != "" {
		t.Errorf("Zero AAGUID: got %q, want empty string", got)
	}
}

// AC-4: Falsche Länge → leerer String, kein Panic
func TestAaguidToName_WrongLength_Empty(t *testing.T) {
	// GIVEN: Leeres Byte-Slice
	// WHEN: aaguidToName aufgerufen wird
	// THEN: Gibt "" zurück ohne Panic
	got := aaguidToName([]byte{})
	if got != "" {
		t.Errorf("empty slice: got %q, want empty string", got)
	}
}

func TestAaguidToName_WrongLength_15Bytes(t *testing.T) {
	// GIVEN: 15-Byte-Slice (zu kurz)
	// WHEN / THEN: kein Panic, leerer String
	got := aaguidToName(make([]byte, 15))
	if got != "" {
		t.Errorf("15-byte slice: got %q, want empty string", got)
	}
}

func TestAaguidToName_WrongLength_17Bytes(t *testing.T) {
	// GIVEN: 17-Byte-Slice (zu lang)
	// WHEN / THEN: kein Panic, leerer String
	got := aaguidToName(make([]byte, 17))
	if got != "" {
		t.Errorf("17-byte slice: got %q, want empty string", got)
	}
}

// Unbekannte AAGUID → leerer String
func TestAaguidToName_UnknownAAGUID(t *testing.T) {
	// GIVEN: Eine gültige 16-Byte-AAGUID die nicht in der Map steht
	unknown := make([]byte, 16)
	unknown[0] = 0xDE
	unknown[1] = 0xAD
	unknown[2] = 0xBE
	unknown[3] = 0xEF

	// WHEN: aaguidToName aufgerufen wird
	got := aaguidToName(unknown)

	// THEN: Gibt "" zurück (graceful fallback)
	if got != "" {
		t.Errorf("unknown AAGUID: got %q, want empty string", got)
	}
}
