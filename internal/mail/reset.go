package mail

import (
	"net/url"

	"github.com/henemm/gregor-api/internal/i18n"
)

// BuildResetMail produces a password-reset Mail with a clickable link pointing
// to publicHost, in der Sprache des Empfaengers (Issue #2678). Query
// parameters are URL-escaped to defend against usernames/tokens containing
// reserved characters (&, =, +, /, ...).
// Note: we build the query string manually (not via url.Values.Encode) to keep
// the deterministic "user, then token" parameter order from the original spec.
func BuildResetMail(lang i18n.Lang, publicHost, username, token string) Mail {
	link := publicHost + "/reset-password?user=" + url.QueryEscape(username) + "&token=" + url.QueryEscape(token)
	return buildLinkMail(lang, "reset", link)
}
