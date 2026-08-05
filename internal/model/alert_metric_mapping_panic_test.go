package model

import (
	"strings"
	"testing"
)

// AC-4 (Fix #1435 Etappe E5): mustParseAlertMetricMapping() muss bei
// kaputten eingebetteten Bytes laut abstuerzen (panic mit konkreter
// Fehlermeldung), statt still eine leere Map zu liefern — eine leere Map
// wuerde ActiveAlertableMetricIDs() fuer JEDEN Trip-Speichervorgang
// lautlos wirkungslos machen (keine Alarmregel wird mehr synchronisiert).
func TestMustParseAlertMetricMapping_PanicsOnInvalidJSON(t *testing.T) {
	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("AC-4: mustParseAlertMetricMapping hat bei kaputtem JSON nicht gepanict")
		}
		msg, ok := r.(string)
		if !ok {
			t.Fatalf("AC-4: Panic-Wert ist kein string: %v (%T)", r, r)
		}
		if !strings.Contains(msg, "alert_metric_mapping") {
			t.Errorf(
				"AC-4: Panic-Meldung %q nennt die Quelle nicht (erwartet: Hinweis auf alert_metric_mapping.generated.json)",
				msg,
			)
		}
	}()

	mustParseAlertMetricMapping([]byte("{invalid"))
	t.Fatal("AC-4: mustParseAlertMetricMapping ist zurueckgekehrt statt zu panicen")
}
