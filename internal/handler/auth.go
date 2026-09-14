package handler

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sort"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type authRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Email    string `json:"email"`
}

func RegisterHandler(s *store.Store, bcryptCost int, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req authRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if len(req.Username) < 3 || len(req.Username) > 50 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}
		if !validUsernameRe.MatchString(req.Username) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}
		if len(req.Password) < 8 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}
		// Issue #1517: Existenzprüfung wandert VOR die E-Mail-Pflichtprüfung —
		// ein Register-Aufruf ohne email gegen einen bereits existierenden User
		// muss 409 liefern, nicht fälschlich 400 (bricht sonst
		// scripts/setup-validator-user.sh, das nie ein email-Feld sendet).
		if s.UserExists(req.Username) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(409)
			w.Write([]byte(`{"error":"user already exists"}`))
			return
		}

		// Issue #1226: E-Mail ist ab jetzt Pflichtfeld — nur mit gesetzter,
		// formal gültiger Adresse kann der Verifikations-Dispatch (Double-Opt-In)
		// überhaupt greifen. Leeres Feld → generischer "validation failed"; Feld
		// ohne "@" → eigener Fehlercode "invalid_email", damit das Frontend gezielt
		// mappen kann. Formatprüfung minimal (strings.Contains) — Precedent aus
		// PasskeyRegisterPublicBeginHandler.
		if req.Email == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}
		if !strings.Contains(req.Email, "@") {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid_email"}`))
			return
		}

		hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcryptCost)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		// Issue #2147 Scheibe B1: Adress-Eindeutigkeit unter Lock — zwei
		// gleichzeitige Registrierungen (oder Registrierung/Profil-Update) auf
		// dieselbe Adresse duerfen zusammen nur genau ein Konto ergeben (AC-13).
		normalizedEmail := store.NormalizeEmailAddress(req.Email)
		unlock := store.LockEmailAddress(normalizedEmail)
		defer unlock()

		taken, err := s.IsAddressTakenByOtherAccount(normalizedEmail, "")
		if err != nil {
			log.Printf("register: address uniqueness check failed: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}
		if taken {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(409)
			w.Write([]byte(`{"error":"email_taken"}`))
			return
		}

		user := model.User{
			ID:           req.Username,
			PasswordHash: string(hash),
			Email:        normalizedEmail,
			MailTo:       normalizedEmail,
			CreatedAt:    time.Now(),
		}
		if err := s.SaveUser(user); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		s.ProvisionUserDirs(req.Username)

		// Issue #1226: nach erfolgreicher Persistenz denselben #1219-Verifikations-
		// Trigger auslösen wie UpdateProfileHandler — sonst bliebe EmailVerifiedAt
		// für immer nil und die Adresse dauerhaft von Resend-Versand ausgeschlossen.
		dispatchVerificationMail(s, cfg, req.Username, &user)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(map[string]string{"id": req.Username})
	}
}

// hasVerifiedEmail liest den Bestaetigungsstand IMMER frisch von der Platte
// (Issue #2271). Das ist kein Zierrat: selfHealEmailVerification schreibt per
// SaveUser (auth.go:812) und laesst die Struct des Aufrufers unberuehrt — ein
// Praedikat auf einer mitgereichten model.User saehe den im selben Request
// geheilten Stand nicht und sperrte genau das Konto aus, das sich gerade heilt.
//
// Zweiter Rueckgabewert: false, wenn der Nutzer gar nicht lesbar war. Dann ist
// "nicht bestaetigt" die falsche Aussage — der Aufrufer quittiert mit 500.
func hasVerifiedEmail(s *store.Store, userId string) (verified bool, readable bool) {
	user, err := s.LoadUser(userId)
	if err != nil {
		log.Printf("email verify gate: user.json unreadable for %s: %v", userId, err)
		return false, false
	}
	if user == nil {
		return false, true
	}
	return user.EmailVerifiedAt != nil, true
}

// issueSession ist der Weg fuer ANMELDUNGEN (Issue #2271): erst das
// Bestaetigungs-Gate, dann die Ausstellung. Bewusst OHNE Parameter der
// Aufrufer — ein Flag koennte ein kuenftiger siebter Anmeldeweg vergessen oder
// als Abkuerzung setzen; das Gate liegt deshalb unumgehbar hier.
//
// Liefert false, wenn bereits geantwortet wurde (Gate oder Fehlerfall).
func issueSession(w http.ResponseWriter, r *http.Request, s *store.Store, userId, secret string) bool {
	verified, readable := hasVerifiedEmail(s, userId)
	if !readable {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(500)
		w.Write([]byte(`{"error":"internal error"}`))
		return false
	}
	if !verified {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		w.Write([]byte(`{"error":"email_not_verified"}`))
		return false
	}
	return issueSessionWithoutVerificationGate(w, r, s, userId, secret)
}

