package mail

import "fmt"

// BuildMagicLinkMail constructs the OTP e-mail (subject + plaintext + HTML)
// for the magic-link login flow. The 6-digit code is rendered prominently
// in both bodies; expiry is 15 minutes by spec.
func BuildMagicLinkMail(code string) Mail {
	plain := fmt.Sprintf(
		"Hallo,\n\nDein Einmalcode für Gregor 20: %s\n\nDer Code ist 15 Minuten gültig.\nGib ihn auf der Anmeldeseite ein.\n\nFalls du diesen Code nicht angefordert hast, ignoriere diese E-Mail.\n",
		code,
	)
	html := fmt.Sprintf(
		`<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`+
			`<p>Hallo,</p>`+
			`<p>Dein Einmalcode f&uuml;r <strong>Gregor 20</strong>:</p>`+
			`<p style="font-size:2em;font-weight:bold;letter-spacing:0.2em;font-family:monospace">%s</p>`+
			`<p>Der Code ist <strong>15 Minuten</strong> g&uuml;ltig.</p>`+
			`<p style="color:#888;font-size:0.85em">Falls du diesen Code nicht angefordert hast, ignoriere diese E-Mail.</p>`+
			`</body></html>`,
		code,
	)
	return Mail{
		Subject:   "Gregor 20 — Dein Einmalcode",
		PlainBody: plain,
		HTMLBody:  html,
	}
}
