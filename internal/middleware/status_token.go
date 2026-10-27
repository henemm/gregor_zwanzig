package middleware

import (
	"crypto/sha256"
	"crypto/subtle"
	"log"
	"net/http"
)

// StatusTokenHeader traegt das Maschinen-Token fuer /api/scheduler/status
// (Issue #2155 S2, ADR-0079).
const StatusTokenHeader = "X-GZ-Status-Token"

// RequireStatusToken laesst nur Anfragen durch, deren Header
// X-GZ-Status-Token dem konfigurierten Token entspricht. Fail-closed: ist
// token leer (GZ_STATUS_TOKEN nicht gesetzt) oder stimmt der Header nicht,
// antwortet die Middleware 401 {"error":"unauthorized"} und der Handler laeuft
// nicht. Eine Sitzung ersetzt das Token nicht -- geprueft wird ausschliesslich
// der Header. Vergleich ueber sha256 (feste Laenge) + ConstantTimeCompare.
func RequireStatusToken(token string) func(http.Handler) http.Handler {
	if token == "" {
		log.Printf("[auth] GZ_STATUS_TOKEN nicht gesetzt — /api/scheduler/status ist für alle Anfragen gesperrt.")
	}
	want := sha256.Sum256([]byte(token))
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			got := sha256.Sum256([]byte(r.Header.Get(StatusTokenHeader)))
			if token == "" || subtle.ConstantTimeCompare(want[:], got[:]) != 1 {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnauthorized)
				w.Write([]byte(`{"error":"unauthorized"}`))
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
