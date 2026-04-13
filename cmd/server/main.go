package main

import (
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/store"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	s := store.New(cfg.DataDir, cfg.UserID)

	r := chi.NewRouter()
	r.Use(middleware.Logger)

	r.Get("/api/health", handler.HealthHandler(cfg.PythonCoreURL))
	r.Get("/api/config", handler.ProxyHandler(cfg.PythonCoreURL, "/config"))
	r.Get("/api/forecast", handler.ProxyHandler(cfg.PythonCoreURL, "/forecast"))
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
