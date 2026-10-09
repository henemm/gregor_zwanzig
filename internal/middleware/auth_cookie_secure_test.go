package middleware

// Issue #2159 AC-9 — Secure-Matrix des Session-Cookies. Neue Signatur:
// SetSessionCookie(w, r, token, publicHost). Secure gilt bei r.TLS != nil oder
// publicHost mit https://; X-Forwarded-Proto wird ignoriert.

import (
	"crypto/tls"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSetSessionCookie_SecureMatrix(t *testing.T) {
	cases := []struct {
		name           string
		publicHost     string
		forwardedProto string
		tls            bool
		want           bool
	}{
		{"https-PublicHost ohne X-Forwarded-Proto", "https://gregor20.henemm.com", "", false, true},
		{"http-PublicHost ohne TLS", "http://localhost:4173", "", false, false},
		{"http-PublicHost, X-Forwarded-Proto https wird ignoriert", "http://localhost:4173", "https", false, false},
		{"http-PublicHost, echte TLS-Verbindung", "http://localhost:4173", "", true, true},
		{"https-PublicHost, X-Forwarded-Proto http", "https://gregor20.henemm.com", "http", false, true},
	}
	for _, tc := range cases {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/login", nil)
		if tc.forwardedProto != "" {
			req.Header.Set("X-Forwarded-Proto", tc.forwardedProto)
		}
		if tc.tls {
			req.TLS = &tls.ConnectionState{}
		}
		rr := httptest.NewRecorder()
		SetSessionCookie(rr, req, "tok", tc.publicHost)
		var found *http.Cookie
		for _, c := range rr.Result().Cookies() {
			if c.Name == "gz_session" {
				found = c
			}
		}
		if found == nil {
			t.Fatalf("%s: gz_session nicht gesetzt", tc.name)
		}
		if found.Secure != tc.want {
			t.Errorf("%s: Secure=%v, erwartet %v", tc.name, found.Secure, tc.want)
		}
	}
}
