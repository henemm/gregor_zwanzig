package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// Issue #2677 (Adversary F001): ein 412 darf keinen vorab gesetzten ETag
// mitliefern, sonst haelt der Client einen Stand fuer gueltig, den er nie
// gesehen hat.
func TestWritePreconditionFailedEntferntVorabGesetztenETag(t *testing.T) {
	w := httptest.NewRecorder()
	w.Header().Set("ETag", `"veraltet"`)
	writePreconditionFailed(w, httptest.NewRequest(http.MethodPut, "/api/x", nil))
	if w.Code != http.StatusPreconditionFailed || w.Header().Get("ETag") != "" {
		t.Fatalf("status %d, ETag %q; erwartet 412 ohne ETag", w.Code, w.Header().Get("ETag"))
	}
}
