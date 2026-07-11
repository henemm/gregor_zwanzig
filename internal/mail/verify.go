package mail

import (
	"fmt"
	"net/url"
)

// BuildVerificationMail produces an e-mail-confirmation Mail with a clickable
// link pointing to publicHost (Issue #1219 Scheibe 2a-i). Analog zu
// BuildResetMail, aber mit eigenem Linkpfad und 24h-Gueltigkeitshinweis. Der
// Link zeigt auf eine Frontend-Route, die erst in Scheibe 2b existiert — 2a-i
// liefert nur den Link (siehe Spec "Known Limitations").
func BuildVerificationMail(publicHost, userID, token string) Mail {
	link := publicHost + "/verify-email?user=" + url.QueryEscape(userID) + "&token=" + url.QueryEscape(token)
	plain := fmt.Sprintf(
		"Hallo,\n\nBitte bestaetige deine neue E-Mail-Adresse fuer Gregor 20.\n\n"+
			"Oeffne diesen Link, um die Bestaetigung abzuschliessen (gueltig 24 Stunden):\n\n%s\n\n"+
			"Falls du das nicht angefordert hast, ignoriere diese E-Mail.\n",
		link,
	)
	html := fmt.Sprintf(
		`<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`+
			`<p>Hallo,</p>`+
			`<p>Bitte best&auml;tige deine neue E-Mail-Adresse f&uuml;r Gregor 20.</p>`+
			`<p><a href="%s" style="display:inline-block;padding:10px 20px;background:#0a7;color:#fff;text-decoration:none;border-radius:4px">E-Mail best&auml;tigen</a></p>`+
			`<p>Der Link ist 24 Stunden g&uuml;ltig.</p>`+
			`<p style="color:#888;font-size:0.85em">Oder kopiere diesen Link in den Browser:<br><code>%s</code></p>`+
			`<p style="color:#888;font-size:0.85em">Falls du das nicht angefordert hast, ignoriere diese E-Mail.</p>`+
			`</body></html>`,
		link, link,
	)
	return Mail{
		Subject:   "Bestätige deine E-Mail-Adresse für Gregor 20",
		PlainBody: plain,
		HTMLBody:  html,
	}
}
