// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Schalter „Amtliche Warnungen“ (AC-20).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Implementation Details §1.
//
// Lese-Regel (Issue #3047 E4, PO-Entscheidung 2026-11-16, loest die ODER-Regel aus AC-20 ab):
//   Briefing an  = `official_alerts_enabled` nicht `false` (fehlend = an);
//   Alarm an     = `official_warnings.enabled`, wenn der Schluessel gesetzt ist, sonst
//                  `official_alert_triggers_enabled` nicht `false`;
//   Schalter an  = Briefing ODER Alarm an („beides an"); nur wenn beide aus sind: aus.
// Gleiche Regel wie Python `services/amtliche_warnungen_schalter.py` (steuert Briefing und Alarm).
// Schreib-Regel: `official_alerts_enabled` und `official_warnings.enabled` bekommen denselben
// Wert; weitere Felder von `official_warnings` (z. B. `sources`) bleiben erhalten.
// Gleiche Felder bei Trip und Orts-Briefing (beide top-level am Abo).

import { klon } from './klon.ts';

export type WarnFelder = {
	official_alerts_enabled?: boolean | null;
	official_warnings?: { enabled?: boolean; sources?: string[] } | null;
	official_alert_triggers_enabled?: boolean | null;
};

export type WarnSchreibFelder = {
	official_alerts_enabled: boolean;
	official_warnings: { enabled: boolean; sources?: string[] };
};

/** Wirksamer Wert des Schalters: Briefing ODER Alarm an (#3047 E4). */
export function amtlicheWarnungenAn(abo: WarnFelder | null | undefined): boolean {
	const briefing = abo?.official_alerts_enabled !== false;
	const ow = abo?.official_warnings;
	const alarm =
		ow !== null && ow !== undefined && typeof ow === 'object' && 'enabled' in ow
			? Boolean(ow.enabled)
			: abo?.official_alert_triggers_enabled !== false;
	return briefing || alarm;
}

/** Beide Felder auf denselben Wert, ohne die Eingabe zu veraendern. */
export function amtlicheWarnungenFelder(an: boolean, abo: WarnFelder | null | undefined): WarnSchreibFelder {
	const bestand = abo?.official_warnings && typeof abo.official_warnings === 'object' ? klon(abo.official_warnings) : {};
	return { official_alerts_enabled: an, official_warnings: { ...bestand, enabled: an } };
}
