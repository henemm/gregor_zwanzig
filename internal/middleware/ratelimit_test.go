package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// Issue #117 — Rate-Limit für /api/auth/register.
// Tests verwenden ein kurzes Window (100ms) damit sie schnell laufen.

func newOKHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
}

func doReq(t *testing.T, h http.Handler, remoteAddr, xRealIP string) int {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", nil)
	req.RemoteAddr = remoteAddr
	if xRealIP != "" {
		req.Header.Set("X-Real-IP", xRealIP)
	}
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	return rr.Code
}

// TestIPRateLimiter_AllowsBurst — 5 Requests aus gleicher IP innerhalb des
// Windows müssen alle durchgehen.
func TestIPRateLimiter_AllowsBurst(t *testing.T) {
	limiter := NewIPRateLimiter(5, 100*time.Millisecond)
	h := limiter.Middleware(newOKHandler())

	for i := 1; i <= 5; i++ {
		if got := doReq(t, h, "1.2.3.4:5000", ""); got != http.StatusOK {
			t.Fatalf("request %d: expected 200, got %d", i, got)
		}
	}
}

// TestIPRateLimiter_BlocksSixth — Der 6. Request aus gleicher IP innerhalb
// des Windows muss 429 + Retry-After-Header zurückgeben.
func TestIPRateLimiter_BlocksSixth(t *testing.T) {
	limiter := NewIPRateLimiter(5, 100*time.Millisecond)
	h := limiter.Middleware(newOKHandler())

	for i := 1; i <= 5; i++ {
		_ = doReq(t, h, "1.2.3.4:5000", "")
	}

	// 6. Request — muss 429 sein
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", nil)
	req.RemoteAddr = "1.2.3.4:5000"
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)

	if rr.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d", rr.Code)
	}
	if rr.Header().Get("Retry-After") == "" {
		t.Errorf("expected Retry-After header to be set on 429")
	}
}

// TestIPRateLimiter_DifferentIPsIndependent — Zwei unterschiedliche IPs haben
// unabhängige Buckets. 5+5 = alle 10 erlaubt.
func TestIPRateLimiter_DifferentIPsIndependent(t *testing.T) {
	limiter := NewIPRateLimiter(5, 100*time.Millisecond)
	h := limiter.Middleware(newOKHandler())

	for i := 1; i <= 5; i++ {
		if got := doReq(t, h, "1.1.1.1:5000", ""); got != http.StatusOK {
			t.Fatalf("IP A request %d: expected 200, got %d", i, got)
		}
	}
	for i := 1; i <= 5; i++ {
		if got := doReq(t, h, "2.2.2.2:5000", ""); got != http.StatusOK {
			t.Fatalf("IP B request %d: expected 200, got %d", i, got)
		}
	}
}

// TestIPRateLimiter_PrefersXRealIP — Wenn X-Real-IP gesetzt ist (Nginx),
// dominiert dieser über RemoteAddr. Zwei Requests mit identischem RemoteAddr
// aber unterschiedlichem X-Real-IP zählen als unterschiedliche Buckets.
func TestIPRateLimiter_PrefersXRealIP(t *testing.T) {
	limiter := NewIPRateLimiter(5, 100*time.Millisecond)
	h := limiter.Middleware(newOKHandler())

	// 5 Requests mit X-Real-IP=9.9.9.9 → Bucket A
	for i := 1; i <= 5; i++ {
		if got := doReq(t, h, "1.1.1.1:5000", "9.9.9.9"); got != http.StatusOK {
			t.Fatalf("X-Real-IP=9.9.9.9 request %d: expected 200, got %d", i, got)
		}
	}
	// 6. Request mit X-Real-IP=9.9.9.9 → 429
	if got := doReq(t, h, "1.1.1.1:5000", "9.9.9.9"); got != http.StatusTooManyRequests {
		t.Fatalf("X-Real-IP=9.9.9.9 6th request: expected 429, got %d", got)
	}
	// Aber X-Real-IP=8.8.8.8 (gleiche RemoteAddr!) — fresh bucket → 200
	if got := doReq(t, h, "1.1.1.1:5000", "8.8.8.8"); got != http.StatusOK {
		t.Fatalf("X-Real-IP=8.8.8.8 fresh bucket: expected 200, got %d", got)
	}
}
