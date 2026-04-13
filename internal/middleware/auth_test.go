package middleware

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

const testSecret = "test-secret-32-chars-minimum-ok!"

// helper: create a valid signed cookie value
func makeSessionCookie(userId string, ts int64, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%d", userId, ts)))
	sig := hex.EncodeToString(mac.Sum(nil))
	return fmt.Sprintf("%s.%d.%s", userId, ts, sig)
}

// dummyHandler returns 200 with the userId from context
func dummyHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		uid := UserIDFromContext(r.Context())
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(uid))
	}
}

func TestValidCookie_Returns200(t *testing.T) {
	// GIVEN: a valid session cookie
	ts := time.Now().Unix()
	cookie := makeSessionCookie("default", ts, testSecret)

	// WHEN: request with valid cookie hits a protected endpoint
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookie})
	rr := httptest.NewRecorder()

	handler := AuthMiddleware(testSecret)(dummyHandler())
	handler.ServeHTTP(rr, req)

	// THEN: 200 OK and userId in context
	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rr.Code)
	}
	if rr.Body.String() != "default" {
		t.Errorf("expected userId 'default', got '%s'", rr.Body.String())
	}
}

func TestNoCookie_Returns401(t *testing.T) {
	// GIVEN: no session cookie
	// WHEN: request without cookie
	req := httptest.NewRequest("GET", "/api/trips", nil)
	rr := httptest.NewRecorder()

	handler := AuthMiddleware(testSecret)(dummyHandler())
	handler.ServeHTTP(rr, req)

	// THEN: 401 Unauthorized
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
}

func TestExpiredCookie_Returns401(t *testing.T) {
	// GIVEN: a cookie older than 24h
	ts := time.Now().Unix() - 90000 // 25 hours ago
	cookie := makeSessionCookie("default", ts, testSecret)

	// WHEN: request with expired cookie
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookie})
	rr := httptest.NewRecorder()

	handler := AuthMiddleware(testSecret)(dummyHandler())
	handler.ServeHTTP(rr, req)

	// THEN: 401 Unauthorized
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
}

func TestTamperedHMAC_Returns401(t *testing.T) {
	// GIVEN: a cookie with a manipulated HMAC signature
	ts := time.Now().Unix()
	cookie := fmt.Sprintf("default.%d.deadbeef0000000000000000000000000000000000000000000000000000abcd", ts)

	// WHEN: request with tampered cookie
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookie})
	rr := httptest.NewRecorder()

	handler := AuthMiddleware(testSecret)(dummyHandler())
	handler.ServeHTTP(rr, req)

	// THEN: 401 Unauthorized
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
}

func TestMalformedCookie_Returns401(t *testing.T) {
	// GIVEN: various malformed cookie values
	malformed := []string{
		"",
		"notsplit",
		"only.two",
		"too.many.parts.here",
		"user..sig",
		"user.notanumber.sig",
	}

	for _, val := range malformed {
		req := httptest.NewRequest("GET", "/api/trips", nil)
		req.AddCookie(&http.Cookie{Name: "gz_session", Value: val})
		rr := httptest.NewRecorder()

		handler := AuthMiddleware(testSecret)(dummyHandler())
		handler.ServeHTTP(rr, req)

		if rr.Code != http.StatusUnauthorized {
			t.Errorf("malformed cookie %q: expected 401, got %d", val, rr.Code)
		}
	}
}

func TestHealthEndpoint_NoAuthRequired(t *testing.T) {
	// GIVEN: no cookie, requesting /api/health
	// WHEN: request to health endpoint without auth
	req := httptest.NewRequest("GET", "/api/health", nil)
	rr := httptest.NewRecorder()

	handler := AuthMiddleware(testSecret)(dummyHandler())
	handler.ServeHTTP(rr, req)

	// THEN: 200 OK (health is exempt from auth)
	if rr.Code != http.StatusOK {
		t.Errorf("expected 200 for health endpoint, got %d", rr.Code)
	}
}

func TestWrongSecret_Returns401(t *testing.T) {
	// GIVEN: cookie signed with a different secret
	ts := time.Now().Unix()
	cookie := makeSessionCookie("default", ts, "wrong-secret-not-the-right-one!!")

	// WHEN: middleware validates with the correct secret
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookie})
	rr := httptest.NewRecorder()

	handler := AuthMiddleware(testSecret)(dummyHandler())
	handler.ServeHTTP(rr, req)

	// THEN: 401 Unauthorized
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
}

func TestUserIDFromContext_EmptyWithoutMiddleware(t *testing.T) {
	// GIVEN: a request that did NOT go through auth middleware
	req := httptest.NewRequest("GET", "/api/trips", nil)

	// WHEN: extracting userId from context
	uid := UserIDFromContext(req.Context())

	// THEN: empty string (no userId set)
	if uid != "" {
		t.Errorf("expected empty userId, got '%s'", uid)
	}
}
