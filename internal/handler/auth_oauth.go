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
	"github.com/henemm/gregor-api/internal/middleware"
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
		} else {
			newUser, err := createOAuthUser(s, "google", userinfo.Sub, userinfo.Email)
			if err != nil {
				log.Printf("oauth google: create user failed: %v", err)
				http.Redirect(w, r, "/login?error=oauth_failed", http.StatusFound)
				return
			}
			userId = newUser.ID
		}

		sessionToken := middleware.SignSession(userId, cfg.SessionSecret)
		secure := r.Header.Get("X-Forwarded-Proto") == "https" || r.TLS != nil
		http.SetCookie(w, &http.Cookie{
			Name:     "gz_session",
			Value:    sessionToken,
			Path:     "/",
			HttpOnly: true,
			SameSite: http.SameSiteLaxMode,
			MaxAge:   86400,
			Secure:   secure,
		})

		http.Redirect(w, r, "/", http.StatusFound)
	}
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