// issueSessionWithoutVerificationGate mintet eine Anmelde-Kennung, traegt sie
// in die Gaesteliste des Nutzers ein und setzt das Anmelde-Cookie (Issue
// #2129). EINE Stelle fuer alle Anmeldewege: wird eine davon vergessen, sperrt
// dieser Weg alle seine Nutzer aus, weil ihr Merkmal zwar wohlgeformt, aber
// nicht gelistet waere.
//
// Diese Variante laesst das Bestaetigungs-Gate aus und hat genau EINEN
// legitimen Aufrufer: ChangePasswordHandler (Issue #2271). Wer gerade seine
// E-Mail-Adresse geaendert hat, steht auf EmailVerifiedAt == nil (auth.go:708/713)
// — liefe das Gate dort mit, koennte er sein Passwort nicht mehr aendern und
// verloere im selben Zug seine Sitzung. Der sprechende Name macht die Ausnahme
// sichtbar; ein Parameter an issueSession haette sie unsichtbar gemacht.
//
// Liefert false, wenn bereits geantwortet wurde (Fehlerfall).
func issueSessionWithoutVerificationGate(w http.ResponseWriter, r *http.Request, s *store.Store, userId, secret string) bool {
	sessionId, err := middleware.NewSessionID()
	if err != nil {
		log.Printf("session issue: id generation failed for %s: %v", userId, err)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(500)
		w.Write([]byte(`{"error":"internal error"}`))
		return false
	}
	if err := s.AddSession(userId, sessionId); err != nil {
		log.Printf("session issue: allowlist write failed for %s: %v", userId, err)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(500)
		w.Write([]byte(`{"error":"store_error"}`))
		return false
	}
	middleware.SetSessionCookie(w, r, middleware.SignSessionWithID(userId, sessionId, secret))
	return true
}

func LoginHandler(s *store.Store, secret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req authRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		// Issue #2140: pfadunsichere Kennung wird abgewiesen, BEVOR sie in den
		// Pfadbau geht — und zwar mit exakt der Antwort des "Nutzer unbekannt"-
		// Zweigs unten, damit die Route nicht verraet, welche Kennungen
		// syntaktisch auffallen.
		if !store.ValidUserID(req.Username) {
			log.Printf("login: rejected path-unsafe user id %q", req.Username)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"invalid credentials"}`))
			return
		}

		user, err := s.LoadUser(req.Username)
		if err != nil {
			log.Printf("login: user.json unreadable/corrupt for %s: %v", req.Username, err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"invalid credentials"}`))
			return
		}
		if user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"invalid credentials"}`))
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"invalid credentials"}`))
			return
		}

		if !issueSession(w, r, s, req.Username, secret) {
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"id": req.Username})
	}
}

func DeleteAccountHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		if err := s.DeleteUser(userId); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		// Die Gaesteliste liegt IM Nutzerordner und ist mit DeleteUser bereits
		// verschwunden — jedes Merkmal dieses Kontos ist damit dauerhaft
		// ungueltig, auch nach einem Dienst-Neustart (Issue #2129 AC-16).
		middleware.ClearSessionCookie(w)

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"deleted"}`))
	}
}

func ForgotPasswordHandler(s *store.Store, bcryptCost int, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username string `json:"username"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Username == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		// Always return 200 (no user enumeration)
		w.Header().Set("Content-Type", "application/json")

		// Issue #2140: identischer Antwortpfad wie der "user == nil"-Zweig
		// unten — der Enumerationsschutz dieser Route darf durch die neue
		// Ablehnung keinen unterscheidbaren Fall bekommen.
		if !store.ValidUserID(req.Username) {
			log.Printf("password reset: rejected path-unsafe user id %q", req.Username)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		user, _ := s.LoadUser(req.Username)
		if user == nil {
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		// Generate random token
		tokenBytes := make([]byte, 32)
		if _, err := rand.Read(tokenBytes); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}
		token := hex.EncodeToString(tokenBytes)

		// Hash token for storage
		hash, err := bcrypt.GenerateFromPassword([]byte(token), bcryptCost)
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		resetToken := model.PasswordResetToken{
			TokenHash: string(hash),
			ExpiresAt: time.Now().Add(30 * time.Minute),
		}
		s.SaveResetToken(req.Username, resetToken)

		// --- Mail dispatch (Issue #124) ---
		recipient := user.MailTo
		if recipient == "" {
			recipient = user.Email
		}
		if recipient == "" {
			log.Printf("password reset: no email address for user %s — token written but not sent", req.Username)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		// Select SMTP config: test users → Gmail, normal users → Resend (cfg.SMTP*)
		var mailCfg mail.MailConfig
		if mail.IsTestUser(req.Username) {
			if cfg.GoogleSMTPHost == "" {
				log.Printf("password reset: Google SMTP not configured, mail not sent for test user %s", req.Username)
				w.Write([]byte(`{"status":"ok"}`))
				return
			}
			mailCfg = mail.MailConfig{
				Host: cfg.GoogleSMTPHost, Port: cfg.GoogleSMTPPort,
				User: cfg.GoogleSMTPUser, Pass: cfg.GoogleSMTPPass,
				From: cfg.GoogleSMTPUser,
			}
		} else {
			if cfg.SMTPHost == "" {
				log.Printf("password reset: SMTP not configured, mail not sent for user %s", req.Username)
				w.Write([]byte(`{"status":"ok"}`))
				return
			}
			mailCfg = mail.MailConfig{
				Host: cfg.SMTPHost, Port: cfg.SMTPPort,
				User: cfg.SMTPUser, Pass: cfg.SMTPPass,
				From: cfg.SMTPFrom,
			}
		}

		msg := mail.BuildResetMail(cfg.PublicHost, req.Username, token)

		// Goroutine with timeout — endpoint must not block on SMTP.
		fallbackCfg := mail.MailConfig{
			Host: cfg.FallbackSMTPHost, Port: 587,
			User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass,
		}
		go func(to string, msg mail.Mail, c, fb mail.MailConfig, username string) {
			done := make(chan error, 1)
			go func() { done <- mail.SendWithFallback(c, fb, to, msg) }()
			select {
			case err := <-done:
				if err != nil {
					log.Printf("password reset: mail send failed for %s: %v", username, err)
				}
			case <-time.After(20 * time.Second):
				log.Printf("password reset: mail send timeout (20s) for %s", username)
			}
		}(recipient, msg, mailCfg, fallbackCfg, req.Username)

		w.Write([]byte(`{"status":"ok"}`))
	}
}

func ResetPasswordHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username    string `json:"username"`
			Token       string `json:"token"`
			NewPassword string `json:"new_password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")

		if len(req.NewPassword) < 8 {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}

		// Issue #2140: vor dem ersten Store-Zugriff, Antwort identisch zum
		// "Token fehlt/passt nicht"-Zweig direkt darunter.
		if !store.ValidUserID(req.Username) {
			log.Printf("password reset confirm: rejected path-unsafe user id %q", req.Username)
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		resetToken, err := s.LoadResetToken(req.Username)
		if err != nil || resetToken == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		if time.Now().After(resetToken.ExpiresAt) {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"token expired"}`))
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(resetToken.TokenHash), []byte(req.Token)); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		// Update password
		user, err := s.LoadUser(req.Username)
		if err != nil || user == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		newHash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcryptCost)
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		user.PasswordHash = string(newHash)
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		// Issue #2129 AC-9: Wer sein Passwort zuruecksetzt, WEIL es abgegriffen
		// wurde, muss den Angreifer damit hinauswerfen — also alle Anmeldungen
		// widerrufen, nicht nur das Passwort tauschen.
		if err := s.ClearSessions(req.Username); err != nil {
			log.Printf("password reset: allowlist clear failed for %s: %v", req.Username, err)
		}

		s.DeleteResetToken(req.Username)

		w.Write([]byte(`{"status":"ok"}`))
	}
}

// VerifyEmailHandler — Issue #1219 Scheibe 2a-ii: Einlösung des in Scheibe
// 2a-i erzeugten E-Mail-Bestätigungs-Tokens. Struktureller Zwilling von
// ResetPasswordHandler auf model.EmailVerificationToken. Public (kein
// Auth-Kontext) — Nutzer klickt den Link unangemeldet aus der Mail heraus.
// Der Token wird NUR bei erfolgreicher Verifikation gelöscht.
func VerifyEmailHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			User  string `json:"user"`
			Token string `json:"token"`
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.User == "" || req.Token == "" {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		// Issue #2140: vor dem ersten Store-Zugriff, Antwort identisch zum
		// "Token fehlt/passt nicht"-Zweig direkt darunter.
		if !store.ValidUserID(req.User) {
			log.Printf("email verification: rejected path-unsafe user id %q", req.User)
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		vt, err := s.LoadVerificationToken(req.User)
		if err != nil || vt == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}
		if time.Now().After(vt.ExpiresAt) {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"token expired"}`))
			return
		}
		if err := bcrypt.CompareHashAndPassword([]byte(vt.TokenHash), []byte(req.Token)); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		user, err := s.LoadUser(req.User) // RMW: vollständiges Objekt laden
		if err != nil || user == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}
		now := time.Now().UTC()
		user.EmailVerifiedAt = &now
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		s.DeleteVerificationToken(req.User)

		w.Write([]byte(`{"status":"ok"}`))
	}
}

// LogoutHandler meldet GENAU DIESES Geraet ab: der Eintrag der Anmelde-Kennung
// verlaesst die Gaesteliste des Nutzers. Weil das dateibasiert geschieht, wirkt
// der Widerruf auch nach einem Dienst-Neustart (Issue #2129 AC-4); die
// bisherige prozesslokale Sperrliste ist damit abgeloest.
//
// Der Endpunkt ist oeffentlich (kein Auth-Kontext), die Nutzerkennung kommt
// deshalb aus dem geprueften Merkmal selbst — nie aus einem Standardwert.
func LogoutHandler(s *store.Store, secret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie("gz_session")
		if err == nil && cookie.Value != "" {
			if userId, sessionId, ok := middleware.SessionFromCookie(cookie.Value, secret); ok {
				if sessionId != "" {
					if err := s.RemoveSession(userId, sessionId); err != nil {
						log.Printf("logout: allowlist removal failed for %s: %v", userId, err)
					}
				} else if err := s.RevokeLegacySessions(userId); err != nil {
					// Alt-Merkmal: es steht auf keiner Gaesteliste, es gaebe
					// also nichts zu entfernen. Ohne den Widerrufs-Vermerk
					// bliebe es bis zu 24 Stunden weiter gueltig — die Zusage
					// "Abmelden wirkt" bekommt auch im Uebergangsfenster
					// keine Ausnahme.
					log.Printf("logout: legacy revocation failed for %s: %v", userId, err)
				}
			}
		}

		middleware.ClearSessionCookie(w)

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	}
}

// LogoutAllHandler meldet den Nutzer auf ALLEN Geraeten ab: die Gaesteliste
// wird geleert (Issue #2129 AC-6). Authentifiziert — die Nutzerkennung kommt
// aus dem geprueften Merkmal, nie aus einem Standardwert, sonst waere es ein
// Widerruf auf fremden Konten.
func LogoutAllHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")
		if userId == "" {
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"unauthorized"}`))
			return
		}

		if err := s.ClearSessions(userId); err != nil {
			log.Printf("logout-all: allowlist clear failed for %s: %v", userId, err)
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		middleware.ClearSessionCookie(w)
		w.Write([]byte(`{"status":"ok"}`))
	}
}

