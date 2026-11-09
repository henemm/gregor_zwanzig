package scheduler

import "os"

// journalBetweenOpens is nil in production. Nur Test-Naht (#2224, #2883):
// lets a test perform a real rotation between opening the current file and
// its predecessor generation ".1".
var journalBetweenOpens func()

// openJournalGenerations opens both generations of a size-rotated diagnostics
// journal (Issue #2224, generalised in #2883): the current file path FIRST
// (descriptor held), then the predecessor path + ".1". A rotation between the
// two opens makes ".1" the very file already open; os.SameFile detects that
// so it is read once — the reverse order would lose the freshly renamed file.
//
// A missing file of either generation is the legitimate empty state (fresh
// deploy, never rotated) and is not an error. Any other open error sets
// readErr while readable files are still returned. The caller closes all
// returned files (closeJournalFiles).
func openJournalGenerations(path string) (files []*os.File, readErr bool) {
	cur := openJournalGeneration(path, &readErr)
	if journalBetweenOpens != nil {
		journalBetweenOpens()
	}
	prev := openJournalGeneration(path+".1", &readErr)

	if cur != nil {
		files = append(files, cur)
	}
	if prev != nil {
		if cur != nil && sameOpenFile(cur, prev) {
			prev.Close() // rotation between the opens (or hardlink): read once
		} else {
			files = append(files, prev)
		}
	}
	return files, readErr
}

// openJournalGeneration opens one journal generation; nil if it cannot be
// opened. Only a non-NotExist error sets *readErr.
func openJournalGeneration(path string, readErr *bool) *os.File {
	f, err := os.Open(path)
	if err != nil {
		if !os.IsNotExist(err) {
			*readErr = true
		}
		return nil
	}
	return f
}

// sameOpenFile reports whether two open descriptors refer to the same file.
// If either cannot be stat'ed, they are treated as distinct.
func sameOpenFile(a, b *os.File) bool {
	ai, errA := a.Stat()
	bi, errB := b.Stat()
	return errA == nil && errB == nil && os.SameFile(ai, bi)
}

// closeJournalFiles closes every file returned by openJournalGenerations.
func closeJournalFiles(files []*os.File) {
	for _, f := range files {
		f.Close()
	}
}
