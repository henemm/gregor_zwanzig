package router

// TDD RED: Issue #1814 — Telegram-Webhook ohne Secret im URL-Pfad.
// Spec: docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md
//
// Scheibe 2 (fix_1814_s2_telegram_alt_route_entfernen):
// AC-1: Alt-Route /{segment} entfernt -> 404/405, nichts an den Core.
// AC-2: /inbound mit korrektem Header -> 200 + Weiterreichung (echter Router + AuthMiddleware).
// AC-3: fehlender/falscher Header auf /inbound -> 403, kein Forwarding.
// AC-5: zwei Chats (zwei Nutzer) -> Zuordnung (Body) unveraendert.
//
// Ist-Zustand: Die Alt-Route {secret} ist seit Scheibe 2 entfernt; /inbound ist die
// einzige Route. Zusaetzlich wird geprueft, dass /inbound als EIGENE statische Route
// registriert ist (kein Param-Treffer).
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

// AC-2 + AC-5: korrekter Header, zwei Chats (zwei Nutzer) nur auf /inbound -> 200,
// jedes Update unveraendert (Zuordnung/Body) an den Core.
func TestTelegramInbound_KorrekterHeader_200UndWeiterreichung_ZweiNutzer(t *testing.T) {
	r, core := tgRouter(t)
	alice := `{"update_id":1,"message":{"chat":{"id":1001},"text":"status"}}`
	bob := `{"update_id":2,"message":{"chat":{"id":2002},"text":"status"}}`
	for _, body := range []string{alice, bob} {
		w := tgPost(r, "/api/webhooks/telegram/inbound", body, "tg-geheim-1814")
		if w.Code != http.StatusOK {
			t.Fatalf("POST /inbound: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
		}
	}
	got := core.snapshot()
	want := []string{alice, bob}
	if len(got) != len(want) {
		t.Fatalf("Python-Core sah %d Updates, erwartet %d: %v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Update %d: Zuordnung/Body verschoben: %q != %q", i, got[i], want[i])
		}
	}
}

// AC-3: fehlender/falscher Header auf /inbound -> 403, kein Forwarding.
func TestTelegramInbound_FalscherOderFehlenderHeader_403_KeinForwarding(t *testing.T) {
	r, core := tgRouter(t)
	for _, header := range []string{"", "falsch"} {
		w := tgPost(r, "/api/webhooks/telegram/inbound", `{"update_id":9}`, header)
		if w.Code != http.StatusForbidden {
			t.Errorf("Header %q: erwartet 403 (nicht 401/404/200), bekam %d", header, w.Code)
		}
	}
	if n := len(core.snapshot()); n != 0 {
		t.Errorf("Python-Core darf bei abgewiesenem Header nichts sehen, sah %d Updates", n)
	}
}

// AC-1: die Alt-Route /{secret} ist entfernt -- auch mit korrektem Header weder
// 200 noch Weiterreichung (Mutation: Route wieder einfuegen => rot).
func TestTelegramInbound_AltRoute_NichtMehrZugestellt(t *testing.T) {
	r, core := tgRouter(t)
	for _, seg := range []string{"tg-geheim-1814", "whatever", "x", "inbound2"} {
		w := tgPost(r, "/api/webhooks/telegram/"+seg, `{"update_id":3}`, "tg-geheim-1814")
		if w.Code != http.StatusNotFound && w.Code != http.StatusMethodNotAllowed {
			t.Errorf("Alt-Route /%s: erwartet 404/405, bekam %d", seg, w.Code)
		}
	}
	if n := len(core.snapshot()); n != 0 {
		t.Errorf("Alt-Route darf nichts an den Core reichen, %d Updates gesehen", n)
	}
}

// AC-3 (Wirkungsort): /inbound ist als EIGENE statische Route registriert --
// nicht ueber eine Param-Route. Die Alt-Route {secret} ist seit Scheibe 2 entfernt;
// der Test sichert, dass der Eingang dadurch nicht still abgeschaltet ist.
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
