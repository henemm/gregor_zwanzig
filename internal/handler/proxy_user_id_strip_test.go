package handler

// TDD RED — Issue #2163 Scheibe 1, Proxy-Block (Punkt 8).
// Spec: docs/specs/modules/auth_haertung_go_2163.md (AC-11, AC-12)
//
// ProxyHandler (nutzerunabhaengige Routen /api/config, /api/metrics,
// /api/templates, /api/sms-symbols, /api/compare/metrics) darf eine von aussen
// gesetzte user_id NICHT an den Python-Core durchreichen. Regel:
//   - ohne user_id-Segment: Roh-Query byte-identisch (kein Encode/Umsortieren)
//   - mit user_id-Segment: nur Segmente entfernen, deren Schluessel NACH
//     URL-Dekodierung exakt "user_id" ist (auch ohne Wert, auch "user%5Fid");
//     alle anderen Segmente behalten Reihenfolge und Kodierung.
//   - Gross/Klein: nur der exakte Schluessel "user_id"; "USER_ID" bleibt.
//
// Echter ProxyHandler gegen einen httptest-Core, der die empfangene Roh-Query
// und die Request-URI aufzeichnet (kein Mock).
//
// RED-Signal heute: ProxyHandler reicht r.URL.RawQuery unveraendert weiter,
// user_id kommt beim Core an. AC-11 ist heute gruen (bewacht gegen eine
// Umsetzung per url.Values.Encode()).

import (
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
)

type queryRecordingCore struct {
	mu   sync.Mutex
	raw  []string
	uris []string
}

func (c *queryRecordingCore) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	c.mu.Lock()
	c.raw = append(c.raw, r.URL.RawQuery)
	c.uris = append(c.uris, r.RequestURI)
	c.mu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	io.WriteString(w, `{"ok":true}`)
}

func (c *queryRecordingCore) last(t *testing.T) (raw, uri string) {
	t.Helper()
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.raw) == 0 {
		t.Fatal("Core hat keinen Aufruf gesehen")
	}
	return c.raw[len(c.raw)-1], c.uris[len(c.uris)-1]
}

// proxyQueryRoundtrip schickt "?"+rawQuery durch den echten ProxyHandler und
// liefert, was der Core als Roh-Query und Request-URI gesehen hat.
func proxyQueryRoundtrip(t *testing.T, rawQuery string) (gotRaw, gotURI string) {
	t.Helper()
	core := &queryRecordingCore{}
	srv := httptest.NewServer(core)
	t.Cleanup(srv.Close)

	h := ProxyHandler(srv.URL, "/config")
	target := "/api/config"
	if rawQuery != "" {
		target += "?" + rawQuery
	}
	req := httptest.NewRequest(http.MethodGet, target, nil)
	if req.URL.RawQuery != rawQuery {
		t.Fatalf("Testaufbau: Anfrage-RawQuery %q != %q", req.URL.RawQuery, rawQuery)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("Proxy-Antwort erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	return core.last(t)
}

// AC-11: ohne user_id kommt die Roh-Query byte-identisch an.
func TestProxyHandler_OhneUserID_QueryByteIdentisch_AC11(t *testing.T) {
	faelle := []string{
		"a=1",
		"q=a+b&s=%20x&m=1&m=2",               // +, %20, Mehrfachparameter
		"z=9&a=1&m=2&m=1",                    // bewusst unsortiert
		"u=%C3%A4%C3%B6&x=%2B%26%3D&e=&flag", // Prozent-Kodierung, leerer Wert, ohne "="
		"name=Gr%C3%BCn+Weg&lat=42.1&lat=42.2&q=%7Bjson%7D",
		"USER_ID=gross&Userid=x", // Gross/Klein-Varianten sind KEIN user_id-Schluessel
	}
	for _, q := range faelle {
		q := q
		t.Run(q, func(t *testing.T) {
			got, _ := proxyQueryRoundtrip(t, q)
			if got != q {
				t.Errorf("AC-11: Roh-Query veraendert: gesendet %q, Core sah %q", q, got)
			}
		})
	}
}

// AC-11: ohne Query kein "?" beim Core.
func TestProxyHandler_OhneQuery_KeinFragezeichen_AC11(t *testing.T) {
	got, uri := proxyQueryRoundtrip(t, "")
	if got != "" || uri != "/config" {
		t.Errorf("AC-11: ohne Query erwartet RawQuery \"\" und URI /config, Core sah %q / %q", got, uri)
	}
}

// AC-12: user_id-Segmente werden entfernt, alle anderen bleiben in Reihenfolge
// und Kodierung erhalten.
func TestProxyHandler_UserIDSegmenteEntfernt_RestUnveraendert_AC12(t *testing.T) {
	faelle := []struct {
		name, in, want string
	}{
		{"Spec-Beispiel", "a=1&user_id=x&b=%20z&user_id=y", "a=1&b=%20z"},
		{"am Anfang", "user_id=x&a=1", "a=1"},
		{"am Ende", "a=1&b=2&user_id=x", "a=1&b=2"},
		{"ohne Wert", "a=1&user_id", "a=1"},
		{"leerer Wert", "a=1&user_id=", "a=1"},
		{"kodierter Schluessel", "user%5Fid=x&a=1", "a=1"},
		{"kodierter Schluessel komplett", "%75%73%65%72%5F%69%64=x&q=a+b", "q=a+b"},
		{"Gross-Variante bleibt", "USER_ID=x&user_id=y&a=1", "USER_ID=x&a=1"},
		{"Sonderzeichen im Rest", "q=a+b&user_id=evil&s=%2B%26&m=1&m=2", "q=a+b&s=%2B%26&m=1&m=2"},
	}
	for _, f := range faelle {
		f := f
		t.Run(f.name, func(t *testing.T) {
			got, _ := proxyQueryRoundtrip(t, f.in)
			if got != f.want {
				t.Errorf("AC-12 %s: gesendet %q, erwartet beim Core %q, Core sah %q", f.name, f.in, f.want, got)
			}
		})
	}
}

// AC-12: nur user_id in der Query -> leere Query OHNE "?" beim Core.
func TestProxyHandler_NurUserID_LeereQueryOhneFragezeichen_AC12(t *testing.T) {
	for _, in := range []string{"user_id=x", "user_id=x&user_id=y", "user_id"} {
		in := in
		t.Run(in, func(t *testing.T) {
			got, uri := proxyQueryRoundtrip(t, in)
			if got != "" {
				t.Errorf("AC-12: %q: Core sah RawQuery %q, erwartet leer", in, got)
			}
			if uri != "/config" {
				t.Errorf("AC-12: %q: Core sah Request-URI %q, erwartet /config (ohne \"?\")", in, uri)
			}
		})
	}
}
