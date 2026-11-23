// Issue #2961 (Spec AC-1 bis AC-4, AC-25; Fix-Runde Gegenpruefung F5/F6):
// Ergaenzende Nachweise fuer den abgeschotteten Link-Abruf — Egress-Waechter
// je Abruf, IPv4-mapped und eingebettete IPv4-Adressen, Nutzer-Info, kein
// Umgebungs-Proxy, Komoot-Hostpruefung, feste Laender-Domain-Liste, Port.
package resolver_test

import (
	"net"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/egress"
	"github.com/henemm/gregor-api/internal/resolver"
)

// lauscheAufNichtFreigegebenemLoopback lauscht auf "<host>:0" fuer den ersten
// nutzbaren Kandidaten und gibt Listener und Host zurueck (Issue #3294).
// Hintergrund: macOS kennt auf lo0 nur 127.0.0.1 und ::1, 127.0.0.2 fehlt dort;
// 127.0.0.1 taugt nicht, weil der Egress-Waechter es freigibt. Ist kein
// Kandidat nutzbar, wird der Test mit Begruendung uebersprungen.
func lauscheAufNichtFreigegebenemLoopback(t *testing.T, kandidaten ...string) (net.Listener, string) {
	t.Helper()
	var fehler []string
	for _, host := range kandidaten {
		ln, err := net.Listen("tcp", net.JoinHostPort(host, "0"))
		if err == nil {
			return ln, host
		}
		fehler = append(fehler, host+": "+err.Error())
	}
	t.Skipf("Messaufbau: keine nicht freigegebene Loopback-Adresse nutzbar (%v)", fehler)
	return nil, ""
}

// F5a: Auf Staging fragt der abgeschottete Client den Egress-Waechter je
// Abruf; ein dort nicht freigegebener Host wird nicht abgerufen. Der
// Ziel-Server lauscht auf einer Loopback-Adresse, die der Waechter nicht
// freigibt (er kennt nur localhost/127.0.0.1): unter Linux 127.0.0.2, unter
// macOS (lo0 ohne 127.0.0.2) ::1 (Issue #3294). Der Kontrollabruf ohne
// Waechter erreicht denselben Server.
func TestLinkAbruf_EgressWaechterWirdJeAbrufGefragt(t *testing.T) {
	pruefeEgressWaechterJeAbruf(t, egressLoopbackKandidaten...)
}

// egressLoopbackKandidaten: nicht freigegebene Loopback-Adressen in
// Vorzugsreihenfolge (Linux 127.0.0.2, macOS ::1). Festgeschrieben in
// TestLoopbackAuswahl3294_EgressTestLaeuftOhne127002 (Issue #3294, F003).
var egressLoopbackKandidaten = []string{"127.0.0.2", "::1"}

func pruefeEgressWaechterJeAbruf(t *testing.T, kandidaten ...string) {
	t.Helper()
	resolver.OhneNachschlagDienste(t)
	ln, host := lauscheAufNichtFreigegebenemLoopback(t, kandidaten...)
	var e empfang
	srv := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		e.mu.Lock()
		e.hits++
		e.mu.Unlock()
	}))
	srv.Listener.Close()
	srv.Listener = ln
	srv.Start()
	t.Cleanup(srv.Close)
	link := srv.URL + "/maps?q=.google."
	resolver.ErlaubeTestHosts(t, host)
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeLoopbackVerbindung(t)

	// Kontrolle ohne Waechter: der Abruf findet statt.
	_, _ = resolver.Resolve(link)
	if e.anzahl() != 1 {
		t.Fatalf("Messaufbau: Kontrollabruf erreichte den Server %d-mal", e.anzahl())
	}

	orig := http.DefaultTransport
	if !egress.Install(&config.Config{Env: "staging"}) {
		t.Fatal("Egress-Waechter nicht installiert")
	}
	t.Cleanup(func() {
		egress.Uninstall()
		http.DefaultTransport = orig
	})
	_, err := resolver.Resolve(link)
	erwarteNichtAufloesbar(t, link, err)
	if e.anzahl() != 1 {
		t.Fatalf("nicht freigegebener Host trotz Waechter abgerufen (%d)", e.anzahl())
	}
}

