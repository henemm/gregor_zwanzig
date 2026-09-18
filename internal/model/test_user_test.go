package model

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// TDD RED — Issue #2152, AC-5 (Go) + AC-8 (Roundtrip): Testkonto-Status ueber
// Profilfeld statt Namens-Heuristik.
// Spec: docs/specs/modules/testkonto_profilfeld.md
//
// Erwartete Produktivsymbole (entstehen in /50, NICHT hier deklariert — der
// Build-Fehler dieses Pakets ist das beabsichtigte RED):
//
//	User.IsTestUser bool `json:"is_test_user,omitempty"`
//	func IsTestAccount(u *User) bool   // = u.IsTestUser || strings.EqualFold(u.ID, "tg-live-e2e")
//	                                    // nil-sicher: IsTestAccount(nil) == false
//
// IsTestUserID (rohe ID) und IsTestUserIDSubstringOnly sind laut Spec
// (Implementation Details 2) entfallen — die frueheren Tests
// TestIsTestUserID_CaseParity / TestIsTestUserIDSubstringOnly_ExcludesFixedFixture
// pinnten die Namens-Heuristik und wurden in GREEN ersatzlos entfernt (AC-10);
// die Case-Paritaet der Fixture-ID prueft TestIsTestAccount_ProfilfeldStattNamensHeuristik.
// ---------------------------------------------------------------------------

// TestIsTestAccount_ProfilfeldStattNamensHeuristik — AC-5: tg-live-e2e ohne
// Flag bleibt Testkonto; "protester" ohne Flag ist KEINS (Name enthaelt
// "test"); "mitarbeiter42" mit Flag ist eins (Name neutral).
func TestIsTestAccount_ProfilfeldStattNamensHeuristik(t *testing.T) {
	cases := []struct {
		name string
		u    *User
		want bool
	}{
		{"tg-live-e2e ohne Flag", &User{ID: "tg-live-e2e"}, true},
		{"TG-LIVE-E2E ohne Flag (case-insensitive)", &User{ID: "TG-LIVE-E2E"}, true},
		{"protester ohne Flag", &User{ID: "protester"}, false},
		{"tdd-prod-user ohne Flag", &User{ID: "tdd-prod-user"}, false},
		{"mitarbeiter42 mit Flag", &User{ID: "mitarbeiter42", IsTestUser: true}, true},
		{"admin mit Flag", &User{ID: "admin", IsTestUser: true}, true},
		{"henning ohne Flag", &User{ID: "henning"}, false},
		{"nil-Profil", nil, false},
	}
	for _, c := range cases {
		if got := IsTestAccount(c.u); got != c.want {
			t.Errorf("IsTestAccount(%s) = %v, want %v", c.name, got, c.want)
		}
	}
}

// TestUserIsTestUser_JSONRoundtripErhaeltAlleFelder — AC-8 (Schema-Rework,
// BUG-DATALOSS-GR221): User mit IsTestUser=true → JSON → zurueck, das Flag UND
// die Nachbarfelder bleiben erhalten; ohne Flag fehlt der Schluessel im JSON
// (omitempty), damit Bestandsdaten unveraendert laden.
func TestUserIsTestUser_JSONRoundtripErhaeltAlleFelder(t *testing.T) {
	created := time.Date(2026, 9, 17, 10, 0, 0, 0, time.UTC)
	in := User{
		ID: "mitarbeiter42", Email: "m42@example.com", MailTo: "m42-briefing@example.com",
		TelegramChatID: "424242", DisplayName: "M 42", Tier: "basic",
		CreatedAt: created, IsTestUser: true,
	}
	data, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if !strings.Contains(string(data), `"is_test_user":true`) {
		t.Errorf("JSON traegt kein is_test_user:true — got %s", data)
	}
	var out User
	if err := json.Unmarshal(data, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !reflect.DeepEqual(in, out) {
		t.Errorf("Roundtrip veraendert Felder:\n in=%+v\nout=%+v", in, out)
	}

	plain, _ := json.Marshal(User{ID: "henning", CreatedAt: created})
	if strings.Contains(string(plain), "is_test_user") {
		t.Errorf("ohne Flag darf der Schluessel fehlen (omitempty) — got %s", plain)
	}
}
