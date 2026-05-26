package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
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

	r.Get("/api/health", handler.HealthHandler(cfg.PythonCoreURL))
	r.Get("/api/config", handler.ProxyHandler(cfg.PythonCoreURL, "/config"))
	r.Get("/api/metrics", handler.ProxyHandler(cfg.PythonCoreURL, "/metrics"))
	r.Get("/api/templates", handler.ProxyHandler(cfg.PythonCoreURL, "/templates"))
	r.Get("/api/forecast", handler.ForecastHandler(weatherProvider))
	r.Get("/api/locations", handler.LocationsHandler(s))
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
	r.Get("/api/subscriptions", handler.SubscriptionsHandler(s))
	r.Get("/api/subscriptions/{id}", handler.SubscriptionHandler(s))
	r.Post("/api/subscriptions", handler.CreateSubscriptionHandler(s))
	r.Put("/api/subscriptions/{id}", handler.UpdateSubscriptionHandler(s))
	r.Patch("/api/subscriptions/{id}/run-status", handler.PatchSubscriptionRunStatusHandler(s))
	r.Delete("/api/subscriptions/{id}", handler.DeleteSubscriptionHandler(s))
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
