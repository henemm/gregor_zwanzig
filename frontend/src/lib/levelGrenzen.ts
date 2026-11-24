// Issue #3319 (AC-2/AC-3) — Zugriff auf die einzige Quelle der oeffentlich
// gezeigten Level-Zahlen (`level_grenzen.json`, `null` = unbegrenzt). Die Datei
// ist per Drift-Test an den Code gebunden: Go `internal/model/tier_katalog_drift_test.go`,
// Python `tests/test_level_grenzen_drift.py`. Texte stehen im Katalog (`level.*`).
import grenzen from './level_grenzen.json' with { type: 'json' };

export type LevelName = 'free' | 'standard' | 'premium';

export type LevelFeld =
	| 'trips'
	| 'ortsvergleiche'
	| 'orte'
	| 'email'
	| 'telegram'
	| 'sms_pro_tag'
	| 'premium_sms_pro_tag'
	| 'premium_sms_antworten_pro_tag'
	| 'alarme_pro_tag';

export type LevelWert = number | boolean | null;

export const LEVEL_NAMEN: readonly LevelName[] = ['free', 'standard', 'premium'];

/** Zeilen der Kurzform (Startseite) und der vollen Tabelle (/funktionen). */
export const FELDER_KURZ: readonly LevelFeld[] = [
	'trips',
	'ortsvergleiche',
	'orte',
	'sms_pro_tag',
	'premium_sms_pro_tag',
	'alarme_pro_tag'
];

export const FELDER_VOLL: readonly LevelFeld[] = [
	'trips',
	'ortsvergleiche',
	'orte',
	'email',
	'telegram',
	'sms_pro_tag',
	'premium_sms_pro_tag',
	'premium_sms_antworten_pro_tag',
	'alarme_pro_tag'
];

const DATEN = grenzen as Record<LevelName, Record<LevelFeld, LevelWert>>;

export function levelWert(level: LevelName, feld: LevelFeld): LevelWert {
	return DATEN[level][feld];
}
