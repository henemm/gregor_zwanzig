package store

// Issue #3122 B2 (F003): eine Kennung, die als <id>.json keinen Dateinamen
// mehr ergibt (> 255 Bytes), ist ungueltig -- gemessen in Bytes, nicht Zeichen.

import (
	"strings"
	"testing"
)

func TestValidEntityID_LaengengrenzeInBytes(t *testing.T) {
	faelle := []struct {
		id   string
		want bool
	}{
		{strings.Repeat("x", MaxEntityIDBytes), true},
		{strings.Repeat("x", MaxEntityIDBytes+1), false},
		{strings.Repeat("ü", MaxEntityIDBytes/2), true},
		{strings.Repeat("ü", MaxEntityIDBytes/2+1), false},
		{strings.Repeat("x", 5000), false},
	}
	for _, f := range faelle {
		if got := ValidEntityID(f.id); got != f.want {
			t.Errorf("ValidEntityID(%d Bytes) = %v, erwartet %v", len(f.id), got, f.want)
		}
	}
	// Eine Kennung an der Grenze ist als Datei les- und schreibbar gedacht:
	// der Dateiname <id>.json bleibt innerhalb von 255 Bytes.
	if n := len(strings.Repeat("x", MaxEntityIDBytes) + ".json"); n != 255 {
		t.Errorf("Dateiname an der Grenze hat %d Bytes, erwartet 255", n)
	}
}
