package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/middleware"
)

const logoutTestSecret = "test-secret-32-chars-minimum-ok!"

func TestLogoutHandlerClearsCookie(t *testing.T) {
	s := newTestStore(t)
	h := LogoutHandler(s, logoutTestSecret)

	req := httptest.NewRequest("POST", "/api/auth/logout", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: "alice.123.sig"})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	// Check cookie is cleared
	cookies := w.Result().Cookies()
	var sessionCookie *http.Cookie
	for _, c := range cookies {
		if c.Name == "gz_session" {
			sessionCookie = c
			break
		}
	}
	if sessionCookie == nil {
		t.Fatal("expected gz_session cookie to be set (cleared)")
	}
	if sessionCookie.MaxAge != -1 {
		t.Errorf("expected MaxAge -1 (delete), got %d", sessionCookie.MaxAge)
	}
}

// Issue #2129: Abmelden entfernt den Eintrag aus der Gaesteliste des Nutzers,
// statt den Token in einer prozesslokalen Sperrliste zu vermerken. Das ist der
// Unterschied, auf dem die unbefristete Anmeldung beruht: der Widerruf liegt
// auf der Platte und ueberlebt damit einen Dienst-Neustart.
func TestLogoutRemovesSessionFromAllowlist(t *testing.T) {
	s := newTestStore(t)
	sessionId, err := middleware.NewSessionID()
	if err != nil {
		t.Fatalf("NewSessionID: %v", err)
	}
	if err := s.AddSession("alice", sessionId); err != nil {
		t.Fatalf("AddSession: %v", err)
	}

	// Positivkontrolle: vor dem Abmelden steht die Anmeldung auf der Liste.
	if listed, err := s.HasSession("alice", sessionId); err != nil || !listed {
		t.Fatalf("Positivkontrolle: Anmeldung muss vor dem Abmelden gelistet sein (listed=%v err=%v)",
			listed, err)
	}

	token := middleware.SignSessionWithID("alice", sessionId, logoutTestSecret)
	req := httptest.NewRequest("POST", "/api/auth/logout", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: token})
	w := httptest.NewRecorder()
	LogoutHandler(s, logoutTestSecret).ServeHTTP(w, req)

	if listed, err := s.HasSession("alice", sessionId); err != nil || listed {
		t.Errorf("Anmeldung muss nach dem Abmelden von der Gaesteliste verschwunden sein (listed=%v err=%v)",
			listed, err)
	}
}

// Ein Abmelde-Aufruf darf nur die eigene Anmeldung treffen, nicht die des
// zweiten Geraets.
func TestLogoutKeepsOtherSessionsOfSameUser(t *testing.T) {
	s := newTestStore(t)
	deviceA, _ := middleware.NewSessionID()
	deviceB, _ := middleware.NewSessionID()
	if err := s.AddSession("alice", deviceA); err != nil {
		t.Fatalf("AddSession A: %v", err)
	}
	if err := s.AddSession("alice", deviceB); err != nil {
		t.Fatalf("AddSession B: %v", err)
	}

	req := httptest.NewRequest("POST", "/api/auth/logout", nil)
	req.AddCookie(&http.Cookie{
		Name:  "gz_session",
		Value: middleware.SignSessionWithID("alice", deviceA, logoutTestSecret),
	})
	LogoutHandler(s, logoutTestSecret).ServeHTTP(httptest.NewRecorder(), req)

	if listed, _ := s.HasSession("alice", deviceA); listed {
		t.Error("Geraet A muss abgemeldet sein")
	}
	if listed, _ := s.HasSession("alice", deviceB); !listed {
		t.Error("Geraet B muss angemeldet bleiben")
	}
}

func TestLogoutWithoutCookieStillReturns200(t *testing.T) {
	s := newTestStore(t)
	h := LogoutHandler(s, logoutTestSecret)

	req := httptest.NewRequest("POST", "/api/auth/logout", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 even without cookie, got %d", w.Code)
	}
}
