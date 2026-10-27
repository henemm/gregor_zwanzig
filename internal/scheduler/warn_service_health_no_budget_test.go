package scheduler

import (
	"os"
	"path/filepath"
	"sort"
	"testing"
)

// TDD RED — Issue #2266 (Epic #2258): Rueckbau des MeteoAlarm-Budget-Spiegels.
// Spec: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md, AC-5 + AC-6 (Go-Teil).
//
// KEINE Mocks: echte JSONL-/JSON-Dateien in t.TempDir(), WarnServiceHealth()
// wird real aufgerufen. Bewusst OHNE Bezug auf Budget-Symbole des Pakets, damit
// der Test nach dem Rueckbau weiter kompiliert. Nutzt die Helfer
// newWarnServiceHealthTestScheduler / writeWarnServiceCallsJournal aus
// warn_service_health_test.go (muessen beim Rueckbau erhalten bleiben).
func TestWarnServiceHealthHasNoMeteoAlarmBudgetBlockAndKeepsServiceFields(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	// Feste Zeitstempel: exakte Erwartung je kanonischem Dienstnamen.
	journal := "" +
		// dpc: Erfolg, danach ein echter Fehlschlag -> letzter Erfolg != letzter Versuch.
		`{"service":"dpc","cache_hit":false,"ok":true,"self_throttled":false,"ts":"2026-10-27T08:00:00Z"}` + "\n" +
		`{"service":"dpc","cache_hit":false,"ok":false,"self_throttled":false,"ts":"2026-10-27T09:00:00Z"}` + "\n" +
		// meteoalarm_feed (Feed-Weg AT/IT): zwei Laender, ein kanonischer Name.
		`{"service":"meteoalarm_feed:IT","cache_hit":false,"ok":true,"self_throttled":false,"ts":"2026-10-27T09:30:00Z"}` + "\n" +
		`{"service":"meteoalarm_feed:AT","cache_hit":false,"ok":true,"self_throttled":false,"ts":"2026-10-27T09:45:00Z"}` + "\n" +
		// Cache-Treffer zaehlt nie als Versuch.
		`{"service":"meteoalarm_feed:AT","cache_hit":true,"ok":true,"self_throttled":false,"ts":"2026-10-27T10:30:00Z"}` + "\n" +
		// Alt-Zeile aus der EDR-Zeit im Bestandsjournal: self_throttled=true muss
		// unveraendert durchgereicht werden (Schema-Stabilitaet, AC-6).
		`{"service":"meteoalarm:AT:p1","cache_hit":false,"ok":false,"self_throttled":true,"ts":"2026-10-26T22:00:00Z"}` + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, journal)

	// Eine auf Produktion/Staging liegengebliebene Altdatei darf nichts mehr bewirken.
	budgetPath := filepath.Join(tmpDir, "diagnostics", "meteoalarm_budget.json")
	if err := os.WriteFile(budgetPath, []byte(`{"date":"2026-10-27","calls":200,"observed_reset_ts":1893456000}`), 0644); err != nil {
		t.Fatalf("write meteoalarm_budget.json: %v", err)
	}

	health := sched.WarnServiceHealth()

	if block, exists := health["meteoalarm_budget"]; exists {
		t.Errorf("meteoalarm_budget must no longer appear in warn_service_health (#2266), got: %v", block)
	}

	var keys []string
	for k := range health {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	wantKeys := []string{"dpc", "meteoalarm", "meteoalarm_feed"}
	if len(keys) != len(wantKeys) {
		t.Errorf("result keys: want exactly %v, got %v", wantKeys, keys)
	} else {
		for i := range wantKeys {
			if keys[i] != wantKeys[i] {
				t.Errorf("result keys: want exactly %v, got %v", wantKeys, keys)
				break
			}
		}
	}

	cases := []struct {
		name          string
		lastSuccessAt any
		lastAttemptAt any
		selfThrottled bool
	}{
		{"dpc", "2026-10-27T08:00:00Z", "2026-10-27T09:00:00Z", false},
		{"meteoalarm_feed", "2026-10-27T09:45:00Z", "2026-10-27T09:45:00Z", false},
		{"meteoalarm", nil, "2026-10-26T22:00:00Z", true},
	}
	for _, c := range cases {
		svc, ok := health[c.name].(map[string]any)
		if !ok {
			t.Errorf("%s: key missing or wrong type: %v", c.name, health[c.name])
			continue
		}
		if got := svc["last_success_at"]; got != c.lastSuccessAt {
			t.Errorf("%s.last_success_at: want %v, got %v", c.name, c.lastSuccessAt, got)
		}
		if got := svc["last_attempt_at"]; got != c.lastAttemptAt {
			t.Errorf("%s.last_attempt_at: want %v, got %v", c.name, c.lastAttemptAt, got)
		}
		got, isBool := svc["self_throttled"].(bool)
		if !isBool || got != c.selfThrottled {
			t.Errorf("%s.self_throttled: want %v, got %v", c.name, c.selfThrottled, svc["self_throttled"])
		}
	}
}
