package handler

// TDD RED — Issue #2124 AC-6 + AC-9: Zeitgrenzen-Kette Go-Client < nginx.
//
// Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md (AC-6, AC-9)
//
// Die Kette muss widerspruchsfrei sein: Python-Lauf < Go-Client (300 s) <
// nginx proxy_read_timeout (330 s). Der effektive http.Client.Timeout eines
// Handlers ist ohne Produktiv-Refactor nicht beobachtbar (Client wird im
// Handler-Body gebaut); die Spec erlaubt ausdruecklich die Pruefung ueber
// benannte Konstanten.
//
// EHRLICH (Spec AC-6): Dieser Test schuetzt nur die Go-Seite. Eine geloeschte
// vhost-Zeile in henemm-infra macht ihn NICHT rot — den Nachweis liefert AC-7
// auf Staging (`sudo nginx -T`).
//
// Vom Developer exakt so zu implementieren (package handler):
//   var   sendProxyTimeout          = 300 * time.Second  // Trip- UND Compare-Versand
//   const nginxProxyReadTimeout     = 330 * time.Second  // Spiegel der vhost-Zeile
//   var   stagesWeatherProxyTimeout = 120 * time.Second  // StagesWeatherProxyHandler
//
// `sendProxyTimeout` und `stagesWeatherProxyTimeout` sind bewusst Paket-`var`
// (nicht `const`): nur so kann ein Test sie kurz herabsetzen und beobachten,
// dass die Handler den Wert TATSAECHLICH als http.Client.Timeout verwenden
// (Zusicherung dort pruefen, wo sie wirkt — sonst koennte ein Handler den
// Literal-Wert behalten und alle Konstanten-Tests blieben gruen).
//
// RED heute: die Symbole existieren nicht -> Compile-Fehler (gueltiges RED).

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// startSlowUpstream antwortet erst nach `delay` mit 200 (oder bricht ab,
// sobald der Proxy die Verbindung schliesst).
func startSlowUpstream(t *testing.T, delay time.Duration) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-time.After(delay):
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"ok"}`))
		case <-r.Context().Done():
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func serveTimed(h http.HandlerFunc, method, pattern, path string) (int, time.Duration) {
	router := chi.NewRouter()
	router.Method(method, pattern, h)
	req := httptest.NewRequest(method, path, nil).WithContext(
		middleware.ContextWithUserID(context.Background(), "alice"))
	rec := httptest.NewRecorder()
	start := time.Now()
	router.ServeHTTP(rec, req)
	return rec.Code, time.Since(start)
}

// AC-6 (Wirkort): Trip- UND Compare-Sende-Handler nutzen sendProxyTimeout
// als effektiven Client-Timeout.
func TestTimeoutChain_BothSendHandlersHonourSendProxyTimeout(t *testing.T) {
	orig := sendProxyTimeout
	sendProxyTimeout = 100 * time.Millisecond
	t.Cleanup(func() { sendProxyTimeout = orig })

	py := startSlowUpstream(t, 2*time.Second)

	cases := []struct {
		name, pattern, path string
		h                   http.HandlerFunc
	}{
		{"Trip", "/api/trips/{id}/send", "/api/trips/t-2124/send?report_type=evening", SendTripReportProxyHandler(py.URL)},
		{"Compare", "/api/compare/presets/{id}/send", "/api/compare/presets/cp-2124/send", SendComparePresetHandler(py.URL)},
	}
	for _, c := range cases {
		code, took := serveTimed(c.h, http.MethodPost, c.pattern, c.path)
		if code != http.StatusBadGateway || took > time.Second {
			t.Errorf("%s-Sende-Handler ignoriert sendProxyTimeout: Status %d nach %v "+
				"(erwartet 502 nach ~100ms)", c.name, code, took)
		}
	}
}

// AC-9 (Wirkort): StagesWeatherProxyHandler nutzt stagesWeatherProxyTimeout.
func TestTimeoutChain_StagesWeatherHandlerHonoursItsTimeout(t *testing.T) {
	orig := stagesWeatherProxyTimeout
	stagesWeatherProxyTimeout = 100 * time.Millisecond
	t.Cleanup(func() { stagesWeatherProxyTimeout = orig })

	py := startSlowUpstream(t, 2*time.Second)
	code, took := serveTimed(StagesWeatherProxyHandler(py.URL), http.MethodGet,
		"/api/trips/{id}/stages/weather", "/api/trips/t-2124/stages/weather")
	if code != http.StatusBadGateway || took > time.Second {
		t.Errorf("StagesWeatherProxyHandler ignoriert stagesWeatherProxyTimeout: Status %d nach %v "+
			"(erwartet 502 nach ~100ms)", code, took)
	}
}

func TestTimeoutChain_SendProxyTimeoutIs300Seconds(t *testing.T) {
	if sendProxyTimeout != 300*time.Second {
		t.Errorf("sendProxyTimeout = %v, erwartet 300s (gemeinsam fuer Trip- und Compare-Versand)",
			sendProxyTimeout)
	}
}

func TestTimeoutChain_NginxProxyReadTimeoutIs330Seconds(t *testing.T) {
	if nginxProxyReadTimeout != 330*time.Second {
		t.Errorf("nginxProxyReadTimeout = %v, erwartet 330s (Spiegel von proxy_read_timeout in henemm-infra)",
			nginxProxyReadTimeout)
	}
}

func TestTimeoutChain_EveryProxyTimeoutBelowNginx(t *testing.T) {
	proxyTimeouts := map[string]time.Duration{
		"sendProxyTimeout":          sendProxyTimeout,
		"stagesWeatherProxyTimeout": stagesWeatherProxyTimeout,
	}
	for name, d := range proxyTimeouts {
		if d >= nginxProxyReadTimeout {
			t.Errorf("%s = %v ist nicht kleiner als nginxProxyReadTimeout = %v — nginx wuerde "+
				"vor dem Go-Client abbrechen und 504 liefern", name, d, nginxProxyReadTimeout)
		}
	}
	// Puffer: nginx muss den Go-Fehlerpfad (502 nach Client-Timeout) noch
	// durchreichen koennen, statt selbst vorher abzubrechen.
	if nginxProxyReadTimeout-sendProxyTimeout < 30*time.Second {
		t.Errorf("Puffer nginx - sendProxyTimeout = %v, erwartet >= 30s",
			nginxProxyReadTimeout-sendProxyTimeout)
	}
}

// AC-9: Wetterabruf wartet laenger als die alte 60-s-Grenze, bleibt aber unter nginx.
func TestTimeoutChain_StagesWeatherAbove60sBelowNginx(t *testing.T) {
	if stagesWeatherProxyTimeout <= 60*time.Second {
		t.Errorf("stagesWeatherProxyTimeout = %v, erwartet > 60s (alte Grenze, 502 am 30.08.)",
			stagesWeatherProxyTimeout)
	}
	if stagesWeatherProxyTimeout >= nginxProxyReadTimeout {
		t.Errorf("stagesWeatherProxyTimeout = %v, erwartet < nginxProxyReadTimeout (%v)",
			stagesWeatherProxyTimeout, nginxProxyReadTimeout)
	}
}
