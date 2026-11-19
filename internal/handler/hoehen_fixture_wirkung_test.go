//go:build !integration

// Selbsttests des Hoehen-Nachschlag-Fixtures hoehenDienstAuf (Issue #3158,
// ADR-0094, ADR-0114): die Umleitung gilt nur fuer den exakten Host
// api.open-elevation.com, alle anderen Abrufe bleiben an der Netzsperre
// haengen, und nach dem Test ist exakt der vorige Transport (die Sperre)
// wiederhergestellt -- ohne Duldung des Hoehen-Nachschlags. Nur ohne
// Build-Tag, weil die Sperre nur dann von TestMain installiert ist.
package handler

import (
	"io"
	"net/http"
	"strings"
	"testing"
)

// nimmEigenenSperrEintrag prueft, dass der Selbsttest genau einen
// Sperr-Eintrag fuer ziel erzeugt hat, und entfernt nur diesen einen, damit
// TestMain nicht rot wird. Fehlt er oder steht er mehrfach da, ist das ein
// Befund (die Sperre hat nicht gegriffen bzw. es wurde mehr abgerufen).
func nimmEigenenSperrEintrag(t *testing.T, ziel string) {
	t.Helper()
	netzsperreMu.Lock()
	defer netzsperreMu.Unlock()
	treffer := 0
	rest := make([]string, 0, len(netzsperreVersuche))
	for _, v := range netzsperreVersuche {
		if v == ziel {
			treffer++
			continue
		}
		rest = append(rest, v)
	}
	if treffer != 1 {
		t.Fatalf("erwartet genau einen Sperr-Eintrag %q, gefunden %d (Register: %v)", ziel, treffer, netzsperreVersuche)
	}
	netzsperreVersuche = rest
}

func holeUeberStandardClient(url string) (int, string, error) {
	resp, err := http.DefaultClient.Get(url)
	if err != nil {
		return 0, "", err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(b), nil
}

// AC-3: Bei aktiver Umleitung bleibt ein Fremd-Host gesperrt und erreicht
// das Fixture nicht -- auch ein Host, der open-elevation nur im Namen traegt.
func TestHoehenFixture_FremderHostBleibtGesperrt(t *testing.T) {
	pruefeNetzsperreInstalliert(t)
	fx := hoehenDienstAuf(t, 1234.6)

	for _, ziel := range []string{
		"http://netzsperre-probe.invalid/api/v1/lookup",
		"https://api.open-elevation.com.netzsperre-probe.invalid/api/v1/lookup",
	} {
		_, _, err := holeUeberStandardClient(ziel + "?locations=1.000000,2.000000")
		if err == nil || !strings.Contains(err.Error(), netzsperreFehlerTag) {
			t.Errorf("Abruf an %s muss trotz aktiver Umleitung von der Netzsperre abgelehnt werden, bekam err=%v", ziel, err)
		}
		nimmEigenenSperrEintrag(t, ziel)
	}
	if n := len(fx.locations()); n != 0 {
		t.Fatalf("Fremd-Host-Abruf darf das Fixture nicht erreichen, Fixture zaehlt %d Anfrage(n): %v", n, fx.locations())
	}
}

// AC-4 + AC-5: Waehrend des Unter-Tests leitet das Fixture open-elevation auf
// Loopback um; nach dessen Cleanup ist exakt der vorige Transport zurueck,
// und ein Open-Elevation-Abruf wird wieder abgelehnt und vermerkt (keine
// Duldung mehr, TestMain wuerde den Lauf rot machen).
func TestHoehenFixture_CleanupStelltSperreWiederHer(t *testing.T) {
	pruefeNetzsperreInstalliert(t)
	vorher := http.DefaultTransport

	t.Run("mit_fixture", func(t *testing.T) {
		fx := hoehenDienstAuf(t, 1234.6)
		if http.DefaultTransport == vorher {
			t.Fatal("hoehenDienstAuf muss einen umleitenden Transport ueber die Sperre legen")
		}
		status, body, err := holeUeberStandardClient("https://api.open-elevation.com/api/v1/lookup?locations=47.078900,11.685600")
		if err != nil {
			t.Fatalf("Open-Elevation-Abruf muss bei aktivem Fixture auf Loopback umgeleitet werden, bekam err=%v", err)
		}
		if status != http.StatusOK || !strings.Contains(body, "1234.6") {
			t.Fatalf("Fixture-Antwort: Status %d, Body %q; erwartet 200 mit elevation 1234.6", status, body)
		}
		if got := fx.locations(); len(got) != 1 || got[0] != "47.078900,11.685600" {
			t.Fatalf("Fixture muss die Abfrage locations=47.078900,11.685600 merken, bekam %v", got)
		}
	})

	if http.DefaultTransport != vorher {
		t.Fatalf("nach dem Cleanup muss exakt der vorige Transport zurueck sein, ist %T", http.DefaultTransport)
	}
	pruefeNetzsperreInstalliert(t)

	const ziel = "https://api.open-elevation.com/api/v1/lookup"
	_, _, err := holeUeberStandardClient(ziel + "?locations=47.078900,11.685600")
	if err == nil || !strings.Contains(err.Error(), netzsperreFehlerTag) {
		t.Fatalf("ohne Fixture muss der Open-Elevation-Abruf von der Sperre abgelehnt werden, bekam err=%v", err)
	}
	// Steht im Register (keine Duldung mehr): TestMain wuerde rot werden.
	nimmEigenenSperrEintrag(t, ziel)
}
