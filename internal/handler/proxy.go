package handler

import (
	"encoding/json"
	"io"
	"net/http"
	"time"
)

const version = "0.1.0"

func HealthHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 2 * time.Second}
		pythonStatus := "ok"

		resp, err := client.Get(pythonURL + "/health")
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
}

func ProxyHandler(pythonURL, path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 10 * time.Second}

		url := pythonURL + path
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
}
