package scheduler

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #1555 — tier_request_health im oeffentlichen Status-Endpoint.
//
// Spec: docs/specs/modules/fix_1555_tier_antrag_sichtbarkeit.md
//
// KEINE Mocks: echte user.json-Dateien in t.TempDir(), echter httptest-
// Roundtrip gegen Status() (Muster: briefing_health_test.go).
//
// Alle Test-Nutzer-IDs tragen das unverwechselbare Praefix "gz1555" — die
// Datenschutz-Pruefung (AC-8) sucht danach im rohen Antwort-Text und darf
// nicht zufaellig auf einem Teilstring von etwas anderem anschlagen.

// tierUserJSON baut den Inhalt einer echten user.json. Leere Werte werden
// weggelassen (genau wie omitempty es in der Produktion tut) — so entsteht der
// Fall "Feld geloescht" wirklich als fehlendes Feld, nicht als Leerstring.
func tierUserJSON(id, tier, requestedTier string, requestedAt time.Time) string {
	parts := []string{
		`"id":"` + id + `"`,
		`"display_name":"` + id + `-anzeigename"`,
		`"email":"` + id + `@example.invalid"`,
	}
	if tier != "" {
		parts = append(parts, `"tier":"`+tier+`"`)
	}
	if requestedTier != "" {
		parts = append(parts, `"requested_tier":"`+requestedTier+`"`)
	}
	if !requestedAt.IsZero() {
		parts = append(parts, `"requested_at":"`+requestedAt.Format(time.RFC3339)+`"`)
	}
	return "{" + strings.Join(parts, ",") + "}"
}

// newTierRequestScheduler legt fuer jeden Eintrag (uid -> roher user.json-Inhalt)
// eine echte Datei an und baut einen Scheduler darauf.
func newTierRequestScheduler(t *testing.T, tmpDir string, users map[string]string) *Scheduler {
	t.Helper()
	st := store.New(tmpDir, "default")
	for uid, content := range users {
		dir := filepath.Join(tmpDir, "users", uid)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatalf("mkdir user dir: %v", err)
		}
		if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(content), 0o644); err != nil {
			t.Fatalf("write user.json: %v", err)
		}
	}
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, st)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return sched
}

// tierRequestHealthBlock fuehrt den echten HTTP-Roundtrip aus und liefert den
// tier_request_health-Block plus den rohen Antworttext.
func tierRequestHealthBlock(t *testing.T, sched *Scheduler) (map[string]any, string) {
	t.Helper()
	code, body, rawBody := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	th, ok := body["tier_request_health"].(map[string]any)
	if !ok {
		t.Fatalf("tier_request_health fehlt oder hat falschen Typ: %v", body["tier_request_health"])
	}
	return th, rawBody
}

// assertOpenCount prueft open_count als Zahl (JSON: float64).
func assertOpenCount(t *testing.T, th map[string]any, want float64) {
	t.Helper()
	if got := th["open_count"]; got != want {
		t.Errorf("open_count: want %v, got %v", want, got)
	}
}

// AC-1: Keine offenen Antraege -> Nullwerte, kein Fehler, kein fehlendes Feld.
func TestTierRequestHealthNullStateWhenNoOpenRequests(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-ac1-a": tierUserJSON("gz1555-ac1-a", "free", "", time.Time{}),
		"gz1555-ac1-b": tierUserJSON("gz1555-ac1-b", "standard", "", time.Time{}),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 0)
	if got := th["oldest_open_age_hours"]; got != float64(0) {
		t.Errorf("oldest_open_age_hours: want 0.0, got %v", got)
	}
}

// AC-2: ZWEI offene Antraege (8 Tage / 2 Stunden alt) -> gemeldet wird das
// Alter des AELTEREN. Zwingend zwei Antraege: bei nur einem waeren "aeltester"
// und "juengster" derselbe Wert und der Test koennte die Verwechslung gar nicht
// sehen. Die Mutation Before -> After in der Aeltester-Auswahl MUSS diesen Test
// rot machen (sie liefert dann ~2h statt >168h).
func TestTierRequestHealthReportsAgeOfOldestOpenRequest(t *testing.T) {
	tmpDir := t.TempDir()
	achtTage := time.Now().UTC().Add(-8 * 24 * time.Hour)
	zweiStunden := time.Now().UTC().Add(-2 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-ac2-alt": tierUserJSON("gz1555-ac2-alt", "free", "premium", achtTage),
		"gz1555-ac2-neu": tierUserJSON("gz1555-ac2-neu", "free", "standard", zweiStunden),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 2)

	age, ok := th["oldest_open_age_hours"].(float64)
	if !ok {
		t.Fatalf("oldest_open_age_hours fehlt oder falscher Typ: %v", th["oldest_open_age_hours"])
	}
	if age <= 168 || age > 200 {
		t.Errorf("oldest_open_age_hours: want Alter des AELTEREN Antrags (~192h, >168), got %v", age)
	}
}

