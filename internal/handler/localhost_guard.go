package handler

// Sicherheitsfix (Team-Lead-Befund, 2026-08-10): die frueherer localhost-Sperre
// auf den internen Endpoints (PostPremiumSmsLearnHandler,
// PostTelegramConnectHandler) pruefte nur r.RemoteAddr. Das wirkt NICHT:
// nginx laeuft auf demselben Host und proxyt nach 127.0.0.1, also ist
// r.RemoteAddr bei JEDER ueber nginx hereingeholten Anfrage -- egal von
// welcher externen IP -- "127.0.0.1:<port>", ununterscheidbar von einem
// direkten Aufruf des lokalen Python-Core. Gemessen: Staging von aussen
// erreichte den Endpoint bis zur Fachlogik (409 statt 403).
//
// Fix kehrt die Frage um: nicht "sieht das nach einem externen Aufrufer
// aus?", sondern "bin ich SICHER, dass dieser Aufruf lokal ist?" -- im
// Zweifel ablehnen. nginx setzt fuer JEDE durchgeleitete Anfrage mindestens
// einen der Proxy-Header (X-Forwarded-For/X-Real-IP/X-Forwarded-Proto,
// siehe /etc/nginx/sites-enabled/*gregor*). Der lokale Python-Core ruft
// direkt per net/http auf localhost:8090 und setzt keinen dieser Header.
// Traegt eine Anfrage einen davon, ist sie zwangslaeufig durch nginx
// gelaufen, egal was RemoteAddr behauptet.

import (
	"net/http"
	"strings"
)

// isProxiedRequest meldet, ob r einen der Header traegt, die nginx jeder von
// aussen hereingeholten Anfrage aufpraegt.
func isProxiedRequest(r *http.Request) bool {
	return r.Header.Get("X-Forwarded-For") != "" ||
		r.Header.Get("X-Real-IP") != "" ||
		r.Header.Get("X-Forwarded-Proto") != ""
}

// requireLocalOnly erzwingt, dass eine Anfrage ein echter Loopback-Aufruf
// eines lokalen Prozesses ist -- nicht einer, der ueber nginx aus dem
// Internet hereingeholt wurde. Schreibt bei Ablehnung 403 und liefert false;
// Aufrufer MUESSEN bei false sofort zurueckkehren, ohne weiterzuarbeiten.
func requireLocalOnly(w http.ResponseWriter, r *http.Request) bool {
	remoteHost := r.RemoteAddr
	isLoopback := strings.HasPrefix(remoteHost, "127.0.0.1:") || strings.HasPrefix(remoteHost, "[::1]:")
	if !isLoopback || isProxiedRequest(r) {
		http.Error(w, "forbidden", http.StatusForbidden)
		return false
	}
	return true
}
