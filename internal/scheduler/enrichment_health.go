package scheduler

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// enrichmentCallEntry mirrors one line of data/diagnostics/enrichment_calls.jsonl
// (written by src/providers/enrichment_health.py's log_enrichment_call(),
// Issue #1581). Both degradable enrichment paths — the thunder direct sources
// ("thunder") and the radar nowcast ("radar_nowcast") — write through that one
// function into that one file; Path is what keeps them apart here.
type enrichmentCallEntry struct {
	Ts      string `json:"ts"`
	Path    string `json:"path"`
	Outcome string `json:"outcome"`
	Detail  string `json:"detail"`
}

// Outcome vocabulary of log_enrichment_call() — kept as constants so a rename
// on the Python side surfaces as a failing test here rather than as a silently
// empty aggregate.
const (
	enrichmentOutcomeOK            = "ok"
	enrichmentOutcomeFallback      = "fallback"
	enrichmentOutcomeUnavailable   = "unavailable"
	enrichmentOutcomeSelfThrottled = "self_throttled"
)

// enrichmentAgg accumulates the per-path aggregate while scanning the journal
// once.
type enrichmentAgg struct {
	lastAttemptAt  string
	lastSuccessAt  string
	lastFallbackAt string
	selfThrottled  bool
}

// aggregateEnrichmentCalls scans path (data/diagnostics/enrichment_calls.jsonl)
// and returns one enrichmentAgg per enrichment path, plus whether the file
// exists but could not be read (a genuine read error — e.g. the path is a
// directory — must stay distinguishable from "file does not exist yet", exactly
// like aggregateWarnServiceCalls). Fail-soft on individual corrupt lines.
//
// Only "ok" counts as a success: a call served through the named substitute
// ("fallback") DID deliver values, but the primary source is down — booking it
// as a success would keep last_success_at fresh through a multi-day
// degradation and hide precisely the state ADR-0018 wants visible. It gets its
// own last_fallback_at instead.
//
// Every line with a usable timestamp is an attempt, including
// "self_throttled": the call was skipped by our own budget gate, but the path
// was live and asked for — that is what makes a growing distance between
// last_attempt_at and last_success_at readable from outside.
func aggregateEnrichmentCalls(path string) (map[string]*enrichmentAgg, bool) {
	aggs := map[string]*enrichmentAgg{}

	f, err := os.Open(path)
	if err != nil {
		return aggs, false // missing file: legitimate empty state, no error flag
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		var entry enrichmentCallEntry
		if err := json.Unmarshal(scanner.Bytes(), &entry); err != nil {
			continue // skip corrupt line, keep scanning
		}
		// A line without a path cannot be attributed, one without a usable
		// timestamp cannot be compared — both are journal corruption (neither
		// is producible via log_enrichment_call()), and dropping them is the
		// honest state: an empty ts would sort as "ancient" in the
		// lexicographic comparisons below and could not even be aged out by a
		// freshness filter.
		if entry.Path == "" || strings.TrimSpace(entry.Ts) == "" {
			continue
		}

		agg, ok := aggs[entry.Path]
		if !ok {
			agg = &enrichmentAgg{}
			aggs[entry.Path] = agg
		}

		if entry.Ts > agg.lastAttemptAt {
			agg.lastAttemptAt = entry.Ts
		}
		switch entry.Outcome {
		case enrichmentOutcomeOK:
			if entry.Ts > agg.lastSuccessAt {
				agg.lastSuccessAt = entry.Ts
			}
		case enrichmentOutcomeFallback:
			if entry.Ts > agg.lastFallbackAt {
				agg.lastFallbackAt = entry.Ts
			}
		case enrichmentOutcomeSelfThrottled:
			agg.selfThrottled = true
		}
	}
	// A path pointing at a directory opens fine but fails on the first Read
	// (Linux: EISDIR) — that surfaces here as a Scan error, distinct from the
	// os.Open failure above.
	if scanner.Err() != nil {
		return aggs, true
	}
	return aggs, false
}

// EnrichmentHealth aggregates raw call outcomes per enrichment path (Issue
// #1581) directly from data/diagnostics/enrichment_calls.jsonl under
// s.store.DataDir — no Python HTTP call, no login required, analog
// WarnServiceHealth().
//
// Deliberately a top-level sibling of briefing_health, NOT a key inside it:
// check-gregor20.sh reads briefing_health as "is the briefing healthy", and an
// enrichment outage is explicitly not a briefing outage (ADR-0018; the guard
// over coreBriefingSources in briefing_health_test.go enforces the other half
// of that separation).
//
// Raw timestamps and flags only, no threshold decision (s. spec ADR rationale
// 2): "grows with the outage duration" is a property of jetzt −
// last_success_at, formed by check-gregor20.sh, exactly like the existing
// warn_service_health pattern. A path never called at all does not appear as a
// key (no fabricated failure). A missing journal yields an empty map (fresh
// deploy); an existing-but-unreadable journal additionally sets
// "journal_read_error": true — our own fault, unlike a provider outage.
func (s *Scheduler) EnrichmentHealth() map[string]any {
	result := map[string]any{}

	if s.store == nil {
		return result
	}

	journalPath := filepath.Join(s.store.DataDir, "diagnostics", "enrichment_calls.jsonl")
	aggs, readErr := aggregateEnrichmentCalls(journalPath)
	if readErr {
		result["journal_read_error"] = true
	}
	for name, agg := range aggs {
		result[name] = map[string]any{
			"last_attempt_at":  nilIfEmpty(agg.lastAttemptAt),
			"last_success_at":  nilIfEmpty(agg.lastSuccessAt),
			"last_fallback_at": nilIfEmpty(agg.lastFallbackAt),
			"self_throttled":   agg.selfThrottled,
		}
	}
	return result
}