// AC-3: Nutzer ohne requested_tier zaehlt nicht mit. Das tier-Feld ist hier
// absichtlich GESETZT: eine Implementierung, die auf "Tier leer" statt auf
// "RequestedTier leer" prueft, zaehlt diesen Nutzer dann faelschlich als offen.
func TestTierRequestHealthUserWithoutRequestDoesNotCount(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-ac3-ohne": tierUserJSON("gz1555-ac3-ohne", "standard", "", time.Time{}),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 0)
}

// AC-4: PO hat requested_tier geloescht (tier="standard") -> nicht mehr offen.
// requested_at bleibt absichtlich stehen: ein Aggregat, das das Alter aus
// requested_at ohne Offen-Pruefung berechnet, wird hier rot.
func TestTierRequestHealthClearedRequestedTierIsNotOpen(t *testing.T) {
	tmpDir := t.TempDir()
	achtTage := time.Now().UTC().Add(-8 * 24 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-ac4-erledigt": tierUserJSON("gz1555-ac4-erledigt", "standard", "", achtTage),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 0)
	if got := th["oldest_open_age_hours"]; got != float64(0) {
		t.Errorf("oldest_open_age_hours: want 0.0 (kein offener Antrag), got %v", got)
	}
}

// AC-5: tier="free", requested_tier="premium" -> offen. Zusammen mit AC-4/AC-6
// faengt das eine Implementierung, die nur auf "requested_tier nicht leer" oder
// nur auf den Vergleich prueft.
func TestTierRequestHealthUnhandledRequestIsOpen(t *testing.T) {
	tmpDir := t.TempDir()
	dreiStunden := time.Now().UTC().Add(-3 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-ac5-offen": tierUserJSON("gz1555-ac5-offen", "free", "premium", dreiStunden),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 1)

	age, ok := th["oldest_open_age_hours"].(float64)
	if !ok {
		t.Fatalf("oldest_open_age_hours fehlt oder falscher Typ: %v", th["oldest_open_age_hours"])
	}
	if age < 2.9 || age > 3.1 {
		t.Errorf("oldest_open_age_hours: want ~3.0, got %v", age)
	}
}

// AC-6: bereits exakt so freigeschaltet (tier == requested_tier, Feld stehen
// geblieben) -> nicht mehr offen. Mutations-Gegenprobe zu einer Pruefung, die
// nur "requested_tier nicht leer" abfragt.
func TestTierRequestHealthGrantedRequestWithLeftoverFieldIsNotOpen(t *testing.T) {
	tmpDir := t.TempDir()
	achtTage := time.Now().UTC().Add(-8 * 24 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-ac6-gewaehrt": tierUserJSON("gz1555-ac6-gewaehrt", "premium", "premium", achtTage),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 0)
	if got := th["oldest_open_age_hours"]; got != float64(0) {
		t.Errorf("oldest_open_age_hours: want 0.0 (Antrag bereits gewaehrt), got %v", got)
	}
}

// Normalisierung (Spec "Implementation Details"): die Offen-Pruefung MUSS
// model.EffectiveTier auf das gespeicherte tier anwenden. Ein Nutzer ohne
// tier-Feld, der "free" beantragt hat, ist bereits auf dem beantragten Level —
// eine Implementierung, die das rohe (leere) tier vergleicht, meldet ihn
// faelschlich als offen.
func TestTierRequestHealthEffectiveTierNormalizationApplied(t *testing.T) {
	tmpDir := t.TempDir()
	dreiStunden := time.Now().UTC().Add(-3 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-norm-leer": tierUserJSON("gz1555-norm-leer", "", "free", dreiStunden),
	})

	th, _ := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 0)
}

// AC-7: eine kaputte user.json darf die Gesamtauswertung nicht kippen. Der
// defekte Nutzer steht lexikalisch VOR dem gueltigen, damit auch ein
// vorzeitiges return statt continue auffliegt.
func TestTierRequestHealthCorruptUserJsonIsSkippedFailSoft(t *testing.T) {
	tmpDir := t.TempDir()
	dreiStunden := time.Now().UTC().Add(-3 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		"gz1555-aaa-defekt":  `{"id":"gz1555-aaa-defekt","tier":"free",`,
		"gz1555-zzz-gueltig": tierUserJSON("gz1555-zzz-gueltig", "free", "premium", dreiStunden),
	})

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200 trotz defekter user.json, got %d", code)
	}
	th, ok := body["tier_request_health"].(map[string]any)
	if !ok {
		t.Fatalf("tier_request_health fehlt oder hat falschen Typ: %v", body["tier_request_health"])
	}
	assertOpenCount(t, th, 1)
}

