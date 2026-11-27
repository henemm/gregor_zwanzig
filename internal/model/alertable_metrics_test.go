package model

import (
	"sort"
	"strings"
	"testing"
)

// Issue #2994: AlertableMetrics wird aus der eingebetteten, von Python
// generierten Datei alertable_metrics.generated.json gebaut (kein
// Handliteral mehr). Spec: docs/specs/modules/feat_2994_alertable_metrics_vocab.md

// AC-3: genau die sechs alarmfaehigen Metriken, jede mit Default-Delta-Schwelle.
func TestAlertableMetrics_ExactlySixWithDeltaDefaults(t *testing.T) {
	want := []string{
		"precipitation_sum", "snow_line", "temperature_max",
		"temperature_min", "thunder_level", "wind_gust",
	}
	var got []string
	for m := range AlertableMetrics {
		got = append(got, string(m))
		if _, ok := DefaultDeltaThreshold[m]; !ok {
			t.Errorf("AC-3: %q hat keinen DefaultDeltaThreshold", m)
		}
	}
	sort.Strings(got)
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("AC-3: AlertableMetrics = %v, want %v", got, want)
	}
}

// AC-3: die Parse-Funktion baut die Menge aus den Bytes (nicht aus einem Literal).
func TestMustParseAlertableMetrics_BuildsSetFromBytes(t *testing.T) {
	got := mustParseAlertableMetrics([]byte(`["wind_gust","snow_line"]`))
	if len(got) != 2 {
		t.Fatalf("AC-3: want 2 entries, got %d (%v)", len(got), got)
	}
	for _, m := range []AlertMetric{AlertMetricWindGust, AlertMetricSnowLine} {
		if _, ok := got[m]; !ok {
			t.Errorf("AC-3: %q fehlt in %v", m, got)
		}
	}
}

// AC-4: kaputte Eingaben fuehren zu einem lauten Panic, der die Datei nennt.
func TestMustParseAlertableMetrics_PanicsLoudly(t *testing.T) {
	cases := map[string]string{
		"ungueltiges JSON":           `["wind_gust"`,
		"leere Liste":                `[]`,
		"ohne DefaultDeltaThreshold": `["wind_gust","fresh_snow"]`,
	}
	for name, raw := range cases {
		t.Run(name, func(t *testing.T) {
			defer func() {
				r := recover()
				if r == nil {
					t.Fatalf("AC-4 (%s): kein Panic", name)
				}
				msg, ok := r.(string)
				if !ok {
					t.Fatalf("AC-4 (%s): Panic-Wert ist kein string: %v (%T)", name, r, r)
				}
				if !strings.Contains(msg, "alertable_metrics.generated.json") {
					t.Errorf("AC-4 (%s): Meldung %q nennt die Datei nicht", name, msg)
				}
			}()
			mustParseAlertableMetrics([]byte(raw))
		})
	}
}
