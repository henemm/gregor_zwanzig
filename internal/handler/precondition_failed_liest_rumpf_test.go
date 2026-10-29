package handler

import (
	"bufio"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
)

// Issue #2347 S3c (F001): eine 412-Antwort darf die Verbindung nicht mit
// ungelesenem Anfrage-Rumpf schliessen.
//
// Gemessener Befund (lokaler CI-Stack, KS-1 route Wetter-Metriken, 6/41 rot):
// Der Vite-Proxy schickt jede Anfrage mit `Connection: close` (http-proxy ohne
// Agent). Dann verwirft net/http einen ungelesenen Rumpf NICHT (server.go:
// Verwerfen nur bei !closeAfterReply; transfer.go body.Close: "closing the
// connection next, no point in reading to EOF") und schliesst den Socket. Liegen
// dort noch ungelesene Bytes (weather-config-Rumpf 4137 B > 4-KiB-Lesepuffer),
// sendet der Kernel RST statt FIN — der Proxy sieht `write ECONNRESET` und
// macht aus dem 412 ein 502. Der Nutzer bekommt "Fehler" statt
// "Nochmal speichern".
//
// Der Test faehrt deshalb einen ECHTEN Server und spricht rohes TCP: Ein
// ResponseRecorder hat keinen Socket und koennte den Reset nicht zeigen.

const veralteterStempel = `"0000000000000000000000000000000000000000000000000000000000000000"`

// grosserRumpf liefert gueltiges JSON mit mindestens n Bytes.
func grosserRumpf(n int) string {
	return `{"theme":"` + strings.Repeat("x", n) + `"}`
}

// sendeMitVerbindungsende schickt eine Anfrage mit `Connection: close` wie der
// Vite-Proxy und liest die Antwort bis zum Verbindungsende. Rueckgabe: die
// rohe Antwort und ein Lesefehler (ECONNRESET, wenn der Server den Socket mit
// ungelesenem Rumpf geschlossen hat).
func sendeMitVerbindungsende(t *testing.T, addr, method, pfad, rumpf string) (string, error) {
	t.Helper()
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		t.Fatalf("Dial: %v", err)
	}
	defer conn.Close()
	kopf := method + " " + pfad + " HTTP/1.1\r\n" +
		"Host: " + addr + "\r\n" +
		"Content-Type: application/json\r\n" +
		"If-Match: " + veralteterStempel + "\r\n" +
		"Connection: close\r\n" +
		"Content-Length: " + strconv.Itoa(len(rumpf)) + "\r\n\r\n"
	if _, err := io.WriteString(conn, kopf+rumpf); err != nil {
		return "", err
	}
	// Dem Server Zeit geben, zu antworten und (vor dem Fix) den Socket mit
	// ungelesenen Bytes zu schliessen — der RST ist dann sicher angekommen.
	time.Sleep(50 * time.Millisecond)
	_ = conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	antwort, err := io.ReadAll(bufio.NewReader(conn))
	return string(antwort), err
}

func TestPreconditionFailed_LiestRumpf_KeinVerbindungsResetBeiConnectionClose(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "pf-rumpf-trip", "Trip")
	seedComparePreset(t, s, "pf-rumpf-cmp", "Vergleich", []string{"loc-1", "loc-2"})

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	srv := httptest.NewServer(r)
	defer srv.Close()
	addr := strings.TrimPrefix(srv.URL, "http://")

	faelle := []struct{ name, pfad string }{
		{"weather-config", "/api/trips/pf-rumpf-trip/weather-config"},
		{"trip", "/api/trips/pf-rumpf-trip"},
		{"compare-preset", "/api/compare/presets/pf-rumpf-cmp"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			antwort, err := sendeMitVerbindungsende(t, addr, http.MethodPut, f.pfad, grosserRumpf(64<<10))
			if err != nil {
				t.Fatalf("Verbindung mit Fehler beendet (%v) — der Server hat bei 412 mit ungelesenem Rumpf "+
					"geschlossen; ein Proxy macht daraus 502. Gelesen: %q", err, antwort)
			}
			if !strings.HasPrefix(antwort, "HTTP/1.1 412 ") {
				t.Fatalf("erwartet 412, bekommen: %q", antwort)
			}
			if !strings.Contains(antwort, "precondition_failed") {
				t.Errorf("412-Rumpf fehlt: %q", antwort)
			}
		})
	}
}
