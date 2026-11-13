package handler

// Ratebremse fuer Verknuepfungs-Code-Vergleiche — Issue #2154 Scheibe A, D5;
// Zeitfenster seit Issue #2961.
//
// Global, nicht je IP (der Lernaufruf kommt immer von localhost), nicht je
// Absendernummer (faelschbar) und nicht je Konto (sonst koennte ein Angreifer
// gezielt einzelne Konten aussperren, indem er denselben falschen Code gegen
// jedes Konto probiert).
//
// Gezaehlt werden Fehlversuche in einem GLEITENDEN Fenster
// (premiumSmsLinkCodeFenster, eine Stunde): frueher galt das Budget "bis zum
// Neustart" — nach zehn Fehlversuchen war die Verknuepfung fuer alle Nutzer
// bis zum naechsten Deploy gesperrt, und ein Neustart setzte das Budget fuer
// einen Angreifer wieder auf null. Erschoepft sich das Fenster, schreibt die
// Bremse eine Warnung ins Log.
//
// Schluesselraum (Format seit #2323: "XX" + 3 aus 23 Buchstaben + 3 aus 8
// Ziffern): 23^3 * 8^3 = 6.229.504, rund 6,2 Mio. moegliche Codes (~22,6 Bit)
// — NICHT die frueher hier genannten ~2,75e10. Bei 10 Fehlversuchen je Stunde
// braucht vollstaendiges Durchprobieren rund 71 Jahre, im Mittel die Haelfte;
// jeder Versuch ist ausserdem eine echte, bezahlte Satelliten-SMS und wird
// erst beim naechsten Poll geprueft. Die Bremse ist damit die tragende Grenze,
// nicht mehr nur Tiefenstaffelung.

import (
	"log"
	"sync"
	"time"
)

// DefaultPremiumSmsLinkCodeBudget ist die Zahl erfolgloser Code-Vergleiche, die
// der Dienst je premiumSmsLinkCodeFenster hinnimmt. Zehn Fehlversuche sind fuer
// den legitimen Fall (abgetippter Code, ein bis zwei Vertipper) reichlich.
const DefaultPremiumSmsLinkCodeBudget = 10

// premiumSmsLinkCodeFenster: gleitendes Zeitfenster der Fehlversuche.
const premiumSmsLinkCodeFenster = time.Hour

// PremiumSmsRateLimiter zaehlt erfolglose Code-Vergleiche gegen ein Budget je
// gleitendem Zeitfenster.
type PremiumSmsRateLimiter struct {
	mu      sync.Mutex
	budget  int
	fenster time.Duration
	jetzt   func() time.Time
	fehler  []time.Time
	gewarnt bool
}

// NewPremiumSmsRateLimiter baut eine Bremse mit dem angegebenen Budget je
// Stunde (gleitend).
func NewPremiumSmsRateLimiter(budget int) *PremiumSmsRateLimiter {
	return &PremiumSmsRateLimiter{budget: budget, fenster: premiumSmsLinkCodeFenster, jetzt: time.Now}
}

// aufraeumen entfernt Fehlversuche ausserhalb des Fensters; Aufrufer haelt mu.
func (l *PremiumSmsRateLimiter) aufraeumen() {
	grenze := l.jetzt().Add(-l.fenster)
	i := 0
	for i < len(l.fehler) && !l.fehler[i].After(grenze) {
		i++
	}
	l.fehler = l.fehler[i:]
	if len(l.fehler) < l.budget {
		l.gewarnt = false
	}
}

// Allow meldet, ob ueberhaupt noch ein Code-Vergleich stattfinden darf. Wird
// VOR jedem bcrypt-Vergleich gefragt (AC-7) — sonst waere die Bremse gegen
// genau den Angriff wirkungslos, den sie abwehren soll.
func (l *PremiumSmsRateLimiter) Allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.aufraeumen()
	if len(l.fehler) < l.budget {
		return true
	}
	if !l.gewarnt {
		l.gewarnt = true
		log.Printf("[premium-sms] WARN: Ratebremse fuer Verknuepfungs-Codes erschoepft (%d Fehlversuche in %s) — Code-Vergleiche pausieren", len(l.fehler), l.fenster)
	}
	return false
}

// RecordFailure verbucht einen erfolglosen Code-Vergleich.
func (l *PremiumSmsRateLimiter) RecordFailure() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.aufraeumen()
	l.fehler = append(l.fehler, l.jetzt())
}

// FailedAttempts liefert die Fehlversuche im aktuellen Fenster.
func (l *PremiumSmsRateLimiter) FailedAttempts() int {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.aufraeumen()
	return len(l.fehler)
}

// scratch liefert eine Wegwerf-Bremse mit demselben Budget. Der Trockenlauf
// rechnet ausschliesslich dagegen (AC-8): der prozessweite Zaehler ist aus
// diesem Zweig heraus strukturell unerreichbar, nicht bloss per Bedingung
// uebersprungen.
func (l *PremiumSmsRateLimiter) scratch() *PremiumSmsRateLimiter {
	l.mu.Lock()
	defer l.mu.Unlock()
	return &PremiumSmsRateLimiter{budget: l.budget, fenster: l.fenster, jetzt: l.jetzt}
}
