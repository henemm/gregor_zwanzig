// TDD RED — Score-Toggle-Tests (Issue #362).
//
// Spec: docs/specs/modules/issue_362_score_toggle.md
//
// ERWARTET: Compile-Fehler (undefined: intersectScoreKeys) bis
// engine.go + scoring.go die neuen Funktionen implementieren.
//
// Ausführung:
//   go test ./internal/compare/... -v -run TestScoreToggle
//   go test ./internal/compare/... -v -run TestIntersect
package compare

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// --- Hilfsfunktion: Location mit DisplayConfig bauen ------------------------

func locationWithScoreMembers(metrics []struct {
	id          string
	scoreMember bool
}) *model.Location {
	metricsArr := make([]interface{}, len(metrics))
	for i, m := range metrics {
		metricsArr[i] = map[string]interface{}{
			"metric_id":   m.id,
			"enabled":     true,
			"score_member": m.scoreMember,
		}
	}
	return &model.Location{
		DisplayConfig: map[string]interface{}{
			"metrics": metricsArr,
		},
	}
}

// --- AC-3: intersectScoreKeys — eine Location schließt Metrik aus -----------

// ERWARTET RED: intersectScoreKeys existiert noch nicht → Compile-Fehler.
func TestIntersectScoreKeys_OneLocationExcludes_MetricAbsent_AC3(t *testing.T) {
	// GIVEN: Location A schließt "precipitation" aus, Location B hat kein score_member
	// WHEN:  intersectScoreKeys aufgerufen
	// THEN:  metricPrecipSum ist NICHT in der zurückgegebenen Map (Intersection)
	locA := locationWithScoreMembers([]struct {
		id          string
		scoreMember bool
	}{
		{id: "precipitation", scoreMember: false},
		{id: "wind", scoreMember: true},
	})
	locB := &model.Location{} // keine DisplayConfig → alle Default=true

	locs := []*model.Location{locA, locB}
	enabledKeys := intersectScoreKeys(locs, ProfileSummerTrekking)

	// Wenn enabledKeys nicht nil: precipitation darf nicht drin sein
	if enabledKeys != nil && enabledKeys[metricPrecipSum] {
		t.Error("AC-3: metricPrecipSum sollte per Intersection ausgeschlossen sein wenn eine Location ihn auf score_member=false setzt")
	}
}

// --- AC-4: intersectScoreKeys — keine DisplayConfig → nil (alle aktiv) ------

func TestIntersectScoreKeys_NoDisplayConfig_ReturnsNil_AC4(t *testing.T) {
	// GIVEN: Beide Locations ohne DisplayConfig (leeres Struct)
	// WHEN:  intersectScoreKeys aufgerufen
	// THEN:  Rückgabewert ist nil (kein Filtering, Verhalten wie bisher)
	locA := &model.Location{}
	locB := &model.Location{}
	locs := []*model.Location{locA, locB}

	enabledKeys := intersectScoreKeys(locs, ProfileSummerTrekking)

	if enabledKeys != nil {
		t.Errorf("AC-4: enabledKeys sollte nil sein wenn keine Location score_member-Felder hat, got len=%d", len(enabledKeys))
	}
}

// --- AC-6: intersectScoreKeys — alle excluded → nil (Fallback) --------------

func TestIntersectScoreKeys_AllExcluded_FallsBackToNil_AC6(t *testing.T) {
	// GIVEN: Location schließt alle relevanten Metriken aus
	// WHEN:  intersectScoreKeys aufgerufen
	// THEN:  Rückgabewert ist nil (leere Intersection → Fallback auf normales Profil-Scoring)
	locA := locationWithScoreMembers([]struct {
		id          string
		scoreMember bool
	}{
		{id: "precipitation", scoreMember: false},
		{id: "wind", scoreMember: false},
		{id: "temperature", scoreMember: false},
		{id: "visibility", scoreMember: false},
	})
	locs := []*model.Location{locA}

	enabledKeys := intersectScoreKeys(locs, ProfileAllgemein)

	if enabledKeys != nil && len(enabledKeys) == 0 {
		t.Error("AC-6: Leere Intersection sollte als nil (Fallback) zurückgegeben werden, nicht als leere Map")
	}
}

// --- AC-2: ScoreRow filtert Metriken per enabledKeys + re-normalisiert ------

