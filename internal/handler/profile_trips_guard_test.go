package handler

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
)

// TDD (#1708 Scheibe A, ADR-0023): Seit dem Cutover leben Trips
// ausschliesslich in data/users/<uid>/briefings/<id>.json. Ein frisch
// registrierter Nutzer darf deshalb KEIN trips/-Verzeichnis mehr bekommen --
// dessen Anlage widerspricht ADR-0023 und stellt die tote Ablage aus #1708
// bei jeder Registrierung laufend neu her. Der Bestandstest
// TestRegisterCreatesUserDirs behaelt die drei uebrigen Verzeichnisse
// (locations/, gpx/, weather_snapshots/) als echte Zusicherung.
func TestRegisterCreatesNoLegacyTripsDir(t *testing.T) {
	s := newTestStore(t)
	// Leere Config → dispatchVerificationMail bricht mangels SMTPHost sofort ab
	// (kein Netz-Zugriff); dieser Test prüft nur die Verzeichnis-Anlage.
	h := RegisterHandler(s, bcrypt.MinCost, config.Config{})

	body := `{"username":"newuser2","password":"geheim123","email":"newuser2@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	base := filepath.Join(s.DataDir, "users", "newuser2")
	tripsPath := filepath.Join(base, "trips")
	if _, err := os.Stat(tripsPath); !os.IsNotExist(err) {
		t.Errorf("#1708/ADR-0023: erwartet KEIN Legacy-Verzeichnis %s nach Registrierung, existiert aber (Stat-Fehler=%v)", tripsPath, err)
	}
}
