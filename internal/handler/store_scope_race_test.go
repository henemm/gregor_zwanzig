package handler

// Issue #1396 Scheibe S1 — TDD RED.
//
// 25 Handler in diesem Paket weisen den WithUser-Aufruf per "=" ihrem
// aeusseren Store-Parameter zu — der vom http.Server GETEILTEN Closure-
// Variable (statt einer anfragelokalen ":="-Deklaration, vgl. trip.go:20).
// Der Server ruft denselben Handler-Wert aus einer eigenen Goroutine je
// Anfrage auf — zwei gleichzeitige Anfragen verschiedener Nutzer koennen sich
// dadurch die Nutzerkennung ueberschreiben (Cross-User-Datenleck ueber
// data/users/<user_id>/).
//
// Der belastbare Nachweis ist der Wettlauf-Detektor (go test -race), NICHT
// die Inhaltspruefung: ob sich zwei parallele Anfragen tatsaechlich die
// Kennung ueberschreiben, haengt am Zeitverhalten. Eine reine Inhaltspruefung
// koennte auch am unreparierten Stand zufaellig gruen sein und wuerde
// flackern. Die Inhaltspruefung (AC-1) laeuft deshalb zusaetzlich mit, der
// Detektor ist die eigentliche Zusage (AC-2).
//
// Listengetrieben: EIN Testrumpf, eine Tabelle mit einem Eintrag je Datei aus
// der Spec (docs/specs/modules/fix_1396_store_scope_race.md) — keine 25
// Kopien desselben Beweises. Vollstaendigkeit (alle 25 Stellen, keine neue)
// ist NICHT Teil dieser Scheibe, das leistet erst der Waechter aus S2.
//
// Wichtig fuer die Aussagekraft: der Handler wird je Tabelleneintrag GENAU
// EINMAL konstruiert (h := tc.build(s)), danach parallel aufgerufen — exakt
// wie im Produktivpfad (internal/router/router.go registriert jeden Handler
// einmal, die Closure lebt fuer die Prozesslaufzeit). Wer den Handler in der
// Goroutine konstruiert, erzeugt je Aufruf eine eigene Closure ohne geteilten
// Zustand — der Test waere dann wertlos (gruen trotz vorhandenem Fehler).

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	storeScopeRaceAlice = "alice-1396"
	storeScopeRaceBob   = "bob-1396"
	// N Goroutinen je Fall, alice/bob abwechselnd — genuegend Ueberlappung,
	// damit der Detektor zuverlaessig anschlaegt.
	storeScopeRaceN = 60
)

// storeScopeRaceCase buendelt einen der 6 repraesentativen Zugriffswege
// (einer je betroffener Datei, Spec "Source"): Saet-Funktion fuer je einen
// Nutzer-Datensatz mit einer eindeutigen Kennzeichnung ("marker"), Aufbau des
// Handlers (einmalig!) und die abgefragte Route.
type storeScopeRaceCase struct {
	name  string
	seed  func(t *testing.T, dataDir, user, marker string)
	build func(s *store.Store) http.Handler
	path  string
}

