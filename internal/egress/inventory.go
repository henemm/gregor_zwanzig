// Package egress ist der Egress-Waechter des Go-Dienstes (Issue #1337, Scheibe
// "Go-Prozess"). Spec: docs/specs/modules/egress_guard_go.md.
//
// Zwillingsliste zu src/app/egress_guard.py::INVENTORY — beide Quellen muessen
// Host fuer Host deckungsgleich sein; erzwungen von
// tests/test_egress_inventory_drift.py. Die Zeilenform "host": Kind, wird von
// jenem Test per Regex geparst und darf nicht umformatiert werden.
package egress

// Kind ist die deklarierte Isolationsart eines Hosts.
type Kind string

const (
	// TestAccess: Test/Staging darf diesen Host erreichen.
	TestAccess Kind = "test_access"
	// Blocked: bewusst deklariert, aber in Test/Staging gesperrt.
	Blocked Kind = "blocked"
)

// Inventory listet jeden Host, den einer der beiden Prozesse rufen kann.
// Nicht gelistete Hosts sind ein Tripwire (Fehler statt stiller Erfolg).
var Inventory = map[string]Kind{
	"api.open-meteo.com":             TestAccess,
	"air-quality-api.open-meteo.com": TestAccess,
	"dataset.api.hub.geosphere.at":   TestAccess,
	// #1457 S2b: DWD-opendata (ICON-D2 Gewittersignale) — kostenlos und
	// kontingentfrei; Staging braucht den Host fuer den Gewitter-Nachweis
	// (Python-Seite seit 9f57ae16, hier nachgezogen gegen Inventar-Drift).
	"opendata.dwd.de": TestAccess,
	// Scheibe 2b #1348: Test/Staging erreichen echte Warn-APIs nicht mehr
	"warnungen.zamg.at":             Blocked,
	"api.brightsky.dev":             TestAccess,
	"radar-api.protezionecivile.it": TestAccess,
	// Scheibe 2b #1348: Test/Staging erreichen echte Warn-APIs nicht mehr
	"api.meteoalarm.org": Blocked,
	// Issue #1445 S1: derselbe Anbieter, kontingentfreier Feed-Transport --
	// Test/Staging duerfen auch diesen Warn-Host nicht real erreichen.
	"feeds.meteoalarm.org":              Blocked,
	"public-api.meteofrance.fr":         Blocked,
	"www.risque-prevention-incendie.fr": Blocked,
	"gateway.seven.io":                  TestAccess,
	"api.telegram.org":                  TestAccess,
	"mail.henemm.com":                   TestAccess,
	// Go-Dienst: Ortsauflösung, Höhen, Tour-Import — kostenlos und
	// nebenwirkungsfrei, muss auf Staging funktionieren.
	"nominatim.openstreetmap.org": TestAccess,
	"api.open-elevation.com":      TestAccess,
	"www.komoot.com":              TestAccess,
	// Auflösung geteilter Google-Maps-Links (followGoogleMapsRedirect).
	"maps.app.goo.gl": TestAccess,
	"goo.gl":          TestAccess,
	"www.google.com":  TestAccess,
	"maps.google.com": TestAccess,
	// Google-Login auf Staging.
	"www.googleapis.com":    TestAccess,
	"oauth2.googleapis.com": TestAccess,
	"accounts.google.com":   TestAccess,
	// Staging darf keine Produktions-Heartbeats gruen pingen — das waere
	// Falsch-Gruen im Monitoring.
	"uptime.betterstack.com": Blocked,
}
