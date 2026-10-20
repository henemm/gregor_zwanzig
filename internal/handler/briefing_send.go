package handler

// Issue #2280 S2: kind-neutraler Handversand im /api/briefings-Dispatcher
// (ADR-0023, Muster briefing_preview.go). kind ist Pflicht-Query, die ID wird
// vor dem Weiterreichen geprueft, die Besitzpruefung macht der user-scoped
// Python-Loader (fremde ID -> 404). Weiterleitung ueber forwardSend.
//
// Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-1 bis AC-3,
// AC-13, AC-14).

import (
	"net/http"
	"net/url"
)

// POST /api/briefings/{id}/send?kind=route|vergleich[&report_type=]
// Weiter an Python POST /api/briefings/{id}/send?kind=…&user_id=<auth>;
// report_type geht nur bei kind=route mit.
func BriefingSendHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		target, kind, ok := briefingPreviewTarget(w, r, pythonURL, "send")
		if !ok {
			return
		}
		q := url.Values{}
		q.Set("kind", kind)
		if rt := r.URL.Query().Get("report_type"); kind == briefingKindRoute && rt != "" {
			q.Set("report_type", rt)
		}
		forwardSend(w, r, target, q.Encode())
	}
}
