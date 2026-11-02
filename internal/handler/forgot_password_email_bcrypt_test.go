package handler

// Issue #2194, Adversary-Finding F002: "Passwort vergessen" per E-Mail muss
// bei 0 und bei mehreren Treffern den Dummy-Vergleich (burnDummyCompare)
// laufen lassen, damit die Antwortzeit die Trefferzahl nicht verraet.
//
// Gezaehlt wird an der Naht bcryptCompareFn (zaehleBcrypt2194 aus
// login_email_bcrypt_einmal_test.go, delegiert an echtes bcrypt).
//
// Ist-Verhalten (gemessen): Bei genau einem Treffer laeuft KEIN Vergleich —
// dieser Pfad bezahlt seine bcrypt-Kosten ueber GenerateFromPassword fuer den
// Reset-Token. Deshalb: 0 und 2 Treffer => genau 1 Vergleich; 1 Treffer =>
// 0 Vergleiche UND ein persistierter Reset-Token (Beleg, dass der teure
// Schritt lief). Antwort in allen drei Faellen 200 mit identischem Koerper.
//
// Kein t.Parallel (package-Variable).

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
)

func TestForgotPasswordPerEmail_DummyVergleich_NullEinsZweiTreffer_F002_2194(t *testing.T) {
	s := newTestStore(t)
	kontoBcrypt2194(t, s, "einzel2194", "einzel@beispiel.de", "einzel-passwort-1")
	kontoBcrypt2194(t, s, "doppel-a2194", "zwei@beispiel.de", "doppel-a-passwort")
	kontoBcrypt2194(t, s, "doppel-b2194", "zwei@beispiel.de", "doppel-b-passwort")

	h := ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{})
	anfordern := func(kennung string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/forgot-password",
			strings.NewReader(`{"username":"`+kennung+`"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}

	n := zaehleBcrypt2194(t)
	faelle := []struct {
		name, kennung string
		vergleiche    int64
		tokenFuer     string // Konto, fuer das ein Reset-Token entstehen muss
	}{
		{"0 Treffer", "niemand@beispiel.de", 1, ""},
		{"1 Treffer", "Einzel@Beispiel.de", 0, "einzel2194"},
		{"2 Treffer", "zwei@beispiel.de", 1, ""},
	}
	var ersterKoerper string
	for i, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			atomic.StoreInt64(n, 0)
			w := anfordern(f.kennung)
			got := atomic.LoadInt64(n)
			t.Logf("[%s] bcryptCompareFn-Aufrufe: %d", f.name, got)
			if w.Code != http.StatusOK {
				t.Errorf("F002 [%s]: Status erwartet 200, bekommen %d", f.name, w.Code)
			}
			if i == 0 {
				ersterKoerper = w.Body.String()
			} else if w.Body.String() != ersterKoerper {
				t.Errorf("F002 [%s]: Koerper weicht ab: %q vs. %q", f.name, w.Body.String(), ersterKoerper)
			}
			if got != f.vergleiche {
				t.Errorf("F002 [%s]: erwartet %d bcrypt-Vergleich(e) ueber bcryptCompareFn, gezaehlt %d",
					f.name, f.vergleiche, got)
			}
			if f.tokenFuer != "" {
				tok, err := s.LoadResetToken(f.tokenFuer)
				if err != nil || tok == nil || tok.TokenHash == "" {
					t.Errorf("F002 [%s]: Reset-Token fuer %s erwartet (teurer Schritt), bekommen %+v / %v",
						f.name, f.tokenFuer, tok, err)
				}
			}
		})
	}
	for _, id := range []string{"doppel-a2194", "doppel-b2194"} {
		if tok, _ := s.LoadResetToken(id); tok != nil && tok.TokenHash != "" {
			t.Errorf("F002: bei 2 Treffern darf fuer %s kein Reset-Token entstehen", id)
		}
	}
}
