package main

import (
	"log"
	"net/http"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/egress"
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

// installGuards installiert die Transport-Waechter in der verbindlichen
// Reihenfolge (Issue #2142, AC-4): ZUERST coreauth.Install, DANACH
// egress.Install. egress.Install merkt sich den beim Aufruf vorgefundenen
// Transport und stellt ihn bei Uninstall zeiger-identisch wieder her; liefe
// coreauth.Install danach, ginge der Auth-Header bei einem egress.Uninstall()
// still verloren und der Python-Core wiese ab Scheibe 2 jede Anfrage mit 401
// ab. main() ruft ausschliesslich diese Funktion — die Reihenfolge steht
// damit an genau einer Stelle und ist ueber main_test.go pruefbar.
func installGuards(cfg *config.Config) {
	coreauth.Install(cfg)
	egress.Install(cfg)
}

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	// Issue #2139 — Session-Secret Fail-Fast: ein leeres, unveraendertes oder
	// zu kurzes Secret erlaubt selbst signierte Session-Cookies.
	if err := config.ValidateSessionSecret(cfg); err != nil {
		log.Fatalf("session secret invalid: %v", err)
	}

	// Issue #2142 — Core-Shared-Secret Fail-Fast: ohne Geheimnis sendet die
	// Go-API keinen Auth-Header und der Python-Core riegelt jede Anfrage ab.
	if err := config.ValidateCoreSharedSecret(cfg); err != nil {
		log.Fatalf("core shared secret invalid: %v", err)
	}

	// Issue #2142 F002 — Reihenfolge der Transport-Waechter steht an genau
	// dieser einen Stelle; installGuards() ist auch der Pruefling von
	// cmd/server/main_test.go (AC-4).
	installGuards(cfg)

	s := store.New(cfg.DataDir, cfg.UserID)
	telegramTokenStore := handler.NewTelegramTokenStore(cfg.DataDir)

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

	// Issue #450 — WebAuthn/Passkey init.
	// Issue #2130: RP-ID/Origins werden in config.NewWebAuthn aus PublicHost
	// abgeleitet. Der Aufbau steht bewusst NICHT mehr hier inline — sonst waeren
	// die Tests gruen, waehrend der laufende Server weiter "localhost" sendet.
	webAuthn, err := config.NewWebAuthn(cfg)
	if err != nil {
		log.Fatalf("webauthn init: %v", err)
	}
	challengeStore := handler.NewChallengeStore()

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		log.Fatalf("scheduler error: %v", err)
	}
	if scheduler.SchedulerEnabled(cfg) {
		sched.Start()
	} else {
		log.Printf("[scheduler] disabled for env=%s (staging quota gate, Issue #1329)", cfg.Env)
	}
	defer sched.Stop()

	r := router.New(router.Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    weatherProvider,
		WebAuthn:           webAuthn,
		ChallengeStore:     challengeStore,
		Scheduler:          sched,
		TelegramTokenStore: telegramTokenStore,
		GitCommit:          gitCommit,
	})

	log.Printf("Go API listening on %s:%s, proxying to %s", cfg.Host, cfg.Port, cfg.PythonCoreURL)
	http.ListenAndServe(cfg.Host+":"+cfg.Port, r)
}
