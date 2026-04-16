---
entity_id: scheduler_multi_user
type: module
created: 2026-04-16
updated: 2026-04-16
status: implemented
version: "1.0"
tags: [go, scheduler, multi-user, store, cron]
---

# Scheduler Multi-User Iteration (Issue #63)

## Approval

- [x] Approved

## Purpose

Extends the Go cron scheduler to iterate over all registered users and fire one HTTP request per user per job, appending `?user_id=X` to each Python endpoint call. This enables multi-user operation without any changes to the Python endpoints, which already support the `user_id` query parameter.

## Scope

### In Scope
- `ListUserIDs()` method on `internal/store.Store`
- `triggerEndpointForUser(path, userID string) error` replacing `triggerEndpoint`
- Per-user iteration loop in all 5 job functions
- Continue-on-error semantics: one user's failure does not stop other users
- `recordRun` aggregation: "ok" only if all users succeeded, "error" if any failed
- Wiring: pass `*store.Store` into `scheduler.New()`

### Out of Scope
- Parallel user iteration (kept sequential to avoid Python overload)
- Changes to Python endpoints (`api/routers/scheduler.py`)
- Retry logic for failed per-user jobs
- New cron expressions or schedule changes

## Source

- **File:** `internal/scheduler/scheduler.go`
- **Identifier:** `Scheduler`, `New()`, `triggerEndpointForUser()`

Additional files touched:
- **File:** `internal/store/user.go` — `ListUserIDs()`
- **File:** `cmd/server/main.go` — wiring

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store.Store` | go struct | Provides `ListUserIDs()` to enumerate registered users |
| `internal/config.Config` | go struct | PythonCoreURL, Heartbeat URLs, Timezone — unchanged |
| `api/routers/scheduler.py` | python service | Existing trigger endpoints, already accept `?user_id=X` — no changes |
| `cmd/server/main.go` | go entrypoint | Must pass `*store.Store` to `scheduler.New()` |
| `robfig/cron/v3` | go module | Cron scheduling library — unchanged |

## Implementation Details

### Step 1: `ListUserIDs()` on Store

Add a method to `internal/store/user.go` that reads `data/users/`, lists subdirectories, and returns only those containing a `user.json` file. Returns an empty slice (not an error) when the directory doesn't exist or contains no valid users.

```go
// internal/store/user.go

// ListUserIDs returns the IDs of all registered users.
// A valid user directory must contain a user.json file.
// Returns an empty slice if the users directory does not exist.
func (s *Store) ListUserIDs() ([]string, error) {
    usersDir := filepath.Join(s.dataDir, "users")
    entries, err := os.ReadDir(usersDir)
    if err != nil {
        if os.IsNotExist(err) {
            return []string{}, nil
        }
        return nil, fmt.Errorf("read users dir: %w", err)
    }

    var ids []string
    for _, e := range entries {
        if !e.IsDir() {
            continue
        }
        userJSON := filepath.Join(usersDir, e.Name(), "user.json")
        if _, err := os.Stat(userJSON); err == nil {
            ids = append(ids, e.Name())
        }
    }
    return ids, nil
}
```

### Step 2: Add Store field to Scheduler and update `New()`

`scheduler.New()` gains a `*store.Store` parameter. The struct gets a `store` field.

```go
// internal/scheduler/scheduler.go

type Scheduler struct {
    cron             *cron.Cron
    pythonURL        string
    heartbeatMorning string
    heartbeatEvening string
    client           *http.Client
    store            *store.Store   // NEW
}

func New(cfg *config.Config, st *store.Store) (*Scheduler, error) {
    // ... existing timezone/cron setup ...
    s := &Scheduler{
        // ... existing fields ...
        store: st,   // NEW
    }
    // ... AddFunc calls unchanged ...
    return s, nil
}
```

### Step 3: Replace `triggerEndpoint` with `triggerEndpointForUser`

```go
// internal/scheduler/scheduler.go

func (s *Scheduler) triggerEndpointForUser(path, userID string) error {
    url := s.pythonURL + path + "?user_id=" + userID
    resp, err := s.client.Post(url, "application/json", nil)
    if err != nil {
        return fmt.Errorf("HTTP error: %w", err)
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)
    if resp.StatusCode >= 400 {
        return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
    }
    log.Printf("[scheduler] %s?user_id=%s → %d", path, userID, resp.StatusCode)
    return nil
}
```

The old `triggerEndpoint(path string) error` is removed entirely.

### Step 4: Per-user iteration in job functions

All 5 job functions use the same pattern. Example for `morningSubscriptions`:

```go
func (s *Scheduler) morningSubscriptions() {
    log.Println("[scheduler] Running morning subscriptions...")
    userIDs, err := s.store.ListUserIDs()
    if err != nil {
        log.Printf("[scheduler] morningSubscriptions: list users failed: %v", err)
        return
    }
    if len(userIDs) == 0 {
        log.Println("[scheduler] morningSubscriptions: no users registered, skipping")
        return
    }

    allOK := true
    for _, uid := range userIDs {
        if err := s.triggerEndpointForUser("/api/scheduler/morning-subscriptions", uid); err != nil {
            log.Printf("[scheduler] morningSubscriptions: user %s failed: %v", uid, err)
            allOK = false
            // continue — do not stop other users
        }
    }

    if allOK {
        s.pingHeartbeat(s.heartbeatMorning)
    }
}
```

The same pattern applies verbatim to `eveningSubscriptions`, `tripReports`, `alertChecks`, and `inboundCommands`. Heartbeat is only pinged when `allOK == true`. Jobs without a heartbeat (trip reports, alert checks, inbound) simply omit the `allOK` ping.

### Step 5: Wiring in `cmd/server/main.go`

```go
// cmd/server/main.go — change scheduler.New() call
sched, err := scheduler.New(cfg, store)   // pass store
if err != nil {
    log.Fatalf("scheduler error: %v", err)
}
```

No other changes to `main.go`.

## Expected Behavior

### Normal operation — multiple users
- **Input:** `data/users/alice/user.json` and `data/users/bob/user.json` exist
- **Output:** Each job fires two HTTP requests: `POST /api/scheduler/<job>?user_id=alice` and `POST /api/scheduler/<job>?user_id=bob`
- **Side effects:** Log entries per user, heartbeat pinged after morning/evening jobs if all succeed

### No registered users
- **Input:** `data/users/` is empty or does not exist
- **Output:** Job logs "no users registered, skipping" and returns immediately
- **Side effects:** No HTTP requests, no heartbeat ping, no error returned

### One user fails, others succeed
- **Input:** `alice` returns HTTP 500, `bob` returns HTTP 200
- **Output:** Error logged for `alice`, `bob` processed normally; `allOK = false`
- **Side effects:** No heartbeat ping for morning/evening jobs; subsequent users are still processed

### `ListUserIDs` fails (I/O error)
- **Input:** `data/users/` is unreadable (permissions error)
- **Output:** Job logs the error and returns — no HTTP requests sent
- **Side effects:** No heartbeat ping

## Known Limitations

- Sequential user iteration: a slow Python response for one user delays all subsequent users in the same job run. Acceptable for the expected user count (< 20).
- No partial-success tracking in `recordRun` beyond the boolean `allOK` flag. A full per-user run history is out of scope.
- `ListUserIDs` scans the filesystem on every job invocation. No caching. Acceptable given call frequency (at most once per 5 minutes).

## Changelog

- 2026-04-16: v1.0 Initial spec — Scheduler Multi-User Iteration (Issue #63)
- 2026-04-16: v1.1 Status updated to implemented — all 9 tests pass (4 store + 5 scheduler)
