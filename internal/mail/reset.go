package mail

import (
	"fmt"
	"net/url"
)

// BuildResetMail produces a password-reset Mail with a clickable link pointing
// to publicHost. Mirrors the spec wording (no localisation pass yet — German
// short, plus the link). Query parameters are URL-escaped to defend against
// usernames/tokens containing reserved characters (&, =, +, /, ...).
// Note: we build the query string manually (not via url.Values.Encode) to keep
// the deterministic "user, then token" parameter order from the original spec.
func BuildResetMail(publicHost, username, token string) Mail {
	link := publicHost + "/reset-password?user=" + url.QueryEscape(username) + "&token=" + url.QueryEscape(token)
	plain := fmt.Sprintf(
		"Hallo,\n\nDu hast eine Passwort-Zuruecksetzung fuer Gregor 20 angefordert.\n\n"+
			"Oeffne diesen Link, um ein neues Passwort zu setzen (gueltig 30 Minuten):\n\n%s\n\n"+
			"Falls du das nicht angefordert hast, ignoriere diese E-Mail.\n",
		link,
	)
	html := fmt.Sprintf(
		`<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`+
			`<p>Hallo,</p>`+
			`<p>Du hast eine Passwort-Zur&uuml;cksetzung f&uuml;r Gregor 20 angefordert.</p>`+
			`<p><a href="%s" style="display:inline-block;padding:10px 20px;background:#0a7;color:#fff;text-decoration:none;border-radius:4px">Neues Passwort setzen</a></p>`+
			`<p>Der Link ist 30 Minuten g&uuml;ltig.</p>`+
			`<p style="color:#888;font-size:0.85em">Oder kopiere diesen Link in den Browser:<br><code>%s</code></p>`+
			`<p style="color:#888;font-size:0.85em">Falls du das nicht angefordert hast, ignoriere diese E-Mail.</p>`+
			`</body></html>`,
		link, link,
	)
	return Mail{
		Subject:   "Gregor 20 — Passwort zuruecksetzen",
		PlainBody: plain,
		HTMLBody:  html,
	}
}
