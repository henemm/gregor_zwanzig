package coreauth

import (
	"crypto/sha256"
	"crypto/subtle"
	"log"
	"net/http"
)

// RequireCoreAuth ist die Rueckrichtung zu transport.go (Issue #2159, ADR-0062):
// der Python-Core authentifiziert sich gegenueber Go mit demselben Geheimnis
// im Header HeaderName. Leeres Secret => 503 (fail-closed, nie "" == ""),
// fehlender/falscher Header => 401. Vergleich sha256 + ConstantTimeCompare.
func RequireCoreAuth(secret string) func(http.Handler) http.Handler {
	if secret == "" {
		log.Printf("[coreauth] GZ_CORE_SHARED_SECRET nicht gesetzt — /api/internal/* ist gesperrt (503).")
	}
	want := sha256.Sum256([]byte(secret))
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if secret == "" {
				writeErr(w, http.StatusServiceUnavailable, "core_auth_not_configured")
				return
			}
			got := sha256.Sum256([]byte(r.Header.Get(HeaderName)))
			if subtle.ConstantTimeCompare(want[:], got[:]) != 1 {
				writeErr(w, http.StatusUnauthorized, "unauthorized")
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

func writeErr(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	w.Write([]byte(`{"error":"` + msg + `"}`))
}
