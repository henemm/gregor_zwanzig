package handler

import (
	"bytes"
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// AC-6 (#2158), Handler-Teil: Haelt ein Fremder den flock auf
// <id>.json.lock (ADR-0083-Pfad, literal), antwortet der Trip-Speichern-
// Handler nach der Frist (~5 s, echter Standardwert) mit 503 + Retry-After,
// und die Datei ist byte-identisch.
func TestSchreibsperre_Trip503NachFristMitRetryAfter_DateiUnveraendert(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "u503")
	seedTrip(t, s, "t1", "Alt")
	datei := filepath.Join(dir, "users", "u503", "briefings", "t1.json")
	vorher, err := os.ReadFile(datei)
	if err != nil {
		t.Fatalf("seed nicht lesbar: %v", err)
	}

	f, err := os.OpenFile(filepath.Join(dir, "users", "u503", "briefings", "t1.json.lock"), os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		t.Fatalf("lock open: %v", err)
	}
	defer f.Close()
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
		t.Fatalf("flock: %v", err)
	}
	defer syscall.Flock(int(f.Fd()), syscall.LOCK_UN)

	type ergebnis struct {
		code       int
		retryAfter string
		dauer      time.Duration
	}
	res := make(chan ergebnis, 1)
	go func() {
		t0 := time.Now()
		w := p2158Do(UpdateTripHandler(s), "PUT", "/api/trips/{id}", "/api/trips/t1", `{"name":"Neu"}`, "u503")
		res <- ergebnis{w.Code, w.Header().Get("Retry-After"), time.Since(t0)}
	}()

	select {
	case r := <-res:
		if r.code != 503 {
			t.Errorf("erwartet 503 bei gehaltener fremder Sperre, bekam %d", r.code)
		}
		if r.retryAfter == "" {
			t.Errorf("Header Retry-After fehlt")
		}
		if r.dauer < 2*time.Second {
			t.Errorf("Handler antwortete nach %v -- erwartet wird Warten bis zur Frist (~5 s)", r.dauer)
		}
	case <-time.After(20 * time.Second):
		t.Fatal("Handler antwortet auch nach 20 s nicht (Frist fehlt)")
	}

	nachher, err := os.ReadFile(datei)
	if err != nil {
		t.Fatalf("Datei nicht lesbar: %v", err)
	}
	if !bytes.Equal(vorher, nachher) {
		t.Errorf("Trip-Datei wurde trotz Sperr-Timeout veraendert")
	}
}
