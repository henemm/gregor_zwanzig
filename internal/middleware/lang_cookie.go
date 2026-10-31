package middleware

import "net/http"

// LangCookieMaxAgeSeconds: ein Jahr (Issue #2646, ADR-0104).
const LangCookieMaxAgeSeconds = 31536000

// SetLangCookie setzt gz_lang auf die Nutzersprache (Issue #2646). Nicht
// HttpOnly: der Frontend-Server liest es; Secure wie beim Session-Cookie.
func SetLangCookie(w http.ResponseWriter, r *http.Request, lang, publicHost string) {
	http.SetCookie(w, &http.Cookie{
		Name:     "gz_lang",
		Value:    lang,
		Path:     "/",
		MaxAge:   LangCookieMaxAgeSeconds,
		SameSite: http.SameSiteLaxMode,
		Secure:   CookieSecure(r, publicHost),
	})
}
