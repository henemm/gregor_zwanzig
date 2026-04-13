package main

import (
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/provider/openmeteo"
	"github.com/henemm/gregor-api/internal/store"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	s := store.New(cfg.DataDir, cfg.UserID)

	omProvider := openmeteo.NewProvider(openmeteo.ProviderConfig{
		BaseURL:    cfg.OpenMeteoBaseURL,
		AQURL:      cfg.OpenMeteoAQURL,
		TimeoutSec: cfg.OpenMeteoTimeout,
		Retries:    cfg.OpenMeteoRetries,
		CacheDir:   cfg.CacheDir,
	})

	r := chi.NewRouter()
	r.Use(chimw.Logger)
	r.Use(authmw.AuthMiddleware(cfg.SessionSecret))

	r.Get("/api/health", handler.HealthHandler(cfg.PythonCoreURL))
	r.Get("/api/config", handler.ProxyHandler(cfg.PythonCoreURL, "/config"))
	r.Get("/api/forecast", handler.ForecastHandler(omProvider))
	r.Get("/api/locations", handler.LocationsHandler(s))
	r.Post("/api/locations", handler.CreateLocationHandler(s))
	r.Put("/api/locations/{id}", handler.UpdateLocationHandler(s))
	r.Delete("/api/locations/{id}", handler.DeleteLocationHandler(s))
	r.Get("/api/trips", handler.TripsHandler(s))
	r.Get("/api/trips/{id}", handler.TripHandler(s))
	r.Post("/api/trips", handler.CreateTripHandler(s))
	r.Put("/api/trips/{id}", handler.UpdateTripHandler(s))
	r.Delete("/api/trips/{id}", handler.DeleteTripHandler(s))

	log.Printf("Go API listening on :%s, proxying to %s", cfg.Port, cfg.PythonCoreURL)
	http.ListenAndServe(":"+cfg.Port, r)
}
