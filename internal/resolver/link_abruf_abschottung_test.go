// Issue #2961 (ADR-0114): Abrufe geteilter Kartenlinks laufen nur ueber die
// Erlaubnisliste und den abgeschotteten Client. Gemessen wird am Empfaenger:
// echte httptest-Server halten fest, ob und mit welchen Kopfzeilen eine
// Anfrage ankam. Spec: docs/specs/modules/security_haertung_2026_11_go_schnittstellen.md
// (AC-1 bis AC-5).
package resolver_test

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/resolver"
)

type empfang struct {
	mu     sync.Mutex
	hits   int
	header string
}

func (e *empfang) anzahl() int {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.hits
}

func zielServer(t *testing.T, e *empfang, h http.HandlerFunc) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		e.mu.Lock()
		e.hits++
		e.header = r.Header.Get(coreauth.HeaderName)
		e.mu.Unlock()
		if h != nil {
			h(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(srv.Close)
	return srv
}

func hostOf(t *testing.T, raw string) string {
	t.Helper()
	u, err := url.Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	return u.Hostname()
}

func erwarteNichtAufloesbar(t *testing.T, input string, err error) {
	t.Helper()
	re, ok := err.(*resolver.ResolveError)
	if !ok {
		t.Fatalf("%q: erwartet ResolveError, bekam %v", input, err)
	}
	if re.Code != "resolve_failed" || re.Key != "fach.resolver.maps_aufloesen" {
		t.Fatalf("%q: erwartet resolve_failed/maps_aufloesen, bekam %q/%q", input, re.Code, re.Key)
	}
}

// AC-1: Eine Eingabe, die nur nach Kartenlink aussieht, aber auf einen
// fremden Host zeigt, wird nie abgerufen.
func TestLinkAbruf_FremderHostWirdNichtAbgerufen(t *testing.T) {
	var e empfang
	srv := zielServer(t, &e, nil)

	for _, input := range []string{
		srv.URL + "/x?y=.google.maps",
		srv.URL + "/maps.app.goo.gl/abc",
		"https://maps.google.com@" + hostOf(t, srv.URL) + "/maps",
	} {
		_, err := resolver.Resolve(input)
		erwarteNichtAufloesbar(t, input, err)
	}
	if n := e.anzahl(); n != 0 {
		t.Fatalf("fremder Host wurde %d-mal abgerufen, erwartet 0", n)
	}
}

// AC-1: Selbst ein erlaubter Host wird ueber http:// nicht abgerufen.
func TestLinkAbruf_NurHTTPS(t *testing.T) {
	var e empfang
	srv := zielServer(t, &e, nil)
	resolver.ErlaubeTestHosts(t, hostOf(t, srv.URL))
	resolver.ErlaubeLoopbackVerbindung(t)

	_, err := resolver.Resolve(srv.URL + "/maps?q=.google.")
	erwarteNichtAufloesbar(t, srv.URL, err)
	if n := e.anzahl(); n != 0 {
		t.Fatalf("http-Link wurde %d-mal abgerufen, erwartet 0", n)
	}
}

// AC-2: Ein Redirect auf einen Host ausserhalb der Liste wird nicht verfolgt.
func TestLinkAbruf_RedirectAufFremdenHostWirdNichtVerfolgt(t *testing.T) {
	var fremd empfang
	fremdSrv := zielServer(t, &fremd, nil)

	var erlaubt empfang
	// "localhost" ist hier der erlaubte Link-Host; das Redirect-Ziel 127.0.0.1
	// ist derselbe Rechner, steht aber nicht auf der Liste.
	erlaubtSrv := zielServer(t, &erlaubt, func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, fremdSrv.URL+"/maps/@47.1,11.1,13z", http.StatusFound)
	})
	u, _ := url.Parse(erlaubtSrv.URL)
	link := "http://localhost:" + u.Port() + "/maps?q=.google."

	resolver.ErlaubeTestHosts(t, "localhost")
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeLoopbackVerbindung(t)

	_, err := resolver.Resolve(link)
	erwarteNichtAufloesbar(t, link, err)
	if erlaubt.anzahl() != 1 {
		t.Fatalf("erlaubter Link: %d Abrufe, erwartet 1", erlaubt.anzahl())
	}
	if n := fremd.anzahl(); n != 0 {
		t.Fatalf("Redirect-Ziel ausserhalb der Liste wurde %d-mal abgerufen", n)
	}
}

