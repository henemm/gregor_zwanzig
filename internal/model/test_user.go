package model

import "strings"

// fixedTestFixtureUserID is the Telegram-E2E-Fixture-Konto — immer als
// Testkonto behandelt, unabhängig von der test/tdd-Namens-Heuristik.
const fixedTestFixtureUserID = "tg-live-e2e"

// IsTestUserIDSubstringOnly reports the "test"/"tdd" substring heuristic
// (case-insensitive) OHNE den Fixed-Fixture-Sonderfall. Exportiert für
// internal/mail (Issue #1265 Fix-Loop 1, Adversary Runde-2-Ripple-Fund):
// mail.IsTestUser behält damit die ALTE Vor-#1265-Semantik für das
// Passwort-Reset-/Verifikations-Mail-Routing in handler/auth.go — kein
// stiller Verhaltenswechsel für tg-live-e2e im Mail-Versandpfad.
func IsTestUserIDSubstringOnly(userID string) bool {
	id := strings.ToLower(userID)
	return strings.Contains(id, "test") || strings.Contains(id, "tdd")
}

// IsTestUserID reports whether userID identifies a synthetic test/tdd
// account that must never be treated as a real user (Issue #1265,
// Scheduler-Härtung/Defense-in-Depth). Consolidates the substring
// heuristic that previously lived duplicated in internal/mail/sender.go
// (IsTestUser) — single source of truth for Go, mirroring the Python
// predicate is_test_user_id() (src/app/config.py:30): "test"/"tdd"
// substring match (case-insensitive) or the fixed E2E fixture user
// "tg-live-e2e" (case-insensitive — Adversary-Finding F002 Fix-Loop 1:
// vorher verglich dieser Zweig gegen die UN-lowercased Originalvariable).
//
// Known Limitation: unlike the Python predicate, this does NOT read the
// user's profile flag (user.json: is_test_user=true) — that check needs
// filesystem access to the data root, which callers of this predicate
// (mail dispatch, scheduler skip-path) do not have cheaply available.
// The namensbasierte Erkennung deckt die vollständige Positivliste aus
// Issue #1265 ab.
func IsTestUserID(userID string) bool {
	return IsTestUserIDSubstringOnly(userID) || strings.ToLower(userID) == fixedTestFixtureUserID
}