// profileResponse is the public view of a User (no password_hash, no public_key).
// Issue #450 adds the Passkey-summary fields.
type profileResponse struct {
	ID             string `json:"id"`
	Email          string `json:"email,omitempty"`
	DisplayName    string `json:"display_name,omitempty"`
	MailTo         string `json:"mail_to,omitempty"`
	SmsTo          string `json:"sms_to,omitempty"`
	TelegramChatID string `json:"telegram_chat_id,omitempty"`
	Tier           string `json:"tier"`
	SmsAllowed     bool   `json:"sms_allowed"`
	// Issue #1258 S6 (R1) — aus EmailVerifiedAt abgeleitet, NIE der Zeitstempel
	// selbst (AC-20).
	EmailVerified bool `json:"email_verified"`
	// Issue #1071 — offener Level-Änderungs-Antrag. Fehlt im JSON, solange kein
	// Antrag vorliegt (omitempty bzw. nil-Pointer).
	RequestedTier string     `json:"requested_tier,omitempty"`
	RequestedAt   *time.Time `json:"requested_at,omitempty"`
	// Issue #1717 S3 — Premium-SMS (Garmin inReach) in der Oberflaeche. REIN
	// LESEND: die Rueckadresse lernt ausschliesslich der interne Rueckkanal
	// (S1), UpdateProfileHandler nimmt die Felder nicht entgegen (AC-7).
	//
	// Rohwerte, Muster RequestedAt (hier IST der Zeitstempel die Nutzinformation
	// — anders als EmailVerifiedAt, das nie ausgegeben wird): fehlen im JSON,
	// solange das Geraet sich nie gemeldet hat. Pointer, weil omitempty bei
	// time.Time-Werten nicht greift.
	PremiumSmsReplyTo string     `json:"premium_sms_reply_to,omitempty"`
	PremiumSmsReplyAt *time.Time `json:"premium_sms_reply_at,omitempty"`
	// Abgeleiteter Zustand ("none"|"stale"|"fresh"), Muster EmailVerified —
	// die Verfallsfrist bleibt serverseitig, damit die Oberflaeche keine zweite
	// 30-Tage-Konstante braucht. Immer vorhanden.
	PremiumSmsReplyState string `json:"premium_sms_reply_state"`
	// Eigenes Tarif-Gate (nur premium), NICHT von SmsAllowed abgeleitet —
	// Muster SmsAllowed. Immer vorhanden.
	PremiumSmsAllowed bool                  `json:"premium_sms_allowed"`
	CreatedAt         string                `json:"created_at"`
	HasPasskey        bool                  `json:"has_passkey"`
	Passkeys          []passkeyProfileEntry `json:"passkeys,omitempty"`
	// Issue #2248 — Abweisung des Passkey-Angebots. Immer vorhanden (Muster
	// HasPasskey): die Oberflaeche entscheidet an diesem Wert und darf nicht
	// zwischen "false" und "Feld fehlt" unterscheiden muessen.
	PasskeyPromptDismissed bool `json:"passkey_prompt_dismissed"`
}

// passkeyProfileEntry exposes a registered Passkey to the client WITHOUT the
// public key — that material is server-side only.
type passkeyProfileEntry struct {
	ID                string `json:"id"`
	Label             string `json:"label,omitempty"`
	AuthenticatorName string `json:"authenticator_name,omitempty"`
	CreatedAt         string `json:"created_at"`
	LastUsedAt        string `json:"last_used_at,omitempty"`
}

func toProfileResponse(u *model.User) profileResponse {
	passkeys := make([]passkeyProfileEntry, 0, len(u.PasskeyCredentials))
	for _, pc := range u.PasskeyCredentials {
		entry := passkeyProfileEntry{
			ID:                base64.RawURLEncoding.EncodeToString(pc.ID),
			Label:             pc.Label,
			AuthenticatorName: aaguidToName(pc.Authenticator.AAGUID),
			CreatedAt:         pc.CreatedAt.Format(time.RFC3339),
		}
		if !pc.LastUsedAt.IsZero() {
			entry.LastUsedAt = pc.LastUsedAt.Format(time.RFC3339)
		}
		passkeys = append(passkeys, entry)
	}
	// Default-Fallback nur am Lesezeitpunkt — kein Schreibpfad setzt "free"
	// zurück in die user.json (Read-Modify-Write-Prinzip, Issue #1068).
	// Issue #1074: auch ungültige Werte (Tippfehler, Legacy-Daten) normalisieren.
	// Issue #1555: eine Quelle für alle Leser — model.EffectiveTier().
	tier := model.EffectiveTier(u.Tier)
	return profileResponse{
		ID:             u.ID,
		Email:          u.Email,
		DisplayName:    u.DisplayName,
		MailTo:         u.MailTo,
		SmsTo:          u.SmsTo,
		TelegramChatID: u.TelegramChatID,
		Tier:           tier,
		SmsAllowed:     model.SmsAllowed(tier),
		EmailVerified:  u.EmailVerifiedAt != nil,
		RequestedTier:  u.RequestedTier,
		RequestedAt:    u.RequestedAt,
		// Issue #1717 S3: Rohwerte durchgereicht, Zustand + Tarif-Gate abgeleitet.
		PremiumSmsReplyTo:    u.PremiumSmsReplyTo,
		PremiumSmsReplyAt:    u.PremiumSmsReplyAt,
		PremiumSmsReplyState: model.DerivePremiumSmsReplyState(u.PremiumSmsReplyTo, u.PremiumSmsReplyAt),
		PremiumSmsAllowed:    model.PremiumSmsAllowed(tier),
		CreatedAt:            u.CreatedAt.Format(time.RFC3339),
		HasPasskey:           len(u.PasskeyCredentials) > 0,
		Passkeys:             passkeys,
		// Issue #2248: auf diesem Weg erfaehrt die Oberflaeche die Abweisung
		// beim naechsten Laden.
		PasskeyPromptDismissed: u.PasskeyPromptDismissed,
	}
}

func GetProfileHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(toProfileResponse(user))
	}
}

// profileUpdateBeforeFreshReload ist eine Test-Naht (Issue #2147 Scheibe B1,
// spiegelt magicLinkBeforeTakeoverReload aus auth_magic.go): im Normalbetrieb
// nil und damit wirkungslos. Tests koennen sie setzen, um unmittelbar VOR dem
// erneuten Laden des eigenen Kontos (innerhalb der Adress-Sperre) eine
// Zwischenzeit-Aenderung einzuspielen.
var profileUpdateBeforeFreshReload func(userID string)

// profileUpdateAfterFirstAddressLock ist eine Test-Naht (Issue #2147 Scheibe
// B1, F008-Fix): im Normalbetrieb nil und damit wirkungslos. Sie feuert
// unmittelbar NACHDEM die erste Adresssperre der Sperrmenge genommen wurde
// und BEVOR eine etwaige zweite genommen wird — genau die Stelle, an der die
// Sortierung von addrs (sort.Strings) die Verklemmungsgefahr bei zwei
// gleichzeitigen Anfragen mit ueberlappender Adressmenge abwendet. Tests
// koennen hier eine Barriere setzen, die beide Anfragen erst gemeinsam
// weiterlaufen laesst.
var profileUpdateAfterFirstAddressLock func(userID string)

