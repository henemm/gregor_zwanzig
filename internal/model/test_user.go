package model

import "strings"

// fixedTestFixtureUserID is the Telegram-E2E-Fixture-Konto — immer als
// Testkonto behandelt, auch ohne gesetztes Profilfeld (Issue #1013).
const fixedTestFixtureUserID = "tg-live-e2e"

// IsTestAccount reports whether u is a synthetic test account that must never
// be treated as a real user (Issue #2152, ADR-0072): entscheidend ist
// AUSSCHLIESSLICH das persistierte Profilfeld is_test_user ODER die feste
// Fixture-ID tg-live-e2e (case-insensitive). Die fruehere "test"/"tdd"-
// Namens-Heuristik (IsTestUserID, Issue #1265) ist bewusst ERSATZLOS
// entfallen — sie traf echte Nutzer ("protester") und verfehlte echte
// Testkonten mit neutralem Namen ("admin"). Kein Fallback auf den Namen,
// wenn das Feld fehlt: genau das wuerde den False Positive erhalten.
// Spiegelt das Python-Praedikat is_test_user_id() (src/app/config.py).
// nil-sicher: ein nicht geladenes Profil ist kein Testkonto.
func IsTestAccount(u *User) bool {
	return u != nil && (u.IsTestUser || strings.EqualFold(u.ID, fixedTestFixtureUserID))
}
