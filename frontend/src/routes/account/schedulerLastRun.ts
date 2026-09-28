// Issue #2155 S2 (AC-8): Farbpunkt der Konto-Karte "Deine Reports" aus dem
// eigenen last_run (GET /api/scheduler/status/me).
//   kein Lauf (null/undefined/ohne time) -> 'none'    (grau, "Zuletzt: —")
//   'ok'                                  -> 'ok'      (gruen)
//   'error'                               -> 'error'   (rot)
//   jeder andere Status (partial, budget, skipped_in_flight, not_reached,
//   kuenftige Werte)                      -> 'neutral' (weder gruen noch rot)

export type LastRunDot = 'ok' | 'error' | 'neutral' | 'none';

export function lastRunDot(
	lastRun: { time?: string | null; status?: string | null } | null | undefined
): LastRunDot {
	if (!lastRun || !lastRun.time) return 'none';
	if (lastRun.status === 'ok') return 'ok';
	if (lastRun.status === 'error') return 'error';
	return 'neutral';
}
