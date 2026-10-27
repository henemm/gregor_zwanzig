package handler

// Ratebremse fuer Verknuepfungs-Code-Vergleiche — Issue #2154 Scheibe A, D5.
//
// Global, nicht je IP (der Lernaufruf kommt immer von localhost), nicht je
// Absendernummer (faelschbar) und nicht je Konto (sonst koennte ein Angreifer
// gezielt einzelne Konten aussperren, indem er denselben falschen Code gegen
// jedes Konto probiert).
//
// Der Zaehler liegt bewusst im Arbeitsspeicher und ueberlebt keinen Neustart
// (Spec "Known Limitations"): die Bremse ist Tiefenstaffelung, die tragende
// Grenze ist der Schluesselraum von ~2,75e10 in Verbindung damit, dass jeder
// Rateversuch dem Angreifer eine echte, bezahlte SMS kostet.

import "sync"

// DefaultPremiumSmsLinkCodeBudget ist die Zahl erfolgloser Code-Vergleiche, die
// der Dienst zwischen zwei Neustarts hinnimmt. Zehn Fehlversuche sind fuer den
// legitimen Fall (abgetippter Code, ein bis zwei Vertipper) reichlich und fuer
// einen Angreifer nichts: bei ~2,75e10 moeglichen Codes braucht Raten
// Groessenordnungen mehr Versuche, jeder davon eine bezahlte SMS.
const DefaultPremiumSmsLinkCodeBudget = 10

// PremiumSmsRateLimiter zaehlt erfolglose Code-Vergleiche gegen ein Budget.
type PremiumSmsRateLimiter struct {
	mu     sync.Mutex
	budget int
	failed int
}

// NewPremiumSmsRateLimiter baut eine Bremse mit dem angegebenen Budget.
func NewPremiumSmsRateLimiter(budget int) *PremiumSmsRateLimiter {
	return &PremiumSmsRateLimiter{budget: budget}
}

// Allow meldet, ob ueberhaupt noch ein Code-Vergleich stattfinden darf. Wird
// VOR jedem bcrypt-Vergleich gefragt (AC-7) — sonst waere die Bremse gegen
// genau den Angriff wirkungslos, den sie abwehren soll.
func (l *PremiumSmsRateLimiter) Allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.failed < l.budget
}

// RecordFailure verbucht einen erfolglosen Code-Vergleich.
func (l *PremiumSmsRateLimiter) RecordFailure() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.failed++
}

// FailedAttempts liefert den bisherigen Stand.
func (l *PremiumSmsRateLimiter) FailedAttempts() int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.failed
}

// scratch liefert eine Wegwerf-Bremse mit demselben Budget. Der Trockenlauf
// rechnet ausschliesslich dagegen (AC-8): der prozessweite Zaehler ist aus
// diesem Zweig heraus strukturell unerreichbar, nicht bloss per Bedingung
// uebersprungen.
func (l *PremiumSmsRateLimiter) scratch() *PremiumSmsRateLimiter {
	l.mu.Lock()
	defer l.mu.Unlock()
	return &PremiumSmsRateLimiter{budget: l.budget}
}
