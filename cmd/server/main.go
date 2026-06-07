package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/provider/fixture"
	"github.com/henemm/gregor-api/internal/provider/openmeteo"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

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
	passkeyLimiter := authmw.NewIPRateLimiter(30, time.Hour)

	r := chi.NewRouter()
	r.Use(chimw.Logger)
	r.Use(authmw.AuthMiddleware(cfg.SessionSecret))

	// Auth endpoints (register/login exempt from AuthMiddleware)
	// Rate-limit register: 5 attempts per IP per hour (Issue #117).
	registerLimiter := authmw.NewIPRateLimiter(5, time.Hour)
	r.Post("/api/auth/register",
		registerLimiter.Middleware(handler.RegisterHandler(s, bcrypt.DefaultCost)).ServeHTTP,
	)
	loginLimiter := authmw.NewIPRateLimiter(30, time.Hour)
	r.Post("/api/auth/login",
		loginLimiter.Middleware(handler.LoginHandler(s, cfg.SessionSecret)).ServeHTTP,
	)
	r.Post("/api/auth/logout", handler.LogoutHandler())
	forgotLimiter := authmw.NewIPRateLimiter(5, time.Hour)
	r.Post("/api/auth/forgot-password",
		forgotLimiter.Middleware(handler.ForgotPasswordHandler(s, bcrypt.DefaultCost, *cfg)).ServeHTTP,
	)
	resetLimiter := authmw.NewIPRateLimiter(10, time.Hour)
	r.Post("/api/auth/reset-password",
		resetLimiter.Middleware(handler.ResetPasswordHandler(s, bcrypt.DefaultCost)).ServeHTTP,
	)
	r.Delete("/api/auth/account", handler.DeleteAccountHandler(s))
	r.Get("/api/auth/profile", handler.GetProfileHandler(s))
	r.Put("/api/auth/profile", handler.UpdateProfileHandler(s))
	r.Put("/api/auth/password", handler.ChangePasswordHandler(s, bcrypt.DefaultCost))
	// Bug #590: Telegram /start-Flow — link generation + status polling + internal connect
	r.Get("/api/auth/telegram-link", handler.GetTelegramLinkHandler(s))
	r.Get("/api/auth/telegram-status", handler.GetTelegramStatusHandler(s))
	r.Post("/api/internal/telegram-connect", handler.PostTelegramConnectHandler(s))
	// Issue #637: Telegram Inbound Webhook (public, secret-header-protected)
	r.Post("/api/webhooks/telegram/{secret}", handler.TelegramWebhookHandler(cfg.PythonCoreURL))
	r.Get("/api/auth/google/init", handler.GoogleOAuthInitHandler(cfg))
	r.Get("/api/auth/google/callback", handler.GoogleOAuthCallbackHandler(cfg, s))
	magicLinkLimiter := authmw.NewIPRateLimiter(5, 15*time.Minute)
	r.Post("/api/auth/magic-link",
		magicLinkLimiter.Middleware(handler.MagicLinkRequestHandler(s, cfg)).ServeHTTP,
	)
	magicVerifyLimiter := authmw.NewIPRateLimiter(10, 15*time.Minute)
	r.Post("/api/auth/magic-link/verify",
		magicVerifyLimiter.Middleware(handler.MagicLinkVerifyHandler(s, cfg)).ServeHTTP,
	)

	// Issue #450 — Passkey/WebAuthn endpoints
	// Public endpoints (exempted in middleware.AuthMiddleware)
	r.Post("/api/auth/passkey/login/begin",
		passkeyLimiter.Middleware(handler.PasskeyLoginBeginHandler(s, webAuthn, challengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/login/finish",
		passkeyLimiter.Middleware(handler.PasskeyLoginFinishHandler(s, webAuthn, challengeStore, cfg.SessionSecret)).ServeHTTP,
	)
	// Issue #467 — Discoverable Credentials + Conditional UI (public)
	r.Post("/api/auth/passkey/discoverable/begin",
		passkeyLimiter.Middleware(handler.PasskeyLoginDiscoverableBeginHandler(webAuthn, challengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/discoverable/finish",
		passkeyLimiter.Middleware(handler.PasskeyLoginDiscoverableFinishHandler(s, webAuthn, challengeStore, cfg.SessionSecret)).ServeHTTP,
	)
	// Authenticated endpoints (cookie required via AuthMiddleware)
	r.Post("/api/auth/passkey/register/begin",
		passkeyLimiter.Middleware(handler.PasskeyRegisterBeginHandler(s, webAuthn, challengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/register/finish",
		passkeyLimiter.Middleware(handler.PasskeyRegisterFinishHandler(s, webAuthn, challengeStore)).ServeHTTP,
	)
	r.Delete("/api/auth/passkey/credentials/{id}",
		passkeyLimiter.Middleware(handler.PasskeyDeleteCredentialHandler(s)).ServeHTTP,
	)
	passkeyRegPubLimiter := authmw.NewIPRateLimiter(5, time.Hour)
	r.Post("/api/auth/passkey/register/public/begin",
		passkeyRegPubLimiter.Middleware(handler.PasskeyRegisterPublicBeginHandler(s, webAuthn, challengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/register/public/finish",
		passkeyRegPubLimiter.Middleware(handler.PasskeyRegisterPublicFinishHandler(s, webAuthn, challengeStore, cfg.SessionSecret)).ServeHTTP,
	)

	r.Get("/api/health", handler.HealthHandler(cfg.PythonCoreURL))
	r.Get("/api/config", handler.ProxyHandler(cfg.PythonCoreURL, "/config"))
	r.Get("/api/metrics", handler.ProxyHandler(cfg.PythonCoreURL, "/metrics"))
	r.Get("/api/templates", handler.ProxyHandler(cfg.PythonCoreURL, "/templates"))
	r.Get("/api/forecast", handler.ForecastHandler(weatherProvider))
	r.Get("/api/locations", handler.LocationsHandler(s))
	r.Get("/api/locations/{id}", handler.LocationHandler(s))
	r.Post("/api/locations/resolve", handler.ResolveLocationHandler())
	r.Post("/api/locations", handler.CreateLocationHandler(s))
	r.Put("/api/locations/{id}", handler.UpdateLocationHandler(s))
	r.Patch("/api/locations/{id}", handler.PatchLocationHandler(s))
	r.Delete("/api/locations/{id}", handler.DeleteLocationHandler(s))
	r.Get("/api/groups", handler.GroupsHandler(s))
	r.Post("/api/groups", handler.CreateGroupHandler(s))
	r.Patch("/api/groups/{id}", handler.UpdateGroupHandler(s))
	r.Delete("/api/groups/{id}", handler.DeleteGroupHandler(s))
	r.Get("/api/trips", handler.TripsHandler(s))
	r.Get("/api/trips/{id}", handler.TripHandler(s))
	r.Post("/api/trips", handler.CreateTripHandler(s))
	r.Put("/api/trips/{id}", handler.UpdateTripHandler(s))
	r.Patch("/api/trips/{id}/state", handler.UpdateTripStateHandler(s))
	r.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", handler.ConfirmWaypointHandler(s))
	r.Delete("/api/trips/{id}", handler.DeleteTripHandler(s))
	r.Get("/api/trips/{id}/stages/weather", handler.StagesWeatherHandler(s, weatherProvider))
	r.Get("/api/trips/{id}/briefing-history", handler.BriefingHistoryHandler(s))
	r.Get("/api/subscriptions", handler.SubscriptionsHandler(s))
	r.Get("/api/subscriptions/{id}", handler.SubscriptionHandler(s))
	r.Post("/api/subscriptions", handler.CreateSubscriptionHandler(s))
	r.Put("/api/subscriptions/{id}", handler.UpdateSubscriptionHandler(s))
	r.Patch("/api/subscriptions/{id}/run-status", handler.PatchSubscriptionRunStatusHandler(s))
	r.Delete("/api/subscriptions/{id}", handler.DeleteSubscriptionHandler(s))
	// Issue #456 — Manueller Versand-Trigger fuer eine einzelne Subscription
	r.Post("/api/subscriptions/{id}/send", handler.SendSubscriptionProxyHandler(cfg.PythonCoreURL))
	r.Get("/api/trips/{id}/weather-config", handler.GetTripWeatherConfigHandler(s))
	r.Put("/api/trips/{id}/weather-config", handler.PutTripWeatherConfigHandler(s))
	r.Get("/api/locations/{id}/weather-config", handler.GetLocationWeatherConfigHandler(s))
	r.Put("/api/locations/{id}/weather-config", handler.PutLocationWeatherConfigHandler(s))
	r.Get("/api/subscriptions/{id}/weather-config", handler.GetSubscriptionWeatherConfigHandler(s))
	r.Put("/api/subscriptions/{id}/weather-config", handler.PutSubscriptionWeatherConfigHandler(s))
	r.Post("/api/gpx/parse", handler.GpxProxyHandler(cfg.PythonCoreURL))
	r.Post("/api/notify/test", handler.ProxyPostHandler(cfg.PythonCoreURL, "/api/notify/test"))
	r.Get("/api/compare", handler.CompareProxyHandler(cfg.PythonCoreURL))
	compareEngine := compare.New(s, weatherProvider)
	r.Post("/api/compare/run", handler.CompareRunHandler(compareEngine))
	r.Get("/api/_internal/trip/{id}/loaded", handler.LoadedTripProxyHandler(cfg.PythonCoreURL))
	// Issue #221: External Validator observability endpoints (cookie-auth via global middleware).
	r.Get("/api/_validator/format-metric", handler.ValidatorFormatMetricProxyHandler(cfg.PythonCoreURL))
	r.Get("/api/_validator/detector-thresholds", handler.DetectorThresholdsProxyHandler(cfg.PythonCoreURL))
	r.Get("/api/_validator/metrics-for-channel", handler.MetricsForChannelProxyHandler(cfg.PythonCoreURL))
	r.Post("/api/_validator/compare-email-preview", handler.CompareEmailPreviewProxyHandler(cfg.PythonCoreURL))
	r.Post("/api/trips/{id}/alert-preview", handler.AlertPreviewProxyHandler(cfg.PythonCoreURL))
	// Issue #140 / #189: Output-Vorschau Email + SMS
	r.Get("/api/preview/{trip_id}/email", handler.PreviewProxyHandler(cfg.PythonCoreURL, "email"))
	r.Get("/api/preview/{trip_id}/sms", handler.PreviewProxyHandler(cfg.PythonCoreURL, "sms"))
	// Issue #363: Signal/Telegram-Vorschau (kanal-bewusster Narrow-Renderer #360)
	r.Get("/api/preview/{trip_id}/signal", handler.PreviewProxyHandler(cfg.PythonCoreURL, "signal"))
	r.Get("/api/preview/{trip_id}/telegram", handler.PreviewProxyHandler(cfg.PythonCoreURL, "telegram"))
	// Epic #138 Issue #177: User-MetricPresets (+ #342 PATCH Read-Modify-Write)
	r.Get("/api/metric-presets", handler.ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", handler.CreateMetricPresetHandler(s))
	r.Patch("/api/metric-presets/{id}", handler.PatchMetricPresetHandler(s))
	r.Delete("/api/metric-presets/{id}", handler.DeleteMetricPresetHandler(s))
	// Issue #458: ComparePreset CRUD (List/Create/Update/Delete/Send-Stub)
	r.Get("/api/compare/presets", handler.ListComparePresetsHandler(s))
	r.Get("/api/compare/presets/{id}", handler.GetComparePresetHandler(s))
	r.Post("/api/compare/presets", handler.CreateComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", handler.UpdateComparePresetHandler(s))
	r.Patch("/api/compare/presets/{id}/state", handler.UpdateComparePresetStateHandler(s)) // Issue #611
	r.Delete("/api/compare/presets/{id}", handler.DeleteComparePresetHandler(s))
	r.Post("/api/compare/presets/{id}/send", handler.SendComparePresetHandler(s))
	// Issue #393: Cockpit-Kacheln — Versandstatus + Alarm-Historie (read-only Logs)
	r.Get("/api/cockpit/status", handler.CockpitStatusHandler(s))
	// Issue #396: Archiv-Statistiken — Briefings + Alarme pro Tour (Gesamtzahl, kein Zeitfilter)
	r.Get("/api/archive/stats", handler.ArchiveStatsHandler(s))

	// Scheduler
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		log.Fatalf("scheduler error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	r.Get("/api/scheduler/status", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.Status())
	})

	// Issue #252 (Adversary Finding 3): subscription names leak user intent and
	// must NOT be served by the public /api/scheduler/status endpoint. Expose
	// them via an authenticated route instead.
	r.Get("/api/scheduler/subscriptions-status", func(w http.ResponseWriter, r *http.Request) {
		userID := authmw.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"compare_subscriptions": sched.BuildCompareSubscriptionsStatus(userID),
		})
	})

	// Scheduler trigger proxies (frontend → Go → Python)
	r.Post("/api/scheduler/trip-reports", handler.ProxyPostHandler(cfg.PythonCoreURL, "/api/scheduler/trip-reports"))
	r.Post("/api/scheduler/morning-subscriptions", handler.ProxyPostHandler(cfg.PythonCoreURL, "/api/scheduler/morning-subscriptions"))
	r.Post("/api/scheduler/evening-subscriptions", handler.ProxyPostHandler(cfg.PythonCoreURL, "/api/scheduler/evening-subscriptions"))
	r.Post("/api/scheduler/alert-checks", handler.ProxyPostHandler(cfg.PythonCoreURL, "/api/scheduler/alert-checks"))
	r.Post("/api/scheduler/inbound-commands", handler.ProxyPostHandler(cfg.PythonCoreURL, "/api/scheduler/inbound-commands"))

	log.Printf("Go API listening on %s:%s, proxying to %s", cfg.Host, cfg.Port, cfg.PythonCoreURL)
	http.ListenAndServe(cfg.Host+":"+cfg.Port, r)
}
