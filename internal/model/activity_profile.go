package model

// ActivityProfile enumerates the supported scoring profiles for a compare run.
//
// Umgezogen aus dem gelöschten Compare-Paket (Issue #1215, Scheibe 3) — der
// Profil-Typ lebt jetzt in model. Einziger echter Nutzer: Preset-CRUD-
// Validierung im Handler.
type ActivityProfile string

const (
	ProfileWintersport    ActivityProfile = "WINTERSPORT"
	ProfileAlpineTour     ActivityProfile = "ALPINE_TOURING"
	ProfileSummerTrekking ActivityProfile = "SUMMER_TREKKING"
	ProfileAllgemein      ActivityProfile = "ALLGEMEIN"
)

// validProfiles is the canonical set of accepted ActivityProfile values.
var validProfiles = map[ActivityProfile]bool{
	ProfileWintersport:    true,
	ProfileAlpineTour:     true,
	ProfileSummerTrekking: true,
	ProfileAllgemein:      true,
}

// IsValidProfile reports whether p is a recognised profile value.
func IsValidProfile(p ActivityProfile) bool {
	return validProfiles[p]
}
