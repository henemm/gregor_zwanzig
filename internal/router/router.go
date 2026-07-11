package router

import (
	"os"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// Deps holds the dependencies required to build the application router.
type Deps struct {
	Config           *config.Config
	Store            *store.Store
	WeatherProvider  provider.WeatherProvider
	WebAuthn         *webauthn.WebAuthn
	ChallengeStore   *handler.ChallengeStore
	Scheduler        *scheduler.Scheduler
	TelegramTokenStore *handler.TelegramTokenStore
	GitCommit        string
}

// New builds the chi router with all application routes.
// It does not start the scheduler or the HTTP server.
func New(deps Deps) chi.Router {
	r := chi.NewRouter()
	r.Use(chimw.Logger)
	r.Use(authmw.AuthMiddleware(deps.Config.SessionSecret))

	// Auth endpoints (register/login exempt from AuthMiddleware)
	// Rate-limit register: 5 attempts per IP per hour (Issue #117).
	registerLimiter := authmw.NewIPRateLimiter(5, time.Hour)
	r.Post("/api/auth/register",
		registerLimiter.Middleware(handler.RegisterHandler(deps.Store, bcrypt.DefaultCost)).ServeHTTP,
	)
	loginLimiter := authmw.NewIPRateLimiter(30, time.Hour)
	r.Post("/api/auth/login",
		loginLimiter.Middleware(handler.LoginHandler(deps.Store, deps.Config.SessionSecret)).ServeHTTP,
	)
	r.Post("/api/auth/logout", handler.LogoutHandler())
	forgotLimiter := authmw.NewIPRateLimiter(5, time.Hour)
	r.Post("/api/auth/forgot-password",
		forgotLimiter.Middleware(handler.ForgotPasswordHandler(deps.Store, bcrypt.DefaultCost, *deps.Config)).ServeHTTP,
	)
	resetLimiter := authmw.NewIPRateLimiter(10, time.Hour)
	r.Post("/api/auth/reset-password",
		resetLimiter.Middleware(handler.ResetPasswordHandler(deps.Store, bcrypt.DefaultCost)).ServeHTTP,
	)
	r.Delete("/api/auth/account", handler.DeleteAccountHandler(deps.Store))
	r.Get("/api/auth/profile", handler.GetProfileHandler(deps.Store))
	r.Put("/api/auth/profile", handler.UpdateProfileHandler(deps.Store, *deps.Config))
	r.Put("/api/auth/password", handler.ChangePasswordHandler(deps.Store, bcrypt.DefaultCost))
	// Issue #1071 — Level-Änderungs-Antrag (authentifiziert, NICHT in Public-Allowlist)
	r.Post("/api/auth/tier-change-request", handler.RequestTierChangeHandler(deps.Store, *deps.Config))
	// Bug #590: Telegram /start-Flow — link generation + status polling + internal connect
	r.Get("/api/auth/telegram-link", handler.GetTelegramLinkHandler(deps.Store, deps.TelegramTokenStore))
	r.Get("/api/auth/telegram-status", handler.GetTelegramStatusHandler(deps.Store))
	r.Post("/api/internal/telegram-connect", handler.PostTelegramConnectHandler(deps.Store, deps.TelegramTokenStore))
	// Issue #637: Telegram Inbound Webhook (public, secret-header-protected)
	r.Post("/api/webhooks/telegram/{secret}", handler.TelegramWebhookHandler(deps.Config.PythonCoreURL))
	r.Get("/api/auth/google/init", handler.GoogleOAuthInitHandler(deps.Config))
	r.Get("/api/auth/google/callback", handler.GoogleOAuthCallbackHandler(deps.Config, deps.Store))
	magicLinkLimiter := authmw.NewIPRateLimiter(5, 15*time.Minute)
	r.Post("/api/auth/magic-link",
		magicLinkLimiter.Middleware(handler.MagicLinkRequestHandler(deps.Store, deps.Config)).ServeHTTP,
	)
	magicVerifyLimiter := authmw.NewIPRateLimiter(10, 15*time.Minute)
	r.Post("/api/auth/magic-link/verify",
		magicVerifyLimiter.Middleware(handler.MagicLinkVerifyHandler(deps.Store, deps.Config)).ServeHTTP,
	)

	// Issue #450 — Passkey/WebAuthn endpoints
	passkeyLimiter := authmw.NewIPRateLimiter(30, time.Hour)
	// Public endpoints (exempted in middleware.AuthMiddleware)
	r.Post("/api/auth/passkey/login/begin",
		passkeyLimiter.Middleware(handler.PasskeyLoginBeginHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/login/finish",
		passkeyLimiter.Middleware(handler.PasskeyLoginFinishHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore, deps.Config.SessionSecret)).ServeHTTP,
	)
	// Issue #467 — Discoverable Credentials + Conditional UI (public)
	r.Post("/api/auth/passkey/discoverable/begin",
		passkeyLimiter.Middleware(handler.PasskeyLoginDiscoverableBeginHandler(deps.WebAuthn, deps.ChallengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/discoverable/finish",
		passkeyLimiter.Middleware(handler.PasskeyLoginDiscoverableFinishHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore, deps.Config.SessionSecret)).ServeHTTP,
	)
	// Authenticated endpoints (cookie required via AuthMiddleware)
	r.Post("/api/auth/passkey/register/begin",
		passkeyLimiter.Middleware(handler.PasskeyRegisterBeginHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/register/finish",
		passkeyLimiter.Middleware(handler.PasskeyRegisterFinishHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore)).ServeHTTP,
	)
	r.Delete("/api/auth/passkey/credentials/{id}",
		passkeyLimiter.Middleware(handler.PasskeyDeleteCredentialHandler(deps.Store)).ServeHTTP,
	)
	passkeyRegPubLimiter := authmw.NewIPRateLimiter(5, time.Hour)
	r.Post("/api/auth/passkey/register/public/begin",
		passkeyRegPubLimiter.Middleware(handler.PasskeyRegisterPublicBeginHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore)).ServeHTTP,
	)
	r.Post("/api/auth/passkey/register/public/finish",
		passkeyRegPubLimiter.Middleware(handler.PasskeyRegisterPublicFinishHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore, deps.Config.SessionSecret)).ServeHTTP,
	)

	r.Get("/api/health", handler.HealthHandler(deps.Config.PythonCoreURL, deps.GitCommit))
	r.Get("/api/config", handler.ProxyHandler(deps.Config.PythonCoreURL, "/config"))
	r.Get("/api/metrics", handler.ProxyHandler(deps.Config.PythonCoreURL, "/metrics"))
	r.Get("/api/templates", handler.ProxyHandler(deps.Config.PythonCoreURL, "/templates"))
	r.Get("/api/forecast", handler.ForecastHandler(deps.WeatherProvider))
	r.Get("/api/locations", handler.LocationsHandler(deps.Store))
	r.Get("/api/locations/{id}", handler.LocationHandler(deps.Store))
	r.Post("/api/locations/resolve", handler.ResolveLocationHandler())
	r.Post("/api/locations", handler.CreateLocationHandler(deps.Store))
	r.Put("/api/locations/{id}", handler.UpdateLocationHandler(deps.Store))
	r.Patch("/api/locations/{id}", handler.PatchLocationHandler(deps.Store))
	r.Delete("/api/locations/{id}", handler.DeleteLocationHandler(deps.Store))
	r.Get("/api/groups", handler.GroupsHandler(deps.Store))
	r.Post("/api/groups", handler.CreateGroupHandler(deps.Store))
	r.Patch("/api/groups/{id}", handler.UpdateGroupHandler(deps.Store))
	r.Delete("/api/groups/{id}", handler.DeleteGroupHandler(deps.Store))
	r.Get("/api/trips", handler.TripsHandler(deps.Store))
	r.Get("/api/trips/{id}", handler.TripHandler(deps.Store))
	r.Post("/api/trips", handler.CreateTripHandler(deps.Store))
	r.Put("/api/trips/{id}", handler.UpdateTripHandler(deps.Store))
	r.Patch("/api/trips/{id}/state", handler.UpdateTripStateHandler(deps.Store))
	r.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", handler.ConfirmWaypointHandler(deps.Store))
	r.Delete("/api/trips/{id}", handler.DeleteTripHandler(deps.Store))
	r.Get("/api/trips/{id}/stages/weather", handler.StagesWeatherProxyHandler(deps.Config.PythonCoreURL))
	r.Get("/api/trips/{id}/briefing-history", handler.BriefingHistoryHandler(deps.Store))
	r.Get("/api/subscriptions", handler.SubscriptionsHandler(deps.Store))
	r.Get("/api/subscriptions/{id}", handler.SubscriptionHandler(deps.Store))
	r.Post("/api/subscriptions", handler.CreateSubscriptionHandler(deps.Store))
	r.Put("/api/subscriptions/{id}", handler.UpdateSubscriptionHandler(deps.Store))
	r.Patch("/api/subscriptions/{id}/run-status", handler.PatchSubscriptionRunStatusHandler(deps.Store))
	r.Delete("/api/subscriptions/{id}", handler.DeleteSubscriptionHandler(deps.Store))
	// Issue #456 — Manueller Versand-Trigger fuer eine einzelne Subscription
	r.Post("/api/subscriptions/{id}/send", handler.SendSubscriptionProxyHandler(deps.Config.PythonCoreURL))
	r.Get("/api/trips/{id}/weather-config", handler.GetTripWeatherConfigHandler(deps.Store))
	r.Put("/api/trips/{id}/weather-config", handler.PutTripWeatherConfigHandler(deps.Store))
	r.Get("/api/locations/{id}/weather-config", handler.GetLocationWeatherConfigHandler(deps.Store))
	r.Put("/api/locations/{id}/weather-config", handler.PutLocationWeatherConfigHandler(deps.Store))
	r.Get("/api/subscriptions/{id}/weather-config", handler.GetSubscriptionWeatherConfigHandler(deps.Store))
	r.Put("/api/subscriptions/{id}/weather-config", handler.PutSubscriptionWeatherConfigHandler(deps.Store))
	r.Post("/api/gpx/parse", handler.GpxProxyHandler(deps.Config.PythonCoreURL))
	r.Post("/api/notify/test", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/notify/test"))
	r.Get("/api/compare", handler.CompareProxyHandler(deps.Config.PythonCoreURL))
	r.Get("/api/_internal/trip/{id}/loaded", handler.LoadedTripProxyHandler(deps.Config.PythonCoreURL))
	// Issue #221: External Validator observability endpoints (cookie-auth via global middleware).
	r.Get("/api/_validator/format-metric", handler.ValidatorFormatMetricProxyHandler(deps.Config.PythonCoreURL))
	r.Get("/api/_validator/detector-thresholds", handler.DetectorThresholdsProxyHandler(deps.Config.PythonCoreURL))
	r.Get("/api/_validator/metrics-for-channel", handler.MetricsForChannelProxyHandler(deps.Config.PythonCoreURL))
	r.Post("/api/_validator/compare-email-preview", handler.CompareEmailPreviewProxyHandler(deps.Config.PythonCoreURL))
	r.Post("/api/trips/{id}/send", handler.SendTripReportProxyHandler(deps.Config.PythonCoreURL))
	r.Post("/api/trips/{id}/alert-preview", handler.AlertPreviewProxyHandler(deps.Config.PythonCoreURL))
	// Issue #140 / #189: Output-Vorschau Email + SMS
	r.Get("/api/preview/{trip_id}/email", handler.PreviewProxyHandler(deps.Config.PythonCoreURL, "email"))
	r.Get("/api/preview/{trip_id}/sms", handler.PreviewProxyHandler(deps.Config.PythonCoreURL, "sms"))
	// Issue #363: Signal/Telegram-Vorschau (kanal-bewusster Narrow-Renderer #360)
	r.Get("/api/preview/{trip_id}/signal", handler.PreviewProxyHandler(deps.Config.PythonCoreURL, "signal"))
	r.Get("/api/preview/{trip_id}/telegram", handler.PreviewProxyHandler(deps.Config.PythonCoreURL, "telegram"))
	// Epic #138 Issue #177: User-MetricPresets (+ #342 PATCH Read-Modify-Write)
	r.Get("/api/metric-presets", handler.ListMetricPresetsHandler(deps.Store))
	r.Post("/api/metric-presets", handler.CreateMetricPresetHandler(deps.Store))
	r.Patch("/api/metric-presets/{id}", handler.PatchMetricPresetHandler(deps.Store))
	r.Delete("/api/metric-presets/{id}", handler.DeleteMetricPresetHandler(deps.Store))
	// Issue #458: ComparePreset CRUD (List/Create/Update/Delete/Send-Stub)
	r.Get("/api/compare/presets", handler.ListComparePresetsHandler(deps.Store))
	r.Get("/api/compare/presets/{id}", handler.GetComparePresetHandler(deps.Store))
	r.Post("/api/compare/presets", handler.CreateComparePresetHandler(deps.Store))
	r.Put("/api/compare/presets/{id}", handler.UpdateComparePresetHandler(deps.Store))
	r.Patch("/api/compare/presets/{id}/state", handler.UpdateComparePresetStateHandler(deps.Store)) // Issue #611
	r.Delete("/api/compare/presets/{id}", handler.DeleteComparePresetHandler(deps.Store))
	r.Post("/api/compare/presets/{id}/send", handler.SendComparePresetHandler(deps.Config.PythonCoreURL))
	// Issue #393: Cockpit-Kacheln — Versandstatus + Alarm-Historie (read-only Logs)
	r.Get("/api/cockpit/status", handler.CockpitStatusHandler(deps.Store))
	// Issue #396: Archiv-Statistiken — Briefings + Alarme pro Tour (Gesamtzahl, kein Zeitfilter)
	r.Get("/api/archive/stats", handler.ArchiveStatsHandler(deps.Store))

	// Scheduler status endpoints
	r.Get("/api/scheduler/status", handler.SchedulerStatusHandler(deps.Scheduler))
	r.Get("/api/scheduler/subscriptions-status", handler.SchedulerSubscriptionsStatusHandler(deps.Scheduler))

	// Issue #830 — Staging-only: Debug-Trigger-Endpoint fuer Radar-Alert-Mail-Tests
	if os.Getenv("GZ_ENV") == "staging" {
		r.Post("/api/debug/trigger-radar-alert", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/debug/trigger-radar-alert"))
	}

	// Scheduler trigger proxies (frontend → Go → Python)
	r.Post("/api/scheduler/trip-reports", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/scheduler/trip-reports"))
	r.Post("/api/scheduler/morning-subscriptions", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/scheduler/morning-subscriptions"))
	r.Post("/api/scheduler/evening-subscriptions", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/scheduler/evening-subscriptions"))
	r.Post("/api/scheduler/alert-checks", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/scheduler/alert-checks"))
	r.Post("/api/scheduler/inbound-commands", handler.ProxyPostHandler(deps.Config.PythonCoreURL, "/api/scheduler/inbound-commands"))

	return r
}
