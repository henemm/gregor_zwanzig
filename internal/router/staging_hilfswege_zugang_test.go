package router

// Issue #2961 (Spec security_haertung_2026_11_go_schnittstellen.md AC-18 bis
// AC-20): die Staging-Hilfsendpunkte verlangen zusaetzlich zur Sitzung einen
// berechtigten Aufrufer (Admin, Betreiber-Konto GZ_AUTH_USER, Testkonto), und
// das E-Mail-Token gibt es nicht fuer beliebige fremde Konten. Gemessen am
// echten Router unter GZ_ENV=staging.

import (
	"net/http"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

func (e *bremsUmgebung) kontoMit(t *testing.T, u model.User) *http.Cookie {
	t.Helper()
	if err := e.s.SaveUser(u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := e.s.AddSession(u.ID, sessionIDFor(u.ID)); err != nil {
		t.Fatalf("AddSession: %v", err)
	}
	return sessionCookieFor(u.ID, e.secret)
}

func TestStagingHilfswege_ZugangUndZielkonten(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	e := neueBremsUmgebung(t, func(c *config.Config) {
		c.AdminUserIDs = "ada-admin"
		c.AuthUser = "bea-betreiber"
	})
	alt := time.Now().Add(-48 * time.Hour)
	jetzt := time.Now()
	bestaetigt := alt

	normal := e.kontoMit(t, model.User{ID: "nora-normal", Email: "nora@beispiel.de", CreatedAt: alt, EmailVerifiedAt: &bestaetigt, SmsTo: "+491510000001"})
	test := e.kontoMit(t, model.User{ID: "tim-test", Email: "tim@beispiel.de", CreatedAt: alt, IsTestUser: true, EmailVerifiedAt: &bestaetigt})
	admin := e.kontoMit(t, model.User{ID: "ada-admin", Email: "ada@beispiel.de", CreatedAt: alt, EmailVerifiedAt: &bestaetigt})
	betreiber := e.kontoMit(t, model.User{ID: "bea-betreiber", Email: "bea@beispiel.de", CreatedAt: alt, EmailVerifiedAt: &bestaetigt})
	frisch := e.kontoMit(t, model.User{ID: "u-frisch01", Email: "frisch@beispiel.de", CreatedAt: jetzt, SmsTo: "+491510000002"})
	// Ein bestaetigtes, nicht frisches fremdes Konto.
	e.kontoMit(t, model.User{ID: "vera-fremd", Email: "vera@beispiel.de", CreatedAt: alt, EmailVerifiedAt: &bestaetigt})

	// AC-18: gewoehnliches Konto -> 403 auf allen drei Wegen.
	for _, p := range []struct{ pfad, body string }{
		{"/api/auth/verify-email/staging-token", `{"username":"nora-normal"}`},
		{"/api/auth/staging-seed", `{"tier":"premium"}`},
		{"/api/auth/sms/staging-code", `{}`},
	} {
		if w := e.rufe(t, http.MethodPost, p.pfad, []byte(p.body), normal); w.Code != http.StatusForbidden {
			t.Errorf("%s als gewoehnliches Konto: erwartet 403, bekommen %d: %s", p.pfad, w.Code, w.Body.String())
		}
	}
	if u, _ := e.s.LoadUser("nora-normal"); u == nil || u.Tier == "premium" {
		t.Fatal("Seed hat den Tarif eines gewoehnlichen Kontos veraendert")
	}

	// AC-19: berechtigte Aufrufer (Admin, Betreiber, Testkonto) — Token fuer das
	// frisch registrierte, unbestaetigte Konto (E2E-Zweitnutzer) gibt es.
	for name, c := range map[string]*http.Cookie{"admin": admin, "betreiber": betreiber, "test": test} {
		if w := e.rufe(t, http.MethodPost, "/api/auth/verify-email/staging-token", []byte(`{"username":"u-frisch01"}`), c); w.Code != http.StatusOK {
			t.Errorf("%s: Token fuer frisches Konto erwartet 200, bekommen %d: %s", name, w.Code, w.Body.String())
		}
	}

	// AC-19: fremdes, bestaetigtes Konto und unbekanntes Konto sehen gleich aus.
	wFremd := e.rufe(t, http.MethodPost, "/api/auth/verify-email/staging-token", []byte(`{"username":"vera-fremd"}`), test)
	wUnbekannt := e.rufe(t, http.MethodPost, "/api/auth/verify-email/staging-token", []byte(`{"username":"gibt-es-nicht"}`), test)
	if wFremd.Code != http.StatusNotFound || wFremd.Code != wUnbekannt.Code || wFremd.Body.String() != wUnbekannt.Body.String() {
		t.Fatalf("fremdes Konto (%d %s) muss wie unbekanntes (%d %s) aussehen", wFremd.Code, wFremd.Body.String(), wUnbekannt.Code, wUnbekannt.Body.String())
	}
	if tok, _ := e.s.LoadVerificationToken("vera-fremd"); tok != nil {
		t.Fatal("fuer ein fremdes Konto ist ein Token entstanden")
	}

	// AC-20: ein frisch registriertes Wegwerfkonto holt seinen EIGENEN SMS-Code.
	if w := e.rufe(t, http.MethodPost, "/api/auth/sms/staging-code", []byte(`{}`), frisch); w.Code != http.StatusOK {
		t.Errorf("frisches Konto, eigener SMS-Code: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}
