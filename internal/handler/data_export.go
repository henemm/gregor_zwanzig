package handler

// Datenexport nach DSGVO Art. 20 (Issue #2270) — die lesende Gegenrichtung zu
// DeleteAccountHandler.

import (
	"log"
	"net/http"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// ExportUserDataHandler liefert das Datenarchiv des ANGEMELDETEN Nutzers aus.
//
// Die Kennung kommt ausschliesslich aus dem Auth-Kontext; ein Request-Parameter
// hat keine Wirkung.
//
// Die ausdrueckliche Leer-Pruefung ist keine Formalie: UserIDFromContext
// liefert bei fehlendem Kontext den leeren String (middleware/auth.go:151-154),
// WithUser("") ist im Store ein No-Op (store/store.go:21-24) und die
// Store-Voreinstellung ist "default" (config/config.go:10). Ein Handler, der
// die Kennung nur durchreicht, lieferte also den fremden Sammelordner
// "default" aus.
func ExportUserDataHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":"unauthorized"}`))
			return
		}

		w.Header().Set("Content-Type", "application/zip")
		w.Header().Set("Content-Disposition", `attachment; filename="gregor-zwanzig-export.zip"`)

		// Das Archiv wird durchgereicht: ein Fehler mitten im Packen kann den
		// bereits gesendeten Statuscode nicht mehr korrigieren, die
		// Uebertragung bricht dann ab (Spec Known Limitations b).
		if err := s.ExportUser(userID, w); err != nil {
			log.Printf("data export: archive incomplete: %v", err)
		}
	}
}
