package handler

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
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
		// PasskeyRegisterPublicBeginHandler, keine Uniqueness-Prüfung (Spec).
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

		user := model.User{
			ID:           req.Username,
			PasswordHash: string(hash),
			Email:        req.Email,
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

// issueSession mintet eine Anmelde-Kennung, traegt sie in die Gaesteliste des
// Nutzers ein und setzt das Anmelde-Cookie (Issue #2129). EINE Stelle fuer alle
// sechs Anmeldewege: wird eine davon vergessen, sperrt dieser Weg alle seine
// Nutzer aus, weil ihr Merkmal zwar wohlgeformt, aber nicht gelistet waere.
//
// Liefert false, wenn bereits geantwortet wurde (Fehlerfall).
func issueSession(w http.ResponseWriter, r *http.Request, s *store.Store, userId, secret string) bool {
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
		}
		if err := json.NewDecoder(r.Body).Decode(&update); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if update.DisplayName != nil {
			name := strings.TrimSpace(*update.DisplayName)
			if name == "" {
				user.DisplayName = "" // Fallback auf Login-Name
			} else if utf8.RuneCountInString(name) > 50 || hasControlChars(name) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":"invalid display_name"}`))
				return
			} else {
				user.DisplayName = name
			}
		}

		// Issue #1219 Scheibe 1 (AC-5/AC-6): eine tatsächliche Änderung von
		// email/mail_to setzt die Resend-Verifikation zurück — ein einmal
		// verifiziertes Konto darf nicht nachträglich auf eine ungeprüfte
		// Adresse umgebogen werden. No-Op-Updates (identischer Wert) lösen
		// KEINEN Reset aus.
		addressChanged := false
		if update.Email != nil && *update.Email != user.Email {
			user.Email = *update.Email
			user.EmailVerifiedAt = nil
			addressChanged = true
		}
		if update.MailTo != nil && *update.MailTo != user.MailTo {
			user.MailTo = *update.MailTo
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

	tokenBytes := make([]byte, 32)
	if _, err := rand.Read(tokenBytes); err != nil {
		log.Printf("email verification: token generation failed for %s: %v", userId, err)
		return
	}
	token := hex.EncodeToString(tokenBytes)

	hash, err := bcrypt.GenerateFromPassword([]byte(token), bcrypt.DefaultCost)
	if err != nil {
		log.Printf("email verification: token hash failed for %s: %v", userId, err)
		return
	}

	verificationToken := model.EmailVerificationToken{
		TokenHash: string(hash),
		ExpiresAt: time.Now().Add(24 * time.Hour),
	}
	if err := s.SaveVerificationToken(userId, verificationToken); err != nil {
		log.Printf("email verification: SaveVerificationToken failed for %s: %v", userId, err)
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
		if !issueSession(w, r, s, userId, secret) {
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
