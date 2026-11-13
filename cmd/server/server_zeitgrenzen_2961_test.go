package main

// Issue #2961 (GA8) — Zeitgrenzen des HTTP-Servers.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-25).

import (
	"bufio"
	"io"
	"net"
	"net/http"
	"testing"
	"time"
)

// AC-25: Kopf-Zeitgrenze 10 s, Einlese-/Leerlauf-Grenzen gesetzt, KEINE
// Schreib-Zeitgrenze (langlaufende Versand-/Proxy-Anfragen bis 300 s).
func TestHTTPServer_Zeitgrenzen(t *testing.T) {
	srv := newHTTPServer("127.0.0.1:0", http.NotFoundHandler())
	if srv.ReadHeaderTimeout != 10*time.Second {
		t.Errorf("ReadHeaderTimeout erwartet 10s, ist %v", srv.ReadHeaderTimeout)
	}
	if srv.ReadTimeout <= 0 || srv.IdleTimeout <= 0 {
		t.Errorf("ReadTimeout/IdleTimeout muessen gesetzt sein: %v/%v", srv.ReadTimeout, srv.IdleTimeout)
	}
	if srv.WriteTimeout != 0 {
		t.Errorf("WriteTimeout muss fehlen (Versand bis 300 s), ist %v", srv.WriteTimeout)
	}
}

// AC-25 (Wirkung): eine Verbindung, die ihren Kopf nicht fertig schickt, wird
// nach der Kopf-Zeitgrenze geschlossen; eine Bearbeitung, die laenger als die
// Einlese-Grenze dauert, wird dagegen zu Ende beantwortet.
func TestHTTPServer_ZeitgrenzenWirken(t *testing.T) {
	srv := newHTTPServer("", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(400 * time.Millisecond)
		w.Write([]byte("fertig"))
	}))
	srv.ReadHeaderTimeout = 200 * time.Millisecond
	srv.ReadTimeout = 200 * time.Millisecond
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go srv.Serve(ln)
	t.Cleanup(func() { srv.Close() })

	langsam, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	defer langsam.Close()
	langsam.Write([]byte("GET / HTTP/1.1\r\nHost: x\r\n"))
	langsam.SetReadDeadline(time.Now().Add(3 * time.Second))
	if _, err := bufio.NewReader(langsam).ReadByte(); err == nil {
		// Der Server darf hoechstens eine Fehlerantwort schicken und muss dann schliessen.
		if _, err := io.ReadAll(langsam); err != nil {
			t.Fatalf("unvollstaendiger Kopf: Verbindung haette geschlossen werden muessen: %v", err)
		}
	} else if ne, ok := err.(net.Error); ok && ne.Timeout() {
		t.Fatal("unvollstaendiger Kopf: Server hat die Verbindung nicht geschlossen")
	}

	resp, err := http.Get("http://" + ln.Addr().String())
	if err != nil {
		t.Fatalf("lange Bearbeitung: %v", err)
	}
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if string(b) != "fertig" {
		t.Fatalf("lange Bearbeitung muss zu Ende beantwortet werden, bekommen %q", b)
	}
}