func storeScopeRaceCases() []storeScopeRaceCase {
	return []storeScopeRaceCase{
		{
			// location.go — GET /api/locations
			name: "locations",
			seed: func(t *testing.T, dataDir, user, marker string) {
				dir := filepath.Join(dataDir, "users", user, "locations")
				mustMkdirAll(t, dir)
				body := `{"id":"loc-1396","name":"` + marker + `","lat":1,"lon":1}`
				mustWriteFile(t, filepath.Join(dir, "loc.json"), body)
			},
			build: func(s *store.Store) http.Handler { return LocationsHandler(s) },
			path:  "/api/locations",
		},
		{
			// group.go — GET /api/groups
			name: "groups",
			seed: func(t *testing.T, dataDir, user, marker string) {
				dir := filepath.Join(dataDir, "users", user)
				mustMkdirAll(t, dir)
				body := `{"groups":[{"id":"g-1396","name":"` + marker + `","order":0}]}`
				mustWriteFile(t, filepath.Join(dir, "groups.json"), body)
			},
			build: func(s *store.Store) http.Handler { return GroupsHandler(s) },
			path:  "/api/groups",
		},
		{
			// compare_preset.go — GET /api/compare/presets
			name: "compare_presets",
			seed: func(t *testing.T, dataDir, user, marker string) {
				dir := filepath.Join(dataDir, "users", user, "briefings")
				mustMkdirAll(t, dir)
				body := `{"id":"cp-1396","name":"` + marker + `","kind":"vergleich",` +
					`"schedule":"manual","profil":"ALLGEMEIN","forecast_hours":24,` +
					`"hour_from":0,"hour_to":23,"empfaenger":[],"location_ids":[],` +
					`"created_at":"2026-01-01T00:00:00Z"}`
				mustWriteFile(t, filepath.Join(dir, "cp.json"), body)
			},
			build: func(s *store.Store) http.Handler { return ListComparePresetsHandler(s) },
			path:  "/api/compare/presets",
		},
		{
			// metric_preset.go — GET /api/metric-presets
			name: "metric_presets",
			seed: func(t *testing.T, dataDir, user, marker string) {
				dir := filepath.Join(dataDir, "users", user)
				mustMkdirAll(t, dir)
				body := `[{"id":"mp-1396","name":"` + marker + `","metrics":[],` +
					`"created_at":"2026-01-01T00:00:00Z"}]`
				mustWriteFile(t, filepath.Join(dir, "metric_presets.json"), body)
			},
			build: func(s *store.Store) http.Handler { return ListMetricPresetsHandler(s) },
			path:  "/api/metric-presets",
		},
		{
			// briefing_subscription.go — GET /api/briefings
			name: "briefings",
			seed: func(t *testing.T, dataDir, user, marker string) {
				dir := filepath.Join(dataDir, "users", user, "briefings")
				mustMkdirAll(t, dir)
				body := `{"id":"trip-1396","name":"` + marker + `"}`
				mustWriteFile(t, filepath.Join(dir, "trip.json"), body)
			},
			build: func(s *store.Store) http.Handler { return ListBriefingsHandler(s) },
			path:  "/api/briefings",
		},
		{
			// weather_config.go — GET /api/locations/{id}/weather-config
			// (nur die ORTS-Variante — die Trip-Variante ist seit #1395 S2
			// bereits repariert und nicht Teil dieser Scheibe).
			name: "location_weather_config",
			seed: func(t *testing.T, dataDir, user, marker string) {
				dir := filepath.Join(dataDir, "users", user, "locations")
				mustMkdirAll(t, dir)
				body := `{"id":"wc-1396","name":"WC","lat":1,"lon":1,` +
					`"display_config":{"marker":"` + marker + `"}}`
				// LoadLocation(id) liest per Direktzugriff <id>.json, anders
				// als LoadLocations() (Verzeichnis-Scan) — Dateiname MUSS zur
				// ID passen.
				mustWriteFile(t, filepath.Join(dir, "wc-1396.json"), body)
			},
			build: func(s *store.Store) http.Handler {
				r := chi.NewRouter()
				r.Get("/api/locations/{id}/weather-config", GetLocationWeatherConfigHandler(s))
				return r
			},
			path: "/api/locations/wc-1396/weather-config",
		},
	}
}

func mustMkdirAll(t *testing.T, dir string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll(%s): %v", dir, err)
	}
}

func mustWriteFile(t *testing.T, path, body string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("WriteFile(%s): %v", path, err)
	}
}

