// TDD RED — Scoring-Tests für compare.Engine (Issue #250).
// Erwartet: FAIL (undefined: ScoreRow, ProfileSummerTrekking etc.) bis scoring.go + types.go angelegt.
//
// Ausführung:
//   go test ./internal/compare/... -v
package compare

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func fp(v float64) *float64 { return &v }
func ip(v int) *int         { return &v }

// --- AC-1: Ranking — höherer Regen → niedrigerer Score -------------------

func TestScoreRow_HigherPrecipGetsLowerScore_SummerTrekking(t *testing.T) {
	// GIVEN: Zwei Locations — eine mit wenig Niederschlag, eine mit viel
	// WHEN:  ScoreRow mit SUMMER_TREKKING-Profil
	// THEN:  Wenig-Regen-Location hat höheren Score
	dry := model.SegmentWeatherSummary{PrecipSumMm: fp(0.5), WindMaxKmh: fp(10.0)}
	wet := model.SegmentWeatherSummary{PrecipSumMm: fp(20.0), WindMaxKmh: fp(10.0)}
	all := []model.SegmentWeatherSummary{dry, wet}

	scoreDry := ScoreRow(dry, ProfileSummerTrekking, all, nil)
	scoreWet := ScoreRow(wet, ProfileSummerTrekking, all, nil)

	if scoreDry <= scoreWet {
		t.Errorf("dry(%d) sollte > wet(%d) sein", scoreDry, scoreWet)
	}
}

func TestScoreRow_ScoreInRange0To100(t *testing.T) {
	// GIVEN: Eine valide SegmentWeatherSummary
	// WHEN:  ScoreRow für alle Profile
	// THEN:  Score liegt zwischen 0 und 100
	summary := model.SegmentWeatherSummary{
		PrecipSumMm: fp(2.0),
		WindMaxKmh:  fp(30.0),
		UvIndexMax:  fp(5.0),
	}
	all := []model.SegmentWeatherSummary{summary}

	for _, profile := range []ActivityProfile{
		ProfileWintersport, ProfileAlpineTour, ProfileSummerTrekking, ProfileAllgemein,
	} {
		score := ScoreRow(summary, profile, all, nil)
		if score < 0 || score > 100 {
			t.Errorf("Profil %s: Score %d außerhalb [0,100]", profile, score)
		}
	}
}

func TestScoreRow_AlpineTour_MissingAvalanche_NoError(t *testing.T) {
	// GIVEN: Zwei Locations ohne Lawinenstufe-Feld (AC-6)
	// WHEN:  ScoreRow mit ALPINE_TOURING
	// THEN:  Kein Fehler, beide Scores gültig, Location mit weniger Wind > mehr Wind
	a := model.SegmentWeatherSummary{WindMaxKmh: fp(10.0), SnowNewSumCm: fp(5.0)}
	b := model.SegmentWeatherSummary{WindMaxKmh: fp(60.0), SnowNewSumCm: fp(0.0)}
	all := []model.SegmentWeatherSummary{a, b}

	scoreA := ScoreRow(a, ProfileAlpineTour, all, nil)
	scoreB := ScoreRow(b, ProfileAlpineTour, all, nil)

	if scoreA <= scoreB {
		t.Errorf("a(%d) sollte > b(%d) sein (weniger Wind, mehr Schnee)", scoreA, scoreB)
	}
}

// --- AC-3: Winner-Tags -------------------------------------------------------

func TestWinnerTags_SummerTrekking_ReturnsTags(t *testing.T) {
	// GIVEN: Eine Location mit niedrigem Regen und wenig Wind
	// WHEN:  WinnerTagsTyped mit SUMMER_TREKKING
	// THEN:  Mindestens ein typisierter Tag mit nicht-leerem Type+Label zurückgegeben
	winner := model.SegmentWeatherSummary{
		PrecipSumMm: fp(0.1),
		WindMaxKmh:  fp(5.0),
		UvIndexMax:  fp(6.0),
	}
	tags := WinnerTagsTyped(winner, ProfileSummerTrekking)

	if len(tags) == 0 {
		t.Error("WinnerTagsTyped sollte mindestens einen Tag zurückgeben")
	}
	for _, tag := range tags {
		if tag.Type == "" {
			t.Error("WinnerTag.Type darf nicht leer sein")
		}
		if tag.Label == "" {
			t.Error("WinnerTag.Label darf nicht leer sein")
		}
	}
}

// --- Normalisierung: identische Werte → gleicher Score ----------------------

