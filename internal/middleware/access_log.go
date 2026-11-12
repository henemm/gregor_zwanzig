package middleware

// Zugriffslog ohne Geheimnisse (Issue #2961, ADR-0113): Pfad-Geheimnisse der
// Webhooks und die Query-Werte code/state/token erscheinen maskiert. Format
// und Ausgabe sonst wie chi middleware.Logger.

import (
	"net/http"
	"net/url"
	"strings"

	chimw "github.com/go-chi/chi/v5/middleware"
)

const redacted = "***"

// secretPathPrefixes: das Segment direkt nach dem Praefix ist ein Geheimnis.
var secretPathPrefixes = []string{"/api/webhooks/sms/", "/api/webhooks/mail/"}

// secretQueryKeys: Query-Parameter, deren Wert nie ins Log gehoert.
var secretQueryKeys = map[string]bool{"code": true, "state": true, "token": true}

// RedactURI maskiert Geheimnisse in einem RequestURI (Pfad + Query).
func RedactURI(uri string) string {
	path, query, hasQuery := strings.Cut(uri, "?")
	for _, p := range secretPathPrefixes {
		if strings.HasPrefix(path, p) && len(path) > len(p) {
			rest := path[len(p):]
			_, tail, hasTail := strings.Cut(rest, "/")
			path = p + redacted
			if hasTail {
				path += "/" + tail
			}
			break
		}
	}
	if !hasQuery {
		return path
	}
	parts := strings.Split(query, "&")
	for i, part := range parts {
		k, _, hasVal := strings.Cut(part, "=")
		key, err := url.QueryUnescape(k)
		if err != nil {
			key = k
		}
		if hasVal && secretQueryKeys[strings.ToLower(key)] {
			parts[i] = k + "=" + redacted
		}
	}
	return path + "?" + strings.Join(parts, "&")
}

// AccessLog ersetzt chimw.Logger: dieselben Zeilen ueber chimw.DefaultLogger,
// aber der Logger sieht eine Kopie der Anfrage mit maskiertem RequestURI. Der
// nachfolgende Handler bekommt die unveraenderte Anfrage (samt dem vom Logger
// ergaenzten Kontext).
func AccessLog() func(http.Handler) http.Handler {
	logger := chimw.DefaultLogger
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			clone := *r
			clone.RequestURI = RedactURI(r.RequestURI)
			logger(http.HandlerFunc(func(lw http.ResponseWriter, lr *http.Request) {
				next.ServeHTTP(lw, r.WithContext(lr.Context()))
			})).ServeHTTP(w, &clone)
		})
	}
}
