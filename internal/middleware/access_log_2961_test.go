package middleware

// Issue #2961 Nachbesserung (Gegenpruefung F7/F8) — Zugriffslog maskiert
// auch absolute Form, doppelte Schraegstriche, Query-Schluessel beliebiger
// Schreibweise und weitere Geheimnis-Schluessel. Echter chi-Logger, Ausgabe
// in einen Puffer.

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"

	chimw "github.com/go-chi/chi/v5/middleware"
)

type logPuffer2961 struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (p *logPuffer2961) Write(b []byte) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.b.Write(b)
}

func TestAccessLog_MaskiertAlleSchreibweisen(t *testing.T) {
	var buf logPuffer2961
	orig := chimw.DefaultLogger
	chimw.DefaultLogger = chimw.RequestLogger(&chimw.DefaultLogFormatter{Logger: log.New(&buf, "", 0), NoColor: true})
	t.Cleanup(func() { chimw.DefaultLogger = orig })

	var gesehen []string
	h := AccessLog()(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gesehen = append(gesehen, r.URL.String())
		w.WriteHeader(http.StatusNoContent)
	}))
	ziele := []string{
		"http://gregor.example/api/webhooks/sms/GEHEIM-ABS-1",
		"//api/webhooks/mail/GEHEIM-DOPPEL-2",
		"/api//webhooks/sms/GEHEIM-MITTE-3/rest",
		"/api/auth/google/callback?CODE=GEHEIM-GROSS-4&State=GEHEIM-GROSS-5&scope=email",
		"/api/x?id_token=GEHEIM-6&access_token=GEHEIM-7&invite=GEHEIM-8&secret=GEHEIM-9&password=GEHEIM-10&ok=sichtbar",
	}
	for _, z := range ziele {
		req := httptest.NewRequest(http.MethodPost, "/", nil)
		req.RequestURI = z
		u, err := url.ParseRequestURI(z) // wie der HTTP-Server
		if err != nil {
			t.Fatal(err)
		}
		req.URL = u
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
	ausgabe := buf.b.String()
	if strings.Contains(ausgabe, "GEHEIM") {
		t.Fatalf("Zugriffslog enthaelt Geheimnisse:\n%s", ausgabe)
	}
	for _, sichtbar := range []string{"/api/webhooks/sms/***", "/api/webhooks/mail/***", "/rest", "scope=email", "ok=sichtbar", "CODE=***"} {
		if !strings.Contains(ausgabe, sichtbar) {
			t.Errorf("Zugriffslog soll %q enthalten:\n%s", sichtbar, ausgabe)
		}
	}
	// Der Handler sieht die unveraenderte Anfrage.
	if len(gesehen) != len(ziele) || !strings.Contains(gesehen[0], "GEHEIM-ABS-1") {
		t.Fatalf("Handler muss die Original-URL sehen: %v", gesehen)
	}
}
