package middleware

import (
	"fmt"
	"net/http"
	"testing"
	"time"
)

// Issue #2961 (GA1 f): IPv6-Absender werden auf ihr /64-Netz zusammengefasst —
// ein Anschluss verfuegt typischerweise ueber ein ganzes /64, einzelne
// Adressen daraus duerfen das Kontingent nicht vervielfachen.
func TestIPRateLimiter_IPv6ZaehltJe64Netz(t *testing.T) {
	limiter := NewIPRateLimiter(2, time.Hour)
	h := limiter.Middleware(newOKHandler())

	if got := doReq(t, h, "[2001:db8:1:2::1]:4000", ""); got != http.StatusOK {
		t.Fatalf("1. Anfrage: erwartet 200, bekommen %d", got)
	}
	if got := doReq(t, h, "[2001:db8:1:2:ffff::7]:4000", ""); got != http.StatusOK {
		t.Fatalf("2. Anfrage: erwartet 200, bekommen %d", got)
	}
	if got := doReq(t, h, "[2001:db8:1:2:aaaa:bbbb:cccc:dddd]:4000", ""); got != http.StatusTooManyRequests {
		t.Fatalf("3. Anfrage aus demselben /64: erwartet 429, bekommen %d", got)
	}
	// Gegenprobe: ein anderes /64 hat ein eigenes Kontingent.
	if got := doReq(t, h, "[2001:db8:1:3::1]:4000", ""); got != http.StatusOK {
		t.Fatalf("Anfrage aus anderem /64: erwartet 200, bekommen %d", got)
	}
	// Gegenprobe IPv4: einzelne Adressen bleiben getrennt.
	for _, a := range []string{"10.0.0.1:1", "10.0.0.2:1", "10.0.0.3:1"} {
		if got := doReq(t, h, a, ""); got != http.StatusOK {
			t.Fatalf("IPv4 %s: erwartet 200, bekommen %d", a, got)
		}
	}
}

// Issue #2961 (GA1 f): X-Real-IP vom vertrauten Proxy wird ebenso auf /64
// zusammengefasst.
func TestIPRateLimiter_IPv6AusXRealIPZaehltJe64Netz(t *testing.T) {
	limiter := NewIPRateLimiter(1, time.Hour)
	h := limiter.Middleware(newOKHandler())
	if got := doReq(t, h, "127.0.0.1:5000", "2001:db8:9:9::1"); got != http.StatusOK {
		t.Fatalf("1. Anfrage: erwartet 200, bekommen %d", got)
	}
	if got := doReq(t, h, "127.0.0.1:5000", "2001:db8:9:9::2"); got != http.StatusTooManyRequests {
		t.Fatalf("2. Anfrage aus demselben /64 ueber X-Real-IP: erwartet 429, bekommen %d", got)
	}
}

// Issue #2961 (GA1 f): die Limiter-Tabelle waechst nicht unbegrenzt.
func TestIPRateLimiter_TabelleHatObergrenze(t *testing.T) {
	limiter := NewIPRateLimiter(5, time.Hour)
	limiter.maxEntries = 100
	h := limiter.Middleware(newOKHandler())
	for i := 0; i < 1000; i++ {
		doReq(t, h, fmt.Sprintf("10.%d.%d.%d:1", i/65536, (i/256)%256, i%256), "")
	}
	limiter.mu.Lock()
	n := len(limiter.limiters)
	limiter.mu.Unlock()
	if n > 100 {
		t.Fatalf("Limiter-Tabelle hat %d Eintraege, Obergrenze 100", n)
	}
}