func UpdateProfileHandler(s *store.Store, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var update struct {
			Email          *string `json:"email"`
			DisplayName    *string `json:"display_name"`
			MailTo         *string `json:"mail_to"`
			SmsTo          *string `json:"sms_to"`
			TelegramChatID *string `json:"telegram_chat_id"`
			// Issue #2248 — Pointer (Muster DisplayName): nur ein mitgeschickter
			// Wert wird uebernommen, ein fehlendes Feld laesst die Abweisung
			// unberuehrt.
			PasskeyPromptDismissed *bool `json:"passkey_prompt_dismissed"`
		}
		if err := json.NewDecoder(r.Body).Decode(&update); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		// Display-Name-Format-Pruefung VOR jedem Schreibzugriff — bei einem
		// ungueltigen Wert darf noch nichts (auch keine Adress-Sperre) berührt
		// worden sein.
		var newDisplayName string
		if update.DisplayName != nil {
			newDisplayName = strings.TrimSpace(*update.DisplayName)
			if newDisplayName != "" && (utf8.RuneCountInString(newDisplayName) > 50 || hasControlChars(newDisplayName)) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":"invalid display_name"}`))
				return
			}
		}

		// Issue #2147 Scheibe B1 (PO-Korrektur nach Freigabe, Sicherheitsrueckschritt
		// sonst): ZWEI getrennte Praedikate statt einem.
		// - "Feld geaendert" (Reset-Praedikat): Feld gesendet UND normalisierter
		//   neuer Wert != normalisierter Bestandswert — leer zaehlt als Wert.
		//   Steuert EmailVerifiedAt-Reset + Bestaetigungsmail, EXAKT wie vor B1
		//   (Spec §3: "das heutige Reset-/Mail-Verhalten bleibt in B1
		//   unveraendert"). Sonst wuerde ein bestaetigtes mail_to geleert und
		//   das dann wirksame, nie bestaetigte email als bestaetigt weitergefuehrt
		//   (ResolveAddressOwner saehe einen bestaetigten Inhaber der neuen
		//   wirksamen Adresse, ohne dass sie je bestaetigt wurde).
		// - "geaendert UND belegbar" (Sperr-/Belegt-Praedikat): zusaetzlich neuer
		//   Wert nicht leer — Leeren kann nie 409 ausloesen (Spec §3).
		emailFieldChanged := update.Email != nil &&
			store.NormalizeEmailAddress(*update.Email) != store.NormalizeEmailAddress(user.Email)
		mailToFieldChanged := update.MailTo != nil &&
			store.NormalizeEmailAddress(*update.MailTo) != store.NormalizeEmailAddress(user.MailTo)
		emailChanged := emailFieldChanged && store.NormalizeEmailAddress(*update.Email) != ""
		mailToChanged := mailToFieldChanged && store.NormalizeEmailAddress(*update.MailTo) != ""

		if emailFieldChanged || mailToFieldChanged {
			// Die alte Adresse eines geleerten Felds gehoert mit in die
			// Sperrmenge — sie wird gerade frei.
			addrSet := map[string]struct{}{}
			if emailFieldChanged {
				if o := store.NormalizeEmailAddress(user.Email); o != "" {
					addrSet[o] = struct{}{}
				}
				if n := store.NormalizeEmailAddress(*update.Email); n != "" {
					addrSet[n] = struct{}{}
				}
			}
			if mailToFieldChanged {
				if o := store.NormalizeEmailAddress(user.MailTo); o != "" {
					addrSet[o] = struct{}{}
				}
				if n := store.NormalizeEmailAddress(*update.MailTo); n != "" {
					addrSet[n] = struct{}{}
				}
			}
			addrs := make([]string, 0, len(addrSet))
			for a := range addrSet {
				addrs = append(addrs, a)
			}
			sort.Strings(addrs)
			unlocks := make([]func(), len(addrs))
			for i, a := range addrs {
				unlocks[i] = store.LockEmailAddress(a)
				if i == 0 && profileUpdateAfterFirstAddressLock != nil {
					profileUpdateAfterFirstAddressLock(userId)
				}
			}
			defer func() {
				for i := len(unlocks) - 1; i >= 0; i-- {
					unlocks[i]()
				}
			}()

			// Read-Modify-Write: das eigene Konto FRISCH laden (Spec §3,
			// dieselbe TOCTOU-Absicherung wie F003 fuer den Magic-Link-Pfad).
			if profileUpdateBeforeFreshReload != nil {
				profileUpdateBeforeFreshReload(userId)
			}
			fresh, ferr := s.LoadUser(userId)
			if ferr != nil || fresh == nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(500)
				w.Write([]byte(`{"error":"internal error"}`))
				return
			}
			user = fresh

			if emailChanged {
				taken, terr := s.IsAddressTakenByOtherAccount(*update.Email, userId)
				if terr != nil {
					log.Printf("profile update: address uniqueness check failed: %v", terr)
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(500)
					w.Write([]byte(`{"error":"internal error"}`))
					return
				}
				if taken {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(409)
					w.Write([]byte(`{"error":"email_taken"}`))
					return
				}
			}
			if mailToChanged {
				taken, terr := s.IsAddressTakenByOtherAccount(*update.MailTo, userId)
				if terr != nil {
					log.Printf("profile update: address uniqueness check failed: %v", terr)
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(500)
					w.Write([]byte(`{"error":"internal error"}`))
					return
				}
				if taken {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(409)
					w.Write([]byte(`{"error":"email_taken"}`))
					return
				}
			}
		}

		if update.DisplayName != nil {
			user.DisplayName = newDisplayName // "" => Fallback auf Login-Name
		}

		// Issue #1219 Scheibe 1 (AC-5/AC-6): eine tatsächliche Änderung von
		// email/mail_to setzt die Resend-Verifikation zurück — ein einmal
		// verifiziertes Konto darf nicht nachträglich auf eine ungeprüfte
		// Adresse umgebogen werden. Dieses Reset-Verhalten bleibt in B1
		// UNVERÄNDERT (Spec §3) — es haengt am breiten "Feld geaendert"-
		// Praedikat (leer zaehlt als Wert), NICHT am schmalen Sperr-Praedikat.
		// Nur ein reiner Schreibweise-Unterschied loest KEINEN Reset aus
		// (Issue #2147 Scheibe B1, Known Limitations); Leeren tut es weiterhin,
		// sonst koennte eine nie bestaetigte zweite Adresse durch Leeren der
		// bestaetigten wirksam werden, ohne dass EmailVerifiedAt zurückgesetzt
		// wird (Sicherheitsrueckschritt, PO-Korrektur).
		addressChanged := false
		if update.Email != nil {
			user.Email = store.NormalizeEmailAddress(*update.Email)
		}
		if emailFieldChanged {
			user.EmailVerifiedAt = nil
			addressChanged = true
		}
		if update.MailTo != nil {
			user.MailTo = store.NormalizeEmailAddress(*update.MailTo)
		}
		if mailToFieldChanged {
			user.EmailVerifiedAt = nil
			addressChanged = true
		}
		if update.SmsTo != nil {
			user.SmsTo = *update.SmsTo
		}
		// Issue #2141: die Telegram-Chat-ID ist eine Identitätszuordnung, keine
		// Einstellung — gesetzt wird sie ausschließlich über den
		// localhost-gesperrten Einmal-Token-Flow (PostTelegramConnectHandler).
		// Über diesen generischen Profil-Decoder kommt nur der Leerstring durch,
		// damit "Telegram trennen" im Konto-Bereich weiter funktioniert. Ein
		// nicht-leerer Wert fließt nirgends ein; die Antwort (toProfileResponse)
		// zeigt den unveränderten gespeicherten Wert, der Aufrufer sieht die
		// Nicht-Übernahme also unmittelbar. Muster wie premium_sms_reply_to.
		if update.TelegramChatID != nil && *update.TelegramChatID == "" {
			user.TelegramChatID = ""
		}
		// Issue #2248: Read-Modify-Write — das geladene Objekt wird geaendert,
		// nicht ersetzt (BUG-DATALOSS-GR221).
		if update.PasskeyPromptDismissed != nil {
			user.PasskeyPromptDismissed = *update.PasskeyPromptDismissed
		}

		if err := s.SaveUser(*user); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		if addressChanged {
			dispatchVerificationMail(s, cfg, userId, user)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(toProfileResponse(user))
	}
}

// sendVerificationMailFn ist ein Test-Seam (Issue #1219 F001, PO-Wunsch):
// package-private Funktionsvariable statt eines direkten
// mail.SendVerificationMail-Aufrufs, damit Tests den Resend-Sonderpfad-
// Aufruf (Empfänger, Anzahl) beobachten können, ohne einen echten SMTP-Dial
// zu benötigen. Produktionsverhalten unverändert — Default ist
// mail.SendVerificationMail selbst.
var sendVerificationMailFn = mail.SendVerificationMail

// issueVerificationToken erzeugt einen 24h-Verifikations-Token für userId,
// persistiert seinen bcrypt-Hash und gibt den Klartext zurück (Issue #2304).
// Herausgelöst aus dispatchVerificationMail, damit der staging-only Testweg
// denselben Mechanismus benutzt, statt einen zweiten Token-Pfad zu bauen —
// der Klartext ist nur hier und in der Bestätigungsmail zu sehen.
func issueVerificationToken(s *store.Store, userId string) (string, error) {
	tokenBytes := make([]byte, 32)
	if _, err := rand.Read(tokenBytes); err != nil {
		return "", fmt.Errorf("token generation failed: %w", err)
	}
	token := hex.EncodeToString(tokenBytes)

	hash, err := bcrypt.GenerateFromPassword([]byte(token), bcrypt.DefaultCost)
	if err != nil {
		return "", fmt.Errorf("token hash failed: %w", err)
	}

	if err := s.SaveVerificationToken(userId, model.EmailVerificationToken{
		TokenHash: string(hash),
		ExpiresAt: time.Now().Add(24 * time.Hour),
	}); err != nil {
		return "", fmt.Errorf("SaveVerificationToken failed: %w", err)
	}
	return token, nil
}

