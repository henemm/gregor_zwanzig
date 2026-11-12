package handler

import (
	"context"
	"io"
	"net/http"
	"net/url"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// forwardSend ist die EINE Proxy-Behandlung aller Versand-Routen (Issue #2280
// AC-13/AC-14): POST /api/briefings/{id}/send sowie die Alt-Delegates
// POST /api/trips/{id}/send und POST /api/compare/presets/{id}/send.
//
// rawQuery ist die weiterzureichende Query OHNE Kennung: eine Client-user_id
// wird verworfen und die Kennung aus dem Auth-Kontext injiziert (ADR-0003, nie
// "default"). Der Upstream ist vom Client-Abbruch (Browser/nginx) entkoppelt
// (Issue #2124, context.WithoutCancel); sendProxyTimeout bleibt die obere
// Grenze. Status, Content-Type und Body der Python-Antwort gehen 1:1 zurueck.
func forwardSend(w http.ResponseWriter, r *http.Request, path, rawQuery string) {
	query := appendUserID(rawQuery, middleware.UserIDFromContext(r.Context()))
	target := path
	if query != "" {
		target += "?" + query
	}

	req, err := http.NewRequestWithContext(context.WithoutCancel(r.Context()), http.MethodPost, target, nil)
	if err != nil {
		WriteError(w, r, http.StatusInternalServerError, "proxy_error", sendVarianteVersand)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: sendProxyTimeout}
	resp, err := client.Do(req)
	if err != nil {
		WriteError(w, r, http.StatusBadGateway, "upstream_unreachable", sendVarianteVersand)
		return
	}
	defer resp.Body.Close()

	ct := resp.Header.Get("Content-Type")
	if ct == "" {
		ct = "application/json"
	}
	w.Header().Set("Content-Type", ct)
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

// coreKennung liest den Pfad-Parameter param, prueft ihn als
// Entitaets-Kennung und liefert ihn als KODIERTES Pfadsegment fuer die
// Python-URL (Issue #2961, ADR-0114 Punkt 2). Ungueltig => 400
// validation_error (variante wie uebergeben), ok=false, Python wird nicht
// erreicht.
func coreKennung(w http.ResponseWriter, r *http.Request, param string, variante i18n.Args) (string, bool) {
	id := chi.URLParam(r, param)
	if !store.ValidEntityID(id) {
		WriteError(w, r, http.StatusBadRequest, "validation_error", variante)
		return "", false
	}
	return url.PathEscape(id), true
}
