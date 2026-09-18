package handler

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const googleUserinfoURL = "https://www.googleapis.com/oauth2/v3/userinfo"

func buildGoogleOAuthConfig(cfg *config.Config) *oauth2.Config {
	return buildGoogleOAuthConfigWithEndpoint(cfg, google.Endpoint)
}

func buildGoogleOAuthConfigWithEndpoint(cfg *config.Config, endpoint oauth2.Endpoint) *oauth2.Config {
	return &oauth2.Config{
		ClientID:     cfg.GoogleClientID,
		ClientSecret: cfg.GoogleClientSecret,
		RedirectURL:  cfg.GoogleRedirectURL,
		Scopes:       []string{"openid", "email", "profile"},
		Endpoint:     endpoint,
	}
}

func GoogleOAuthInitHandler(cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if cfg.GoogleClientID == "" {
			http.Error(w, `{"error":"google_oauth_not_configured"}`, http.StatusNotImplemented)
			return
		}

		stateBytes := make([]byte, 16)
		if _, err := rand.Read(stateBytes); err != nil {
			http.Error(w, `{"error":"internal_error"}`, http.StatusInternalServerError)
			return
		}
		state := hex.EncodeToString(stateBytes)

		secure := r.Header.Get("X-Forwarded-Proto") == "https" || r.TLS != nil
		http.SetCookie(w, &http.Cookie{
			Name:     "gz_oauth_state",
			Value:    state,
			Path:     "/",
			HttpOnly: true,
			SameSite: http.SameSiteLaxMode,
			MaxAge:   600,
			Secure:   secure,
		})

		oauthCfg := buildGoogleOAuthConfig(cfg)
		url := oauthCfg.AuthCodeURL(state)
		http.Redirect(w, r, url, http.StatusFound)
	}
}

func GoogleOAuthCallbackHandler(cfg *config.Config, s *store.Store) http.HandlerFunc {
	return googleOAuthCallbackHandlerInternal(cfg, s, googleUserinfoURL, google.Endpoint)
}

// GoogleOAuthCallbackHandlerWithEndpoints ist für Tests — erlaubt Fake-Server für
// Userinfo- und Token-Endpoint, ohne echten Google-Roundtrip.
func GoogleOAuthCallbackHandlerWithEndpoints(cfg *config.Config, s *store.Store, userinfoURL, tokenURL string) http.HandlerFunc {
	endpoint := oauth2.Endpoint{AuthURL: google.Endpoint.AuthURL, TokenURL: tokenURL}
	return googleOAuthCallbackHandlerInternal(cfg, s, userinfoURL, endpoint)
}

