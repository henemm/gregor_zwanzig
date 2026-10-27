package scheduler

// ---------------------------------------------------------------------------
// Fix #2286 AC-8 + AC-9 — gleiche Feldmenge beider Briefing-Sub-Jobs in
// Status(), amtliche Warnungen im compare_alert_checks-Job
//
// Spec: docs/specs/modules/fix_2286_compare_betrieb_health.md
// (Implementierungsdetails 6 + 7, AC-8, AC-9).
//
// AC-8 ist laut Spec im Go-Status heute schon erfuellt -- der Test ist ein
// WAECHTER (bewusst gruen), der einen kuenftigen Schemaunterschied zwischen
// trip_reports_hourly und compare_presets_daily faengt.
// AC-9 ist ROT: compare_official_alert_checks ist heute noch registriert.
// ---------------------------------------------------------------------------

import (
	"sort"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// cmpFieldSet liefert die rekursive Schluesselmenge eines Job-Eintrags
// ("last_run.status", "deadline_aborts.total", ...). Die Job-Identitaet
// (id/name/next_run) gehoert zur Struktur, ihre Werte nicht.
func cmpFieldSet(prefix string, m map[string]any) []string {
	var out []string
	for k, v := range m {
		key := k
		if prefix != "" {
			key = prefix + "." + k
		}
		out = append(out, key)
		if sub, ok := v.(map[string]any); ok {
			out = append(out, cmpFieldSet(key, sub)...)
		}
	}
	sort.Strings(out)
	return out
}

func cmpStatusJobs(t *testing.T, sched *Scheduler) map[string]map[string]any {
	t.Helper()
	jobs, ok := sched.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any")
	}
	out := map[string]map[string]any{}
	for _, j := range jobs {
		if id, ok := j["id"].(string); ok {
			out[id] = j
		}
	}
	return out
}

// AC-8 (Waechter, heute gruen): nach einem echten briefingDispatch()-Lauf
// besitzen beide Sub-Jobs in Status() dieselbe Feldmenge inkl. last_run.* und
// deadline_aborts.
func TestStatus_TripAndCompareSubJobsHaveSameFieldSet(t *testing.T) {
	core := &cmpFlankCore{}
	srv := core.server(t)
	cfg := &config.Config{PythonCoreURL: srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStoreWithUsers(t, "tdd-2286-usera"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	sched.briefingDispatch()

	jobs := cmpStatusJobs(t, sched)
	trip, ok := jobs["trip_reports_hourly"]
	if !ok {
		t.Fatal("trip_reports_hourly missing in status")
	}
	cmp, ok := jobs["compare_presets_daily"]
	if !ok {
		t.Fatal("compare_presets_daily missing in status")
	}
	tripFields := cmpFieldSet("", trip)
	cmpFields := cmpFieldSet("", cmp)
	if strings.Join(tripFields, ",") != strings.Join(cmpFields, ",") {
		t.Fatalf("field sets differ (AC-8):\n trip:    %v\n compare: %v", tripFields, cmpFields)
	}
	for _, must := range []string{"last_run.status", "last_run.duration_s", "deadline_aborts.total"} {
		found := false
		for _, f := range cmpFields {
			if f == must {
				found = true
			}
		}
		if !found {
			t.Fatalf("compare_presets_daily lacks field %q (AC-8): %v", must, cmpFields)
		}
	}
}

// AC-9 (ROT): der Job compare_official_alert_checks existiert nicht mehr;
// compare_alert_checks bleibt registriert und ist ein Fan-out-Job mit
// last_run nach einem Lauf.
func TestStatus_CompareOfficialAlertChecksJobIsGone(t *testing.T) {
	core := &cmpFlankCore{}
	srv := core.server(t)
	cfg := &config.Config{PythonCoreURL: srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	jobs := cmpStatusJobs(t, sched)
	if _, ok := jobs["compare_official_alert_checks"]; ok {
		t.Fatal("job compare_official_alert_checks must no longer be registered (AC-9, #2286)")
	}
	if _, ok := jobs["compare_alert_checks"]; !ok {
		t.Fatal("job compare_alert_checks must stay registered (AC-9)")
	}

	sched.compareAlertChecks()
	if st := cmpJobStatusFromStatus(t, sched, "compare_alert_checks"); st != "ok" {
		t.Fatalf("compare_alert_checks should record an ok run, got %q", st)
	}
}
