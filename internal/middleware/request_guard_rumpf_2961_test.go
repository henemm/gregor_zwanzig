package middleware

// Issue #2961 Nachbesserung (Gegenpruefung F4) — Rumpfe unbekannter Laenge
// (chunked bzw. ContentLength −1) laufen ebenso durch JSON-Pflicht und
// Groessenbegrenzung.

import (
	"bytes"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// rumpfUnbekannt baut eine Anfrage, deren Laenge der Server nicht kennt.
func rumpfUnbekannt(body []byte, chunked bool, ct string) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/api/locations", nil)
	req.Body = io.NopCloser(bytes.NewReader(body))
	req.ContentLength = -1
	if chunked {
		req.TransferEncoding = []string{"chunked"}
	}
	if ct != "" {
		req.Header.Set("Content-Type", ct)
	}
	return req
}

func TestRequireJSONBody_RumpfUnbekannterLaenge(t *testing.T) {
	var gelesen []byte
	h := RequireJSONBody()(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gelesen, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	for _, chunked := range []bool{true, false} {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, rumpfUnbekannt([]byte(`{"a":1}`), chunked, "text/plain"))
		if w.Code != http.StatusUnsupportedMediaType {
			t.Fatalf("chunked=%v ohne JSON-Typ: erwartet 415, bekommen %d", chunked, w.Code)
		}
	}
	// Mit JSON-Typ: durchgelassen, Rumpf vollstaendig erhalten (Probelesen
	// legt das Byte zurueck).
	w := httptest.NewRecorder()
	h.ServeHTTP(w, rumpfUnbekannt([]byte(`{"a":1}`), false, "application/json"))
	if w.Code != http.StatusOK || string(gelesen) != `{"a":1}` {
		t.Fatalf("JSON unbekannter Laenge: erwartet 200 und vollstaendigen Rumpf, bekommen %d %q", w.Code, gelesen)
	}
	// Leerer Rumpf unbekannter Laenge ohne Typ: kein 415.
	w = httptest.NewRecorder()
	h.ServeHTTP(w, rumpfUnbekannt(nil, false, ""))
	if w.Code != http.StatusOK {
		t.Fatalf("leerer Rumpf: erwartet 200, bekommen %d", w.Code)
	}
}

// Ein chunked Rumpf ueber der Grenze bricht beim Lesen mit MaxBytesError ab.
func TestLimitBody_ChunkedUeberGrenzeBrichtBeimLesenAb(t *testing.T) {
	var lesefehler error
	geschrieben := false
	h := LimitBody(1<<20, nil)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if _, err := io.ReadAll(r.Body); err != nil {
			lesefehler = err
			return
		}
		geschrieben = true
		w.WriteHeader(http.StatusOK)
	}))
	gross := []byte(`{"x":"` + strings.Repeat("a", 2<<20) + `"}`)
	h.ServeHTTP(httptest.NewRecorder(), rumpfUnbekannt(gross, true, "application/json"))
	var mbe *http.MaxBytesError
	if !errors.As(lesefehler, &mbe) {
		t.Fatalf("erwartet MaxBytesError beim Lesen, bekommen %v", lesefehler)
	}
	if geschrieben {
		t.Fatal("der Handler darf bei abgebrochenem Rumpf nichts verarbeiten")
	}
}
