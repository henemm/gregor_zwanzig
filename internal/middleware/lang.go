package middleware

import (
	"log"
	"net/http"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// LangCookieMaxAgeSeconds: ein Jahr (Issue #2646, ADR-0104).
const LangCookieMaxAgeSeconds = 31536000

// UserLoader ist der Ausschnitt des Stores, den die Sprach-Middleware braucht.
type UserLoader interface {
	LoadUser(id string) (*model.User, error)
}

var _ UserLoader = (*store.Store)(nil)

// Lang bestimmt die Sprache einmal je Anfrage und legt sie in den Kontext
// (Issue #2675, ADR-0104). Laeuft NACH AuthMiddleware: geladen wird
// ausschliesslich der Nutzer aus dem Auth-Kontext, ohne Kennung nichts (nie
// ein Fallback "default"). Ein Ladefehler bricht die Anfrage nicht ab, dann
// gelten Cookie und Accept-Language.
func Lang(users UserLoader) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			var user *model.User
			if uid := UserIDFromContext(r.Context()); uid != "" {
				u, err := users.LoadUser(uid)
				if err != nil {
					log.Printf("lang: Profil von %q nicht lesbar, Sprache aus Cookie/Header: %v", uid, err)
				} else {
					user = u
				}
			}
			ctx := i18n.WithLang(r.Context(), i18n.FromRequest(r, user))
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// SetLangCookie setzt gz_lang (Issue #2646/#2675). Nicht HttpOnly: der
// Frontend-Server liest es; Secure wie beim Session-Cookie.
func SetLangCookie(w http.ResponseWriter, r *http.Request, lang i18n.Lang, publicHost string) {
	http.SetCookie(w, &http.Cookie{
		Name:     i18n.CookieName,
		Value:    string(lang),
		Path:     "/",
		MaxAge:   LangCookieMaxAgeSeconds,
		SameSite: http.SameSiteLaxMode,
		Secure:   CookieSecure(r, publicHost),
	})
}
