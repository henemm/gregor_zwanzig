package handler

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/henemm/gregor-api/internal/resolver"
)

// ResolveLocationHandler liefert eine Location-Vorschau für eine URL oder
// Koordinaten-Eingabe — ohne zu speichern.
func ResolveLocationHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		if r.Body == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request","message":"Feld 'input' fehlt"}`))
			return
		}

		var req struct {
			Input string `json:"input"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request","message":"Feld 'input' fehlt"}`))
			return
		}

		input := strings.TrimSpace(req.Input)
		if input == "" {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request","message":"Feld 'input' fehlt"}`))
			return
		}

		result, err := resolver.Resolve(input)
		if err != nil {
			if resolveErr, ok := err.(*resolver.ResolveError); ok {
				w.WriteHeader(422)
				json.NewEncoder(w).Encode(resolveErr)
				return
			}
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal_error"}`))
			return
		}

		json.NewEncoder(w).Encode(result)
	}
}
