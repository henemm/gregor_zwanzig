package store

// TDD RED — Issue #2152, AC-7: forEachRealAccount (address_owner.go:53)
// entscheidet ueber das geladene Profil-Flag, nicht ueber den Namen.
// Spec: docs/specs/modules/testkonto_profilfeld.md
//
// forEachRealAccount ist unexportiert; gemessen wird ueber die beiden
// exportierten Nutzer ResolveAddressOwner und IsAddressTakenByOtherAccount.
// Bewusst KEIN neues Symbol referenziert (Roh-JSON-Profile) — das RED ist eine
// Assertion, kein Compile-Fehler. GREEN: forEachRealAccount laedt u ZUERST und
// ueberspringt bei model.IsTestAccount(u).

import (
	"testing"
)

const protesterAddr = "protester@example.com"

func seedProtesterConfirmed(t *testing.T, dataDir string) {
	t.Helper()
	writeRawUserJSON(t, dataDir, "protester",
		`{"id":"protester","email":"`+protesterAddr+`","mail_to":"`+protesterAddr+`",`+
			`"password_hash":"$2a$10$x","email_verified_at":"2026-09-17T11:00:00Z"}`)
}

// TestResolveAddressOwner_ProtesterOhneFlagIstInhaber_AC7 — bestaetigtes Konto
// mit "test" im Namen, ohne Flag → AddressOwned, Inhaber protester.
func TestResolveAddressOwner_ProtesterOhneFlagIstInhaber_AC7(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	seedProtesterConfirmed(t, tmpDir)

	u, res, err := s.ResolveAddressOwner(protesterAddr)
	if err != nil {
		t.Fatalf("ResolveAddressOwner: %v", err)
	}
	if res != AddressOwned || u == nil || u.ID != "protester" {
		t.Fatalf("AC-7: protester (ohne Flag) muss als Inhaber erkannt werden, got res=%v u=%+v", res, u)
	}
}

// TestIsAddressTakenByOtherAccount_ProtesterOhneFlagBelegt_AC7 — dieselbe
// Adresse gilt bei der Registrierung eines Zweitkontos als belegt.
func TestIsAddressTakenByOtherAccount_ProtesterOhneFlagBelegt_AC7(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	seedProtesterConfirmed(t, tmpDir)

	taken, err := s.IsAddressTakenByOtherAccount(protesterAddr, "")
	if err != nil {
		t.Fatalf("IsAddressTakenByOtherAccount: %v", err)
	}
	if !taken {
		t.Fatal("AC-7: Adresse von protester (ohne Flag) muss als belegt gelten")
	}
}

// TestResolveAddressOwner_FlaggedNeutralNameZaehltNicht_AC7 — Gegenprobe:
// neutraler Name mit is_test_user=true wird uebersprungen → AddressFree.
func TestResolveAddressOwner_FlaggedNeutralNameZaehltNicht_AC7(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	writeRawUserJSON(t, tmpDir, "mitarbeiter42",
		`{"id":"mitarbeiter42","email":"m42@example.com","mail_to":"m42@example.com",`+
			`"password_hash":"$2a$10$x","email_verified_at":"2026-09-17T11:00:00Z","is_test_user":true}`)

	u, res, err := s.ResolveAddressOwner("m42@example.com")
	if err != nil {
		t.Fatalf("ResolveAddressOwner: %v", err)
	}
	if res != AddressFree || u != nil {
		t.Fatalf("AC-7: mitarbeiter42 (is_test_user=true) darf NICHT Inhaber sein, got res=%v u=%+v", res, u)
	}
	taken, err := s.IsAddressTakenByOtherAccount("m42@example.com", "")
	if err != nil {
		t.Fatalf("IsAddressTakenByOtherAccount: %v", err)
	}
	if taken {
		t.Fatal("AC-7: Adresse eines geflaggten Testkontos darf nicht als belegt gelten")
	}
}

// TestForEachRealAccount_UnlesbaresFixtureProfilIstFailClosed — GREEN-Ergaenzung
// (#2152): die Klassifikation braucht jetzt das geladene Profil, das Laden steht
// also VOR dem Ueberspringen. Damit bricht eine unlesbare user.json auch beim
// Fixture-Konto tg-live-e2e ab, das frueher rein per Namen uebersprungen wurde.
// Bewusste Verhaltensaenderung, hier festgehalten: fail-closed statt still
// weiterzaehlen — eine uebersehene Zeile wuerde die Adress-Eindeutigkeit kippen.
func TestForEachRealAccount_UnlesbaresFixtureProfilIstFailClosed(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	seedProtesterConfirmed(t, tmpDir)
	writeRawUserJSON(t, tmpDir, "tg-live-e2e", `{"id":"tg-live-e2e",`)

	if _, _, err := s.ResolveAddressOwner(protesterAddr); err == nil {
		t.Error("unlesbare user.json muss ResolveAddressOwner mit Fehler abbrechen (fail-closed)")
	}
	if _, err := s.IsAddressTakenByOtherAccount(protesterAddr, ""); err == nil {
		t.Error("unlesbare user.json muss IsAddressTakenByOtherAccount mit Fehler abbrechen (fail-closed)")
	}
}
