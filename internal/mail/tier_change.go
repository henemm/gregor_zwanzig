package mail

import (
	"fmt"
	"html"
	"time"
)

// BuildTierChangeRequestMail produces the PO notification mail for a user's
// tier-change request (Issue #1071). Purely informational — no approval link,
// no interactive element. The PO grants the change manually by editing the
// user's tier field. German texts, Plain+HTML, analog reset.go.
func BuildTierChangeRequestMail(username, currentTier, requestedTier string) Mail {
	ts := time.Now().Format("02.01.2006 15:04")
	subject := fmt.Sprintf("Gregor 20 — Level-Wechsel-Antrag von %s", username)
	plain := fmt.Sprintf(
		"Ein Nutzer hat einen Level-Wechsel beantragt.\n\n"+
			"Nutzer: %s\n"+
			"Aktuelles Level: %s\n"+
			"Gewuenschtes Level: %s\n"+
			"Beantragt am: %s\n\n"+
			"Zum Freigeben in der user.json dieses Nutzers BEIDE Schritte ausfuehren:\n"+
			"1. das Feld tier manuell auf das gewuenschte Level setzen\n"+
			"2. das Feld requested_tier entfernen (loeschen)\n\n"+
			"Bleibt requested_tier stehen, gilt der Antrag weiterhin als offen.\n",
		username, currentTier, requestedTier, ts,
	)
	htmlBody := fmt.Sprintf(
		`<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`+
			`<p>Ein Nutzer hat einen Level-Wechsel beantragt.</p>`+
			`<table style="border-collapse:collapse">`+
			`<tr><td style="padding:2px 12px 2px 0"><b>Nutzer</b></td><td>%s</td></tr>`+
			`<tr><td style="padding:2px 12px 2px 0"><b>Aktuelles Level</b></td><td>%s</td></tr>`+
			`<tr><td style="padding:2px 12px 2px 0"><b>Gew&uuml;nschtes Level</b></td><td>%s</td></tr>`+
			`<tr><td style="padding:2px 12px 2px 0"><b>Beantragt am</b></td><td>%s</td></tr>`+
			`</table>`+
			`<p style="color:#888;font-size:0.85em">Zum Freigeben in der user.json dieses Nutzers <b>beide</b> Schritte ausf&uuml;hren: `+
			`1. das Feld <code>tier</code> manuell auf das gew&uuml;nschte Level setzen, `+
			`2. das Feld <code>requested_tier</code> entfernen (l&ouml;schen). `+
			`Bleibt <code>requested_tier</code> stehen, gilt der Antrag weiterhin als offen.</p>`+
			`</body></html>`,
		html.EscapeString(username), html.EscapeString(currentTier),
		html.EscapeString(requestedTier), ts,
	)
	return Mail{
		Subject:   subject,
		PlainBody: plain,
		HTMLBody:  htmlBody,
	}
}