// selfHealEmailVerification setzt `EmailVerifiedAt`, wenn provenAddress — die
// von einem Anmeldeweg NACHGEWIESENE Adresse (Magic-Link: Empfang des Codes im
// Postfach; Google: `email_verified`) — der effektiven Kontaktadresse des
// Kontos entspricht (mail_to, Rückfall email; dieselbe Vorrangregel wie
// dispatchVerificationMail). Issue #2304, AC-4..AC-6.
//
// Der Adressvergleich steht bewusst HIER und nicht in den Aufrufern: nur so
// ist er an einer Stelle prüfbar und mutierbar. Weicht die Adresse ab, bleibt
// das Feld unangetastet — die Anmeldung selbst hängt nicht daran (S1 sperrt
// nichts). Ein bereits gesetzter Zeitstempel wird nie neu gestempelt.
func selfHealEmailVerification(s *store.Store, userId, provenAddress string) {
	proven := strings.ToLower(strings.TrimSpace(provenAddress))
	if proven == "" {
		return
	}
	user, err := s.LoadUser(userId) // RMW: vollständiges Objekt laden
	if err != nil || user == nil {
		return
	}
	if user.EmailVerifiedAt != nil {
		return
	}
	contact := user.MailTo
	if contact == "" {
		contact = user.Email
	}
	if !strings.EqualFold(strings.TrimSpace(contact), proven) {
		return
	}
	now := time.Now().UTC()
	user.EmailVerifiedAt = &now
	if err := s.SaveUser(*user); err != nil {
		log.Printf("email verification self-heal: SaveUser failed for %s: %v", userId, err)
	}
}

// ResendVerificationHandler verschickt die Bestätigungsmail erneut (Issue
// #2304, AC-7/AC-8). Nutzlast ist die Kennung, nicht die Adresse — analog
// ForgotPasswordHandler, damit sich keine Adresse einem Konto zuordnen lässt.
//
// Die Antwort ist IMMER `200 {"status":"ok"}`: ob das Konto existiert, bereits
// bestätigt ist oder keine Kontaktadresse hält, darf von außen nicht
// unterscheidbar sein.
func ResendVerificationHandler(s *store.Store, cfg config.Config) http.HandlerFunc {
	const ok = `{"status":"ok"}`
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username string `json:"username"`
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Username == "" {
			w.Write([]byte(ok))
			return
		}
		if !store.ValidUserID(req.Username) {
			log.Printf("email verification resend: rejected path-unsafe user id %q", req.Username)
			w.Write([]byte(ok))
			return
		}
		user, _ := s.LoadUser(req.Username)
		if user != nil && user.EmailVerifiedAt == nil {
			dispatchVerificationMail(s, cfg, req.Username, user)
		}
		w.Write([]byte(ok))
	}
}

// dispatchVerificationMail erzeugt einen 24h-Verifikations-Token für userId
// und verschickt eine Bestätigungsmail an die neue Empfänger-Adresse (Issue
// #1219 Scheibe 2a-i) — Muster identisch zu ForgotPasswordHandler
// (Token-Erzeugung, Goroutine mit 20s-Timeout, Test-User→Gmail-Weiche). Die
// effektive Adresse ist mail_to, Rückfall email; ist beides leer, passiert
// nichts (kein Token, keine Mail).
func dispatchVerificationMail(s *store.Store, cfg config.Config, userId string, user *model.User) {
	recipient := user.MailTo
	if recipient == "" {
		recipient = user.Email
	}
	if recipient == "" {
		log.Printf("email verification: no address for user %s — no token generated", userId)
		return
	}

	token, err := issueVerificationToken(s, userId)
	if err != nil {
		log.Printf("email verification: token issuance failed for %s: %v", userId, err)
		return
	}

	msg := mail.BuildVerificationMail(cfg.PublicHost, userId, token)

	// Select SMTP config synchronously (identisches Muster zu
	// ForgotPasswordHandler): Test-User (IsTestUser) → Gmail-Config; echte
	// User → Resend-Sonderpfad SendVerificationMail (NICHT SendWithFallback/
	// Send — die Allowlist-Prüfung darf hier nicht greifen, die Adresse ist
	// per Definition unverifiziert). Nur der eigentliche Sendevorgang läuft
	// in der Goroutine mit 20s-Timeout, der Endpoint blockiert nicht.
	isTestUser := mail.IsTestUser(userId)
	if isTestUser && cfg.GoogleSMTPHost == "" {
		log.Printf("email verification: Google SMTP not configured, mail not sent for test user %s", userId)
		return
	}
	if !isTestUser && cfg.SMTPHost == "" {
		log.Printf("email verification: SMTP not configured, mail not sent for user %s", userId)
		return
	}

	go func(to string, msg mail.Mail, username string) {
		done := make(chan error, 1)
		if isTestUser {
			mailCfg := mail.MailConfig{
				Host: cfg.GoogleSMTPHost, Port: cfg.GoogleSMTPPort,
				User: cfg.GoogleSMTPUser, Pass: cfg.GoogleSMTPPass,
				From: cfg.GoogleSMTPUser,
			}
			fallbackCfg := mail.MailConfig{
				Host: cfg.FallbackSMTPHost, Port: 587,
				User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass,
			}
			go func() { done <- mail.SendWithFallback(mailCfg, fallbackCfg, to, msg) }()
		} else {
			mailCfg := mail.MailConfig{
				Host: cfg.SMTPHost, Port: cfg.SMTPPort,
				User: cfg.SMTPUser, Pass: cfg.SMTPPass,
				From: cfg.SMTPFrom,
			}
			go func() { done <- sendVerificationMailFn(mailCfg, to, msg) }()
		}
		select {
		case err := <-done:
			if err != nil {
				log.Printf("email verification: mail send failed for %s: %v", username, err)
			}
		case <-time.After(20 * time.Second):
			log.Printf("email verification: mail send timeout (20s) for %s", username)
		}
	}(recipient, msg, userId)
}

