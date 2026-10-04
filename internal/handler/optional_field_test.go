package handler

// TDD RED: Issue #2211, Test 1 -- belegt auf Decode-Ebene die encoding/json-
// Annahme: ein Wert-Typ mit UnmarshalJSON wird bei `null` aufgerufen, bei
// fehlendem Key nicht. Der Typ Optional[T] (optional_field.go) existiert erst
// nach /50 -- bis dahin Compile-Fehler "undefined: Optional" (RED).

import (
	"encoding/json"
	"testing"
)

func TestOptionalDecode_ThreeStatesDistinguishable(t *testing.T) {
	type body struct {
		F Optional[int] `json:"f"`
	}

	var null, absent, val body
	if err := json.Unmarshal([]byte(`{"f":null}`), &null); err != nil {
		t.Fatalf("null: %v", err)
	}
	if err := json.Unmarshal([]byte(`{}`), &absent); err != nil {
		t.Fatalf("absent: %v", err)
	}
	if err := json.Unmarshal([]byte(`{"f":5}`), &val); err != nil {
		t.Fatalf("value: %v", err)
	}

	if !null.F.Set || !null.F.Null {
		t.Errorf("{\"f\":null}: erwartet Set=true Null=true, bekommen Set=%v Null=%v", null.F.Set, null.F.Null)
	}
	if absent.F.Set || absent.F.Null {
		t.Errorf("{}: erwartet Set=false Null=false, bekommen Set=%v Null=%v", absent.F.Set, absent.F.Null)
	}
	if !val.F.Set || val.F.Null || val.F.Value != 5 {
		t.Errorf("{\"f\":5}: erwartet Set=true Null=false Value=5, bekommen Set=%v Null=%v Value=%d",
			val.F.Set, val.F.Null, val.F.Value)
	}
}
