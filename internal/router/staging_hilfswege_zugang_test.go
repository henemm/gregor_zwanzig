package router

// Issue #2961 (Spec security_haertung_2026_11_go_schnittstellen.md AC-18 bis
// AC-20): die Staging-Hilfsendpunkte verlangen eine gueltige Sitzung; das
// E-Mail-Token gibt es aber nicht fuer beliebige fremde Konten, und SMS-Code
// und Seed wirken nur auf das eigene Konto. Gemessen am echten Router unter
// GZ_ENV=staging.

import (
	"net/http"
	"testing"
	"time"

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

func TestStagingHilfswege_ZielregelUndEigenesKonto(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	e := neueBremsUmgebung(t, nil)
	alt := time.Now().Add(-48 * time.Hour)
	bestaetigt := alt

	// Gewoehnliches, nicht frisches Konto als Aufrufer (keine Rolle, kein Testkonto).
	nora := e.kontoMit(t, model.User{ID: "nora-normal", Email: "nora@beispiel.de", Tier: "free",
		CreatedAt: alt, EmailVerifiedAt: &bestaetigt, SmsTo: "+491510000001"})
	e.kontoMit(t, model.User{ID: "u-frisch01", Email: "frisch@beispiel.de", CreatedAt: time.Now()})
	e.kontoMit(t, model.User{ID: "tim-test", Email: "tim@beispiel.de", CreatedAt: alt, IsTestUser: true, EmailVerifiedAt: &bestaetigt})
	e.kontoMit(t, model.User{ID: "vera-fremd", Email: "vera@beispiel.de", Tier: "free", CreatedAt: alt, EmailVerifiedAt: &bestaetigt})

	token := func(ziel string) (int, string) {
		w := e.rufe(t, http.MethodPost, "/api/auth/verify-email/staging-token", []byte(`{"username":"`+ziel+`"}`), nora)
		return w.Code, w.Body.String()
	}
	// AC-19: eigenes Konto, Testkonto, frisch registriertes unbestaetigtes Konto.
	for _, ziel := range []string{"nora-normal", "tim-test", "u-frisch01"} {
		if code, body := token(ziel); code != http.StatusOK {
			t.Errorf("Token fuer %s: erwartet 200, bekommen %d: %s", ziel, code, body)
		}
	}
	// AC-18: fremdes bestaetigtes Konto sieht aus wie ein unbekanntes.
	cFremd, bFremd := token("vera-fremd")
	cUnbek, bUnbek := token("gibt-es-nicht")
	if cFremd != http.StatusNotFound || cFremd != cUnbek || bFremd != bUnbek {
		t.Fatalf("fremdes Konto (%d %s) muss wie unbekanntes (%d %s) aussehen", cFremd, bFremd, cUnbek, bUnbek)
	}
	if tok, _ := e.s.LoadVerificationToken("vera-fremd"); tok != nil {
		t.Fatal("fuer ein fremdes Konto ist ein Token entstanden")
	}

	// AC-20: SMS-Code und Seed wirken nur auf das eigene Konto — auch wenn
	// der Rumpf ein fremdes Konto nennt.
	if w := e.rufe(t, http.MethodPost, "/api/auth/sms/staging-code", []byte(`{"username":"vera-fremd"}`), nora); w.Code != http.StatusOK {
		t.Errorf("eigener SMS-Code: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	e.rufe(t, http.MethodPost, "/api/auth/staging-seed", []byte(`{"tier":"premium","user_id":"vera-fremd"}`), nora)
	if u, _ := e.s.LoadUser("vera-fremd"); u == nil || u.Tier != "free" {
		t.Fatal("Seed hat ein fremdes Konto veraendert")
	}
}
