package store

// Issue #2147 Scheibe B2, AC-5 (Resolver-Haelfte) — REGRESSIONSWAECHTER.
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §1 (Entscheidung
// 5), AC-5.
//
// Given ein bestaetigtes Konto mit mail_to=ALT und einer ausstehenden
// Aenderung auf NEU (pending_contact_address/pending_contact_field ROH im
// user.json — die Go-Struct-Felder entstehen erst in /50), plus ein zweites
// echtes Konto / When ResolveAddressOwner(NEU) und (ALT) gefragt werden /
// Then ordnet der Resolver NEU diesem Konto NICHT zu, ALT dagegen schon.
//
// Heute gruen (Pending-Felder werden beim Unmarshal ignoriert); rot wird er,
// sobald eine Umsetzung die ausstehende Adresse in den Resolver einbezieht
// oder email/mail_to vorzeitig ueberschreibt.

import (
	"os"
	"path/filepath"
	"testing"
)

func writeRawUserJSONStore(t *testing.T, dataDir, userID, raw string) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(raw), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}
}

func TestAC5_ResolverOrdnetAusstehendeAdresseDemKontoNichtZu(t *testing.T) {
	dataDir := t.TempDir()
	writeRawUserJSONStore(t, dataDir, "wanderer-alt", `{
		"id": "wanderer-alt",
		"email": "wanderer-alt@gmail.com",
		"mail_to": "wanderer-alt@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z",
		"pending_contact_address": "wanderer-neu@gmail.com",
		"pending_contact_field": "mail_to"
	}`)
	writeRawUserJSONStore(t, dataDir, "wanderer-zweit", `{
		"id": "wanderer-zweit",
		"mail_to": "wanderer-zweit@gmail.com",
		"email_verified_at": "2026-01-01T00:00:00Z"
	}`)
	s := New(dataDir, "default")

	u, res, err := s.ResolveAddressOwner("wanderer-neu@gmail.com")
	if err != nil {
		t.Fatalf("AC-5: ResolveAddressOwner(NEU) Fehler: %v", err)
	}
	if u != nil && u.ID == "wanderer-alt" {
		t.Errorf("AC-5: ausstehende Adresse wurde dem Konto wanderer-alt zugeordnet (res=%v)", res)
	}
	if res == AddressOwned {
		t.Errorf("AC-5: ausstehende Adresse gilt als besessen (res=AddressOwned, user=%v)", u)
	}

	u, res, err = s.ResolveAddressOwner("wanderer-alt@gmail.com")
	if err != nil {
		t.Fatalf("AC-5: ResolveAddressOwner(ALT) Fehler: %v", err)
	}
	if res != AddressOwned || u == nil || u.ID != "wanderer-alt" {
		t.Errorf("AC-5: alte bestaetigte Adresse muss waehrend der ausstehenden Aenderung wanderer-alt gehoeren, "+
			"bekommen res=%v user=%v", res, u)
	}
}
