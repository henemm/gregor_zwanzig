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

// secretPathKinds: unter /api/webhooks/<art>/ ist das folgende Segment ein
// Geheimnis.
var secretPathKinds = map[string]bool{"sms": true, "mail": true}

// secretQueryKeys: Query-Parameter, deren Wert nie ins Log gehoert
// (Vergleich ohne Gross-/Kleinschreibung).
var secretQueryKeys = map[string]bool{
	"code": true, "state": true, "token": true, "id_token": true,
	"access_token": true, "invite": true, "secret": true, "password": true,
}

// redactPath maskiert Pfadgeheimnisse. Leere Segmente (z. B. "//api/…")
// werden fuer die Erkennung uebergangen, damit Schreibvarianten des Pfads
// nicht am Maskieren vorbeikommen.
func redactPath(escapedPath string) string {
	raw := strings.Split(escapedPath, "/")
	segs := make([]string, 0, len(raw))
	for _, sgm := range raw {
		if sgm != "" {
			segs = append(segs, sgm)
		}
	}
	if len(segs) >= 4 && segs[0] == "api" && segs[1] == "webhooks" && secretPathKinds[segs[2]] {
		segs[3] = redacted
		return "/" + strings.Join(segs, "/")
	}
	return escapedPath
}

// redactQuery maskiert die Werte geheimer Query-Parameter.
func redactQuery(rawQuery string) string {
	parts := strings.Split(rawQuery, "&")
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
	return strings.Join(parts, "&")
}

// RedactRequestTarget liefert Pfad und Query der Anfrage maskiert. Grundlage
// ist die geparste URL (nicht der rohe RequestURI): so werden auch die
// absolute Form ("http://h/api/…") und Pfade mit doppeltem Schraegstrich
// erfasst.
func RedactRequestTarget(u *url.URL) string {
	out := redactPath(u.EscapedPath())
	if u.RawQuery != "" {
		out += "?" + redactQuery(u.RawQuery)
	}
	return out
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
			clone.RequestURI = RedactRequestTarget(r.URL)
			logger(http.HandlerFunc(func(lw http.ResponseWriter, lr *http.Request) {
				next.ServeHTTP(lw, r.WithContext(lr.Context()))
			})).ServeHTTP(w, &clone)
		})
	}
}
