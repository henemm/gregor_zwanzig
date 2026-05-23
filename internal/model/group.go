package model

// Group is a named container that locations can be assigned to.
// Issue #341: introduced as a first-class entity replacing the legacy
// free-text Location.Group field. DefaultProfile is one of
// wintersport|wandern|summer-trekking|allgemein (set later, Frontend #301).
type Group struct {
	ID             string  `json:"id"`
	Name           string  `json:"name"`
	DefaultProfile *string `json:"default_profile,omitempty"`
	Order          int     `json:"order"`
}
