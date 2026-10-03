package handler

// Reaper (gc) der drei In-Memory-/Datei-Stores — Issue #2160, AC-15.
//
// Vertrag: je Store eine testbare gc(now) (Muster ChallengeStore.gc):
//   gcOTPStore(now time.Time)               -- Login-OTPs (otpStore)
//   gcDeleteCodeStore(now time.Time)        -- Lösch-Codes (deleteCodeStore)
//   (*TelegramTokenStore).gc(now time.Time) -- Telegram-Deep-Link-Tokens
// Gestartet wird der Reaper aus cmd/server/main.go, NICHT aus Konstruktoren.

import (
	"runtime"
	"testing"
	"time"
)

func TestReaper_LoginOTPs_EntferntAbgelaufeneBehaeltGueltigeUndGesperrteBisAblauf(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	now := time.Now()
	setzeLoginOTP("abgelaufen@beispiel.de", "111111", now.Add(-time.Minute), 0)
	setzeLoginOTP("abgelaufen-gesperrt@beispiel.de", "222222", now.Add(-time.Minute), 3)
	setzeLoginOTP("gueltig@beispiel.de", "333333", now.Add(10*time.Minute), 0)
	setzeLoginOTP("gueltig-gesperrt@beispiel.de", "444444", now.Add(10*time.Minute), 3)

	gcOTPStore(now)

	for _, weg := range []string{"abgelaufen@beispiel.de", "abgelaufen-gesperrt@beispiel.de"} {
		if _, ok := otpStore.Load(weg); ok {
			t.Errorf("abgelaufenes OTP %s muss entfernt sein", weg)
		}
	}
	for _, da := range []string{"gueltig@beispiel.de", "gueltig-gesperrt@beispiel.de"} {
		if _, ok := otpStore.Load(da); !ok {
			t.Errorf("OTP %s ist noch gueltig (auch mit attempts>=3: sie IST die Sperre) und muss bleiben", da)
		}
	}
}

func TestReaper_LoeschCodes_EntferntAbgelaufeneBehaeltGueltige(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	now := time.Now()
	setzeLoeschCode("abgelaufen", "111111", now.Add(-time.Second), 0)
	setzeLoeschCode("abgelaufen-gesperrt", "222222", now.Add(-time.Second), 3)
	setzeLoeschCode("gueltig", "333333", now.Add(5*time.Minute), 0)
	setzeLoeschCode("gueltig-gesperrt", "444444", now.Add(5*time.Minute), 3)

	gcDeleteCodeStore(now)

	for _, weg := range []string{"abgelaufen", "abgelaufen-gesperrt"} {
		if _, ok := deleteCodeStore.Load(weg); ok {
			t.Errorf("abgelaufener Lösch-Code %s muss entfernt sein", weg)
		}
	}
	for _, da := range []string{"gueltig", "gueltig-gesperrt"} {
		if _, ok := deleteCodeStore.Load(da); !ok {
			t.Errorf("gueltiger Lösch-Code %s muss bleiben (gesperrte Codes bis Ablauf)", da)
		}
	}
}

func TestReaper_TelegramTokens_EntferntAbgelaufeneBehaeltGueltige(t *testing.T) {
	dir := t.TempDir()
	ts := NewTelegramTokenStore(dir)
	gueltig := mustIssueToken(t, ts, "anna")
	abgelaufen := mustIssueToken(t, ts, "bertram")
	ts.mu.Lock()
	pt := ts.tokens[abgelaufen]
	pt.ExpiresAt = time.Now().Add(-time.Minute)
	ts.tokens[abgelaufen] = pt
	ts.mu.Unlock()

	ts.gc(time.Now())

	ts.mu.Lock()
	_, hatAbgelaufen := ts.tokens[abgelaufen]
	_, hatGueltig := ts.tokens[gueltig]
	ts.mu.Unlock()
	if hatAbgelaufen {
		t.Error("abgelaufener Token muss nach gc entfernt sein")
	}
	if !hatGueltig {
		t.Error("gueltiger Token muss nach gc bleiben")
	}

	// gc mit einer Uhr jenseits der 24h-TTL raeumt auch den gueltigen.
	ts.gc(time.Now().Add(25 * time.Hour))
	ts.mu.Lock()
	rest := len(ts.tokens)
	ts.mu.Unlock()
	if rest != 0 {
		t.Errorf("nach gc(now+25h) darf kein Token mehr da sein, sind %d", rest)
	}
}

// Der Reaper wird aus main.go gestartet, nicht aus dem Konstruktor: Tests
// bauen viele Stores, jede Goroutine im Konstruktor waere ein Leck.
func TestReaper_KonstruktorStartetKeineGoroutine(t *testing.T) {
	time.Sleep(50 * time.Millisecond)
	vorher := runtime.NumGoroutine()
	for i := 0; i < 30; i++ {
		NewTelegramTokenStore(t.TempDir())
	}
	time.Sleep(50 * time.Millisecond)
	nachher := runtime.NumGoroutine()
	if nachher-vorher >= 15 { // 30 Konstruktoren mit je einer Goroutine => >=30
		t.Errorf("NewTelegramTokenStore startet Goroutinen: %d -> %d", vorher, nachher)
	}
}