// TestStoreScopeRace_ParallelUsersGetOwnDataOnly ist der AC-1/AC-2-Nachweis:
// zwei angemeldete Nutzer fragen wiederholt und gleichzeitig dieselbe Route
// ab; jede Antwort darf ausschliesslich die Daten des anfragenden Nutzers
// enthalten. Unter "go test -race" muss das bei jedem Lauf ausschlagen, weil
// alle 25 betroffenen Handler dieselbe geteilte Closure-Variable schreiben.
//
// Klarstellung zum Fall "location_weather_config" (#1396): der Wettlauf an
// weather_config.go:130/132 ist unabhaengig davon eigenstaendig belegt (12
// Treffer im RED-Lauf am finalen Pfad). Ein zwischenzeitlich beobachtetes
// "404 not_found" bei JEDER Anfrage — nicht nur bei manchen — war dagegen ein
// Fehler im Testaufbau selbst (falscher Seed-Dateiname, s.u.), keine weitere
// Erscheinungsform des Wettlaufs. Nach dessen Behebung zeigt dieser Fall wie
// die anderen 5 den erwarteten Cross-User-Datentausch.
func TestStoreScopeRace_ParallelUsersGetOwnDataOnly(t *testing.T) {
	for _, tc := range storeScopeRaceCases() {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			dataDir := t.TempDir()
			aliceMarker := "ALICE-1396-" + tc.name
			bobMarker := "BOB-1396-" + tc.name
			tc.seed(t, dataDir, storeScopeRaceAlice, aliceMarker)
			tc.seed(t, dataDir, storeScopeRaceBob, bobMarker)

			s := store.New(dataDir, "unused-1396")
			// GENAU EINMAL konstruiert — wie im Produktivpfad (Router-Setup),
			// nicht je Anfrage neu. Nur so teilen sich alle Goroutinen unten
			// dieselbe Closure-Variable und der Test hat Aussagekraft.
			h := tc.build(s)

			type result struct {
				code   int
				body   string
				user   string
				marker string
			}
			results := make([]result, storeScopeRaceN)
			var wg sync.WaitGroup
			for i := 0; i < storeScopeRaceN; i++ {
				user, marker := storeScopeRaceBob, bobMarker
				if i%2 == 0 {
					user, marker = storeScopeRaceAlice, aliceMarker
				}
				wg.Add(1)
				go func(i int, user, marker string) {
					defer wg.Done()
					req := httptest.NewRequest(http.MethodGet, tc.path, nil)
					req = addUserToContext(req, user)
					w := httptest.NewRecorder()
					h.ServeHTTP(w, req)
					results[i] = result{code: w.Code, body: w.Body.String(), user: user, marker: marker}
				}(i, user, marker)
			}
			wg.Wait()

			for i, r := range results {
				if r.code != http.StatusOK {
					t.Fatalf("Anfrage %d (%s): expected 200, got %d: %s", i, r.user, r.code, r.body)
				}
				if !strings.Contains(r.body, r.marker) {
					t.Errorf("Anfrage %d (%s): eigene Kennzeichnung %q fehlt in der Antwort: %s",
						i, r.user, r.marker, r.body)
				}
				otherMarker := bobMarker
				if r.user == storeScopeRaceBob {
					otherMarker = aliceMarker
				}
				if strings.Contains(r.body, otherMarker) {
					t.Errorf("Anfrage %d (%s): FREMDE Kennzeichnung %q in der Antwort — "+
						"Cross-User-Datenleck: %s", i, r.user, otherMarker, r.body)
				}
			}
		})
	}
}

// TestStoreScopeRace_ExplainCommentReferencedInAllSixFiles ist der AC-4-
// Nachweis: jede der 6 reparierten Dateien traegt einen Kurzverweis auf die
// ausfuehrliche Begruendung in trip.go — bewusst ein Inhalts-Check
// (# doc-compliance-test), der Zweck der AC IST hier der Text selbst.
func TestStoreScopeRace_ExplainCommentReferencedInAllSixFiles(t *testing.T) {
	for _, f := range []string{
		"location.go", "group.go", "compare_preset.go",
		"metric_preset.go", "briefing_subscription.go", "weather_config.go",
	} {
		data, err := os.ReadFile(f)
		if err != nil {
			t.Fatalf("ReadFile(%s): %v", f, err)
		}
		if !strings.Contains(string(data), "trip.go:10-28") {
			t.Errorf("%s: kein Verweis auf trip.go:10-28 gefunden", f)
		}
	}
}
