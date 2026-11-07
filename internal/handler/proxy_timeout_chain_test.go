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
		// Issue #2280 AC-14: der neue Dispatcher laeuft ueber dieselbe Grenze.
		{"Dispatcher route", "/api/briefings/{id}/send", "/api/briefings/t-2280/send?kind=route", BriefingSendHandler(py.URL)},
		{"Dispatcher vergleich", "/api/briefings/{id}/send", "/api/briefings/cp-2280/send?kind=vergleich", BriefingSendHandler(py.URL)},
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

// ── Issue #1839 (AC-1, AC-2): Vorschau-Zeitgrenze 120 s statt 30 s ─────────
//
// Spec: docs/specs/modules/fix_1839_trip_vorschau_kalt.md
//
// Vom Developer exakt so zu implementieren (package handler):
//   var previewProxyTimeout = 120 * time.Second   // vorher const 30 s
//
// RED heute: `previewProxyTimeout` ist `const` -> die Zuweisung unten ist ein
// Compile-Fehler (gueltiges RED, wie bei #2124).

type previewHandlerFall struct {
	name, method, pattern, path string
	h                           http.HandlerFunc
}

func previewHandlerFaelle(pyURL string) []previewHandlerFall {
	return []previewHandlerFall{
		{"SMS-Vorschau", http.MethodGet, "/api/preview/{trip_id}/sms", "/api/preview/t-1839/sms", PreviewProxyHandler(pyURL, "sms")},
		{"Trip-Alarm-Vorschau", http.MethodPost, "/api/trips/{id}/alert-preview", "/api/trips/t-1839/alert-preview", AlertPreviewProxyHandler(pyURL)},
		{"Briefing-Alarm-Vorschau route", http.MethodPost, "/api/briefings/{id}/alert-preview", "/api/briefings/t-1839/alert-preview?kind=route", BriefingAlertPreviewHandler(pyURL)},
		{"Briefing-Alarm-Vorschau vergleich", http.MethodPost, "/api/briefings/{id}/alert-preview", "/api/briefings/cp-1839/alert-preview?kind=vergleich", BriefingAlertPreviewHandler(pyURL)},
	}
}

// AC-1 (Wirkort): eine Antwort, die vor der Grenze kommt, geht durch (kein 502).
func TestTimeoutChain_PreviewHandlersWaitForSlowUpstreamWithinTimeout(t *testing.T) {
	orig := previewProxyTimeout
	previewProxyTimeout = 1 * time.Second
	t.Cleanup(func() { previewProxyTimeout = orig })

	py := startSlowUpstream(t, 100*time.Millisecond)
	for _, c := range previewHandlerFaelle(py.URL) {
		code, _ := serveTimed(c.h, c.method, c.pattern, c.path)
		if code != http.StatusOK {
			t.Errorf("%s: Status %d, erwartet 200 (Antwort kommt vor previewProxyTimeout)", c.name, code)
		}
	}
}

// AC-1 (Wirkort): erst NACH der Grenze entsteht der 502.
func TestTimeoutChain_PreviewHandlersHonourPreviewProxyTimeout(t *testing.T) {
	orig := previewProxyTimeout
	previewProxyTimeout = 100 * time.Millisecond
	t.Cleanup(func() { previewProxyTimeout = orig })

	py := startSlowUpstream(t, 2*time.Second)
	for _, c := range previewHandlerFaelle(py.URL) {
		code, took := serveTimed(c.h, c.method, c.pattern, c.path)
		if code != http.StatusBadGateway || took > time.Second {
			t.Errorf("%s ignoriert previewProxyTimeout: Status %d nach %v (erwartet 502 nach ~100ms)",
				c.name, code, took)
		}
	}
}

func TestTimeoutChain_PreviewProxyTimeoutIs120Seconds(t *testing.T) {
	if previewProxyTimeout != 120*time.Second {
		t.Errorf("previewProxyTimeout = %v, erwartet 120s (#1839, gleich stagesWeatherProxyTimeout)",
			previewProxyTimeout)
	}
}

// AC-2: Vorschau-Grenze unter nginx, mit mindestens 30 s Puffer.
func TestTimeoutChain_PreviewProxyTimeoutBelowNginxWithBuffer(t *testing.T) {
	if previewProxyTimeout >= nginxProxyReadTimeout {
		t.Errorf("previewProxyTimeout = %v ist nicht kleiner als nginxProxyReadTimeout = %v",
			previewProxyTimeout, nginxProxyReadTimeout)
	}
	if nginxProxyReadTimeout-previewProxyTimeout < 30*time.Second {
		t.Errorf("Puffer nginx - previewProxyTimeout = %v, erwartet >= 30s",
			nginxProxyReadTimeout-previewProxyTimeout)
	}
}