// hasControlChars reports whether s contains any Unicode control character
// (incl. newlines/tabs) — disallowed in a display name (Issue #642).
func hasControlChars(s string) bool {
	for _, r := range s {
		if unicode.IsControl(r) {
			return true
		}
	}
	return false
}

func ChangePasswordHandler(s *store.Store, bcryptCost int, secret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			OldPassword string `json:"old_password"`
			NewPassword string `json:"new_password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if len(req.NewPassword) < 8 {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}

		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.OldPassword)); err != nil {
			w.WriteHeader(403)
			w.Write([]byte(`{"error":"wrong password"}`))
			return
		}

		newHash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcryptCost)
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		user.PasswordHash = string(newHash)
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		// Issue #2129 AC-8: Der Passwortwechsel meldet auf allen ANDEREN
		// Geraeten ab. Bislang hatte er ueberhaupt keine Session-Wirkung — es
		// gab damit keinen wirksamen Notweg, ein verlorenes Geraet
		// auszusperren.
		//
		// Das Geraet, an dem gewechselt wird, bekommt sofort einen frischen
		// Nachweis: Liste leeren, neue Anmelde-Kennung eintragen, neues Cookie
		// in dieser Antwort. Sonst saehe der Nutzer unmittelbar nach dem
		// Wechsel eine Seite, deren Datenabrufe alle 401 geben.
		//
		// Bewusst NUR hier: Passwort-Zuruecksetzen, Kontoloeschung und "auf
		// allen Geraeten abmelden" stellen KEIN neues Merkmal aus. Wer
		// zuruecksetzt, weil das Passwort abgegriffen wurde, soll ausgesperrt
		// bleiben.
		if err := s.ClearSessions(userId); err != nil {
			log.Printf("password change: allowlist clear failed for %s: %v", userId, err)
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}
		// Issue #2271: bewusst OHNE Bestaetigungs-Gate. Wer gerade seine
		// Adresse geaendert hat, steht auf EmailVerifiedAt == nil — er muss
		// sein Passwort weiter aendern koennen, ohne dabei ausgesperrt zu
		// werden. Das ist die einzige Stelle, die die Ausnahme nutzen darf.
		if !issueSessionWithoutVerificationGate(w, r, s, userId, secret) {
			return
		}

		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}
}

// RequestTierChangeHandler nimmt einen Level-Änderungs-Antrag entgegen (Issue
// #1071). Der Antrag wird per Read-Modify-Write in der user.json vermerkt
// (requested_tier/requested_at) und löst asynchron eine Benachrichtigungsmail
// an den PO aus. Das effektive tier-Feld bleibt unverändert — die Freigabe
// erfolgt weiterhin manuell durch den PO.
func RequestTierChangeHandler(s *store.Store, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")

		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var req struct {
			RequestedTier string `json:"requested_tier"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if req.RequestedTier != "free" && req.RequestedTier != "standard" && req.RequestedTier != "premium" {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid_tier"}`))
			return
		}

		currentTier := model.EffectiveTier(user.Tier)
		if req.RequestedTier == currentTier {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"already_current_tier"}`))
			return
		}

		now := time.Now()
		user.RequestedTier = req.RequestedTier
		user.RequestedAt = &now
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		// Erst nach erfolgreichem Save antworten — Mail beeinflusst die Response nie.
		w.Write([]byte(`{"status":"ok"}`))

		if cfg.PoEmail == "" {
			log.Printf("tier-change: PO_EMAIL not configured — request stored for %s but no mail sent", userId)
			return
		}
		if cfg.SMTPHost == "" {
			log.Printf("tier-change: SMTP not configured — request stored for %s but no mail sent", userId)
			return
		}

		mailCfg := mail.MailConfig{
			Host: cfg.SMTPHost, Port: cfg.SMTPPort,
			User: cfg.SMTPUser, Pass: cfg.SMTPPass,
			From: cfg.SMTPFrom,
		}
		fallbackCfg := mail.MailConfig{
			Host: cfg.FallbackSMTPHost, Port: 587,
			User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass,
		}
		msg := mail.BuildTierChangeRequestMail(userId, currentTier, req.RequestedTier)

		// Goroutine mit Timeout — der Endpoint darf nicht auf SMTP blockieren.
		go func(to string, msg mail.Mail, c, fb mail.MailConfig, username string) {
			done := make(chan error, 1)
			go func() { done <- mail.SendWithFallback(c, fb, to, msg) }()
			select {
			case err := <-done:
				if err != nil {
					log.Printf("tier-change: mail send failed for %s: %v", username, err)
				}
			case <-time.After(20 * time.Second):
				log.Printf("tier-change: mail send timeout (20s) for %s", username)
			}
		}(cfg.PoEmail, msg, mailCfg, fallbackCfg, userId)
	}
}
