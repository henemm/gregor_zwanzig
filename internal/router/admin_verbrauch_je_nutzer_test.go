package router

// TDD RED — Issue #2475 (S4 von #2150): Verbrauch je Nutzer in der Admin-API.
// Spec: docs/specs/modules/forecast_budget_verbrauch_je_nutzer.md (AC-1 bis AC-4)
//
// Echter Produktions-Router ueber adminTestRouter (alice, bob, ops mit Sitzung),
// echte Zaehlerdateien unter data/users/<uid>/diagnostics/. Kein Mock.

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

func vzHeute() string { return time.Now().UTC().Format("2006-01-02") }

// vzZaehlerDatei schreibt den Rohinhalt der Nutzer-Zaehlerdatei.
func vzZaehlerDatei(t *testing.T, s *store.Store, uid, inhalt string) {
	t.Helper()
	dir := filepath.Join(s.UserDir(uid), "diagnostics")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "forecast_budget.json"), []byte(inhalt), 0o644); err != nil {
		t.Fatalf("Zaehlerdatei schreiben: %v", err)
	}
}

func vzZaehler(datum string, n int) string {
	b, _ := json.Marshal(map[string]any{"date": datum, "calls": map[string]int{"openmeteo": n}})
	return string(b)
}

// vzWert liest open_meteo_calls_today eines Eintrags; fehlt das Feld: -1.
func vzWert(t *testing.T, eintrag map[string]json.RawMessage) int {
	t.Helper()
	raw, ok := eintrag["open_meteo_calls_today"]
	if !ok {
		return -1
	}
	var n int
	if err := json.Unmarshal(raw, &n); err != nil {
		t.Fatalf("open_meteo_calls_today ist keine Zahl: %s", raw)
	}
	return n
}

// AC-1: zwei Nutzer, verschiedene Zahlen, keine Vermischung (Gegenprobe mit
// vertauschten Werten im zweiten Lauf).
func TestAdminUsersVerbrauch_AC1_JeNutzerDieRichtigeZahl(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "ops")
	vzZaehlerDatei(t, s, "alice", vzZaehler(vzHeute(), 120))
	vzZaehlerDatei(t, s, "bob", vzZaehler(vzHeute(), 7))

	liste, _ := auListe(t, r, secret, "ops")
	if got := vzWert(t, liste["alice"]); got != 120 {
		t.Errorf("AC-1: alice open_meteo_calls_today = %d, erwartet 120 (-1 = Feld fehlt)", got)
	}
	if got := vzWert(t, liste["bob"]); got != 7 {
		t.Errorf("AC-1: bob open_meteo_calls_today = %d, erwartet 7 (-1 = Feld fehlt)", got)
	}

	// Werte vertauschen: die Antwort muss folgen, nicht an der Reihenfolge haengen.
	vzZaehlerDatei(t, s, "alice", vzZaehler(vzHeute(), 7))
	vzZaehlerDatei(t, s, "bob", vzZaehler(vzHeute(), 120))
	liste, _ = auListe(t, r, secret, "ops")
	if a, b := vzWert(t, liste["alice"]), vzWert(t, liste["bob"]); a != 7 || b != 120 {
		t.Errorf("AC-1 (vertauscht): alice=%d bob=%d, erwartet 7/120", a, b)
	}
}

// AC-2: gestriges Datum => 0, Feld vorhanden.
func TestAdminUsersVerbrauch_AC2_GestrigesDatumIstNull(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "ops")
	gestern := time.Now().UTC().AddDate(0, 0, -1).Format("2006-01-02")
	vzZaehlerDatei(t, s, "alice", vzZaehler(gestern, 8999))

	liste, _ := auListe(t, r, secret, "ops")
	if got := vzWert(t, liste["alice"]); got != 0 {
		t.Errorf("AC-2: gestriger Zaehler muss 0 liefern (-1 = Feld fehlt), bekommen %d", got)
	}
}

// AC-3: fehlende / leere / kaputte Datei => 200 und 0, andere Nutzer behalten Werte.
func TestAdminUsersVerbrauch_AC3_FehlendeLeereKaputteDateiBrichtNichts(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "ops")
	// alice: keine Datei; bob: kaputt; ops: gueltig
	vzZaehlerDatei(t, s, "bob", "{kaputt")
	vzZaehlerDatei(t, s, "ops", vzZaehler(vzHeute(), 42))

	liste, _ := auListe(t, r, secret, "ops") // auListe prueft Status 200
	if got := vzWert(t, liste["alice"]); got != 0 {
		t.Errorf("AC-3: alice (ohne Datei) = %d, erwartet 0", got)
	}
	if got := vzWert(t, liste["bob"]); got != 0 {
		t.Errorf("AC-3: bob (kaputte Datei) = %d, erwartet 0", got)
	}
	if got := vzWert(t, liste["ops"]); got != 42 {
		t.Errorf("AC-3: ops (gueltige Datei) = %d, erwartet 42", got)
	}

	vzZaehlerDatei(t, s, "bob", "") // leere Datei
	liste, _ = auListe(t, r, secret, "ops")
	if got := vzWert(t, liste["bob"]); got != 0 {
		t.Errorf("AC-3: bob (leere Datei) = %d, erwartet 0", got)
	}
}

// AC-4: Nicht-Admin 403, ohne Anmeldung 401 — Koerper ohne Verbrauchszahl.
func TestAdminUsersVerbrauch_AC4_NurAdminSiehtDieZahl(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "ops")
	vzZaehlerDatei(t, s, "alice", vzZaehler(vzHeute(), 120))

	// Positivkontrolle: der Admin sieht das Feld mit dem Wert.
	liste, _ := auListe(t, r, secret, "ops")
	if got := vzWert(t, liste["alice"]); got != 120 {
		t.Fatalf("AC-4 Positivkontrolle: Admin sieht %d, erwartet 120", got)
	}

	for _, wer := range []struct {
		uid  string
		code int
	}{{"bob", http.StatusForbidden}, {"", http.StatusUnauthorized}} {
		w := auRuf(t, r, secret, http.MethodGet, "/api/admin/users", wer.uid, "")
		if w.Code != wer.code {
			t.Errorf("AC-4: %q erwartet %d, bekommen %d", wer.uid, wer.code, w.Code)
		}
		if strings.Contains(w.Body.String(), "open_meteo_calls_today") || strings.Contains(w.Body.String(), "120") {
			t.Errorf("AC-4: Antwort an %q enthaelt Verbrauchsdaten: %s", wer.uid, w.Body.String())
		}
	}
}
