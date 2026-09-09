package store

import "testing"

// Ergaenzung zu Adversary-Finding F001 (Issue #2270): exportNameIstSicher ist
// ueber den Dateisystem-Lauf nicht scharf zu treffen — ein Dateiname mit ".."
// als eigenem Segment laesst sich gar nicht anlegen. Die Funktion bleibt
// trotzdem noetig, sobald ein Eintragsname NICHT vom Dateisystem stammt
// (z.B. aus einem JSON-Feld). Genau diese Eingaben prueft der direkte Aufruf.
//
// Die real herstellbare Fassung der Bedrohung — ein Verweis aus dem
// Nutzerordner heraus — prueft
// internal/handler/data_export_test.go, TestExportFolgtKeinemVerweisAusDemNutzerordner.
func TestExportNameIstSicherWeistAusbruchsnamenAb(t *testing.T) {
	unsicher := []string{
		"locations/../../etc/passwd",
		"../../../etc/passwd",
		"..",
		"briefings/../../bob/user.json",
		"/etc/passwd",
		`locations\..\..\bob\user.json`,
		"",
		".",
	}
	for _, n := range unsicher {
		if exportNameIstSicher(n) {
			t.Errorf("exportNameIstSicher(%q) = true — ein Ausbruchsname wuerde als Archiv-Eintrag akzeptiert", n)
		}
	}
	// Positivkontrolle: ohne sie waere ein "return false" fuer ALLES gruen.
	sicher := []string{
		"user.json",
		"locations/ort-1.json",
		"locations/..evil-1d90.json", // fuehrende Punkte sind legitim
		"briefings/a/b/c.json",
	}
	for _, n := range sicher {
		if !exportNameIstSicher(n) {
			t.Errorf("exportNameIstSicher(%q) = false — ein legitimer Eintragsname wuerde still aus dem Export fallen", n)
		}
	}
}
