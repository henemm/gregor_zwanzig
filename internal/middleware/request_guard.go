package middleware

// Globale Schutzschicht fuer schreibende API-Anfragen (Issue #2961, ADR-0113):
// Herkunftspruefung (Origin/Sec-Fetch-Site), JSON-Pflicht fuer Rumpfe und
// Groessenbegrenzung. Maschinenpfade (Webhooks, interne Aufrufe des
// Python-Kerns, Maschinen-Status, OAuth-Rueckruf) sind ausgenommen: sie kommen
// nicht aus dem Browser und tragen eigene Nachweise.

import (
	"mime"
	"net/http"
	"strings"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/i18n"
)

// isStateChanging: Methoden, die Zustand aendern koennen.
func isStateChanging(method string) bool {
	switch method {
	case http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete:
		return true
	}
	return false
}

// IsMachinePath meldet die von der Browser-Schutzschicht ausgenommenen Pfade.
func IsMachinePath(path string) bool {
	return strings.HasPrefix(path, "/api/webhooks/") ||
		strings.HasPrefix(path, "/api/internal/") ||
		strings.HasPrefix(path, "/api/_internal/") ||
		path == "/api/scheduler/status" ||
		path == "/api/auth/google/callback"
}

func guarded(r *http.Request) bool {
	return isStateChanging(r.Method) && strings.HasPrefix(r.URL.Path, "/api/") && !IsMachinePath(r.URL.Path)
}

// OriginPolicy beschreibt die erlaubten Browser-Urspruenge.
type OriginPolicy struct {
	origins       map[string]struct{}
	allowLoopback bool
}

// NewOriginPolicy baut die Richtlinie aus der Konfiguration
// (config.BrowserOrigins).
func NewOriginPolicy(cfg *config.Config) OriginPolicy {
	list, loopback := config.BrowserOrigins(cfg)
	p := OriginPolicy{origins: map[string]struct{}{}, allowLoopback: loopback}
	for _, o := range list {
		p.origins[o] = struct{}{}
	}
	return p
}

func (p OriginPolicy) allows(origin string) bool {
	n := config.NormalizeOrigin(origin)
	if n == "" {
		return false // auch "null"
	}
	if _, ok := p.origins[n]; ok {
		return true
	}
	return p.allowLoopback && config.IsLoopbackOrigin(n)
}

// OriginGuard weist schreibende API-Anfragen aus fremder Herkunft ab:
// ein vorhandener Origin-Header muss ein erlaubter Ursprung sein, ein
// vorhandener Sec-Fetch-Site-Header "same-origin" oder "none". Fehlen beide
// (Server-zu-Server: SvelteKit-Server-Routen, Skripte), wird durchgelassen.
// Verstoss: 403 origin_forbidden.
func OriginGuard(p OriginPolicy) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if guarded(r) {
				origin := r.Header.Get("Origin")
				site := r.Header.Get("Sec-Fetch-Site")
				if (origin != "" && !p.allows(origin)) ||
					(site != "" && site != "same-origin" && site != "none") {
					writeError(w, i18n.FromRequest(r, nil), http.StatusForbidden, "origin_forbidden")
					return
				}
			}
			next.ServeHTTP(w, r)
		})
	}
}

// hasBody: die Anfrage traegt (wahrscheinlich) einen Rumpf.
func hasBody(r *http.Request) bool {
	if r.Body == nil || r.Body == http.NoBody {
		return false
	}
	return r.ContentLength > 0 || (r.ContentLength < 0 && len(r.TransferEncoding) > 0)
}

// RequireJSONBody verlangt fuer schreibende API-Anfragen mit Rumpf den
// Content-Type application/json; die in multipartPaths genannten Pfade
// (Datei-Upload) nehmen stattdessen multipart/form-data an. Sonst 415
// unsupported_media_type.
func RequireJSONBody(multipartPaths ...string) func(http.Handler) http.Handler {
	multipart := map[string]bool{}
	for _, p := range multipartPaths {
		multipart[p] = true
	}
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if guarded(r) && hasBody(r) {
				mt, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
				ok := err == nil && (mt == "application/json" ||
					(mt == "multipart/form-data" && multipart[r.URL.Path]))
				if !ok {
					writeError(w, i18n.FromRequest(r, nil), http.StatusUnsupportedMediaType, "unsupported_media_type")
					return
				}
			}
			next.ServeHTTP(w, r)
		})
	}
}

// LimitBody begrenzt den Rumpf jeder API-Anfrage (ausser Webhooks, die ihre
// eigenen Grenzen setzen) auf limit Bytes, fuer die in overrides genannten
// Pfade auf den dort angegebenen Wert. Ein angekuendigter zu grosser Rumpf
// wird sofort mit 413 payload_too_large abgewiesen; ein unangekuendigter
// (chunked) bricht beim Lesen ab.
func LimitBody(limit int64, overrides map[string]int64) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if strings.HasPrefix(r.URL.Path, "/api/") && !strings.HasPrefix(r.URL.Path, "/api/webhooks/") &&
				r.Body != nil && r.Body != http.NoBody {
				max := limit
				if o, ok := overrides[r.URL.Path]; ok {
					max = o
				}
				if r.ContentLength > max {
					writeError(w, i18n.FromRequest(r, nil), http.StatusRequestEntityTooLarge, "payload_too_large")
					return
				}
				r.Body = http.MaxBytesReader(w, r.Body, max)
			}
			next.ServeHTTP(w, r)
		})
	}
}
