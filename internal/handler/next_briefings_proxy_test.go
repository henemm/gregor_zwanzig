package handler

// Issue #1969 (Nächstes Briefing), AC-13 (Handler-Teil).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Gemessen wird am Fake-Python-Core: was dort ankommt (Pfad + Query) und was
// er antwortet. Der Fake liefert NUR IDs des user_id, den er tatsaechlich
// empfangen hat — die Antwort an den Client beweist damit, wessen Daten
// durchgereicht wurden (A sieht keine ID von B).

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/middleware"
)

type nbUpstreamCall struct {
	path  string
	query url.Values
}

type nbFakePython struct {
	mu    sync.Mutex
	calls []nbUpstreamCall
	srv   *httptest.Server
}

func (f *nbFakePython) take() []nbUpstreamCall {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := f.calls
	f.calls = nil
	return out
}

// startNbFakePython simuliert GET /api/_internal/next-briefings: die Antwort
// enthaelt ausschliesslich IDs des empfangenen user_id ("trip-<uid>",
// "preset-<uid>").
func startNbFakePython(t *testing.T) *nbFakePython {
	t.Helper()
	f := &nbFakePython{}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		f.calls = append(f.calls, nbUpstreamCall{path: r.URL.Path, query: r.URL.Query()})
		f.mu.Unlock()
		uid := r.URL.Query().Get("user_id")
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"trips":{"trip-`+uid+`":{"at":"2026-10-22T07:00:00+02:00","local_date":"2026-10-22","local_time":"07:00","tz":"Europe/Paris","tz_abbr":"CEST","slot":"morning"}},`+
			`"compare":{"preset-`+uid+`":{"at":null,"reason":"manual"}}}`)
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func callNextBriefings(h http.HandlerFunc, target, userID string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, target, nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	h(w, req)
	return w
}

// AC-13: A fragt mit manipulierter Query ?user_id=B — upstream kommt genau
// user_id=A an, die Antwort traegt nur IDs von A.
func TestNextBriefingsProxy_ForcesAuthenticatedUser_AC13(t *testing.T) {
	py := startNbFakePython(t)
	h := NextBriefingsProxyHandler(py.srv.URL)

	w := callNextBriefings(h, "/api/next-briefings?user_id=userB", "userA")
	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	calls := py.take()
	if len(calls) != 1 {
		t.Fatalf("genau ein Upstream-Aufruf erwartet, %d bekommen", len(calls))
	}
	if calls[0].path != "/api/_internal/next-briefings" {
		t.Errorf("Upstream-Pfad falsch: %q", calls[0].path)
	}
	if got := calls[0].query["user_id"]; len(got) != 1 || got[0] != "userA" {
		t.Errorf("Upstream muss genau user_id=userA tragen (Auth-Kontext), bekam %v", got)
	}
	body := w.Body.String()
	if !strings.Contains(body, "trip-userA") || !strings.Contains(body, "preset-userA") {
		t.Errorf("Antwort muss die IDs von A enthalten: %s", body)
	}
	if strings.Contains(body, "userB") {
		t.Errorf("Antwort enthaelt eine ID von B (Cross-User-Leck): %s", body)
	}
}

// AC-13 + AC-18: die Einschraenkung ?trip_id= / ?preset_id= reist mit (der
// Versand-Reiter laedt nach dem Speichern ueber ?trip_id= neu) — nur user_id
// wird ersetzt.
func TestNextBriefingsProxy_PassesFilterQuery_AC13(t *testing.T) {
	py := startNbFakePython(t)
	h := NextBriefingsProxyHandler(py.srv.URL)

	for _, tc := range []struct{ target, key, want string }{
		{"/api/next-briefings?trip_id=t1&user_id=userB", "trip_id", "t1"},
		{"/api/next-briefings?preset_id=p9&user_id=userB", "preset_id", "p9"},
	} {
		w := callNextBriefings(h, tc.target, "userA")
		if w.Code != http.StatusOK {
			t.Fatalf("%s: 200 erwartet, %d bekommen", tc.target, w.Code)
		}
		calls := py.take()
		if len(calls) != 1 {
			t.Fatalf("%s: genau ein Upstream-Aufruf erwartet, %d", tc.target, len(calls))
		}
		q := calls[0].query
		if q.Get(tc.key) != tc.want {
			t.Errorf("%s: %s=%s muss durchgereicht werden, Upstream-Query %v", tc.target, tc.key, tc.want, q)
		}
		if got := q["user_id"]; len(got) != 1 || got[0] != "userA" {
			t.Errorf("%s: user_id muss genau userA sein, bekam %v", tc.target, got)
		}
	}
}

// AC-13: ohne Auth-Kontext nie durchreichen — appendUserID gaebe die Client-
// Query (user_id=B) sonst unveraendert weiter. 401, kein Upstream-Aufruf,
// nie Rueckfall auf "default".
func TestNextBriefingsProxy_NoAuthContext_401_NoUpstream_AC13(t *testing.T) {
	py := startNbFakePython(t)
	h := NextBriefingsProxyHandler(py.srv.URL)

	w := callNextBriefings(h, "/api/next-briefings?user_id=userB", "")
	if w.Code != http.StatusUnauthorized {
		t.Errorf("ohne Auth-Kontext 401 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	if calls := py.take(); len(calls) != 0 {
		t.Errorf("ohne Auth-Kontext darf kein Upstream-Aufruf erfolgen, bekam %v", calls)
	}
}

// Fehlerpfad: Python nicht erreichbar => 502 mit JSON-Fehler (Frontend zeigt
// dann "—", AC-19).
func TestNextBriefingsProxy_502OnUpstreamUnreachable(t *testing.T) {
	srv := httptest.NewServer(http.NewServeMux())
	dead := srv.URL
	srv.Close()

	w := callNextBriefings(NextBriefingsProxyHandler(dead), "/api/next-briefings", "userA")
	if w.Code != http.StatusBadGateway {
		t.Errorf("502 erwartet, %d bekommen", w.Code)
	}
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type application/json erwartet, %q", ct)
	}
}
