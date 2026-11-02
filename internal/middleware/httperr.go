package middleware

import (
	"encoding/json"
	"net/http"

	"github.com/henemm/gregor-api/internal/i18n"
)

// writeError schreibt das Fehlerobjekt {code, message, error, detail} der
// Middleware in der Sprache lang (Issue #2677, Konventionen Abschnitt 5).
// middleware darf handler nicht importieren, daher ein eigener Helfer.
func writeError(w http.ResponseWriter, lang i18n.Lang, status int, code string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(i18n.ErrorBody(lang, code, nil))
}
