package handler

// SMS-/Premium-SMS-Tageskontingent-Anzeige fuer /account — Issue #2412 S4b.
// Eigener Endpoint statt Einbettung in /api/auth/profile: das Profil wird auf
// JEDER Seite geladen, die Einbettung braeuchte dort einen Python-Roundtrip.

import (
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
)

func GetSmsDailyUsageHandler(cfg config.Config) http.HandlerFunc {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		target := cfg.PythonCoreURL + "/api/_internal/sms/daily-usage?user_id=" + url.QueryEscape(userId)
		resp, err := client.Get(target)
		if err != nil {
			// Fail-Soft: die Kontoseite laedt ohne diesen Block, nie 500.
			w.WriteHeader(http.StatusNoContent)
			return
		}
		defer resp.Body.Close()
		body, err := io.ReadAll(resp.Body)
		if err != nil || resp.StatusCode != http.StatusOK {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(body)
	}
}
