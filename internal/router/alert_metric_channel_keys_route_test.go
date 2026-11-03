package router

// TDD RED — Issue #1895 Scheibe S3a, AC-35 (und der Go-Teil von AC-39).
// Spec: docs/specs/modules/alert_metric_channels.md
//
// Ueber den ECHTEN Router (router.New inkl. AuthMiddleware, echte
// gz_session-Cookies): `GET /api/alert-metric-channel-keys` wird nur mit
// gueltiger Anmeldung an den Python-Core (`/alert-metric-channel-keys`)
// weitergereicht, ohne Anmeldung mit 401 abgelehnt — gleiche Auth-Gruppe wie
// `/api/metrics`. Zwei Nutzer bekommen dieselbe, nutzerunabhaengige Antwort.
//
// RED-Signal heute kommt aus dem ANGEMELDETEN Fall: die Route existiert nicht,
// der Core sieht nie `/alert-metric-channel-keys`. Der 401-Fall allein waere
// kein Nachweis (eine unbekannte Route kann ebenfalls 401 liefern), deshalb
// prueft der Test zusaetzlich, dass der Core den Pfad tatsaechlich empfaengt.

import (
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
)

type pfadRekorderCore struct {
	mu      sync.Mutex
	pfade   []string
	antwort string
}

func (c *pfadRekorderCore) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	c.mu.Lock()
	c.pfade = append(c.pfade, r.URL.Path)
	c.mu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(c.antwort))
}

func (c *pfadRekorderCore) gesehen() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return append([]string(nil), c.pfade...)
}

const amcKeysCoreAntwort = `{"keys":{"wind_gust":["gust"]},"accepted":["gust","snowfall_limit"]}`

func TestAlertMetricChannelKeysRoute_NurAngemeldetZumCore_AC35(t *testing.T) {
	core := &pfadRekorderCore{antwort: amcKeysCoreAntwort}
	srv := httptest.NewServer(core)
	t.Cleanup(srv.Close)
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, pythonZiel: srv.URL})

	// Ohne Anmeldung: 401, und der Core sieht nichts.
	ohne := httptest.NewRecorder()
	r.ServeHTTP(ohne, httptest.NewRequest(http.MethodGet, "/api/alert-metric-channel-keys", nil))
	if ohne.Code != http.StatusUnauthorized {
		t.Errorf("AC-35: ohne Anmeldung erwartet 401, bekam %d: %s", ohne.Code, ohne.Body.String())
	}
	if n := len(core.gesehen()); n != 0 {
		t.Fatalf("AC-35: ohne Anmeldung darf der Core nichts sehen, sah %v", core.gesehen())
	}

	// Mit Anmeldung, zwei Nutzer: 200, Core sieht genau den Zielpfad, beide
	// Antworten sind identisch (nutzerunabhaengig, AC-39).
	antworten := map[string]string{}
	for _, nutzer := range []string{"alice", "bob"} {
		w := proxyGet(t, r, "/api/alert-metric-channel-keys", sessionCookieFor(nutzer, secret))
		if w.Code != http.StatusOK {
			t.Errorf("AC-35 (%s): angemeldet erwartet 200, bekam %d: %s", nutzer, w.Code, w.Body.String())
		}
		antworten[nutzer] = w.Body.String()
	}

	gesehen := core.gesehen()
	if len(gesehen) != 2 {
		t.Fatalf("AC-35: der Core muss genau zwei angemeldete Aufrufe sehen, sah %v", gesehen)
	}
	for _, p := range gesehen {
		if p != "/alert-metric-channel-keys" {
			t.Errorf("AC-35: Proxy-Ziel muss /alert-metric-channel-keys sein, Core sah %q", p)
		}
	}
	if antworten["alice"] != amcKeysCoreAntwort || antworten["alice"] != antworten["bob"] {
		t.Errorf("AC-39: beide Nutzer muessen dieselbe Core-Antwort bekommen — alice=%q bob=%q",
			antworten["alice"], antworten["bob"])
	}
}

// Kontrolle (🟢 HEUTE GRUEN): `/api/metrics` liegt in derselben Auth-Gruppe —
// ohne Anmeldung 401. Haelt fest, dass der 401-Teil oben das Gruppenverhalten
// misst und nicht ein Zufallsverhalten des Routers.
func TestAlertMetricChannelKeysRoute_KontrolleMetricsGleicheAuthGruppe_AC35(t *testing.T) {
	core := &pfadRekorderCore{antwort: `{}`}
	srv := httptest.NewServer(core)
	t.Cleanup(srv.Close)
	r, _ := s2Router(t, s2Optionen{statusToken: s2Token, pythonZiel: srv.URL})

	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/api/metrics", nil))
	if w.Code != http.StatusUnauthorized {
		t.Errorf("Kontrolle: /api/metrics ohne Anmeldung erwartet 401, bekam %d", w.Code)
	}
}
