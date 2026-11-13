package handler

// Issue #2961 (GA9, ADR-0115): die Login-Kennung (email) eines bestaetigten
// Kontos aendert sich nur ueber den Bestaetigungslink an die neue Adresse —
// auch wenn mail_to (die wirksame Kontaktadresse) gleich bleibt. Bis dahin
// blockiert die neue Adresse keine fremde Registrierung.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

func TestKennungswechsel_LaeuftUeberBestaetigungAuchBeiGleicherZustelladresse(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now().UTC()
	for _, id := range []string{"kennung-a", "kennung-b"} {
		if err := s.SaveUser(model.User{ID: id, Email: id + "@beispiel.de", MailTo: id + "-post@beispiel.de",
			CreatedAt: jetzt, EmailVerifiedAt: &jetzt}); err != nil {
			t.Fatal(err)
		}
	}

	req := addUserToContext(httptest.NewRequest(http.MethodPut, "/api/auth/profile",
		strings.NewReader(`{"email":"Kennung-Neu@beispiel.de"}`)), "kennung-a")
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter).ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
	}
	a, _ := s.LoadUser("kennung-a")
	if a.Email != "kennung-a@beispiel.de" {
		t.Fatalf("die Login-Kennung darf vor der Bestaetigung nicht wechseln, ist %q", a.Email)
	}
	if a.PendingContactField != "email" || a.PendingContactAddress != "kennung-neu@beispiel.de" {
		t.Fatalf("Kennungswechsel muss ausstehen: field=%q addr=%q", a.PendingContactField, a.PendingContactAddress)
	}
	if a.MailTo != "kennung-a-post@beispiel.de" || a.EmailVerifiedAt == nil {
		t.Errorf("Zustelladresse und Bestaetigung bleiben: mail_to=%q verified=%v", a.MailTo, a.EmailVerifiedAt)
	}
	if b, _ := s.LoadUser("kennung-b"); b.PendingContactAddress != "" || b.Email != "kennung-b@beispiel.de" {
		t.Errorf("Konto b darf nicht betroffen sein")
	}

	// Die ausstehende Adresse blockiert keine fremde Registrierung.
	rw := httptest.NewRecorder()
	RegisterHandler(s, bcrypt.MinCost, config.Config{}).ServeHTTP(rw, httptest.NewRequest(http.MethodPost, "/api/auth/register",
		strings.NewReader(`{"password":"geheim-123","email":"kennung-neu@beispiel.de"}`)))
	if rw.Code != http.StatusCreated {
		t.Fatalf("ausstehende Kennung darf Registrierung nicht blockieren: %d %s", rw.Code, rw.Body.String())
	}
}

func TestKennungswechsel_WirdMitDemLinkWirksam(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "kennung-c", Email: "kennung-c@beispiel.de", MailTo: "post-c@beispiel.de",
		CreatedAt: jetzt, EmailVerifiedAt: &jetzt}); err != nil {
		t.Fatal(err)
	}
	req := addUserToContext(httptest.NewRequest(http.MethodPut, "/api/auth/profile",
		strings.NewReader(`{"email":"neu-c@beispiel.de"}`)), "kennung-c")
	UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter).ServeHTTP(httptest.NewRecorder(), req)

	token, err := issueVerificationToken(s, "kennung-c", "neu-c@beispiel.de")
	if err != nil {
		t.Fatal(err)
	}
	vw := httptest.NewRecorder()
	VerifyEmailHandler(s).ServeHTTP(vw, httptest.NewRequest(http.MethodPost, "/api/auth/verify-email",
		strings.NewReader(`{"user":"kennung-c","token":"`+token+`"}`)))
	if vw.Code != http.StatusOK {
		t.Fatalf("Bestaetigung: %d %s", vw.Code, vw.Body.String())
	}
	c, _ := s.LoadUser("kennung-c")
	if c.Email != "neu-c@beispiel.de" || c.MailTo != "post-c@beispiel.de" || c.PendingContactAddress != "" {
		t.Errorf("nach Bestaetigung: email=%q mail_to=%q pending=%q", c.Email, c.MailTo, c.PendingContactAddress)
	}
}
