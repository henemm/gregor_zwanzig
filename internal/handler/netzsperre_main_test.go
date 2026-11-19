//go:build !integration

// Installiert die Netzsperre (netzsperre_test.go) fuer den Kern-Lauf des
// Handler-Pakets (Issue #3115, ADR-0094) und macht den Lauf rot, sobald ein
// Netzabruf ausserhalb Loopback versucht wurde.
package handler

import (
	"fmt"
	"net/http"
	"os"
	"testing"
)

func TestMain(m *testing.M) {
	http.DefaultTransport = netzsperreTransport{next: http.DefaultTransport}

	code := m.Run()

	netzsperreMu.Lock()
	versuche := append([]string(nil), netzsperreVersuche...)
	netzsperreMu.Unlock()
	if len(versuche) > 0 {
		fmt.Fprintf(os.Stderr, "FAIL: %s: %d Netzabruf(e) ausserhalb Loopback im Kern-Test:\n", netzsperreFehlerTag, len(versuche))
		for _, v := range versuche {
			fmt.Fprintf(os.Stderr, "  - %s\n", v)
		}
		if code == 0 {
			code = 1
		}
	}
	os.Exit(code)
}
