package handler

import (
	"bytes"
	"encoding/json"
)

// Optional is a three-state JSON field for PATCH-like PUT bodies (Issue #2211):
//
//	key absent    -> Set=false            (keep the stored value)
//	"key": null   -> Set=true,  Null=true (explicitly clear)
//	"key": value  -> Set=true,  Value     (set)
//
// It must be used as a VALUE field (not a pointer): encoding/json calls
// UnmarshalJSON on a value type for a literal null as well, but never for an
// absent key. A pointer field would be reset to nil on null instead.
// Spec: docs/specs/bugfix/optional_felder_null_leert.md
type Optional[T any] struct {
	Set   bool
	Null  bool
	Value T
}

// UnmarshalJSON records presence and distinguishes null from a value.
func (o *Optional[T]) UnmarshalJSON(data []byte) error {
	o.Set = true
	if bytes.Equal(bytes.TrimSpace(data), []byte("null")) {
		o.Null = true
		var zero T
		o.Value = zero
		return nil
	}
	o.Null = false
	return json.Unmarshal(data, &o.Value)
}

// ApplyPtr merges into a pointer model field: absent keeps, null -> nil, value -> set.
func (o Optional[T]) ApplyPtr(dst **T) {
	if !o.Set {
		return
	}
	if o.Null {
		*dst = nil
		return
	}
	v := o.Value
	*dst = &v
}

// ApplyValue merges into a plain model field: absent keeps, null -> zero value, value -> set.
func (o Optional[T]) ApplyValue(dst *T) {
	if !o.Set {
		return
	}
	if o.Null {
		var zero T
		*dst = zero
		return
	}
	*dst = o.Value
}
