package middleware

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
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

// legacyMaxAgeSeconds ist die Ablauffrist, die fuer das ALTE dreiteilige
// Merkmal scharf bleibt. Damit verschwindet der Altbestand binnen 24 Stunden
// nach dem Deploy von selbst und der Legacy-Zweig kann spaeter ersatzlos
// entfallen. Fuer das neue Format gibt es keine Frist -- dort traegt die
// Gaesteliste die Gueltigkeit.
const legacyMaxAgeSeconds = 86400

type contextKey string

const userIDContextKey contextKey = "userId"

// SessionStore ist der Ausschnitt des Stores, den die Pruefstelle braucht.
// Als Schnittstelle, damit die Middleware nicht am ganzen Store haengt.
type SessionStore interface {
	HasSession(userId, sessionId string) (bool, error)
	AddSession(userId, sessionId string) error
	LegacyRevokedAt(userId string) (*time.Time, error)
	UserExists(userId string) bool
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

			userId, sessionId, issuedAt, isNew, ok := validateSession(cookie.Value, secret)
			if !ok {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			}

			if isNew {
				// Die einzige Gueltigkeitsfrage beim neuen Format: steht die
				// Anmelde-Kennung noch auf der Gaesteliste? Kein
				// Zwischenspeicher -- ein zweiter Zustandsbehaelter muesste
				// genau die Widerrufs-Zusicherung tragen, auf der die
				// unbefristete Anmeldung beruht.
				listed, lookupErr := sessions.HasSession(userId, sessionId)
				if lookupErr != nil || !listed {
					http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
					return
				}
			} else if !legacySessionValid(sessions, userId, issuedAt) {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			} else {
				upgradeLegacySession(w, r, sessions, secret, userId)
			}

			ctx := context.WithValue(r.Context(), userIDContextKey, userId)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// legacySessionValid beantwortet die beiden Fragen, die HMAC und Ablauffrist
// beim Altformat NICHT beantworten (Issue #2129):
//
//  1. Existiert das Konto ueberhaupt noch? Ein Alt-Merkmal traegt keine
//     Anmelde-Kennung, die man gegen eine Liste halten koennte — nach einer
//     Kontoloeschung wuerde es sonst weiter durchgehen und die Hebung wuerde
//     den geloeschten Nutzerordner sogar neu anlegen.
//  2. Wurde seit der Ausstellung abgemeldet? Ohne diesen Vermerk gaebe es beim
//     Abmelden mit einem Alt-Merkmal nichts zu widerrufen.
//
// Gleichstand zaehlt als widerrufen (Sekundenaufloesung): ein Merkmal aus
// derselben Sekunde wie der Widerruf darf nicht ueberleben.
func legacySessionValid(sessions SessionStore, userId string, issuedAt int64) bool {
	if !sessions.UserExists(userId) {
		return false
	}
	revokedAt, err := sessions.LegacyRevokedAt(userId)
	if err != nil {
		log.Printf("legacy session check: revocation lookup failed for %s: %v", userId, err)
		return false
	}
	if revokedAt != nil && issuedAt <= revokedAt.Unix() {
		return false
	}
	return true
}

// upgradeLegacySession hebt ein gueltiges Alt-Merkmal still auf das neue
// Format: neue Anmelde-Kennung, Eintrag in die Gaesteliste, neues Cookie im
// Antwort-Header. Niemand muss sich durch das Deploy neu anmelden.
//
// Schlaegt das Anlegen fehl, bleibt es beim Alt-Merkmal: es ist ja gueltig,
// und den Nutzer wegen eines voruebergehenden Schreibfehlers hinauszuwerfen
// waere die schlechtere Antwort. Beim naechsten Aufruf wird erneut versucht.
func upgradeLegacySession(w http.ResponseWriter, r *http.Request, sessions SessionStore, secret, userId string) {
	sessionId, err := NewSessionID()
	if err != nil {
		log.Printf("session upgrade: id generation failed for %s: %v", userId, err)
		return
	}
	if err := sessions.AddSession(userId, sessionId); err != nil {
		log.Printf("session upgrade: allowlist write failed for %s: %v", userId, err)
		return
	}
	SetSessionCookie(w, r, SignSessionWithID(userId, sessionId, secret))
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

// SignSession erzeugt ein Anmelde-Merkmal im ALTEN dreiteiligen Format.
// Format: {userId}.{timestamp}.{hmacSig}
//
// Bleibt fuer den Uebergang bestehen (Bestandstests, Alt-Cookies), wird von
// den Ausstellungsstellen aber nicht mehr benutzt -- die minten ueber
// SignSessionWithID.
func SignSession(userId, secret string) string {
	ts := time.Now().Unix()
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%d", userId, ts)))
	sig := hex.EncodeToString(mac.Sum(nil))
	return fmt.Sprintf("%s.%d.%s", userId, ts, sig)
}

// SignSessionWithID erzeugt das NEUE vierteilige Anmelde-Merkmal.
// Format: {userId}.{sessionId}.{timestamp}.{hmacSig}, signiert ueber
// "{userId}:{sessionId}:{timestamp}".
//
// Der Zeitstempel bleibt erhalten, obwohl er fuer die Gueltigkeit nicht mehr
// gebraucht wird: er haelt die beiden Formate auseinander und ist der
// Anhaltspunkt fuer eine spaetere Geraeteuebersicht.
func SignSessionWithID(userId, sessionId, secret string) string {
	ts := time.Now().Unix()
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%s:%d", userId, sessionId, ts)))
	sig := hex.EncodeToString(mac.Sum(nil))
	return fmt.Sprintf("%s.%s.%d.%s", userId, sessionId, ts, sig)
}

// SetSessionCookie setzt das Anmelde-Cookie. EINE Stelle fuer alle sechs
// Ausstellungswege und die Legacy-Hebung -- vorher stand derselbe Block
// sechsmal im Code, und genau so entsteht Drift zwischen den Wegen.
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
// Liefert (Nutzerkennung, Anmelde-Kennung, Ausstellungszeit, neuesFormat, gueltig).
//
// BEIDE Formate werden VON RECHTS zerlegt: die letzten Segmente sind
// Kennung/Zeitstempel/Signatur, alles davor ist die Nutzerkennung. Sonst
// zerfiele eine Kennung mit Punkt ("alice.smith") in zwei Teile und wuerde
// abgewiesen -- die Frontend-Pruefstelle macht es seit #425 richtig, die
// Go-Seite wurde nie nachgezogen.
//
// Die Segmentzahl allein unterscheidet die Formate NICHT eindeutig: ein
// Alt-Merkmal fuer "alice.smith" hat ebenfalls vier Segmente. Entschieden wird
// darum ueber die Signatur -- erst das neue Format versuchen, dann das alte.
// Beides sind HMAC-Vergleiche, die Reihenfolge kostet nichts.
func validateSession(value, secret string) (string, string, int64, bool, bool) {
	parts := strings.Split(value, ".")

	if len(parts) >= 4 {
		n := len(parts)
		userId := strings.Join(parts[:n-3], ".")
		sessionId, tsStr, sig := parts[n-3], parts[n-2], parts[n-1]
		if userId != "" && sessionId != "" && tsStr != "" && sig != "" {
			if ts, err := strconv.ParseInt(tsStr, 10, 64); err == nil {
				expected := signatureFor(fmt.Sprintf("%s:%s:%d", userId, sessionId, ts), secret)
				if hmac.Equal([]byte(sig), []byte(expected)) {
					// Kein Ablauf: die Gaesteliste traegt die Gueltigkeit.
					return userId, sessionId, ts, true, true
				}
			}
		}
	}

	if len(parts) >= 3 {
		n := len(parts)
		userId := strings.Join(parts[:n-2], ".")
		tsStr, sig := parts[n-2], parts[n-1]
		if userId == "" || tsStr == "" || sig == "" {
			return "", "", 0, false, false
		}
		ts, err := strconv.ParseInt(tsStr, 10, 64)
		if err != nil {
			return "", "", 0, false, false
		}
		if time.Now().Unix()-ts > legacyMaxAgeSeconds {
			return "", "", 0, false, false
		}
		expected := signatureFor(fmt.Sprintf("%s:%d", userId, ts), secret)
		if hmac.Equal([]byte(sig), []byte(expected)) {
			return userId, "", ts, false, true
		}
	}

	return "", "", 0, false, false
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
	uid, sid, _, _, valid := validateSession(value, secret)
	return uid, sid, valid
}
