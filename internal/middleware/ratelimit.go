package middleware

import (
	"net"
	"net/http"
	"strconv"
	"sync"
	"time"

	"golang.org/x/time/rate"

	"github.com/henemm/gregor-api/internal/i18n"
)

// IPRateLimiter limits the number of requests per client IP using a
// token-bucket per IP. See Issue #117 / docs/specs/bugfix/register_rate_limit.md.
type IPRateLimiter struct {
	mu       sync.Mutex
	limiters map[string]*ipEntry
	rate     rate.Limit
	burst    int
	window   time.Duration
	// Issue #2961: Obergrenze der Tabelle; darueber werden zuerst abgelaufene
	// Eintraege entfernt, notfalls ein beliebiger (Speicher bleibt begrenzt).
	maxEntries int
}

// defaultMaxLimiterEntries begrenzt die Tabelle je Limiter-Instanz.
const defaultMaxLimiterEntries = 50_000

type ipEntry struct {
	limiter  *rate.Limiter
	lastSeen time.Time
}

// NewIPRateLimiter creates a limiter that allows `burst` requests per `window`
// per client IP. The refill rate is window/burst (e.g. 5 req/hour => one token
// every 12 minutes). Starts a background cleanup goroutine that drops IP
// entries which have not been seen for longer than `window`.
func NewIPRateLimiter(burst int, window time.Duration) *IPRateLimiter {
	rl := &IPRateLimiter{
		limiters: make(map[string]*ipEntry),
		rate:     rate.Every(window / time.Duration(burst)),
		burst:    burst,
		window:   window,

		maxEntries: defaultMaxLimiterEntries,
	}
	go rl.cleanupLoop()
	return rl
}

// get returns (and lazily creates) the rate.Limiter for the given IP and
// updates its lastSeen timestamp.
func (rl *IPRateLimiter) get(ip string) *rate.Limiter {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	now := time.Now()
	e, ok := rl.limiters[ip]
	if !ok {
		if rl.maxEntries > 0 && len(rl.limiters) >= rl.maxEntries {
			rl.evictLocked(now)
		}
		e = &ipEntry{limiter: rate.NewLimiter(rl.rate, rl.burst)}
		rl.limiters[ip] = e
	}
	e.lastSeen = now
	return e.limiter
}

// evictLocked schafft Platz fuer einen neuen Eintrag (Issue #2961): erst alle
// abgelaufenen Eintraege, reicht das nicht, ein beliebiger. Der Aufrufer
// haelt rl.mu.
func (rl *IPRateLimiter) evictLocked(now time.Time) {
	cutoff := now.Add(-rl.window)
	for k, e := range rl.limiters {
		if e.lastSeen.Before(cutoff) {
			delete(rl.limiters, k)
		}
	}
	for k := range rl.limiters {
		if len(rl.limiters) < rl.maxEntries {
			return
		}
		delete(rl.limiters, k)
	}
}

// cleanupLoop runs every 10 minutes and removes limiter entries that have not
// been used for longer than `window` to keep memory bounded.
func (rl *IPRateLimiter) cleanupLoop() {
	t := time.NewTicker(10 * time.Minute)
	defer t.Stop()
	for range t.C {
		cutoff := time.Now().Add(-rl.window)
		rl.mu.Lock()
		for ip, e := range rl.limiters {
			if e.lastSeen.Before(cutoff) {
				delete(rl.limiters, ip)
			}
		}
		rl.mu.Unlock()
	}
}

// Middleware wraps `next` so that requests exceeding the rate limit get
// HTTP 429 with a Retry-After header (seconds until next token) and the error
// object rate_limit_exceeded in the request language (Issue #2677).
func (rl *IPRateLimiter) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		lim := rl.get(limiterKey(clientIP(r)))
		if !lim.Allow() {
			retry := int(rl.window.Seconds() / float64(rl.burst))
			if retry < 1 {
				retry = 1
			}
			w.Header().Set("Retry-After", strconv.Itoa(retry))
			writeError(w, i18n.FromContext(r.Context()), http.StatusTooManyRequests, "rate_limit_exceeded")
			return
		}
		next.ServeHTTP(w, r)
	})
}

// limiterKey fasst IPv6-Adressen auf ihr /64-Netz zusammen (Issue #2961): ein
// Anschluss verfuegt ueber ein ganzes /64, einzelne Adressen daraus duerfen das
// Kontingent nicht vervielfachen. IPv4 (auch IPv4-in-IPv6) bleibt je Adresse.
func limiterKey(ip string) string {
	parsed := net.ParseIP(ip)
	if parsed == nil || parsed.To4() != nil {
		return ip
	}
	return parsed.Mask(net.CIDRMask(64, 128)).String() + "/64"
}

// clientIP returns the canonical client IP. Prefers the `X-Real-IP` header
// (set by the Nginx reverse proxy — the only ingress since Issue #116), and
// falls back to RemoteAddr (stripping the port).
func clientIP(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		host = r.RemoteAddr
	}
	// X-Real-IP nur von einem Loopback-Absender (nginx / SvelteKit) glauben;
	// sonst ist der Header client-steuerbar (#2159).
	if v := r.Header.Get("X-Real-IP"); v != "" {
		if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
			return v
		}
	}
	return host
}
