package handler

import (
	"context"
	"io"
	"net/http"

	"github.com/henemm/gregor-api/internal/middleware"
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
		writeSendError(w, http.StatusInternalServerError, "proxy_error", sendDetailProxyError)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: sendProxyTimeout}
	resp, err := client.Do(req)
	if err != nil {
		writeSendError(w, http.StatusBadGateway, "upstream_unreachable", sendDetailUpstreamUnreached)
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
