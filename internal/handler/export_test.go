package handler

import "github.com/henemm/gregor-api/internal/mail"

// ResetOTPStoreForTest empties the package-level otpStore used by the
// magic-link handlers. Tests call this via t.Cleanup to keep their state
// isolated. Lives in *_test.go so it is not part of the production binary.
func ResetOTPStoreForTest() {
	otpStore.Range(func(k, _ any) bool {
		otpStore.Delete(k)
		return true
	})
}

// ObserveVerificationMailForTest reicht die bestehende Versand-Naht
// `sendVerificationMailFn` (auth.go) an das EXTERNE Testpaket `handler_test`
// weiter und gibt die Wiederherstellungsfunktion zurück (Aufruf per defer).
// Issue #2304, AC-7.
//
// Warum die Brücke nötig ist: die Nachweise zum Resend-Endpoint (AC-7/AC-8)
// und zum Staging-Testweg (AC-9..AC-12) laufen gegen den ECHTEN, vollständig
// verdrahteten Router — nur dort sind Routen-Registrierung, Rate-Limiter und
// die Anmeldepflicht der Middleware mit im Bild. Ein Test in `package handler`
// kann `internal/router` nicht importieren (Import-Zyklus), ein Test in
// `package handler_test` kommt umgekehrt nicht an die paketprivate Naht. Go
// bindet beide Testpakete in EINE Testbinärdatei, ein hier exportierter
// Bezeichner ist dort also sichtbar (stdlib-Muster export_test.go).
//
// Kein Mock: rec beobachtet den echten Aufrufpunkt mit echtem Empfänger und
// echter, fertig gerenderter Mail — nur der SMTP-Dial entfällt.
func ObserveVerificationMailForTest(rec func(cfg mail.MailConfig, to string, msg mail.Mail) error) func() {
	orig := sendVerificationMailFn
	sendVerificationMailFn = rec
	return func() { sendVerificationMailFn = orig }
}