// AC-8: Datenschutz (#252) — der Endpoint ist ohne Login erreichbar. Die rohe
// Antwort darf weder user_id noch display_name noch E-Mail des Antragstellers
// enthalten. Vorbild: TestBriefingHealthResponseContainsNoUserIdentifiers.
func TestTierRequestHealthResponseContainsNoUserIdentifiers(t *testing.T) {
	tmpDir := t.TempDir()
	uid := "gz1555antragsteller7q"
	dreiStunden := time.Now().UTC().Add(-3 * time.Hour)
	sched := newTierRequestScheduler(t, tmpDir, map[string]string{
		uid: tierUserJSON(uid, "free", "premium", dreiStunden),
	})

	th, rawBody := tierRequestHealthBlock(t, sched)
	// Vorbedingung: es gibt ueberhaupt einen offenen Antrag zu verraten.
	assertOpenCount(t, th, 1)

	forbidden := []string{
		uid,
		uid + "-anzeigename",
		uid + "@example.invalid",
	}
	for _, id := range forbidden {
		if strings.Contains(rawBody, id) {
			t.Errorf("Privacy-Leak: Antwort enthaelt Kennung %q", id)
		}
	}
}

// ---- Issue #2436 (AC-7, AC-8) ----

func newTierRequestSchedulerCfg(t *testing.T, tmpDir string, poEmail, smtpHost string, users map[string]string) *Scheduler {
	t.Helper()
	st := store.New(tmpDir, "default")
	for uid, content := range users {
		dir := filepath.Join(tmpDir, "users", uid)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	cfg := &config.Config{
		PythonCoreURL: "http://localhost:8000", SchedulerTimezone: "Europe/Vienna",
		PoEmail: poEmail, SMTPHost: smtpHost,
	}
	sched, err := New(cfg, st)
	if err != nil {
		t.Fatal(err)
	}
	return sched
}

// AC-7: po_mail_configured nur wenn PO_EMAIL UND SMTP_HOST gesetzt sind.
func TestTierRequestHealthPoMailConfigured(t *testing.T) {
	cases := []struct {
		name, po, host string
		want           bool
	}{
		{"beides", "po@example.com", "smtp.example.com", true},
		{"po fehlt", "", "smtp.example.com", false},
		{"smtp fehlt", "po@example.com", "", false},
		{"beides fehlt", "", "", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			sched := newTierRequestSchedulerCfg(t, t.TempDir(), c.po, c.host, nil)
			th, _ := tierRequestHealthBlock(t, sched)
			if got, ok := th["po_mail_configured"].(bool); !ok || got != c.want {
				t.Errorf("po_mail_configured: want %v, got %v", c.want, th["po_mail_configured"])
			}
		})
	}
}

// AC-8: zwei offene Antraege, einer gemeldet -> unnotified_count 1; keine Kennung.
func TestTierRequestHealthUnnotifiedCountTwoUsers(t *testing.T) {
	ts := time.Now().UTC().Add(-time.Hour).Format(time.RFC3339)
	gemeldet := `{"id":"gz2436-gemeldet","display_name":"gz2436-name-a","email":"gz2436-a@example.invalid","tier":"free","requested_tier":"standard","requested_at":"` + ts + `","requested_notified_at":"` + ts + `"}`
	offen := `{"id":"gz2436-offen","display_name":"gz2436-name-b","email":"gz2436-b@example.invalid","tier":"free","requested_tier":"premium","requested_at":"` + ts + `"}`
	keiner := `{"id":"gz2436-keiner","display_name":"gz2436-name-c","tier":"free"}`
	sched := newTierRequestSchedulerCfg(t, t.TempDir(), "po@example.com", "smtp.example.com", map[string]string{
		"gz2436-gemeldet": gemeldet, "gz2436-offen": offen, "gz2436-keiner": keiner,
	})
	th, raw := tierRequestHealthBlock(t, sched)
	assertOpenCount(t, th, 2)
	if got := th["unnotified_count"]; got != float64(1) {
		t.Errorf("unnotified_count: want 1, got %v", got)
	}
	for _, leak := range []string{"gz2436", "name-a", "name-b", "example.invalid"} {
		if strings.Contains(raw, leak) {
			t.Errorf("Antwort darf %q nicht enthalten", leak)
		}
	}
}

// Haertung #2436 (Mutation "unnotified != nil" ueberlebte): der gemeldete und
// der ungemeldete Antrag muessen einzeln unterschieden werden, nicht nur in der Summe.
func TestTierRequestHealthUnnotifiedCountDistinguishesNotifiedFromNot(t *testing.T) {
	ts := time.Now().UTC().Add(-time.Hour).Format(time.RFC3339)
	nur := func(notified bool) float64 {
		doc := `{"id":"gz2436-x","tier":"free","requested_tier":"standard","requested_at":"` + ts + `"`
		if notified {
			doc += `,"requested_notified_at":"` + ts + `"`
		}
		doc += `}`
		sched := newTierRequestSchedulerCfg(t, t.TempDir(), "po@example.com", "smtp.example.com", map[string]string{"gz2436-x": doc})
		th, _ := tierRequestHealthBlock(t, sched)
		return th["unnotified_count"].(float64)
	}
	if got := nur(true); got != 0 {
		t.Errorf("gemeldeter Antrag: unnotified_count want 0, got %v", got)
	}
	if got := nur(false); got != 1 {
		t.Errorf("ungemeldeter Antrag: unnotified_count want 1, got %v", got)
	}
}
