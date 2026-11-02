package handler

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/resolver"
)

// inputFehlt waehlt fach.fehler.bad_request_input (Issue #2677).
var inputFehlt = i18n.Args{"variante": "input"}

// ResolveLocationHandler liefert eine Location-Vorschau für eine URL oder
// Koordinaten-Eingabe — ohne zu speichern.
func ResolveLocationHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Body == nil {
			WriteError(w, r, http.StatusBadRequest, "bad_request", inputFehlt)
			return
		}

		var req struct {
			Input string `json:"input"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			WriteError(w, r, http.StatusBadRequest, "bad_request", inputFehlt)
			return
		}

		input := strings.TrimSpace(req.Input)
		if input == "" {
			WriteError(w, r, http.StatusBadRequest, "bad_request", inputFehlt)
			return
		}

		result, err := resolver.Resolve(input)
		if err != nil {
			if resolveErr, ok := err.(*resolver.ResolveError); ok {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(422)
				json.NewEncoder(w).Encode(resolveErr)
				return
			}
			WriteError(w, r, http.StatusInternalServerError, "internal_error", nil)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	}
}
