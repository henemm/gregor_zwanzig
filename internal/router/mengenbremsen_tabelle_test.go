package router

// Issue #2961 (Spec AC-5, AC-11 bis AC-15, Fix-Runde Gegenpruefung F4):
// Tabellentest ueber ALLE gebremsten Routen mit festem Limit UND Fenster.
// Die Uhr der Bremsen wird ueber handler.SetBremsenUhr gestellt; Grenzen und
// Fenster stehen hier als Literale, damit eine Verfaelschung der Konstanten
// rot wird.

import (
	"net/http"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/handler"
)

type testUhr struct {
	mu sync.Mutex
	t  time.Time
}

func (u *testUhr) jetzt() time.Time { u.mu.Lock(); defer u.mu.Unlock(); return u.t }
func (u *testUhr) weiter(d time.Duration) {
	u.mu.Lock()
	u.t = u.t.Add(d)
	u.mu.Unlock()
}

func stelleUhr(t *testing.T) *testUhr {
	t.Helper()
	u := &testUhr{t: time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)}
	t.Cleanup(handler.SetBremsenUhr(u.jetzt))
	return u
}

type gebremsteRoute struct {
	method, pfad, body string
	limit              int
	fenster            time.Duration
	variante           string
}

const gpxRumpf = `{"input":"<trkpt lat=\"47.1\" lon=\"11.1\"><ele>1000</ele></trkpt>"}`

var alleGebremstenRouten = []gebremsteRoute{
	{http.MethodPost, "/api/locations/resolve", gpxRumpf, 30, time.Minute, "aufloesen"},
	{http.MethodPost, "/api/notify/test", `{"channel":"telegram"}`, 10, time.Hour, "testnachricht"},
	{http.MethodPost, "/api/trips/t1/send", "", 20, time.Hour, "versand"},
	{http.MethodPost, "/api/compare/presets/p1/send", "", 20, time.Hour, "versand"},
	{http.MethodPost, "/api/briefings/t1/send?kind=route", "", 20, time.Hour, "versand"},
	{http.MethodGet, "/api/compare?location_ids=a", "", 60, time.Minute, "abruf"},
	{http.MethodGet, "/api/trips/t1/stages/weather", "", 60, time.Minute, "abruf"},
	{http.MethodGet, "/api/preview/t1/sms", "", 60, time.Minute, "abruf"},
	{http.MethodPost, "/api/trips/t1/alert-preview", `{}`, 60, time.Minute, "abruf"},
	{http.MethodPost, "/api/briefings/t1/alert-preview?kind=route", `{}`, 60, time.Minute, "abruf"},
	{http.MethodPost, "/api/gpx/parse", `{}`, 30, time.Hour, "gpx"},
}

func rumpf(s string) []byte {
	if s == "" {
		return nil
	}
	return []byte(s)
}

func TestMengenbremse_AlleRoutenLimitUndFenster(t *testing.T) {
	for _, rt := range alleGebremstenRouten {
		t.Run(rt.method+" "+rt.pfad, func(t *testing.T) {
			uhr := stelleUhr(t)
			e := neueBremsUmgebung(t, nil)
			c := e.konto(t, "uwe-tabelle", "de")
			for i := 0; i < rt.limit; i++ {
				if w := e.rufe(t, rt.method, rt.pfad, rumpf(rt.body), c); w.Code == http.StatusTooManyRequests {
					t.Fatalf("Aufruf %d von %d vorzeitig gebremst", i+1, rt.limit)
				}
			}
			vorher := e.core.Load()
			erwarte429(t, e.rufe(t, rt.method, rt.pfad, rumpf(rt.body), c), rt.variante)
			if e.core.Load() != vorher {
				t.Fatal("gebremster Aufruf hat den Core erreicht")
			}
			// Nach einer Minute: Stundenfenster weiter gesperrt.
			uhr.weiter(time.Minute + time.Second)
			w := e.rufe(t, rt.method, rt.pfad, rumpf(rt.body), c)
			if rt.fenster == time.Hour {
				erwarte429(t, w, rt.variante)
				uhr.weiter(time.Hour)
				w = e.rufe(t, rt.method, rt.pfad, rumpf(rt.body), c)
			}
			if w.Code == http.StatusTooManyRequests {
				t.Fatalf("nach Ablauf des Fensters (%s) weiter gebremst: %s", rt.fenster, w.Body.String())
			}
		})
	}
}

// Etappenwetter und Vorschau haben je ein eigenes Minutenfenster; die drei
// Vorschau-Routen teilen sich eines.
func TestMengenbremse_EtappenwetterUndVorschauEigenstaendig(t *testing.T) {
	stelleUhr(t)
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "vera-eigen", "de")
	for i := 0; i < 60; i++ {
		e.rufe(t, http.MethodGet, "/api/trips/t1/stages/weather", nil, c)
	}
	erwarte429(t, e.rufe(t, http.MethodGet, "/api/trips/t1/stages/weather", nil, c), "abruf")
	if w := e.rufe(t, http.MethodGet, "/api/preview/t1/sms", nil, c); w.Code == http.StatusTooManyRequests {
		t.Fatal("Vorschau teilt faelschlich das Fenster des Etappenwetters")
	}

	e2 := neueBremsUmgebung(t, nil)
	c2 := e2.konto(t, "willi-eigen", "de")
	for i := 0; i < 60; i++ {
		e2.rufe(t, http.MethodPost, "/api/trips/t1/alert-preview", []byte(`{}`), c2)
	}
	erwarte429(t, e2.rufe(t, http.MethodGet, "/api/preview/t1/sms", nil, c2), "abruf")
	erwarte429(t, e2.rufe(t, http.MethodPost, "/api/briefings/t1/alert-preview?kind=route", []byte(`{}`), c2), "abruf")
	if w := e2.rufe(t, http.MethodGet, "/api/trips/t1/stages/weather", nil, c2); w.Code == http.StatusTooManyRequests {
		t.Fatal("Etappenwetter teilt faelschlich das Fenster der Vorschau")
	}
}
