package middleware

import (
	"encoding/json"
	"net"
	"net/http"
	"strconv"
	"sync"
	"time"

	"golang.org/x/time/rate"
)

// IPRateLimiter limits the number of requests per client IP using a
// token-bucket per IP. See Issue #117 / docs/specs/bugfix/register_rate_limit.md.
type IPRateLimiter struct {
	mu       sync.Mutex
	limiters map[string]*ipEntry
	rate     rate.Limit
	burst    int
	window   time.Duration
}

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
	}
	go rl.cleanupLoop()
	return rl
}

// get returns (and lazily creates) the rate.Limiter for the given IP and
// updates its lastSeen timestamp.
func (rl *IPRateLimiter) get(ip string) *rate.Limiter {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	e, ok := rl.limiters[ip]
	if !ok {
		e = &ipEntry{limiter: rate.NewLimiter(rl.rate, rl.burst)}
		rl.limiters[ip] = e
	}
	e.lastSeen = time.Now()
	return e.limiter
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
// HTTP 429 with a Retry-After header (seconds until next token) and a JSON body
// `{"error":"rate_limit_exceeded"}`.
func (rl *IPRateLimiter) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := clientIP(r)
		lim := rl.get(ip)
		if !lim.Allow() {
			retry := int(rl.window.Seconds() / float64(rl.burst))
			if retry < 1 {
				retry = 1
			}
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("Retry-After", strconv.Itoa(retry))
			w.WriteHeader(http.StatusTooManyRequests)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "rate_limit_exceeded"})
			return
		}
		next.ServeHTTP(w, r)
	})
}

// clientIP returns the canonical client IP. Prefers the `X-Real-IP` header
// (set by the Nginx reverse proxy — the only ingress since Issue #116), and
// falls back to RemoteAddr (stripping the port).
func clientIP(r *http.Request) string {
	if v := r.Header.Get("X-Real-IP"); v != "" {
		return v
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}
