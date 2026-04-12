package main

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

const version = "0.1.0"

var pythonCoreURL string

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func setupRouter(pythonURL string) *chi.Mux {
	pythonCoreURL = pythonURL

	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Get("/api/health", healthHandler)
	r.Get("/api/config", configHandler)
	r.Get("/api/forecast", forecastHandler)
	return r
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	client := &http.Client{Timeout: 2 * time.Second}
	pythonStatus := "ok"

	resp, err := client.Get(pythonCoreURL + "/health")
	if err != nil || resp.StatusCode != 200 {
		pythonStatus = "unavailable"
	}
	if resp != nil {
		resp.Body.Close()
	}

	status := "ok"
	if pythonStatus == "unavailable" {
		status = "degraded"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":      status,
		"version":     version,
		"python_core": pythonStatus,
	})
}

func proxyToPython(w http.ResponseWriter, r *http.Request, path string) {
	client := &http.Client{Timeout: 10 * time.Second}

	url := pythonCoreURL + path
	if r.URL.RawQuery != "" {
		url += "?" + r.URL.RawQuery
	}

	resp, err := client.Get(url)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(503)
		w.Write([]byte(`{"error":"core_unavailable"}`))
		return
	}
	defer resp.Body.Close()

	for k, vals := range resp.Header {
		for _, v := range vals {
			w.Header().Set(k, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func configHandler(w http.ResponseWriter, r *http.Request) {
	proxyToPython(w, r, "/config")
}

func forecastHandler(w http.ResponseWriter, r *http.Request) {
	proxyToPython(w, r, "/forecast")
}

func main() {
	pythonURL := envOrDefault("PYTHON_CORE_URL", "http://localhost:8000")
	port := envOrDefault("PORT", "8090")

	r := setupRouter(pythonURL)

	log.Printf("Go API listening on :%s, proxying to %s", port, pythonURL)
	http.ListenAndServe(":"+port, r)
}