// F5b/F6: IPv4-mapped, IPv4-kompatible, Teredo- und Site-Local-Adressen
// sind gesperrt (Unmap und eingebettete IPv4 wirken).
func TestLinkAbruf_EingebetteteIPv4Gesperrt(t *testing.T) {
	for _, ip := range []string{
		"::ffff:100.64.0.1", "::ffff:169.254.169.254", "::ffff:192.168.0.1", "::ffff:172.16.0.1",
		"::ffff:0.0.0.1", "::ffff:224.0.0.1", "::ffff:198.18.0.1",
		"::7f00:1", "::a00:1", "2001:0:4136:e378:8000:63bf:3fff:fdd2", "fec0::1",
	} {
		if resolver.IstOeffentlicheAdresse(ip) {
			t.Errorf("IstOeffentlicheAdresse(%q) = true, erwartet false", ip)
		}
	}
	for _, ip := range []string{"::ffff:8.8.8.8", "2a00:1450:4001::200e"} {
		if !resolver.IstOeffentlicheAdresse(ip) {
			t.Errorf("IstOeffentlicheAdresse(%q) = false, erwartet true", ip)
		}
	}
}

// F5c/F6: Nutzer-Info, fremde Laender-Domains und andere Ports werden
// abgelehnt; die gelisteten Domains sind erlaubt.
func TestLinkAbruf_LinkPruefungNutzerInfoDomainsPort(t *testing.T) {
	for _, raw := range []string{
		"https://user@www.google.com/maps/@47.1,11.1,13z",
		"https://user:pw@maps.google.com/maps",
		"https://google.xx/maps", "https://www.google.xx/maps",
		"https://google.com.xx/maps", "https://maps.google.co.xx/maps",
		"https://maps.google.com:8000/maps", "https://www.google.de:444/maps",
		"https://google.evil.example/maps", "https://x.maps.google.com/maps",
	} {
		if err := resolver.PruefeLinkURL(raw); err == nil {
			t.Errorf("PruefeLinkURL(%q) erlaubt, erwartet abgelehnt", raw)
		}
	}
	for _, raw := range []string{"https://maps.google.com:443/maps", "https://maps.app.goo.gl/abc", "https://goo.gl/maps/abc"} {
		if err := resolver.PruefeLinkURL(raw); err != nil {
			t.Errorf("PruefeLinkURL(%q) abgelehnt: %v", raw, err)
		}
	}
	for _, d := range resolver.GoogleLaenderDomains() {
		for _, vor := range []string{"", "www.", "maps."} {
			raw := "https://" + vor + d + "/maps"
			if err := resolver.PruefeLinkURL(raw); err != nil {
				t.Errorf("gelistete Domain %q abgelehnt: %v", raw, err)
			}
		}
	}
	for _, d := range []string{"google.de", "google.at", "google.ch", "google.it", "google.fr", "google.co.uk", "google.com.au"} {
		if err := resolver.PruefeLinkURL("https://www." + d + "/maps"); err != nil {
			t.Errorf("Zielgruppen-Domain %q abgelehnt", d)
		}
	}
}

// F5d: der abgeschottete Client nutzt keinen Proxy aus der Umgebung — sonst
// pruefte die Adresssperre die Adresse des Proxys statt des Ziels.
func TestLinkAbruf_KeinUmgebungsProxy(t *testing.T) {
	t.Setenv("HTTPS_PROXY", "http://127.0.0.1:9")
	t.Setenv("HTTP_PROXY", "http://127.0.0.1:9")
	if !resolver.LinkClientOhneUmgebungsProxy() {
		t.Fatal("Link-Client hat einen Proxy gesetzt")
	}
}

// F5e: ein fremder Host mit "komoot.com" in Pfad oder Query wird nicht als
// Komoot-Link behandelt (kein Komoot-API-Abruf, fachlicher Fehler komoot_url).
func TestLinkAbruf_KomootNurAmHost(t *testing.T) {
	for _, raw := range []string{
		"https://evil.example/www.komoot.com/highlight/126361",
		"https://evil.example/x?u=https://www.komoot.com/de-de/highlight/126361",
		"https://komoot.com.evil.example/highlight/126361",
	} {
		_, err := resolver.Resolve(raw)
		re, ok := err.(*resolver.ResolveError)
		if !ok || re.Key != "fach.resolver.komoot_url" {
			t.Errorf("%q: erwartet fach.resolver.komoot_url ohne API-Abruf, bekam %v", raw, err)
		}
	}
}
