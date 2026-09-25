package handler

// TDD RED — SMS-/Premium-SMS-Tageskontingent im Account sichtbar (S4b,
// Sammel-Issue #2153, Einzel-Issue #2412, Epic #2138).
// Spec: docs/specs/modules/sms_daily_usage_anzeige.md — AC-4, AC-5.
//
// `GetSmsDailyUsageHandler` existiert noch nicht -> Compile-Fehler heute.
// Sobald die Funktion angelegt ist, bleiben diese beiden Faelle rot, bis das
// Fail-Soft- und das Mandantentrennungs-Verhalten implementiert sind.

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
)

// AC-5: der Python-Core ist nicht erreichbar (echter, absichtlich
// geschlossener httptest.Server -- kein Mock des HTTP-Clients) -> der
// Handler antwortet 204, nie 500, damit die Kontoseite ansonsten unveraendert
// laedt.
func TestGetSmsDailyUsageHandlerFailsSoftWhenPythonCoreUnreachable(t *testing.T) {
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	py.Close() // sofort schliessen: echter Server, aber nicht erreichbar

	cfg := config.Config{PythonCoreURL: py.URL}
	h := GetSmsDailyUsageHandler(cfg)

	req := httptest.NewRequest("GET", "/api/auth/sms-daily-usage", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "sms-daily-usage-ac5")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()

	h.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("AC-5: Python-Core unerreichbar erwartet %d, bekommen %d: %s",
			http.StatusNoContent, w.Code, w.Body.String())
	}
}

// AC-4 / Mandantentrennung: die `user_id` MUSS aus dem Auth-Kontext kommen,
// niemals aus Query oder Body -- ein Angreifer, der eine fremde `user_id` im
// Query-String unterschiebt, darf damit nicht das Konto eines anderen
// Nutzers abfragen.
func TestGetSmsDailyUsageHandlerUsesContextUserIdNeverQuery(t *testing.T) {
	var empfangeneUserId string
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		empfangeneUserId = r.URL.Query().Get("user_id")
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"sms":{"used":0,"limit":10,"reserve":2},"premium_sms":{"used":0,"limit":0,"reserve":3,"reply_overshoot":3}}`))
	}))
	defer py.Close()

	cfg := config.Config{PythonCoreURL: py.URL}
	h := GetSmsDailyUsageHandler(cfg)

	echterNutzer := "sms-daily-usage-echt"
	fremderQueryWert := "sms-daily-usage-fremd"

	req := httptest.NewRequest("GET", "/api/auth/sms-daily-usage?user_id="+url.QueryEscape(fremderQueryWert), nil)
	ctx := middleware.ContextWithUserID(req.Context(), echterNutzer)
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()

	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if empfangeneUserId != echterNutzer {
		t.Fatalf("Mandantentrennung: der Python-Core-Aufruf muss die Auth-Kontext-user_id %q tragen, bekommen %q (Query-Wert waere %q gewesen)",
			echterNutzer, empfangeneUserId, fremderQueryWert)
	}
}
