package handler

// Ratebremse fuer Verknuepfungs-Code-Vergleiche — Issue #2154 Scheibe A, D5;
// Zeitfenster seit Issue #2961, Bremse je Absendernummer seit Issue #2961
// Welle 2 (ADR-0116).
//
// Zwei Stufen, beide als GLEITENDES Fenster (premiumSmsLinkCodeFenster, eine
// Stunde):
//
//  1. Global (DefaultPremiumSmsLinkCodeBudget Fehlversuche je Stunde) — die
//     tragende Obergrenze. Nicht je IP (der Lernaufruf kommt immer von
//     localhost) und nicht je Konto (sonst koennte ein Angreifer gezielt
//     einzelne Konten aussperren, indem er denselben falschen Code gegen jedes
//     Konto probiert).
//  2. Je Absendernummer (DefaultPremiumSmsLinkCodeSenderBudget Fehlversuche je
//     Stunde) — damit ein einzelner Absender nicht das globale Budget fuer
//     alle verbraucht. Die Absendernummer ist keine Identitaet (Garmin vergibt
//     sie aus einem Pool, faelschbar ist sie ebenfalls); diese Stufe ist eine
//     Fairness-Bremse, die Sicherheitsgrenze bleibt die globale Stufe.
//
// Frueher galt das Budget "bis zum Neustart" — nach zehn Fehlversuchen war die
// Verknuepfung fuer alle Nutzer bis zum naechsten Deploy gesperrt, und ein
// Neustart setzte das Budget fuer einen Angreifer wieder auf null. Erschoepft
// sich das globale Fenster, schreibt die Bremse eine Warnung ins Log.
//
// Schluesselraum (ADR-0116): neue Codes "XX" + 5 aus 23 Buchstaben + 3 aus 8
// Ziffern = 23^5 * 8^3 = 3.295.407.616 (~3,3 Mrd., ~31,6 Bit). Bei 30
// Fehlversuchen je Stunde braucht vollstaendiges Durchprobieren rund 12.500
// Jahre. Bestandscodes im alten Format ("XX" + 3 Buchstaben + 3 Ziffern,
// 23^3 * 8^3 = 6.229.504) bleiben gueltig; fuer sie sind es rund 24 Jahre
// (im Mittel die Haelfte) — deshalb empfiehlt die Konto-Seite das Erneuern.
// Jeder Versuch ist ausserdem eine echte, bezahlte Satelliten-SMS und wird
// erst beim naechsten Poll geprueft.

import (
	"log"
	"sync"
	"time"
)

// DefaultPremiumSmsLinkCodeBudget ist die Zahl erfolgloser Code-Vergleiche, die
// der Dienst je premiumSmsLinkCodeFenster INSGESAMT hinnimmt (globale
// Obergrenze, ADR-0116: 30 statt frueher 10, weil die Bremse je Absender den
// Einzelnen bereits bei drei Fehlversuchen anhaelt).
const DefaultPremiumSmsLinkCodeBudget = 30

// DefaultPremiumSmsLinkCodeSenderBudget ist die Zahl erfolgloser
// Code-Vergleiche je Absendernummer und Fenster. Drei sind fuer den legitimen
// Fall (abgetippter Code, ein bis zwei Vertipper) reichlich.
const DefaultPremiumSmsLinkCodeSenderBudget = 3

// premiumSmsLinkCodeFenster: gleitendes Zeitfenster der Fehlversuche.
const premiumSmsLinkCodeFenster = time.Hour

// PremiumSmsRateLimiter zaehlt erfolglose Code-Vergleiche gegen ein Budget je
// gleitendem Zeitfenster.
type PremiumSmsRateLimiter struct {
	mu           sync.Mutex
	budget       int
	senderBudget int
	fenster      time.Duration
	jetzt        func() time.Time
	fehler       []time.Time
	jeAbsender   map[string][]time.Time
	gewarnt      bool
}

// NewPremiumSmsRateLimiter baut eine Bremse mit dem angegebenen globalen Budget
// je Stunde (gleitend) und dem Standard-Budget je Absendernummer.
func NewPremiumSmsRateLimiter(budget int) *PremiumSmsRateLimiter {
	return &PremiumSmsRateLimiter{
		budget: budget, senderBudget: DefaultPremiumSmsLinkCodeSenderBudget,
		fenster: premiumSmsLinkCodeFenster, jetzt: time.Now,
		jeAbsender: map[string][]time.Time{},
	}
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
	// Je Absender: abgelaufene Eintraege und leere Schluessel entfernen, damit
	// die Karte nicht ueber die Fensterlaenge hinaus waechst.
	for absender, zeiten := range l.jeAbsender {
		j := 0
		for j < len(zeiten) && !zeiten[j].After(grenze) {
			j++
		}
		if j == len(zeiten) {
			delete(l.jeAbsender, absender)
		} else {
			l.jeAbsender[absender] = zeiten[j:]
		}
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

// AllowFrom meldet, ob fuer diese Absendernummer noch ein Code-Vergleich
// stattfinden darf: erst die Stufe je Absender, dann die globale Obergrenze.
// Eine erschoepfte Absender-Stufe fragt die globale nicht mehr (kein Verbrauch).
func (l *PremiumSmsRateLimiter) AllowFrom(absender string) bool {
	l.mu.Lock()
	erschoepft := len(l.jeAbsenderFehler(absender)) >= l.senderBudget
	l.mu.Unlock()
	if erschoepft {
		return false
	}
	return l.Allow()
}

// jeAbsenderFehler liefert die Fehlversuche des Absenders im Fenster; Aufrufer
// haelt mu.
func (l *PremiumSmsRateLimiter) jeAbsenderFehler(absender string) []time.Time {
	l.aufraeumen()
	return l.jeAbsender[absender]
}

// RecordFailure verbucht einen erfolglosen Code-Vergleich (nur global).
func (l *PremiumSmsRateLimiter) RecordFailure() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.aufraeumen()
	l.fehler = append(l.fehler, l.jetzt())
}

// RecordFailureFrom verbucht einen erfolglosen Code-Vergleich global UND fuer
// die Absendernummer.
func (l *PremiumSmsRateLimiter) RecordFailureFrom(absender string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.aufraeumen()
	jetzt := l.jetzt()
	l.fehler = append(l.fehler, jetzt)
	l.jeAbsender[absender] = append(l.jeAbsender[absender], jetzt)
}

// SenderFailedAttempts liefert die Fehlversuche einer Absendernummer im
// aktuellen Fenster.
func (l *PremiumSmsRateLimiter) SenderFailedAttempts(absender string) int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return len(l.jeAbsenderFehler(absender))
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
	return &PremiumSmsRateLimiter{
		budget: l.budget, senderBudget: l.senderBudget, fenster: l.fenster,
		jetzt: l.jetzt, jeAbsender: map[string][]time.Time{},
	}
}