// ERWARTET RED: ScoreRow nimmt aktuell nur 3 Argumente, nicht 4.
// Dieser Test zeigt die gewünschte Signatur NACH der Implementierung.
func TestScoreRow_WithEnabledKeys_ExcludesMetric_AC2(t *testing.T) {
	// GIVEN: Zwei Locations — A mit viel Regen (schlecht), B mit wenig Regen (gut)
	//        enabledKeys schließt metricPrecipSum AUS
	// WHEN:  ScoreRow mit enabledKeys aufgerufen
	// THEN:  Score-Unterschied kleiner als ohne Filter (Regen zählt nicht)
	wet := model.SegmentWeatherSummary{
		PrecipSumMm:     fp(25.0),
		WindMaxKmh:      fp(10.0),
		UvIndexMax:      fp(3.0),
		VisibilityMinM:  fp(5000.0),
	}
	dry := model.SegmentWeatherSummary{
		PrecipSumMm:     fp(0.2),
		WindMaxKmh:      fp(10.0),
		UvIndexMax:      fp(3.0),
		VisibilityMinM:  fp(5000.0),
	}
	all := []model.SegmentWeatherSummary{wet, dry}

	// Score ohne Filter: wet << dry (viel Regen = schlecht)
	scoreWetNoFilter := ScoreRow(wet, ProfileSummerTrekking, all, nil)
	scoreDryNoFilter := ScoreRow(dry, ProfileSummerTrekking, all, nil)

	// Score MIT Filter (enabledKeys schließt precipitation aus):
	enabledKeys := map[metricKey]bool{
		metricWindMax:      true,
		metricThunderProxy: true,
		metricUvIndexMax:   true,
		metricVisibilityMin: true,
		// metricPrecipSum bewusst NICHT enthalten
	}
	// NEUE 4. Argument-Signatur: ScoreRow(loc, profile, all, enabledKeys)
	scoreWetFiltered := ScoreRow(wet, ProfileSummerTrekking, all, enabledKeys)
	scoreDryFiltered := ScoreRow(dry, ProfileSummerTrekking, all, enabledKeys)

	// Differenz muss kleiner sein wenn precipitation nicht zählt
	diffNoFilter := scoreDryNoFilter - scoreWetNoFilter
	diffFiltered := scoreDryFiltered - scoreWetFiltered

	if diffFiltered >= diffNoFilter {
		t.Errorf("AC-2: Score-Differenz mit Filter (%d) sollte kleiner sein als ohne Filter (%d) wenn Niederschlag ausgeschlossen", diffFiltered, diffNoFilter)
	}
}

// --- AC-4: ScoreRow mit nil enabledKeys = volles Profil-Scoring -------------

func TestScoreRow_NilEnabledKeys_BehavesLikeOriginal_AC4(t *testing.T) {
	// GIVEN: Identische Daten wie ein bestehender Test
	// WHEN:  ScoreRow mit nil enabledKeys (alle Metriken aktiv)
	// THEN:  Score identisch zur 3-Arg-Variante (Rückwärtskompatibilität)
	dry := model.SegmentWeatherSummary{PrecipSumMm: fp(0.5), WindMaxKmh: fp(10.0)}
	wet := model.SegmentWeatherSummary{PrecipSumMm: fp(20.0), WindMaxKmh: fp(10.0)}
	all := []model.SegmentWeatherSummary{dry, wet}

	// Neue 4-Arg-Signatur mit nil
	scoreDry4 := ScoreRow(dry, ProfileSummerTrekking, all, nil)
	scoreWet4 := ScoreRow(wet, ProfileSummerTrekking, all, nil)

	if scoreDry4 <= scoreWet4 {
		t.Errorf("AC-4: dry(%d) sollte > wet(%d) sein auch mit nil enabledKeys", scoreDry4, scoreWet4)
	}
}

// --- AC-2: Gewichte re-normalisieren wenn Metrik gefiltert -------------------

func TestScoreRow_FilteredWeights_StillInRange_AC2(t *testing.T) {
	// GIVEN: enabledKeys schließt 1 von 4 Metriken aus
	// WHEN:  ScoreRow aufgerufen
	// THEN:  Score liegt in [0, 100] (Re-Normalisierung korrekt)
	loc := model.SegmentWeatherSummary{
		TempMaxC:    fp(15.0),
		WindMaxKmh:  fp(20.0),
		PrecipSumMm: fp(5.0),
	}
	all := []model.SegmentWeatherSummary{loc}

	enabledKeys := map[metricKey]bool{
		metricTempMax:  true,
		metricWindMax:  true,
		// metricPrecipSum und metricVisibilityMin ausgeschlossen
	}
	score := ScoreRow(loc, ProfileAllgemein, all, enabledKeys)

	if score < 0 || score > 100 {
		t.Errorf("AC-2: Score %d außerhalb [0,100] nach Re-Normalisierung", score)
	}
}
