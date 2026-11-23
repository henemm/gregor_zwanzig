// Issue #3294 (Spec docs/specs/modules/imac_portabilitaet.md, AC-3):
// Der Egress-Waechter-Test braucht eine Loopback-Adresse, die der Waechter
// NICHT freigibt. Unter Linux ist das 127.0.0.2; macOS kennt auf lo0 nur
// 127.0.0.1 und ::1. Die Auswahl nimmt die erste nutzbare Adresse der Liste.
package resolver_test

import (
	"net"
	"testing"
)

// Fehlt die erste Adresse (192.0.2.1, TEST-NET-1, auf keinem Rechner lokal),
// faellt die Auswahl auf ::1 zurueck — so wie auf macOS bei 127.0.0.2.
func TestLoopbackAuswahl3294_FaelltAufIPv6Zurueck(t *testing.T) {
	probe, err := net.Listen("tcp", "[::1]:0")
	if err != nil {
		t.Skipf("Messaufbau: ::1 auf diesem Rechner nicht nutzbar: %v", err)
	}
	probe.Close()

	ln, host := lauscheAufNichtFreigegebenemLoopback(t, "192.0.2.1", "::1")
	defer ln.Close()
	if host != "::1" {
		t.Fatalf("erwartet Rueckfall auf ::1, bekommen %q", host)
	}
	if got := ln.Addr().(*net.TCPAddr).IP.String(); got != "::1" {
		t.Fatalf("Listener lauscht auf %q statt ::1", got)
	}
}

// Ist die erste Adresse nutzbar, wird sie genommen (Server: 127.0.0.2).
func TestLoopbackAuswahl3294_ErsteNutzbareAdresseGewinnt(t *testing.T) {
	probe, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Skipf("Messaufbau: 127.0.0.1 nicht nutzbar: %v", err)
	}
	probe.Close()

	ln, host := lauscheAufNichtFreigegebenemLoopback(t, "127.0.0.1", "::1")
	defer ln.Close()
	if host != "127.0.0.1" {
		t.Fatalf("erwartet 127.0.0.1, bekommen %q", host)
	}
}

// F003: Der echte Egress-Waechter-Test laeuft auch auf einem Rechner ohne
// 127.0.0.2 (macOS) und wird dort NICHT uebersprungen. Simuliert, indem
// 127.0.0.2 in der Kandidatenliste durch eine nirgends lokale Adresse ersetzt
// wird; faellt ::1 aus der Liste, wird der Teiltest uebersprungen -> rot.
func TestLoopbackAuswahl3294_EgressTestLaeuftOhne127002(t *testing.T) {
	probe, err := net.Listen("tcp", "[::1]:0")
	if err != nil {
		t.Skipf("Messaufbau: ::1 auf diesem Rechner nicht nutzbar: %v", err)
	}
	probe.Close()

	var ohne []string
	for _, k := range egressLoopbackKandidaten {
		if k == "127.0.0.2" {
			k = "192.0.2.1"
		}
		ohne = append(ohne, k)
	}
	uebersprungen := false
	t.Run("wie-macOS", func(st *testing.T) {
		defer func() { uebersprungen = st.Skipped() }()
		pruefeEgressWaechterJeAbruf(st, ohne...)
	})
	if uebersprungen {
		t.Fatalf("Egress-Test ohne 127.0.0.2 uebersprungen (Kandidaten %v): auf macOS waere er wirkungslos", ohne)
	}
}
