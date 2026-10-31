package handler

import (
	"encoding/json"
	"net/http"

	"github.com/henemm/gregor-api/internal/i18n"
)

// WriteError schreibt das Fehlerobjekt {code, message} in der Sprache der
// Anfrage (Issue #2675, Konventionen Abschnitt 5). Uebergangsfelder error
// (= code) und detail bleiben fuer bestehende Clients erhalten.
func WriteError(w http.ResponseWriter, r *http.Request, status int, code string, args i18n.Args) {
	WriteErrorWith(w, r, status, code, args, nil)
}

// WriteErrorWith ergaenzt das Fehlerobjekt um Zusatzfelder (z. B. "resource",
// "compare_presets"). Header wie Retry-After setzt der Aufrufer vorher.
func WriteErrorWith(w http.ResponseWriter, r *http.Request, status int, code string, args i18n.Args, extra map[string]any) {
	body := i18n.ErrorBody(i18n.FromContext(r.Context()), code, args)
	for k, v := range extra {
		body[k] = v
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
