package handler

// Issue #2961 (Fix-Runde F-C): Adresse, Login-Kennung und ausstehende
// Aenderung werden nur auf dem frisch geladenen Stand geschrieben. Ein
// bestaetigter Adresswechsel bzw. ein verworfenes Pending ueberlebt parallele
// Profil-Schreiber (mit -race laufen lassen), fuer zwei Nutzer.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

func TestAdressfelder_BestaetigterWechselUeberlebtParalleleProfilSchreiber(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now().UTC()
	for _, id := range []string{"fc-a", "fc-b"} {
		if err := s.SaveUser(model.User{ID: id, Email: id + "@beispiel.de", CreatedAt: jetzt, EmailVerifiedAt: &jetzt,
			PendingContactAddress: id + "-neu@beispiel.de", PendingContactField: "email"}); err != nil {
			t.Fatal(err)
		}
	}
	h := UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter)
	var wg sync.WaitGroup
	for _, id := range []string{"fc-a", "fc-b"} {
		id := id
		token, err := issueVerificationToken(s, id, id+"-neu@beispiel.de")
		if err != nil {
			t.Fatal(err)
		}
		for i := 0; i < 8; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				req := addUserToContext(httptest.NewRequest(http.MethodPut, "/api/auth/profile",
					strings.NewReader(`{"display_name":"Name `+id+`","mail_to":""}`)), id)
				h.ServeHTTP(httptest.NewRecorder(), req)
			}()
		}
		wg.Add(1)
		go func() {
			defer wg.Done()
			w := httptest.NewRecorder()
			VerifyEmailHandler(s).ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/verify-email",
				strings.NewReader(`{"user":"`+id+`","token":"`+token+`"}`)))
			if w.Code != http.StatusOK {
				t.Errorf("%s Bestaetigung: %d %s", id, w.Code, w.Body.String())
			}
		}()
	}
	wg.Wait()
	for _, id := range []string{"fc-a", "fc-b"} {
		u, _ := s.LoadUser(id)
		if u.Email != id+"-neu@beispiel.de" || u.PendingContactAddress != "" {
			t.Errorf("%s: bestaetigter Wechsel zurueckgedreht: email=%q pending=%q", id, u.Email, u.PendingContactAddress)
		}
		if u.DisplayName != "Name "+id {
			t.Errorf("%s: Profilfeld fehlt oder fremd: %q", id, u.DisplayName)
		}
	}
}

func TestAdressfelder_VerworfenesPendingUeberlebtVeraltetenSchreiber(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "fc-c", Email: "fc-c@beispiel.de", CreatedAt: jetzt, EmailVerifiedAt: &jetzt,
		PendingContactAddress: "fc-c-neu@beispiel.de", PendingContactField: "mail_to"}); err != nil {
		t.Fatal(err)
	}
	veraltet, _ := s.LoadUser("fc-c")
	if _, err := s.UpdateUser("fc-c", func(u *model.User) error {
		u.PendingContactAddress, u.PendingContactField = "", ""
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	veraltet.DisplayName = "Neu"
	if err := s.SaveUser(*veraltet); err != nil {
		t.Fatal(err)
	}
	u, _ := s.LoadUser("fc-c")
	if u.PendingContactAddress != "" || u.PendingContactField != "" || u.DisplayName != "Neu" {
		t.Fatalf("verworfenes Pending zurueckgedreht oder Profilfeld fehlt: %+v", u)
	}
}
