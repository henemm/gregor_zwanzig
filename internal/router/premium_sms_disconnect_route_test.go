package router

// Verdrahtungs- und Anmelde-Nachweis fuer DELETE /api/auth/premium-sms-reply
// (Issue #2961 Welle 2, ADR-0116): echter Produktions-Router inklusive
// AuthMiddleware, zwei Konten. Angemeldet trennt nur das eigene Konto; anonym
// weist die Middleware ab, und nichts wird veraendert.

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

const disconnectRoutePath = "/api/auth/premium-sms-reply"

func TestPremiumSmsDisconnectRouteTrenntNurDasEigeneKonto(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	at := time.Now().UTC().Add(-time.Hour)
	for id, nummer := range map[string]string{"psmsanna": "4917000000061", "psmsbert": "4917000000062"} {
		if err := s.SaveUser(model.User{
			ID: id, Tier: "premium", CreatedAt: time.Now(),
			PremiumSmsReplyTo: nummer, PremiumSmsReplyAt: &at,
		}); err != nil {
			t.Fatalf("SaveUser: %v", err)
		}
	}
	if err := s.AddSession("psmsanna", sessionIDFor("psmsanna")); err != nil {
		t.Fatalf("AddSession: %v", err)
	}

	rr := doBriefingRequest(t, r, http.MethodDelete, disconnectRoutePath, nil, sessionCookieFor("psmsanna", secret))
	if rr.Code != http.StatusNoContent {
		t.Fatalf("angemeldet erwartet 204, bekam %d: %s", rr.Code, rr.Body.String())
	}
	if u, _ := s.LoadUser("psmsanna"); u == nil || u.PremiumSmsReplyTo != "" || u.PremiumSmsReplyAt != nil {
		t.Errorf("anna: Rueckadresse muss geloescht sein, bekam %+v", u)
	}
	if u, _ := s.LoadUser("psmsbert"); u == nil || u.PremiumSmsReplyTo != "4917000000062" {
		t.Errorf("bert darf nicht beruehrt werden, bekam %+v", u)
	}
}

func TestPremiumSmsDisconnectRouteWeistAnonymeAufrufeAb(t *testing.T) {
	r, s, _ := newBriefingTestRouter(t)
	at := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "default", Tier: "premium", PremiumSmsReplyTo: "4917000000063", PremiumSmsReplyAt: &at}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodDelete, disconnectRoutePath, nil))
	if w.Code != http.StatusUnauthorized && w.Code != http.StatusForbidden {
		t.Fatalf("anonym erwartet 401/403, bekam %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("default"); u == nil || u.PremiumSmsReplyTo != "4917000000063" {
		t.Errorf("anonymer Aufruf darf kein Konto veraendern, default: %+v", u)
	}
}
