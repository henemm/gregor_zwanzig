package router

// TDD RED: Issue #1814 — Telegram-Webhook ohne Secret im URL-Pfad.
// Spec: docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md
//
// AC-3: POST /api/webhooks/telegram/inbound mit korrektem Header -> 200 + Weiterreichung,
//       ueber den ECHTEN Router inkl. AuthMiddleware, ohne Sitzungs-Cookie.
// AC-4: fehlender/falscher Header -> derselbe Status wie auf der Alt-Route, kein Forwarding.
// AC-5: Alt-Route /{beliebiges-Segment} bleibt bis zur Folge-Scheibe erreichbar.
// AC-6: zwei Chats (zwei Nutzer) -> Zuordnung (Body) identisch ueber beide Routen.
//
// RED-Signal heute: /inbound ist nur ueber die Param-Route {secret} erreichbar;
// die Param-Route akzeptiert ihn ebenfalls -- daher wird zusaetzlich geprueft, dass
// die neue Adresse als EIGENE statische Route registriert ist (kein Param-Treffer).
// Kein t.Parallel() (t.Setenv).

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/go-chi/chi/v5"
)

const tgHeader = "X-Telegram-Bot-Api-Secret-Token"

type tgCore struct {
	mu     sync.Mutex
	bodies []string
}

func (c *tgCore) handler(w http.ResponseWriter, r *http.Request) {
	b, _ := io.ReadAll(r.Body)
	c.mu.Lock()
	c.bodies = append(c.bodies, string(b))
	c.mu.Unlock()
	w.WriteHeader(http.StatusOK)
}

func (c *tgCore) snapshot() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return append([]string(nil), c.bodies...)
}

func tgRouter(t *testing.T) (http.Handler, *tgCore) {
	t.Helper()
	t.Setenv("TELEGRAM_WEBHOOK_SECRET", "tg-geheim-1814")
	core := &tgCore{}
	srv := httptest.NewServer(http.HandlerFunc(core.handler))
	t.Cleanup(srv.Close)
	r, _ := s2Router(t, s2Optionen{statusToken: s2Token, pythonZiel: srv.URL})
	return r, core
}

func tgPost(r http.Handler, pfad, body, header string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, pfad, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if header != "" {
		req.Header.Set(tgHeader, header)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req) // bewusst OHNE gz_session-Cookie
	return w
}

// AC-3 + AC-6: korrekter Header, zwei Chats, beide Routen -> gleiche Weiterreichung.
func TestTelegramInbound_KorrekterHeader_200UndWeiterreichung_BeideRoutenGleich(t *testing.T) {
	r, core := tgRouter(t)
	alice := `{"update_id":1,"message":{"chat":{"id":1001},"text":"status"}}`
	bob := `{"update_id":2,"message":{"chat":{"id":2002},"text":"status"}}`

	for _, pfad := range []string{"/api/webhooks/telegram/inbound", "/api/webhooks/telegram/altes-segment"} {
		for _, body := range []string{alice, bob} {
			w := tgPost(r, pfad, body, "tg-geheim-1814")
			if w.Code != http.StatusOK {
				t.Fatalf("POST %s: erwartet 200, bekam %d: %s", pfad, w.Code, w.Body.String())
			}
		}
	}
	got := core.snapshot()
	want := []string{alice, bob, alice, bob}
	if len(got) != len(want) {
		t.Fatalf("Python-Core sah %d Updates, erwartet %d: %v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Update %d: Zuordnung/Body verschoben: %q != %q", i, got[i], want[i])
		}
	}
}

// AC-4: fehlender/falscher Header auf /inbound -> gleicher Status wie Alt-Route, kein Forwarding.
func TestTelegramInbound_FalscherOderFehlenderHeader_GleicherStatusWieAltRoute_KeinForwarding(t *testing.T) {
	r, core := tgRouter(t)
	for _, header := range []string{"", "falsch"} {
		neu := tgPost(r, "/api/webhooks/telegram/inbound", `{"update_id":9}`, header)
		alt := tgPost(r, "/api/webhooks/telegram/altes-segment", `{"update_id":9}`, header)
		if neu.Code != alt.Code {
			t.Errorf("Header %q: /inbound %d != Alt-Route %d", header, neu.Code, alt.Code)
		}
		if neu.Code != http.StatusForbidden {
			t.Errorf("Header %q: erwartet 403 (nicht 401/404/200), bekam %d", header, neu.Code)
		}
	}
	if n := len(core.snapshot()); n != 0 {
		t.Errorf("Python-Core darf bei abgewiesenem Header nichts sehen, sah %d Updates", n)
	}
}

// AC-5: andere Segmente werden von der statischen Route nicht verdraengt.
func TestTelegramInbound_AltRoute_BleibtErreichbar(t *testing.T) {
	r, core := tgRouter(t)
	for _, seg := range []string{"whatever", "x", "inbound2"} {
		w := tgPost(r, "/api/webhooks/telegram/"+seg, `{"update_id":3}`, "tg-geheim-1814")
		if w.Code != http.StatusOK {
			t.Errorf("Alt-Route /%s: erwartet 200, bekam %d", seg, w.Code)
		}
	}
	if n := len(core.snapshot()); n != 3 {
		t.Errorf("erwartet 3 weitergereichte Updates, bekam %d", n)
	}
}

// AC-3 (Wirkungsort): /inbound ist als EIGENE statische Route registriert --
// nicht nur zufaellig ueber {secret} erreichbar. Sonst wuerde die Folge-Scheibe
// (Alt-Route entfernen) den Eingang still abschalten.
func TestTelegramInbound_IstEigeneStatischeRoute(t *testing.T) {
	r, _ := tgRouter(t)
	cr, ok := r.(chi.Routes)
	if !ok {
		t.Fatalf("Router ist kein chi.Routes: %T", r)
	}
	gefunden := false
	_ = chi.Walk(cr, func(method, route string, _ http.Handler, _ ...func(http.Handler) http.Handler) error {
		if method == http.MethodPost && route == "/api/webhooks/telegram/inbound" {
			gefunden = true
		}
		return nil
	})
	if !gefunden {
		t.Error("POST /api/webhooks/telegram/inbound ist nicht als statische Route registriert")
	}
}
