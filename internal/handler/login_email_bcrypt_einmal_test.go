package handler

// TDD RED — Issue #2194 (Epic #2138), AC-3: bei 0, 1 und n Treffern auf dem
// E-Mail-Pfad laeuft GENAU EIN bcrypt-Vergleich, und die Antwort ist
// identisch (401 invalid_credentials, gleicher Koerper).
// Spec: docs/specs/modules/email_login_identifier.md
//
// Festgelegtes neues Symbol (package handler, unexportiert):
//
//	var bcryptCompareFn = bcrypt.CompareHashAndPassword
//
// Die EINZIGE Funktion, ueber die der Login bcrypt-Vergleiche ausfuehrt:
// sowohl burnDummyCompare (Dummy-Vergleich der Nicht-Treffer-Zweige, #2163)
// als auch der echte Passwortvergleich in LoginHandler rufen sie auf. Nur so
// ist "genau einer" am Wirkort zaehlbar — laege der echte Vergleich daneben,
// bestuende eine Implementierung, die bei 2 Treffern gegen ALLE Passwoerter
// prueft (Timing verraet die Trefferzahl, die Reihenfolge entschiede).
//
//   - Fall 0 Treffer mit Zaehlwert 1 erzwingt, dass burnDummyCompare ueber die
//     Naht laeuft.
//   - Fall 1 Treffer mit richtigem Passwort (Positivkontrolle, 200) erzwingt,
//     dass der echte Vergleich ueber die Naht laeuft.
//   - Fall 2 Treffer (falsches UND richtiges Passwort) verbietet "gegen alle
//     pruefen" und "erster Treffer gewinnt".
//
// Der Wrapper zaehlt und delegiert an das ECHTE bcrypt (kein Mock), per
// t.Cleanup zurueckgesetzt. Kein t.Parallel (package-Variable).
//
// Alle Konten tragen einen GUELTIGEN bcrypt-Hash: heute macht der Login bei
// leerem/kaputtem Hash zwei Vergleiche (echter + Dummy, auth.go), das wuerde
// die Zaehlung verfaelschen.
//
// RED-Beleg: Build-Fehler "undefined: bcryptCompareFn". Deshalb eigene Datei —
// beim Nachweis der Verhaltenstests wird sie beiseitegelegt.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func zaehleBcrypt2194(t *testing.T) *int64 {
	t.Helper()
	var n int64
	orig := bcryptCompareFn
	bcryptCompareFn = func(hash, pw []byte) error {
		atomic.AddInt64(&n, 1)
		return bcrypt.CompareHashAndPassword(hash, pw)
	}
	t.Cleanup(func() { bcryptCompareFn = orig })
	return &n
}

func kontoBcrypt2194(t *testing.T, s *store.Store, uid, email, passwort string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(passwort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt %q: %v", uid, err)
	}
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{
		ID: uid, Email: email, MailTo: email, PasswordHash: string(hash),
		EmailVerifiedAt: &jetzt, CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser %q: %v", uid, err)
	}
}

func TestLoginPerEmail_BcryptEinmal_NullEinsZweiTreffer_AC3_2194(t *testing.T) {
	s := newTestStore(t)
	kontoBcrypt2194(t, s, "ella2194", "ella@beispiel.de", "ella-passwort-1")
	kontoBcrypt2194(t, s, "fritz2194", "doppelt@beispiel.de", "fritz-passwort-1")
	kontoBcrypt2194(t, s, "gerd2194", "doppelt@beispiel.de", "gerd-passwort-1")

	h := LoginHandler(s, timingSecret, "")
	login := func(kennung, passwort string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/login",
			strings.NewReader(`{"username":"`+kennung+`","password":"`+passwort+`"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}

	// Positivkontrolle: ein Treffer, richtiges Passwort => 200, genau 1 Vergleich.
	n := zaehleBcrypt2194(t)
	w := login("ella@beispiel.de", "ella-passwort-1")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3 Positivkontrolle: Login per E-Mail mit richtigem Passwort erwartet 200, bekommen %d: %s",
			w.Code, w.Body.String())
	}
	if got := atomic.LoadInt64(n); got != 1 {
		t.Errorf("AC-3 Positivkontrolle: erwartet genau 1 bcrypt-Vergleich ueber bcryptCompareFn, gezaehlt %d", got)
	}

	faelle := []struct {
		name, kennung, passwort string
	}{
		{"0 Treffer", "niemand@beispiel.de", "irgendwas-123"},
		{"1 Treffer, falsches Passwort", "ella@beispiel.de", "falsch-falsch-1"},
		{"2 Treffer, falsches Passwort", "doppelt@beispiel.de", "falsch-falsch-1"},
		{"2 Treffer, richtiges Passwort des ersten", "doppelt@beispiel.de", "fritz-passwort-1"},
		{"2 Treffer, richtiges Passwort des zweiten", "doppelt@beispiel.de", "gerd-passwort-1"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			atomic.StoreInt64(n, 0)
			w := login(f.kennung, f.passwort)
			if w.Code != http.StatusUnauthorized {
				t.Errorf("AC-3 [%s]: Status erwartet 401, bekommen %d", f.name, w.Code)
			}
			if got := w.Body.String(); got != wantLoginRejectBody {
				t.Errorf("AC-3 [%s]: Koerper weicht ab:\n erwartet %q\n bekommen %q", f.name, wantLoginRejectBody, got)
			}
			for _, c := range w.Result().Cookies() {
				if c.Name == "gz_session" {
					t.Errorf("AC-3 [%s]: abgewiesene Anmeldung darf kein gz_session setzen", f.name)
				}
			}
			if got := atomic.LoadInt64(n); got != 1 {
				t.Errorf("AC-3 [%s]: erwartet genau 1 bcrypt-Vergleich, gezaehlt %d", f.name, got)
			}
		})
	}
}
