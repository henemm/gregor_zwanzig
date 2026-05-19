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

	scoreDry := ScoreRow(dry, ProfileSummerTrekking, all)
	scoreWet := ScoreRow(wet, ProfileSummerTrekking, all)

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
		score := ScoreRow(summary, profile, all)
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

	scoreA := ScoreRow(a, ProfileAlpineTour, all)
	scoreB := ScoreRow(b, ProfileAlpineTour, all)

	if scoreA <= scoreB {
		t.Errorf("a(%d) sollte > b(%d) sein (weniger Wind, mehr Schnee)", scoreA, scoreB)
	}
}

// --- AC-3: Winner-Tags -------------------------------------------------------

func TestWinnerTags_SummerTrekking_ReturnsTags(t *testing.T) {
	// GIVEN: Eine Location mit niedrigem Regen und wenig Wind
	// WHEN:  WinnerTags mit SUMMER_TREKKING
	// THEN:  Mindestens ein nicht-leerer Tag zurückgegeben
	winner := model.SegmentWeatherSummary{
		PrecipSumMm: fp(0.1),
		WindMaxKmh:  fp(5.0),
		UvIndexMax:  fp(6.0),
	}
	tags := WinnerTags(winner, ProfileSummerTrekking)

	if len(tags) == 0 {
		t.Error("WinnerTags sollte mindestens einen Tag zurückgeben")
	}
	for _, tag := range tags {
		if tag == "" {
			t.Error("WinnerTag darf nicht leer sein")
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

	if ScoreRow(a, ProfileAllgemein, all) != ScoreRow(b, ProfileAllgemein, all) {
		t.Error("Identische Metriken müssen identische Scores ergeben")
	}
}

// Suppress unused import warning until implementation exists
var _ = ip
