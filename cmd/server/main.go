package main

import (
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/provider/fixture"
	"github.com/henemm/gregor-api/internal/provider/openmeteo"
	"github.com/henemm/gregor-api/internal/router"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// gitCommit is injected at build time via -ldflags "-X main.gitCommit=<sha>".
var gitCommit = "dev"

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	s := store.New(cfg.DataDir, cfg.UserID)
	handler.InitTelegramTokenStore(cfg.DataDir)

	// Seed default user from ENV credentials on first run
	if !s.UserExists(cfg.UserID) && cfg.AuthPass != "" {
		hash, _ := bcrypt.GenerateFromPassword([]byte(cfg.AuthPass), bcrypt.DefaultCost)
		s.SaveUser(model.User{
			ID:           cfg.UserID,
			PasswordHash: string(hash),
			CreatedAt:    time.Now(),
		})
		log.Printf("Seed user '%s' created", cfg.UserID)
	}

	var weatherProvider provider.WeatherProvider
	if cfg.TestFixtureDir != "" {
		weatherProvider = fixture.NewProvider(cfg.TestFixtureDir)
		log.Printf("[fixture] FixtureProvider aktiv — dir: %s", cfg.TestFixtureDir)
	} else {
		weatherProvider = openmeteo.NewProvider(openmeteo.ProviderConfig{
			BaseURL:    cfg.OpenMeteoBaseURL,
			AQURL:      cfg.OpenMeteoAQURL,
			TimeoutSec: cfg.OpenMeteoTimeout,
			Retries:    cfg.OpenMeteoRetries,
			CacheDir:   cfg.CacheDir,
		})
	}

	// Issue #450 — WebAuthn/Passkey init (RPID/RPOrigins from config).
	origins := strings.Split(cfg.WebAuthnRPOrigins, ",")
	for i := range origins {
		origins[i] = strings.TrimSpace(origins[i])
	}
	webAuthn, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     origins,
	})
	if err != nil {
		log.Fatalf("webauthn init: %v", err)
	}
	challengeStore := handler.NewChallengeStore()

	compareEngine := compare.New(s, weatherProvider)

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		log.Fatalf("scheduler error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	r := router.New(router.Deps{
		Config:          cfg,
		Store:           s,
		WeatherProvider: weatherProvider,
		WebAuthn:        webAuthn,
		ChallengeStore:  challengeStore,
		CompareEngine:   compareEngine,
		Scheduler:       sched,
		GitCommit:       gitCommit,
	})

	log.Printf("Go API listening on %s:%s, proxying to %s", cfg.Host, cfg.Port, cfg.PythonCoreURL)
	http.ListenAndServe(cfg.Host+":"+cfg.Port, r)
}
