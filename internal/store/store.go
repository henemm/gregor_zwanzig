package store

// Store provides JSON file storage scoped to a single user under DataDir.
type Store struct {
	DataDir string
	UserID  string
}

// New creates a Store for the given data directory and user.
func New(dataDir, userID string) *Store {
	return &Store{DataDir: dataDir, UserID: userID}
}

// WithUser returns a shallow copy of the Store with a different UserID.
// Empty userId is a no-op: returns the original Store unchanged.
//
// Der leere String laeuft BEWUSST nicht ueber ValidUserID (Issue #2140): er
// wuerde dort als "ungueltig" gelten, obwohl er hier seit jeher schlicht "kein
// Wechsel" bedeutet. Die Pfadsicherheit haengt nicht an dieser Stelle, sondern
// an den Store-Methoden, die aus einer Kennung einen Pfad bauen.
func (s *Store) WithUser(userId string) *Store {
	if userId == "" {
		return s
	}
	copy := *s
	copy.UserID = userId
	return &copy
}