func googleOAuthCallbackHandlerInternal(cfg *config.Config, s *store.Store, userinfoURL string, endpoint oauth2.Endpoint) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if cfg.GoogleClientID == "" {
			http.Error(w, `{"error":"google_oauth_not_configured"}`, http.StatusNotImplemented)
			return
		}

		stateCookie, err := r.Cookie("gz_oauth_state")
		if err != nil {
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}
		http.SetCookie(w, &http.Cookie{
			Name:   "gz_oauth_state",
			Value:  "",
			Path:   "/",
			MaxAge: -1,
		})

		stateParam := r.URL.Query().Get("state")
		if subtle.ConstantTimeCompare([]byte(stateCookie.Value), []byte(stateParam)) != 1 {
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		code := r.URL.Query().Get("code")
		if code == "" {
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		oauthCfg := buildGoogleOAuthConfigWithEndpoint(cfg, endpoint)
		token, err := oauthCfg.Exchange(context.Background(), code)
		if err != nil {
			log.Printf("oauth google: token exchange failed: %v", err)
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		client := oauthCfg.Client(context.Background(), token)
		resp, err := client.Get(userinfoURL)
		if err != nil {
			log.Printf("oauth google: userinfo fetch failed: %v", err)
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		var userinfo struct {
			Sub           string `json:"sub"`
			Email         string `json:"email"`
			EmailVerified bool   `json:"email_verified"`
		}
		if err := json.Unmarshal(body, &userinfo); err != nil {
			log.Printf("oauth google: userinfo parse failed: %v", err)
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		if userinfo.Sub == "" {
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}
		if !userinfo.EmailVerified {
			log.Printf("oauth google: email not verified for sub %q", userinfo.Sub)
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		existingUser, err := s.FindUserByOAuthSub("google", userinfo.Sub)
		if err != nil {
			log.Printf("oauth google: store lookup failed: %v", err)
			http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
			return
		}

		var userId string
		if existingUser != nil {
			userId = existingUser.ID
			// Issue #2304 (AC-6): Google hat userinfo.Email bestätigt
			// (email_verified oben erzwungen). Deckt sich das mit der
			// effektiven Kontaktadresse, heilt die Bestätigung sich selbst.
			// NUR im Bestands-Zweig: neu angelegte OAuth-Konten durchlaufen
			// den #1226-Double-Opt-In über dispatchVerificationMail unten —
			// eine Vorab-Bestätigung würde den wirkungslos machen.
			selfHealEmailVerification(s, userId, userinfo.Email)
		} else {
			// Issue #2147 Scheibe C: Adresse auflösen + Konto anlegen/verknüpfen/
			// übernehmen unter EINER Sperre je normalisierter Adresse — dieselbe
			// wie Registrierung, Profil und Magic-Link. Gehalten bis zum Ende des
			// Requests (Muster auth_magic.go).
			unlock := store.LockEmailAddress(store.NormalizeEmailAddress(userinfo.Email))
			defer unlock()
			resolvedID, ok := resolveGoogleAccount(w, r, s, *cfg, userinfo.Sub, userinfo.Email)
			if !ok {
				return
			}
			userId = resolvedID
		}

		// Issue #2271: Vorpruefung NACH der Selbstheilung oben — liefe sie
		// davor, wiese sie genau das Konto ab, das sich in diesem Request
		// gerade heilt. Sie steht hier, weil dieser Fluss ein Redirect-Fluss
		// ist: Erfolg und Ablehnung sind beide 302, der Unterschied steckt
		// allein im Location-Header. Ein rohes JSON haette hier niemand
		// gelesen.
		if verified, readable := hasVerifiedEmail(s, userId); !readable || !verified {
			log.Printf("oauth google: login refused, email not verified for %s", userId)
			http.Redirect(w, r, "/login?error=email_not_verified", http.StatusFound)
			return
		}

		// Das Gate in issueSession bleibt als Rueckfallebene bestehen (kein
		// Weg umgeht es), ist hier aber durch die Vorpruefung unerreichbar.
		if !issueSession(w, r, s, userId, cfg.SessionSecret) {
			return
		}

		http.Redirect(w, r, "/", http.StatusFound)
	}
}

// resolveGoogleAccount ordnet einen noch unbekannten Google-sub genau einem
// Konto zu (Issue #2147 Scheibe C, Spec google_login_adress_verknuepfung.md).
// Der Aufrufer hält store.LockEmailAddress der normalisierten Adresse. Liefert
// false, wenn bereits per Redirect geantwortet wurde. Inhaltliche Ablehnungen
// laufen alle auf oauth_link_failed, Lesefehler auf oauth_failed; Logzeilen
// nennen weder Adresse noch Kontokennung.
func resolveGoogleAccount(w http.ResponseWriter, r *http.Request, s *store.Store, cfg config.Config, sub, email string) (string, bool) {
	address := store.NormalizeEmailAddress(email)
	// Erneut UNTER der Sperre (AC-13): ein paralleler Callback desselben sub
	// (Doppelklick) kann das Konto soeben angelegt oder verknüpft haben. Ohne
	// diesen Blick liefe der zweite Callback in die Adressklassifikation und
	// fände ein unbestätigtes Konto mit Zugangsdaten -> oauth_link_failed.
	// Bewusst OHNE selfHealEmailVerification: das Konto entstand in genau
	// diesem Moment durch den parallelen Callback und durchläuft den
	// Double-Opt-In (#1226) — beide Callbacks enden gleich (AC-13).
	existing, err := s.FindUserByOAuthSub("google", sub)
	if err != nil {
		log.Printf("oauth google: store lookup under address lock failed — login refused")
		return googleOAuthFail(w, r, "oauth_failed")
	}
	if existing != nil {
		return existing.ID, true
	}
	owner, resolution, err := s.ResolveAddressOwner(address)
	if err != nil {
		log.Printf("oauth google: address resolution failed — login refused")
		return googleOAuthFail(w, r, "oauth_failed")
	}
	switch {
	case resolution == store.AddressFree:
		newUser, err := createOAuthUser(s, "google", sub, address)
		if err != nil {
			log.Printf("oauth google: create user failed: %v", err)
			return googleOAuthFail(w, r, "oauth_failed")
		}
		// Issue #1226: neu angelegte OAuth-Konten durchlaufen denselben
		// #1219-Double-Opt-In wie die klassische Registrierung. NUR bei
		// tatsächlicher Neuanlage — beim Login eines bestehenden sub darf
		// KEIN Dispatch laufen (sonst Mail-Spam bei jedem Login, AC-5).
		dispatchVerificationMail(s, cfg, newUser.ID, newUser)
		return newUser.ID, true
	case resolution == store.AddressOwned && owner.EmailVerifiedAt != nil:
		return linkGoogleAccount(w, r, s, cfg, owner.ID, sub, address)
	case resolution == store.AddressOwned:
		return takeOverGoogleAccount(w, r, s, owner.ID, sub, address)
	}
	log.Printf("oauth google: address not uniquely assignable — login refused")
	return googleOAuthFail(w, r, "oauth_link_failed")
}

func googleOAuthFail(w http.ResponseWriter, r *http.Request, code string) (string, bool) {
	http.Redirect(w, r, "/login?error="+code, http.StatusFound)
	return "", false
}

// linkGoogleAccount verknüpft ein bestätigtes Konto ohne Google-Identität mit
// sub (AC-3): frisch geladen (Read-Modify-Write), nur OAuthProvider/OAuthSub
// gesetzt, EmailVerifiedAt und Sitzungen unberührt, danach Hinweis-Mail an die
// wirksame Adresse. Ein bereits gesetzter anderer Sub wird nie überschrieben (AC-5).
func linkGoogleAccount(w http.ResponseWriter, r *http.Request, s *store.Store, cfg config.Config, ownerID, sub, address string) (string, bool) {
	user, err := s.LoadUser(ownerID)
	if err != nil || user == nil {
		log.Printf("oauth google: linking refused — account unreadable")
		return googleOAuthFail(w, r, "oauth_failed")
	}
	if user.EmailVerifiedAt == nil || store.EffectiveContactAddress(user) != address {
		log.Printf("oauth google: linking refused — account changed since assignment")
		return googleOAuthFail(w, r, "oauth_link_failed")
	}
	if user.OAuthSub != "" {
		log.Printf("oauth google: linking refused — account already carries another Google identity")
		return googleOAuthFail(w, r, "oauth_link_failed")
	}
	user.OAuthProvider = "google"
	user.OAuthSub = sub
	if err := s.SaveUser(*user); err != nil {
		log.Printf("oauth google: linking failed — account not saved")
		return googleOAuthFail(w, r, "oauth_failed")
	}
	sendGoogleLinkNotice(cfg, user, store.EffectiveContactAddress(user))
	return user.ID, true
}

// googleLinkBeforeTakeoverReload ist eine Test-Naht (Issue #2147 Scheibe C,
// Muster magicLinkBeforeTakeoverReload): im Normalbetrieb nil und damit
// wirkungslos. Tests spielen damit eine Zwischenzeit-Änderung zwischen der
// Zuordnung (ResolveAddressOwner) und dem erneuten Laden ein — z. B. ein per
// ResetPasswordHandler gesetztes Passwort, der die Adress-Sperre nicht hält.
var googleLinkBeforeTakeoverReload func(userID string)

// takeOverGoogleAccount übernimmt ein unbestätigtes, zugangsloses Konto (AC-6,
// Muster resolveMagicLinkAccount): frisch geladen, Nachprüfung, dass es
// weiterhin unbestätigt, zugangslos und mit derselben wirksamen Adresse ist;
// dann bestätigt, verknüpft und alte Sitzungen beendet. Keine Hinweis-Mail —
// es gibt keinen Vorbesitzer, der gewarnt werden müsste.
func takeOverGoogleAccount(w http.ResponseWriter, r *http.Request, s *store.Store, ownerID, sub, address string) (string, bool) {
	if googleLinkBeforeTakeoverReload != nil {
		googleLinkBeforeTakeoverReload(ownerID)
	}
	user, err := s.LoadUser(ownerID)
	if err != nil || user == nil {
		log.Printf("oauth google: takeover refused — account unreadable")
		return googleOAuthFail(w, r, "oauth_failed")
	}
	if user.EmailVerifiedAt != nil || store.HasLoginCredentials(user) || store.EffectiveContactAddress(user) != address {
		log.Printf("oauth google: takeover refused — account changed since assignment")
		return googleOAuthFail(w, r, "oauth_link_failed")
	}
	now := time.Now().UTC()
	user.EmailVerifiedAt = &now
	user.OAuthProvider = "google"
	user.OAuthSub = sub
	if err = s.SaveUser(*user); err == nil {
		err = s.ClearSessions(ownerID)
	}
	if err != nil {
		log.Printf("oauth google: takeover failed — account not saved")
		return googleOAuthFail(w, r, "oauth_failed")
	}
	return ownerID, true
}

// buildGoogleLinkNoticeMail: Hinweis ohne einlösbaren Link oder Token.
func buildGoogleLinkNoticeMail() mail.Mail {
	return mail.Mail{
		Subject: "Google-Anmeldung mit deinem Gregor-20-Konto verknüpft",
		PlainBody: "Hallo,\n\ndein Gregor-20-Konto wurde soeben mit einer Google-Anmeldung verknuepft. " +
			"Du kannst dich ab jetzt auch mit \"Mit Google anmelden\" anmelden.\n\n" +
			"Warst du das nicht, melde dich bitte umgehend bei uns.\n",
		HTMLBody: `<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">` +
			`<p>Hallo,</p>` +
			`<p>dein Gregor-20-Konto wurde soeben mit einer Google-Anmeldung verkn&uuml;pft. ` +
			`Du kannst dich ab jetzt auch mit &bdquo;Mit Google anmelden&ldquo; anmelden.</p>` +
			`<p>Warst du das nicht, melde dich bitte umgehend bei uns.</p>` +
			`</body></html>`,
	}
}

// sendGoogleLinkNotice verschickt die Hinweis-Mail über denselben Versandweg
// wie die Bestätigungsmail (dispatchVerificationMail), fail-soft. Ein
// Versandfehler wird nie roh protokolliert — SMTP-Fehler nennen den Empfänger.
func sendGoogleLinkNotice(cfg config.Config, user *model.User, to string) {
	isTestUser := mail.IsTestUser(user)
	if (isTestUser && cfg.GoogleSMTPHost == "") || (!isTestUser && cfg.SMTPHost == "") {
		log.Printf("oauth google: link notice not sent — SMTP not configured")
		return
	}
	msg := buildGoogleLinkNoticeMail()
	go func() {
		done := make(chan error, 1)
		if isTestUser {
			mailCfg := mail.MailConfig{Host: cfg.GoogleSMTPHost, Port: cfg.GoogleSMTPPort,
				User: cfg.GoogleSMTPUser, Pass: cfg.GoogleSMTPPass, From: cfg.GoogleSMTPUser}
			fallbackCfg := mail.MailConfig{Host: cfg.FallbackSMTPHost, Port: 587,
				User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass}
			go func() { done <- mail.SendWithFallback(mailCfg, fallbackCfg, to, msg) }()
		} else {
			mailCfg := mail.MailConfig{Host: cfg.SMTPHost, Port: cfg.SMTPPort,
				User: cfg.SMTPUser, Pass: cfg.SMTPPass, From: cfg.SMTPFrom}
			go func() { done <- sendVerificationMailFn(mailCfg, to, msg) }()
		}
		select {
		case err := <-done:
			if err != nil {
				log.Printf("oauth google: link notice mail send failed")
			}
		case <-time.After(20 * time.Second):
			log.Printf("oauth google: link notice mail send timeout (20s)")
		}
	}()
}

func createOAuthUser(s *store.Store, provider, sub, email string) (*model.User, error) {
	for attempts := 0; attempts < 3; attempts++ {
		idBytes := make([]byte, 4)
		if _, err := rand.Read(idBytes); err != nil {
			return nil, err
		}
		id := fmt.Sprintf("g-%s", hex.EncodeToString(idBytes))

		if s.UserExists(id) {
			continue
		}

		user := model.User{
			ID:            id,
			OAuthProvider: provider,
			OAuthSub:      sub,
			Email:         email,
			MailTo:        email,
			CreatedAt:     time.Now(),
		}
		if err := s.SaveUser(user); err != nil {
			return nil, err
		}
		if err := s.ProvisionUserDirs(id); err != nil {
			return nil, err
		}
		return &user, nil
	}
	return nil, fmt.Errorf("could not generate unique user ID after 3 attempts")
}
