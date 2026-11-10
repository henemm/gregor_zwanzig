// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Schalter „Amtliche Warnungen“ (AC-20).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Implementation Details §1.
//
// Lese-Regel (ODER): ist `official_warnings` vorhanden, gilt
//   official_warnings.enabled || official_alerts_enabled;
// sonst `official_alert_triggers_enabled` (Default an: nur `false` schaltet aus).
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

/** Wirksamer Wert des Schalters (ODER-Regel, Fallback Default an). */
export function amtlicheWarnungenAn(abo: WarnFelder | null | undefined): boolean {
	const ow = abo?.official_warnings;
	if (ow !== null && ow !== undefined && typeof ow === 'object') {
		return ow.enabled === true || abo?.official_alerts_enabled === true;
	}
	return abo?.official_alert_triggers_enabled !== false;
}

/** Beide Felder auf denselben Wert, ohne die Eingabe zu veraendern. */
export function amtlicheWarnungenFelder(an: boolean, abo: WarnFelder | null | undefined): WarnSchreibFelder {
	const bestand = abo?.official_warnings && typeof abo.official_warnings === 'object' ? klon(abo.official_warnings) : {};
	return { official_alerts_enabled: an, official_warnings: { ...bestand, enabled: an } };
}
