package handler

// Mengenbremse fuer Bestaetigungsmails — Issue #2404 (Sammel-Issue #2153,
// Scheibe S2), Spec docs/specs/bugfix/profile_mail_ratelimit.md.
//
// Zwei unabhaengige Token-Buckets je Vorgang: einer je Nutzerkennung, einer je
// Zieladresse. Der Adress-Bucket ist der Cross-Account-Schutz — ohne ihn
// koennten mehrere eigene Konten dieselbe fremde Adresse gemeinsam fluten.
// Bauart nach Vorbild middleware.IPRateLimiter, aber schluesselbasiert statt
// als http.Handler-Wrapper, weil die Pruefung mitten im Handler sitzen muss
// (erst dort steht fest, ob ueberhaupt eine Mail entstuende).
//
// Der Zustand liegt bewusst im Arbeitsspeicher und ueberlebt keinen Neustart
// (Spec "Known Limitations"): Neustarts sind nicht angreifergesteuert.

import (
	"strconv"
	"sync"
	"time"

	"golang.org/x/time/rate"
)

type mailFloodEntry struct {
	limiter  *rate.Limiter
	lastSeen time.Time
}

// MailFloodLimiter begrenzt Bestaetigungsmails je Nutzerkennung und je
// Zieladresse.
type MailFloodLimiter struct {
	mu             sync.Mutex
	userBuckets    map[string]*mailFloodEntry
	addressBuckets map[string]*mailFloodEntry
	rate           rate.Limit
	burst          int
	window         time.Duration
}

// NewMailFloodLimiter baut eine Bremse, die je Schluessel burst Vorgaenge pro
// window zulaesst. Nachfuellrate window/burst, analog NewIPRateLimiter.
func NewMailFloodLimiter(burst int, window time.Duration) *MailFloodLimiter {
	l := &MailFloodLimiter{
		userBuckets:    make(map[string]*mailFloodEntry),
		addressBuckets: make(map[string]*mailFloodEntry),
		rate:           rate.Every(window / time.Duration(burst)),
		burst:          burst,
		window:         window,
	}
	go l.cleanupLoop()
	return l
}

// bucket liefert (und legt bei Bedarf an) den Bucket zu key. Der Aufrufer
// haelt l.mu.
func (l *MailFloodLimiter) bucket(m map[string]*mailFloodEntry, key string, now time.Time) *rate.Limiter {
	e, ok := m[key]
	if !ok {
		e = &mailFloodEntry{limiter: rate.NewLimiter(l.rate, l.burst)}
		m[key] = e
	}
	e.lastSeen = now
	return e.limiter
}

// Allow meldet, ob fuer userID eine Mail an address verschickt werden darf.
// Verbraucht nur dann Kontingent, wenn BEIDE Buckets sofort liefern — eine
// Ablehnung laesst beide Seiten unberuehrt (AC-7).
func (l *MailFloodLimiter) Allow(userID, address string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()

	now := time.Now()
	nutzer := l.bucket(l.userBuckets, userID, now).ReserveN(now, 1)
	adresse := l.bucket(l.addressBuckets, address, now).ReserveN(now, 1)
	if sofort(nutzer, now) && sofort(adresse, now) {
		return true
	}
	// CancelAt(now), nicht Cancel(): Cancel() rechnet mit einem frisch
	// gelesenen time.Now(), das hinter timeToAct liegt — CancelAt kehrt dann
	// ohne Rueckgabe um und die gerade erfolgreiche Seite verlöre ihr Token.
	nutzer.CancelAt(now)
	adresse.CancelAt(now)
	return false
}

// AllowAddressOnly prueft und verbraucht ausschliesslich den Adress-Bucket.
// Fuer den unauthentifizierten Resend-Pfad, dessen Kennung aus dem Rumpf
// stammt und damit faelschbar ist: wuerde dort ein User-Bucket verbraucht,
// koennte ein Fremder das Kontingent eines Opfers leerlaufen lassen (AC-8).
func (l *MailFloodLimiter) AllowAddressOnly(address string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()

	now := time.Now()
	adresse := l.bucket(l.addressBuckets, address, now).ReserveN(now, 1)
	if sofort(adresse, now) {
		return true
	}
	adresse.CancelAt(now)
	return false
}

// RetryAfterHeader liefert den Retry-After-Wert in Sekunden, identische
// Rechnung wie IPRateLimiter.Middleware.
func (l *MailFloodLimiter) RetryAfterHeader() string {
	sek := int(l.window.Seconds() / float64(l.burst))
	if sek < 1 {
		sek = 1
	}
	return strconv.Itoa(sek)
}

// sofort meldet, ob die Reservierung ohne Wartezeit gilt — nur das zaehlt als
// freies Token.
func sofort(r *rate.Reservation, now time.Time) bool {
	return r.OK() && r.DelayFrom(now) == 0
}

// cleanupLoop raeumt alle zehn Minuten Schluessel weg, die laenger als das
// Fenster ungenutzt sind (Vorbild IPRateLimiter.cleanupLoop).
func (l *MailFloodLimiter) cleanupLoop() {
	t := time.NewTicker(10 * time.Minute)
	defer t.Stop()
	for range t.C {
		cutoff := time.Now().Add(-l.window)
		l.mu.Lock()
		for _, m := range []map[string]*mailFloodEntry{l.userBuckets, l.addressBuckets} {
			for k, e := range m {
				if e.lastSeen.Before(cutoff) {
					delete(m, k)
				}
			}
		}
		l.mu.Unlock()
	}
}