func TestScoreRow_IdenticalMetrics_SameScore(t *testing.T) {
	// GIVEN: Zwei Locations mit identischen Wetterdaten
	// WHEN:  ScoreRow für ALLGEMEIN
	// THEN:  Beide Scores sind gleich
	a := model.SegmentWeatherSummary{TempMaxC: fp(20.0), WindMaxKmh: fp(15.0), PrecipSumMm: fp(2.0)}
	b := model.SegmentWeatherSummary{TempMaxC: fp(20.0), WindMaxKmh: fp(15.0), PrecipSumMm: fp(2.0)}
	all := []model.SegmentWeatherSummary{a, b}

	if ScoreRow(a, ProfileAllgemein, all, nil) != ScoreRow(b, ProfileAllgemein, all, nil) {
		t.Error("Identische Metriken müssen identische Scores ergeben")
	}
}

// --- F002: Negative Temperaturen — höhere Temp gewinnt -------------------

func TestScoreRow_NegativeTemps_HigherTempGetsHigherScore(t *testing.T) {
	// Zwei alpine Standorte im Winter: -3°C vs -8°C
	warm := model.SegmentWeatherSummary{TempMaxC: fp(-3.0), WindMaxKmh: fp(20.0), PrecipSumMm: fp(1.0)}
	cold := model.SegmentWeatherSummary{TempMaxC: fp(-8.0), WindMaxKmh: fp(20.0), PrecipSumMm: fp(1.0)}
	all := []model.SegmentWeatherSummary{warm, cold}
	scoreWarm := ScoreRow(warm, ProfileAllgemein, all, nil)
	scoreCold := ScoreRow(cold, ProfileAllgemein, all, nil)
	if scoreWarm <= scoreCold {
		t.Errorf("warm(%d) sollte > cold(%d) sein (gleicher Wind, wärmere Temp)", scoreWarm, scoreCold)
	}
}

// Suppress unused import warning until implementation exists
var _ = ip

// --- Issue #367: SunnyHoursH ersetzt DniAvgWm2 im WINTERSPORT-Scoring -------

// AC-3: Mehr Sonnenstunden → höherer Score im WINTERSPORT-Profil.
// ERWARTET RED: SegmentWeatherSummary.SunnyHoursH existiert noch nicht (Compile-Fehler).
func TestScoreRow_Wintersport_MoreSunnyHoursGetsHigherScore(t *testing.T) {
	// GIVEN: Zwei Locations — A mit 6h Sonne, B mit 2h Sonne, sonst identisch
	// WHEN:  ScoreRow mit ProfileWintersport
	// THEN:  Location A hat höheren Score als B
	sunny := model.SegmentWeatherSummary{
		SnowDepthCm:  fp(50.0),
		SnowNewSumCm: fp(10.0),
		SunnyHoursH:  fp(6.0),
		WindMaxKmh:   fp(20.0),
		CloudAvgPct:  ip(30),
	}
	cloudy := model.SegmentWeatherSummary{
		SnowDepthCm:  fp(50.0),
		SnowNewSumCm: fp(10.0),
		SunnyHoursH:  fp(2.0),
		WindMaxKmh:   fp(20.0),
		CloudAvgPct:  ip(30),
	}
	all := []model.SegmentWeatherSummary{sunny, cloudy}

	scoreSunny := ScoreRow(sunny, ProfileWintersport, all, nil)
	scoreCloudy := ScoreRow(cloudy, ProfileWintersport, all, nil)

	if scoreSunny <= scoreCloudy {
		t.Errorf("sunny(%d) sollte > cloudy(%d) sein (mehr SunnyHoursH)", scoreSunny, scoreCloudy)
	}
}

// AC-2: SunnyHoursH liegt physikalisch zwischen 0 und 24.
// ERWARTET RED: SegmentWeatherSummary.SunnyHoursH existiert noch nicht (Compile-Fehler).
func TestSunnyHoursH_MaximumBoundary_NotExceedsDay(t *testing.T) {
	// GIVEN: Location mit vollem Sonnentag (24.0h)
	// WHEN:  Score berechnet
	// THEN:  Score liegt in [0, 100], Feld ist akzeptiert
	full := model.SegmentWeatherSummary{
		SunnyHoursH: fp(24.0),
	}
	zero := model.SegmentWeatherSummary{
		SunnyHoursH: fp(0.0),
	}
	all := []model.SegmentWeatherSummary{full, zero}

	score := ScoreRow(full, ProfileWintersport, all, nil)
	if score < 0 || score > 100 {
		t.Errorf("Score %d außerhalb [0,100] bei SunnyHoursH=24.0", score)
	}
}
