package mail

import "github.com/henemm/gregor-api/internal/i18n"

// BuildMagicLinkMail constructs the OTP e-mail (subject + plaintext + HTML)
// for the magic-link login flow in lang (Issue #2678). The 6-digit code is
// rendered prominently in both bodies; expiry is 15 minutes by spec.
func BuildMagicLinkMail(lang i18n.Lang, code string) Mail {
	t := texte(lang, "magic")
	plain := t("plain.z1") + "\n\n" + i18n.T(lang, "mail.magic.plain.z2", i18n.Args{"code": code}) + "\n\n" +
		t("plain.z3") + "\n" + t("plain.z4") + "\n\n" + t("plain.z5") + "\n"
	html := htmlKopf +
		"<p>" + t("html.z1") + "</p>" +
		"<p>" + i18n.T(lang, "mail.magic.html.z2", i18n.Args{"betont": "<strong>Gregor 20</strong>"}) + "</p>" +
		htmlCode + code + "</p>" +
		"<p>" + i18n.T(lang, "mail.magic.html.z3", i18n.Args{"dauer": "<strong>" + t("html.dauer") + "</strong>"}) + "</p>" +
		htmlKlein + t("html.z4") + "</p>" +
		htmlFuss
	return Mail{Subject: t("betreff"), PlainBody: plain, HTMLBody: html, Lang: i18n.Parse(string(lang))}
}
