package handler

// Issue #3441 (S5b): Test-Alarm im Menue „Test schicken" (Spec
// docs/specs/modules/feat_3441_test_alarm.md, AC-9, AC-13). Muster
// BriefingSendHandler: kind ist Pflicht (Whitelist), die ID wird vor dem
// Weiterreichen geprueft, user_id setzt forwardSend aus der Anmeldung; jeder
// weitere Client-Wert (user_id, Empfaenger) wird verworfen. Besitzpruefung,
// Kanalmenge und Kontingent entscheidet der Python-Core.

import (
	"net/http"
	"net/url"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/store"
)

// POST /api/briefings/{id}/test-alert?kind=route|vergleich
// Weiter an Python POST /api/briefings/{id}/test-alert?kind=…&user_id=<auth>.
func BriefingTestAlertHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			WriteError(w, r, http.StatusBadRequest, "kind_required", nil)
			return
		}
		id := chi.URLParam(r, "id")
		if !store.ValidEntityID(id) {
			WriteError(w, r, http.StatusBadRequest, "validation_error", sendVarianteKennung)
			return
		}
		q := url.Values{}
		q.Set("kind", kind)
		forwardSend(w, r, pythonURL+"/api/briefings/"+url.PathEscape(id)+"/test-alert", q.Encode())
	}
}
