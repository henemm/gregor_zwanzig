package middleware

import "net/http"

// RequireAdmin laesst nur Nutzer durch, deren Kennung in admins steht
// (Issue #2155 S1, ADR-0078). Fail-closed: leere Kennung oder leere Menge =>
// 403 {"error":"forbidden"}, der Handler laeuft nicht. Die Anmeldepflicht
// (401) bleibt Sache der vorgeschalteten AuthMiddleware.
func RequireAdmin(admins map[string]struct{}) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			userID := UserIDFromContext(r.Context())
			if _, ok := admins[userID]; userID == "" || !ok {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusForbidden)
				w.Write([]byte(`{"error":"forbidden"}`))
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
