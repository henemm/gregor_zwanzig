package scheduler

// Epic #2261, Scheibe A-2 S2 (AC-10): laufzaehlende Schwellen und ihre
// Echtzeit. failureAlertThreshold=3 / partialAlertThreshold=8 zaehlen LAEUFE;
// beim 5-Minuten-Takt der Radar-Jobs bedeutet das MQ-Stoermeldung nach
// 3 x 5 = 15 Minuten (statt 45) bzw. 8 x 5 = 40 Minuten (statt 120).
// PO-sichtbare Folge, bewusst belassen (Spec Abschnitt 6).
//
// SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md AC-10
//
// Echtzeit = Schwelle x ECHTER Cron-Abstand. Aenderung einer Schwelle oder
// des Takts ohne bewusste Anpassung wird rot und macht die Echtzeitfolge
// sichtbar. RED heute: Takt 15 Min -> 45/120 Min.

import (
	"testing"
	"time"
)

func TestRadarSchwellen_EchtzeitAusTaktUndSchwelle(t *testing.T) {
	if failureAlertThreshold != 3 || partialAlertThreshold != 8 {
		t.Fatalf("Schwellenkonstanten muessen 3 und 8 bleiben, got %d/%d",
			failureAlertThreshold, partialAlertThreshold)
	}
	sched := radarTaktTestScheduler(t)
	for _, id := range []string{"radar_alert_checks", "compare_radar_alert_checks"} {
		takt := radarTaktAbstand(t, sched, id)
		if got := time.Duration(failureAlertThreshold) * takt; got != 15*time.Minute {
			t.Errorf("%s: Stoermeldung (Ausfall) nach %v, erwartet 15m (3 x 5 Min)", id, got)
		}
		if got := time.Duration(partialAlertThreshold) * takt; got != 40*time.Minute {
			t.Errorf("%s: Stoermeldung (Teilausfall) nach %v, erwartet 40m (8 x 5 Min)", id, got)
		}
	}
}
