// Issue #1329 (Maßnahme A): Der autonome Go-Cron-Scheduler darf auf Staging
// (GZ_ENV=staging) nicht starten, um das gemeinsame open-meteo-Tageskontingent
// nicht blind mit Prod zu teilen. Fail-safe: nur der exakte Wert "staging"
// deaktiviert, jeder andere Wert (inkl. ungesetzt, Tippfehler, Groß-/
// Kleinschreibung) lässt den Scheduler laufen.
package scheduler

import (
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

func TestSchedulerEnabled(t *testing.T) {
	tests := []struct {
		name string
		env  string
		want bool
	}{
		{"staging deaktiviert", "staging", false},
		{"ungesetzt (prod) aktiv", "", true},
		{"prod aktiv", "prod", true},
		{"dev aktiv", "dev", true},
		{"Staging Grossbuchstabe faellt auf aktiv zurueck", "Staging", true},
		{"stagin Tippfehler faellt auf aktiv zurueck", "stagin", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := &config.Config{Env: tt.env}
			got := SchedulerEnabled(cfg)
			if got != tt.want {
				t.Errorf("SchedulerEnabled(Env=%q) = %v, want %v", tt.env, got, tt.want)
			}
		})
	}
}
