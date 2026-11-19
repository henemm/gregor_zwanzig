//go:build !integration

// Wirkungstests der Netzsperre des Handler-Pakets (Issue #3115, ADR-0094):
// die von TestMain installierte Sperre lehnt fremde Hosts ab, bevor eine
// Verbindung aufgebaut wird, und laesst Loopback durch. Nur ohne Build-Tag,
// weil die Sperre nur dann installiert ist.
package handler

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func pruefeNetzsperreInstalliert(t *testing.T) {
	t.Helper()
	if _, ok := http.DefaultTransport.(netzsperreTransport); !ok {
		t.Fatalf("http.DefaultTransport ist %T, erwartet die von TestMain installierte netzsperreTransport", http.DefaultTransport)
	}
}

// Ein Abruf an einen fremden Host scheitert ueber den Standard-Client an der
// Sperre und wird vermerkt.
func TestNetzsperre_StandardClientBlocktFremdenHost(t *testing.T) {
	pruefeNetzsperreInstalliert(t)
	const ziel = "http://netzsperre-probe.invalid/"
	t.Cleanup(func() {
		netzsperreMu.Lock()
		defer netzsperreMu.Unlock()
		rest := make([]string, 0, len(netzsperreVersuche))
		for _, v := range netzsperreVersuche {
			if !strings.HasPrefix(v, ziel) {
				rest = append(rest, v)
			}
		}
		netzsperreVersuche = rest
	})

	resp, err := http.DefaultClient.Get(ziel)
	if resp != nil {
		resp.Body.Close()
	}
	if err == nil || !strings.Contains(err.Error(), netzsperreFehlerTag) {
		t.Fatalf("Abruf an fremden Host muss von der Netzsperre abgelehnt werden, bekam err=%v", err)
	}

	netzsperreMu.Lock()
	gefunden := false
	for _, v := range netzsperreVersuche {
		if strings.HasPrefix(v, ziel) {
			gefunden = true
		}
	}
	netzsperreMu.Unlock()
	if !gefunden {
		t.Fatal("abgelehnter Abruf muss vermerkt werden, sonst bleibt ein still geschluckter Netzabruf unbemerkt")
	}
}

// Loopback bleibt ueber den Standard-Client erreichbar (Fixture-Server).
func TestNetzsperre_LoopbackBleibtErreichbar(t *testing.T) {
	pruefeNetzsperreInstalliert(t)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	resp, err := http.DefaultClient.Get(srv.URL)
	if err != nil {
		t.Fatalf("Loopback-Abruf %s muss durch die Netzsperre gehen, bekam err=%v", srv.URL, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Loopback-Abruf: Status %d, erwartet 200", resp.StatusCode)
	}
}
