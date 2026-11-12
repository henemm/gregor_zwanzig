package router

// Issue #2961 (Spec security_haertung_2026_11_go_schnittstellen.md AC-9):
// Zugriffe auf UNBEKANNTE Kennungen hinterlassen keine <id>.json.lock im
// Nutzerverzeichnis — gemessen am echten Router und am Dateisystem. Die
// Gegenprobe zeigt, dass die Sperrdatei bei einem existierenden Trip ihre
// Rolle als Betriebsmittel behaelt (ADR-0083).

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func sperrdateien(t *testing.T, dir string) []string {
	t.Helper()
	var funde []string
	_ = filepath.Walk(dir, func(p string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() && strings.HasSuffix(p, ".lock") {
			funde = append(funde, p)
		}
		return nil
	})
	return funde
}

func TestSperrdatei_UnbekannteKennungHinterlaesstNichts(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "lara-sperre", "de")

	const n = 25
	for i := 0; i < n; i++ {
		id := fmt.Sprintf("gibt-es-nicht-%d", i)
		for _, a := range []struct {
			method, pfad, body string
		}{
			{http.MethodGet, "/api/trips/" + id, ""},
			{http.MethodPut, "/api/trips/" + id, `{"id":"` + id + `","name":"x"}`},
			{http.MethodPatch, "/api/trips/" + id + "/state", `{"state":"archived"}`},
			{http.MethodGet, "/api/trips/" + id + "/weather-config", ""},
			{http.MethodPut, "/api/trips/" + id + "/weather-config", `{}`},
			{http.MethodGet, "/api/compare/presets/" + id, ""},
			{http.MethodPut, "/api/compare/presets/" + id, `{"name":"x"}`},
			{http.MethodPatch, "/api/compare/presets/" + id + "/state", `{"state":"archived"}`},
			{http.MethodDelete, "/api/compare/presets/" + id, ""},
			{http.MethodDelete, "/api/trips/" + id, ""},
			{http.MethodGet, "/api/briefings/" + id + "?kind=route", ""},
			{http.MethodGet, "/api/briefings/" + id + "?kind=vergleich", ""},
		} {
			var body []byte
			if a.body != "" {
				body = []byte(a.body)
			}
			w := e.rufe(t, a.method, a.pfad, body, c)
			if w.Code < 400 {
				t.Fatalf("%s %s: erwartet Fehlerstatus fuer unbekannte Kennung, bekommen %d: %s",
					a.method, a.pfad, w.Code, w.Body.String())
			}
		}
	}
	if funde := sperrdateien(t, filepath.Join(e.s.DataDir, "users")); len(funde) != 0 {
		t.Fatalf("%d Sperrdateien fuer unbekannte Kennungen hinterlassen, erwartet 0: %v", len(funde), funde[:min(3, len(funde))])
	}

	// Gegenprobe: ein angelegter Trip bleibt les- und schreibbar.
	w := e.rufe(t, http.MethodPost, "/api/trips", []byte(`{"id":"echt-1","name":"Echt","stages":[]}`), c)
	if w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("Anlage: %d %s", w.Code, w.Body.String())
	}
	if w := e.rufe(t, http.MethodGet, "/api/trips/echt-1", nil, c); w.Code != http.StatusOK {
		t.Fatalf("Lesen nach Anlage: %d %s", w.Code, w.Body.String())
	}
}
