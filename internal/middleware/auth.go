package middleware

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// SessionMaxAgeSeconds ist die Lebensdauer des Anmelde-Cookies (Issue #2129).
// 400 Tage: die Anmeldung gilt unbefristet, bis sie widerrufen wird, aber
// Browser deckeln persistente Cookies inzwischen bei 400 Tagen -- ein hoeherer
// Wert waere eine Zusage, die der Browser ohnehin nicht einloest.
const SessionMaxAgeSeconds = 400 * 24 * 60 * 60

type contextKey string

const userIDContextKey contextKey = "userId"

// SessionStore ist der Ausschnitt des Stores, den die Pruefstelle braucht.
// Als Schnittstelle, damit die Middleware nicht am ganzen Store haengt.
type SessionStore interface {
	HasSession(userId, sessionId string) (bool, error)
}

var _ SessionStore = (*store.Store)(nil)

func AuthMiddleware(secret string, sessions SessionStore) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path == "/api/health" || r.URL.Path == "/api/scheduler/status" ||
				r.URL.Path == "/api/auth/register" || r.URL.Path == "/api/auth/login" ||
				r.URL.Path == "/api/auth/logout" ||
				r.URL.Path == "/api/auth/forgot-password" || r.URL.Path == "/api/auth/reset-password" ||
				r.URL.Path == "/api/auth/verify-email" ||
				// Issue #2304: exakter Pfad. Der Eintrag darueber ist ein
				// Gleichheitsvergleich und deckt diesen Unterpfad nicht mit
				// ab; der staging-only Testweg unter demselben Praefix bleibt
				// bewusst anmeldepflichtig und steht deshalb NICHT hier.
				r.URL.Path == "/api/auth/verify-email/resend" ||
				r.URL.Path == "/api/auth/google/init" || r.URL.Path == "/api/auth/google/callback" ||
				r.URL.Path == "/api/auth/magic-link" || r.URL.Path == "/api/auth/magic-link/verify" ||
				r.URL.Path == "/api/auth/passkey/login/begin" || r.URL.Path == "/api/auth/passkey/login/finish" ||
				r.URL.Path == "/api/auth/passkey/register/public/begin" ||
				r.URL.Path == "/api/auth/passkey/register/public/finish" ||
				r.URL.Path == "/api/auth/passkey/discoverable/begin" || r.URL.Path == "/api/auth/passkey/discoverable/finish" ||
				strings.HasPrefix(r.URL.Path, "/api/internal/") ||
				strings.HasPrefix(r.URL.Path, "/api/webhooks/telegram/") ||
				strings.HasPrefix(r.URL.Path, "/api/debug/") {
				next.ServeHTTP(w, r)
				return
			}

			cookie, err := r.Cookie("gz_session")
			if err != nil {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			}

			userId, sessionId, _, ok := validateSession(cookie.Value, secret)
			if !ok {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			}

			// Die einzige Gueltigkeitsfrage: steht die Anmelde-Kennung noch auf
			// der Gaesteliste? Kein Zwischenspeicher -- ein zweiter
			// Zustandsbehaelter muesste genau die Widerrufs-Zusicherung tragen,
			// auf der die unbefristete Anmeldung beruht.
			listed, lookupErr := sessions.HasSession(userId, sessionId)
			if lookupErr != nil || !listed {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			}

			ctx := context.WithValue(r.Context(), userIDContextKey, userId)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func UserIDFromContext(ctx context.Context) string {
	uid, _ := ctx.Value(userIDContextKey).(string)
	return uid
}

// NewSessionID erzeugt eine Anmelde-Kennung: 16 Zufallsbytes hex.
func NewSessionID() (string, error) {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}

// SignSessionWithID erzeugt das vierteilige Anmelde-Merkmal.
// Format: {userId}.{sessionId}.{timestamp}.{hmacSig}, signiert ueber
// "{userId}:{sessionId}:{timestamp}".
//
// Der Zeitstempel bleibt erhalten, obwohl er fuer die Gueltigkeit nicht mehr
// gebraucht wird: er ist der Anhaltspunkt fuer eine spaetere
// Geraeteuebersicht.
func SignSessionWithID(userId, sessionId, secret string) string {
	ts := time.Now().Unix()
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%s:%d", userId, sessionId, ts)))
	sig := hex.EncodeToString(mac.Sum(nil))
	return fmt.Sprintf("%s.%s.%d.%s", userId, sessionId, ts, sig)
}

// SetSessionCookie setzt das Anmelde-Cookie. EINE Stelle fuer alle
// Ausstellungswege -- vorher stand derselbe Block sechsmal im Code, und genau
// so entsteht Drift zwischen den Wegen.
func SetSessionCookie(w http.ResponseWriter, r *http.Request, token string) {
	http.SetCookie(w, &http.Cookie{
		Name:     "gz_session",
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   SessionMaxAgeSeconds,
		Secure:   r.Header.Get("X-Forwarded-Proto") == "https" || r.TLS != nil,
	})
}

// ClearSessionCookie loescht das Anmelde-Cookie im Browser.
func ClearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     "gz_session",
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		MaxAge:   -1,
	})
}

// ContextWithUserID returns a new context with the given userId set.
// Used by AuthMiddleware internally and by tests to simulate authenticated requests.
func ContextWithUserID(ctx context.Context, userId string) context.Context {
	return context.WithValue(ctx, userIDContextKey, userId)
}

// validateSession zerlegt und prueft ein Anmelde-Merkmal.
// Liefert (Nutzerkennung, Anmelde-Kennung, Ausstellungszeit, gueltig).
//
// Zerlegt wird VON RECHTS: die letzten drei Segmente sind
// Kennung/Zeitstempel/Signatur, alles davor ist die Nutzerkennung. Sonst
// zerfiele eine Kennung mit Punkt ("alice.smith") in zwei Teile und wuerde
// abgewiesen -- die Frontend-Pruefstelle macht es seit #425 richtig, die
// Go-Seite wurde nie nachgezogen.
func validateSession(value, secret string) (string, string, int64, bool) {
	parts := strings.Split(value, ".")
	if len(parts) < 4 {
		return "", "", 0, false
	}

	n := len(parts)
	userId := strings.Join(parts[:n-3], ".")
	sessionId, tsStr, sig := parts[n-3], parts[n-2], parts[n-1]
	if userId == "" || sessionId == "" || tsStr == "" || sig == "" {
		return "", "", 0, false
	}
	ts, err := strconv.ParseInt(tsStr, 10, 64)
	if err != nil {
		return "", "", 0, false
	}
	expected := signatureFor(fmt.Sprintf("%s:%s:%d", userId, sessionId, ts), secret)
	if !hmac.Equal([]byte(sig), []byte(expected)) {
		return "", "", 0, false
	}
	// Kein Ablauf: die Gaesteliste traegt die Gueltigkeit.
	return userId, sessionId, ts, true
}

func signatureFor(payload, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

// SessionFromCookie zerlegt ein Anmelde-Merkmal fuer Aufrufer ausserhalb der
// Middleware (Abmelden laeuft ueber einen oeffentlichen Pfad und hat deshalb
// keinen Auth-Kontext, aus dem es die Nutzerkennung nehmen koennte).
func SessionFromCookie(value, secret string) (userId, sessionId string, ok bool) {
	uid, sid, _, valid := validateSession(value, secret)
	return uid, sid, valid
}
