package handler

import (
	"errors"
	"net/http"

	"github.com/henemm/gregor-api/internal/store"
)

// lockBriefingOr503 nimmt die Briefing-Sperre (Mutex + flock, ADR-0083) mit
// Frist. Laeuft sie ab, antwortet es 503 + Retry-After; es wurde nichts
// geschrieben. ok=false => Handler muss sofort zurueckkehren.
func lockBriefingOr503(w http.ResponseWriter, s *store.Store, id string) (unlock func(), ok bool) {
	// gz-store-scope-call: Hilfsfunktion, jeder Aufrufer reicht seinen bereits per WithUser gebundenen Store durch
	unlock, err := s.LockBriefingErr(id)
	if err == nil {
		return unlock, true
	}
	w.Header().Set("Content-Type", "application/json")
	if errors.Is(err, store.ErrBriefingLockTimeout) {
		w.Header().Set("Retry-After", "5")
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error":"busy","detail":"Datei gerade gesperrt, bitte erneut versuchen"}`))
		return nil, false
	}
	w.WriteHeader(http.StatusInternalServerError)
	w.Write([]byte(`{"error":"store_error"}`))
	return nil, false
}
