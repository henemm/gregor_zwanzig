package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/middleware"
)

// TDD RED: Tests for logout — must FAIL until implemented.

func TestLogoutHandlerClearsCookie(t *testing.T) {
	h := LogoutHandler()

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

func TestLogoutBlacklistsSession(t *testing.T) {
	token := "alice.123.fakesig"

	// Before logout: not blacklisted
	if middleware.IsBlacklisted(token) {
		t.Fatal("token should not be blacklisted before logout")
	}

	h := LogoutHandler()
	req := httptest.NewRequest("POST", "/api/auth/logout", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: token})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// After logout: blacklisted
	if !middleware.IsBlacklisted(token) {
		t.Error("token should be blacklisted after logout")
	}
}

func TestLogoutWithoutCookieStillReturns200(t *testing.T) {
	h := LogoutHandler()

	req := httptest.NewRequest("POST", "/api/auth/logout", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 even without cookie, got %d", w.Code)
	}
}
