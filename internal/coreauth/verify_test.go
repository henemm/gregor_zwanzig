package coreauth

// TDD RED — Issue #2159 AC-2/AC-3: Rueckrichtung Python -> Go.
// RequireCoreAuth(secret) prueft den Header X-GZ-Core-Auth konstantzeitig.
// Leeres Secret => 503 (nie "" == ""), fehlend/falsch => 401, richtig => Handler.

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

const verifySecret = "core-shared-secret-fuer-tests-0123456789"

func runRequireCoreAuth(secret string, setHeader bool, header string) (code int, reached bool) {
	h := RequireCoreAuth(secret)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reached = true
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodPost, "/api/internal/x", nil)
	req.RemoteAddr = "127.0.0.1:50000"
	if setHeader {
		req.Header.Set(HeaderName, header)
	}
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	return rr.Code, reached
}

func TestRequireCoreAuth_FehlenderHeaderIst401(t *testing.T) {
	code, reached := runRequireCoreAuth(verifySecret, false, "")
	if code != http.StatusUnauthorized || reached {
		t.Fatalf("erwartet 401 ohne Handler-Aufruf, bekam %d (reached=%v)", code, reached)
	}
}

func TestRequireCoreAuth_FalscherHeaderIst401(t *testing.T) {
	code, reached := runRequireCoreAuth(verifySecret, true, verifySecret+"x")
	if code != http.StatusUnauthorized || reached {
		t.Fatalf("erwartet 401, bekam %d (reached=%v)", code, reached)
	}
	// Praefix des richtigen Secrets darf ebenfalls nicht reichen.
	code, reached = runRequireCoreAuth(verifySecret, true, verifySecret[:10])
	if code != http.StatusUnauthorized || reached {
		t.Fatalf("Praefix: erwartet 401, bekam %d (reached=%v)", code, reached)
	}
}

func TestRequireCoreAuth_LeeresSecretIst503AuchBeiLeeremHeader(t *testing.T) {
	for name, tc := range map[string]struct {
		set    bool
		header string
	}{
		"leerer Header":   {true, ""},
		"kein Header":     {false, ""},
		"beliebiger Wert": {true, "irgendwas"},
	} {
		code, reached := runRequireCoreAuth("", tc.set, tc.header)
		if code != http.StatusServiceUnavailable || reached {
			t.Fatalf("%s: erwartet 503 ohne Handler-Aufruf (nie \"\"==\"\"), bekam %d (reached=%v)", name, code, reached)
		}
	}
}

func TestRequireCoreAuth_RichtigerHeaderLaesstHandlerLaufen(t *testing.T) {
	code, reached := runRequireCoreAuth(verifySecret, true, verifySecret)
	if code != http.StatusOK || !reached {
		t.Fatalf("erwartet 200 mit Handler-Aufruf, bekam %d (reached=%v)", code, reached)
	}
}
