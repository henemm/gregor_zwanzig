// TDD RED — Issue #2266 (Epic #2258): Rueckbau der MeteoAlarm-EDR-Klasse.
// Spec: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md, AC-4.
//
// Prueft die Go-Inventar-Datenstruktur selbst (kein Quelltext-Parsing): der
// zurueckgebaute EDR-Host api.meteoalarm.org ist nicht mehr deklariert, der
// kontingentfreie Feed-Host feeds.meteoalarm.org bleibt als gesperrt erhalten.
// Python-Gegenstueck: tests/tdd/test_meteoalarm_edr_rueckbau.py.
package egress

import (
	"sort"
	"strings"
	"testing"
)

func TestInventoryKnowsOnlyMeteoAlarmFeedHostAfterEDRRemoval(t *testing.T) {
	kind, ok := Inventory["feeds.meteoalarm.org"]
	if !ok || kind != Blocked {
		t.Fatalf("feeds.meteoalarm.org must stay declared as Blocked, got declared=%v kind=%q", ok, kind)
	}

	var meteoalarmHosts []string
	for host := range Inventory {
		if strings.Contains(host, "meteoalarm") {
			meteoalarmHosts = append(meteoalarmHosts, host)
		}
	}
	sort.Strings(meteoalarmHosts)

	if _, stillDeclared := Inventory["api.meteoalarm.org"]; stillDeclared {
		t.Errorf("api.meteoalarm.org is removed with the EDR class (#2266) and must not be declared; meteoalarm hosts: %v", meteoalarmHosts)
	}
	if len(meteoalarmHosts) != 1 || meteoalarmHosts[0] != "feeds.meteoalarm.org" {
		t.Errorf("the only MeteoAlarm host must be the feed, got %v", meteoalarmHosts)
	}
}