// AC-2: Hoechstens fuenf Weiterleitungen.
func TestLinkAbruf_HoechstensFuenfWeiterleitungen(t *testing.T) {
	var e empfang
	var srv *httptest.Server
	srv = zielServer(t, &e, func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, srv.URL+"/maps?q=.google.", http.StatusFound)
	})
	resolver.ErlaubeTestHosts(t, hostOf(t, srv.URL))
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeLoopbackVerbindung(t)

	_, err := resolver.Resolve(srv.URL + "/maps?q=.google.")
	erwarteNichtAufloesbar(t, srv.URL, err)
	if n := e.anzahl(); n > 6 {
		t.Fatalf("%d Abrufe in der Weiterleitungskette, erwartet hoechstens 6", n)
	}
}

// AC-3: Ein erlaubter Name, der auf eine interne Adresse aufloest, wird nicht
// verbunden — die Sperre greift an der tatsaechlichen IP.
func TestLinkAbruf_InterneAdresseWirdNichtVerbunden(t *testing.T) {
	var e empfang
	srv := zielServer(t, &e, nil)
	u, _ := url.Parse(srv.URL)
	resolver.ErlaubeTestHosts(t, "localhost")
	resolver.ErlaubeHTTPSchema(t)
	// bewusst KEIN ErlaubeLoopbackVerbindung

	_, err := resolver.Resolve("http://localhost:" + u.Port() + "/maps?q=.google.")
	erwarteNichtAufloesbar(t, srv.URL, err)
	if n := e.anzahl(); n != 0 {
		t.Fatalf("interne Adresse wurde %d-mal erreicht, erwartet 0", n)
	}
}

// AC-4: Ein Abruf aus dem Resolver traegt das Dienstgeheimnis fuer den
// Python-Core nie — auch dann nicht, wenn das Ziel zufaellig die Core-Adresse
// ist und alle anderen Sperren fuer den Test geoeffnet sind.
func TestLinkAbruf_TraegtKeinDienstgeheimnis(t *testing.T) {
	var core empfang
	coreSrv := zielServer(t, &core, nil)

	orig := http.DefaultTransport
	coreauth.Install(&config.Config{PythonCoreURL: coreSrv.URL, CoreSharedSecret: "core-shared-secret-fuer-tests-0123456789"})
	t.Cleanup(func() {
		coreauth.Uninstall()
		http.DefaultTransport = orig
	})

	// Ohne Oeffnung: kein Abruf.
	_, err := resolver.Resolve(coreSrv.URL + "/api/compare?x=.google.maps")
	erwarteNichtAufloesbar(t, coreSrv.URL, err)
	if core.anzahl() != 0 {
		t.Fatalf("Core wurde aus dem Resolver erreicht (%d)", core.anzahl())
	}

	// Mit Oeffnung (nur im Test): Abruf findet statt, aber ohne Geheimnis.
	resolver.ErlaubeTestHosts(t, hostOf(t, coreSrv.URL))
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeLoopbackVerbindung(t)
	_, _ = resolver.Resolve(coreSrv.URL + "/maps?q=.google.")
	if core.anzahl() != 1 {
		t.Fatalf("Kontrollabruf: %d Abrufe, erwartet 1", core.anzahl())
	}
	if core.header != "" {
		t.Fatalf("Resolver-Abruf trug %s — das Dienstgeheimnis darf nie mitgehen", coreauth.HeaderName)
	}
}

// AC-1/AC-3: Erlaubnisliste und Adresssperre im Einzelnen.
func TestLinkAbruf_ErlaubnislisteUndAdresssperre(t *testing.T) {
	for host, want := range map[string]bool{
		"maps.app.goo.gl": true, "goo.gl": true, "www.google.com": true,
		"maps.google.com": true, "google.com": true, "www.google.de": true,
		"www.google.co.uk": true, "maps.google.com.au": true, "WWW.GOOGLE.FR": true,
		"google.evil.example": false, "evilgoogle.com": false, "google.com.evil.example": false,
		"x.www.google.com": false, "localhost": false, "127.0.0.1": false, "": false,
	} {
		if got := resolver.IstGoogleLinkHost(host); got != want {
			t.Errorf("IstGoogleLinkHost(%q) = %v, erwartet %v", host, got, want)
		}
	}
	for ip, want := range map[string]bool{
		"8.8.8.8": true, "2a00:1450:4001::200e": true,
		"127.0.0.1": false, "10.1.2.3": false, "172.16.0.1": false, "192.168.1.1": false,
		"169.254.169.254": false, "100.64.0.1": false, "224.0.0.1": false, "0.0.0.0": false,
		"255.255.255.255": false, "::1": false, "fe80::1": false, "fc00::1": false,
		"ff02::1": false, "::ffff:127.0.0.1": false, "::ffff:10.0.0.1": false, "::": false,
		"64:ff9b::a00:1": false, "2002:a00:1::": false,
	} {
		if got := resolver.IstOeffentlicheAdresse(ip); got != want {
			t.Errorf("IstOeffentlicheAdresse(%q) = %v, erwartet %v", ip, got, want)
		}
	}
}
