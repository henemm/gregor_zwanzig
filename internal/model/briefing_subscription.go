package model

import "encoding/json"

// BriefingSubscription is the Issue #1250 Scheibe 5 lossless scaffold for
// the future unified Trip/ComparePreset model (ADR-0023). It carries typed
// discriminator/core fields (ID, Kind) PLUS a raw catch-all so that every
// other field survives a Load->Save round-trip without modeling the full
// union (deferred to Scheibe 6, ADR-0023 Entscheidung 4 — Go has no
// built-in catch-all bucket like Python's `raw`/`extra`, so an unmodeled
// field would otherwise be silently dropped, BUG-DATALOSS-GR221-Muster).
//
// NOT wired into any read/write path yet (S6/S7) — the app keeps reading
// trips/compare_presets in S5 (verhaltensneutral).
type BriefingSubscription struct {
	ID   string
	Kind string
	raw  map[string]json.RawMessage
}

// UnmarshalJSON captures every field into raw, then extracts the typed
// discriminator fields (ID, Kind) for convenient access. Nothing is lost —
// raw remains the source of truth for MarshalJSON.
func (b *BriefingSubscription) UnmarshalJSON(data []byte) error {
	raw := map[string]json.RawMessage{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	b.raw = raw
	if v, ok := raw["id"]; ok {
		_ = json.Unmarshal(v, &b.ID)
	}
	if v, ok := raw["kind"]; ok {
		_ = json.Unmarshal(v, &b.Kind)
	}
	return nil
}

// MarshalJSON re-emits raw verbatim, syncing the typed ID/Kind fields back
// in first (so a caller that mutates b.ID/b.Kind directly still sees the
// change persisted) — Issue #1250 Scheibe 5, ADR-0023: lossless round-trip
// is the entire point of this scaffold; the full typed union model is
// Scheibe-6 work.
func (b BriefingSubscription) MarshalJSON() ([]byte, error) {
	out := map[string]json.RawMessage{}
	for k, v := range b.raw {
		out[k] = v
	}
	if b.ID != "" {
		idBytes, err := json.Marshal(b.ID)
		if err != nil {
			return nil, err
		}
		out["id"] = idBytes
	}
	if b.Kind != "" {
		kindBytes, err := json.Marshal(b.Kind)
		if err != nil {
			return nil, err
		}
		out["kind"] = kindBytes
	}
	return json.Marshal(out)
}
