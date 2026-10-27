// Issue #2277 S5 (AC-9): Konstanten der Karte "E-Mail-Inhalt" (shared/mailInhaltKonstanten.ts).
// Uebernimmt die Zusicherungen aus issue_693_email_config_cleanup (CONTENT_MODULE_DESCRIPTIONS)
// und issue_619 (Default-Auswahl der Kennzahlen). Echte Funktionsaufrufe, kein Mock.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/mail_inhalt_konstanten.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

const { CONTENT_MODULE_DESCRIPTIONS, DEFAULT_DAILY_SUMMARY_METRICS } = await import(
	'../mailInhaltKonstanten.ts'
);

test('CONTENT_MODULE_DESCRIPTIONS erklaert die Bausteine inkl. show_outlook', () => {
	for (const key of ['show_stage_stats', 'show_metrics_summary', 'show_outlook']) {
		const entry = CONTENT_MODULE_DESCRIPTIONS[key];
		assert.ok(entry, `Eintrag fehlt fuer ${key}`);
		assert.ok(entry.label && entry.label.length > 0, `Label fehlt fuer ${key}`);
		assert.ok(entry.description && entry.description.length >= 10, `Erklaerung zu kurz/fehlt fuer ${key}`);
	}
});

test('die drei angezeigten Schalter tragen die Labels der Karte', () => {
	assert.equal(CONTENT_MODULE_DESCRIPTIONS.show_outlook.label, 'Ausblick');
	assert.equal(CONTENT_MODULE_DESCRIPTIONS.show_stage_stats.label, 'Etappen-Kennzahlen');
	assert.equal(CONTENT_MODULE_DESCRIPTIONS.show_yesterday_comparison.label, 'Vortag-Vergleich');
});

test('DEFAULT_DAILY_SUMMARY_METRICS: Regen/Wind/Sicht/Gewitter an, Temperatur aus', () => {
	assert.deepEqual([...DEFAULT_DAILY_SUMMARY_METRICS], ['precipitation', 'wind', 'visibility', 'thunder']);
});
