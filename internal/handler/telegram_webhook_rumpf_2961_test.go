package handler

// Issue #2961 Nachbesserung (Gegenpruefung F9): der Telegram-Eingang liest den
// Rumpf hoechstens bis 1 MB; groessere Rumpfe werden abgewiesen und nicht an
// den Python-Kern weitergereicht.

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestTelegramWebhook_RumpfBegrenztAufEinMB(t *testing.T) {
	var weiter atomic.Int32
	var laenge atomic.Int64
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		weiter.Add(1)
		laenge.Store(int64(len(b)))
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()
	h := TelegramWebhookHandler(backend.URL, "s3cr3t")
	senden := func(n int) int {
		body := `{"x":"` + strings.Repeat("a", n) + `"}`
		req := httptest.NewRequest(http.MethodPost, "/api/webhooks/telegram/inbound", nil)
		req.Body = io.NopCloser(bytes.NewReader([]byte(body))) // Laenge unbekannt
		req.ContentLength = -1
		req.Header.Set("X-Telegram-Bot-Api-Secret-Token", "s3cr3t")
		w := httptest.NewRecorder()
		h(w, req)
		return w.Code
	}
	if c := senden(1 << 20); c != http.StatusRequestEntityTooLarge {
		t.Fatalf("Rumpf ueber 1 MB: erwartet 413, bekommen %d", c)
	}
	if n := weiter.Load(); n != 0 {
		t.Fatalf("ein zu grosser Rumpf darf nicht weitergereicht werden (%d Weiterleitungen)", n)
	}
	if c := senden(512 << 10); c != http.StatusOK {
		t.Fatalf("Rumpf 512 KB: erwartet 200, bekommen %d", c)
	}
	if weiter.Load() != 1 || laenge.Load() != int64(512<<10+8) {
		t.Fatalf("Rumpf unter der Grenze muss vollstaendig weitergereicht werden (Laenge %d)", laenge.Load())
	}
}
