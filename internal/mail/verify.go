package mail

import (
	"net/url"

	"github.com/henemm/gregor-api/internal/i18n"
)

// Tag-Geruest der Konto-Mails; der Satztext kommt aus dem Katalog mail.*
// (Issue #2678, ADR-0104). Tags stehen nie im Katalog.
const (
	htmlKopf      = `<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`
	htmlFuss      = `</body></html>`
	htmlKnopfAuf  = `<p><a href="`
	htmlKnopfStil = `" style="display:inline-block;padding:10px 20px;background:#0a7;color:#fff;text-decoration:none;border-radius:4px">`
	htmlKlein     = `<p style="color:#888;font-size:0.85em">`
	htmlCode      = `<p style="font-size:2em;font-weight:bold;letter-spacing:0.2em;font-family:monospace">`
)

// texte liefert eine Lese-Funktion fuer mail.<art>.<k> in lang.
func texte(lang i18n.Lang, art string) func(k string) string {
	return func(k string) string { return i18n.T(lang, "mail."+art+"."+k, nil) }
}

// buildLinkMail baut verify und reset (gleicher Aufbau: Gruss, Satz, Link,
// Fusszeile; HTML mit Knopf, Gueltigkeit und Kopierhinweis).
func buildLinkMail(lang i18n.Lang, art, link string) Mail {
	t := texte(lang, art)
	plain := t("plain.z1") + "\n\n" + t("plain.z2") + "\n\n" + t("plain.z3") + "\n\n" + link + "\n\n" + t("plain.z4") + "\n"
	html := htmlKopf +
		"<p>" + t("html.z1") + "</p>" +
		"<p>" + t("html.z2") + "</p>" +
		htmlKnopfAuf + link + htmlKnopfStil + t("html.z3") + "</a></p>" +
		"<p>" + t("html.z4") + "</p>" +
		htmlKlein + t("html.z5") + "<br><code>" + link + "</code></p>" +
		htmlKlein + t("html.z6") + "</p>" +
		htmlFuss
	return Mail{Subject: t("betreff"), PlainBody: plain, HTMLBody: html, Lang: i18n.Parse(string(lang))}
}

// BuildVerificationMail produces an e-mail-confirmation Mail with a clickable
// link pointing to publicHost (Issue #1219 Scheibe 2a-i), in der Sprache des
// Empfaengers (Issue #2678). Analog zu BuildResetMail, aber mit eigenem
// Linkpfad und 24h-Gueltigkeitshinweis.
func BuildVerificationMail(lang i18n.Lang, publicHost, userID, token string) Mail {
	link := publicHost + "/verify-email?user=" + url.QueryEscape(userID) + "&token=" + url.QueryEscape(token)
	return buildLinkMail(lang, "verify", link)
}
