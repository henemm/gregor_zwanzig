package config

import (
	"net"
	"net/url"
	"strings"
)

// BrowserOrigins liefert die Browser-Urspruenge, von denen schreibende
// API-Anfragen kommen duerfen (Issue #2961, ADR-0113): der aus GZ_PUBLIC_HOST
// abgeleitete eigene Ursprung plus die Passkey-Urspruenge (dieselbe
// Oberflaeche). allowLoopback ist im Staging, im Fixture-Modus und bei einem
// lokalen GZ_PUBLIC_HOST (Entwicklung) gesetzt: dann sind zusaetzlich
// localhost-/Loopback-Urspruenge mit beliebigem Port erlaubt (Vite-Dev-Server,
// Playwright-Vorschau, CI-Stack).
func BrowserOrigins(cfg *Config) (origins []string, allowLoopback bool) {
	seen := map[string]bool{}
	add := func(o string) {
		if n := NormalizeOrigin(o); n != "" && !seen[n] {
			seen[n] = true
			origins = append(origins, n)
		}
	}
	if _, derived, ok := deriveFromPublicHost(cfg.PublicHost); ok {
		add(derived)
	}
	_, rpOrigins := resolveWebAuthnRP(cfg)
	for _, o := range rpOrigins {
		if !IsLoopbackOrigin(o) {
			add(o)
		}
	}
	allowLoopback = cfg.Env == "staging" || cfg.TestFixtureDir != "" || IsLoopbackOrigin(cfg.PublicHost)
	return origins, allowLoopback
}

// NormalizeOrigin bringt einen Ursprung auf die Form scheme://host[:port] in
// Kleinbuchstaben; "" bei Unbrauchbarem.
func NormalizeOrigin(raw string) string {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || u.Host == "" {
		return ""
	}
	scheme := strings.ToLower(u.Scheme)
	if scheme != "http" && scheme != "https" {
		return ""
	}
	return scheme + "://" + strings.ToLower(u.Host)
}

// IsLoopbackOrigin meldet Urspruenge auf localhost bzw. einer Loopback-IP.
func IsLoopbackOrigin(raw string) bool {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return false
	}
	scheme := strings.ToLower(u.Scheme)
	if scheme != "http" && scheme != "https" {
		return false
	}
	host := strings.ToLower(u.Hostname())
	if host == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}
