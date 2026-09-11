package handler

// Staging-only Testweg für die E-Mail-Bestätigung (Issue #2304, AC-9..AC-12).
// Spec: docs/specs/modules/email_verify_vorbereitung_2304.md, Punkt 4.
//
// Zweck: auf Staging entstehen zur Laufzeit ständig neue Test-Konten, deren
// Bestätigungsmail dort strukturell nicht zugestellt werden kann (Egress-Sperre
// #1337, Resend-Sperre). Ohne einen Weg, an das Token zu kommen, wäre die
// spätere Login-Pflicht (#2271) auf Staging nicht prüfbar.
//
// Der Handler gibt NUR das Token heraus. `email_verified_at` setzt weiterhin
// ausschließlich VerifyEmailHandler — der Testweg prüft damit den echten
// Produktionspfad mit, statt ihn zu umgehen.
//
// 🔴 Registrierung nur bei GZ_ENV=staging (router.go) UND anmeldepflichtig.
// Die Anmeldepflicht hängt daran, dass der Pfad NICHT unter `/api/debug/`,
// `/api/internal/` oder `/api/webhooks/telegram/` liegt — diese drei Präfixe
// befreit AuthMiddleware pauschal (internal/middleware/auth.go). Der Pfad
// gehört auch nicht in die Public-Allowlist.

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/henemm/gregor-api/internal/store"
)

// StagingVerificationTokenHandler erzeugt ein Verifikations-Token für das
// genannte Konto und liefert es im Klartext zurück — ohne Mailversand.
func StagingVerificationTokenHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username string `json:"username"`
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Username == "" {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}
		if !store.ValidUserID(req.Username) {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}
		user, err := s.LoadUser(req.Username)
		if err != nil || user == nil {
			w.WriteHeader(http.StatusNotFound)
			w.Write([]byte(`{"error":"unknown user"}`))
			return
		}

		// Bewusst OHNE Blick auf user.EmailVerifiedAt: der Testweg gibt auch
		// für ein bereits bestätigtes Konto ein Token heraus (AC-11) und
		// rührt den bestehenden Zeitstempel dabei nicht an.
		token, err := issueVerificationToken(s, req.Username)
		if err != nil {
			log.Printf("staging verification token: issuance failed for %s: %v", req.Username, err)
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"token": token})
	}
}
