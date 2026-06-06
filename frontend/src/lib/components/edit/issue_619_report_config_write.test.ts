// TDD RED: Issue #619 — Auswahl-/Schalter-UI für E-Mail-Elemente.
//
// Spec: docs/specs/modules/issue_619_mail_elements_ui.md
//
// Diese Tests sind ABSICHTLICH ROT, bis der pure Helper
// `reportConfigWrite.ts` existiert und EditReportConfigSection ihn nutzt.
// Sie prüfen ECHTES Laufzeitverhalten (importierte pure Funktionen), kein
// Datei-Inhalt. Vorbild: issue_610_signal_removal_red.test.ts.
//
// Abgedeckte ACs (Unit-Ebene):
//   AC-2: Default-Auswahl der Tages-Summe-Metriken.
//   AC-3: Toggle einer Metrik fügt hinzu / entfernt korrekt (kein Duplikat).
//   AC-4: Write-Back erhält unbekannte Felder (change_threshold_*, custom)
//         und schreibt die 5 neuen Felder.
//
// AC-1 (UI sichtbar) und AC-5 (Mail-Inhalt) werden per Playwright/staging-
// validator gegen Staging verifiziert (issue-619-mail-elements-ui.spec.ts).
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/components/edit/issue_619_report_config_write.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	DAILY_SUMMARY_METRICS,
	DEFAULT_DAILY_SUMMARY_METRICS,
	toggleDailySummaryMetric,
	buildMailElementWrite,
} from './reportConfigWrite.ts';

// ── Katalog ──────────────────────────────────────────────────────────────────

test('#619: Metrik-Katalog enthält genau die 5 wählbaren Kennzahlen', () => {
	assert.deepEqual(
		[...DAILY_SUMMARY_METRICS].sort(),
		['precipitation', 'temperature', 'thunder', 'visibility', 'wind'].sort()
	);
});

test('#619 AC-2: Default-Auswahl = Regen/Wind/Sicht/Gewitter (ohne Temperatur)', () => {
	assert.deepEqual(
		[...DEFAULT_DAILY_SUMMARY_METRICS].sort(),
		['precipitation', 'thunder', 'visibility', 'wind'].sort()
	);
	assert.ok(!DEFAULT_DAILY_SUMMARY_METRICS.includes('temperature'));
});

// ── AC-3: Toggle-Logik ───────────────────────────────────────────────────────

test('#619 AC-3: Aktivieren fügt Metrik hinzu', () => {
	const next = toggleDailySummaryMetric(['precipitation', 'wind'], 'temperature', true);
	assert.ok(next.includes('temperature'));
	assert.ok(next.includes('precipitation'));
	assert.ok(next.includes('wind'));
});

test('#619 AC-3: Deaktivieren entfernt Metrik', () => {
	const next = toggleDailySummaryMetric(['precipitation', 'wind', 'thunder'], 'wind', false);
	assert.ok(!next.includes('wind'));
	assert.deepEqual(next.sort(), ['precipitation', 'thunder'].sort());
});

test('#619 AC-3: Aktivieren erzeugt kein Duplikat', () => {
	const next = toggleDailySummaryMetric(['precipitation'], 'precipitation', true);
	assert.equal(next.filter((m) => m === 'precipitation').length, 1);
});

// ── AC-4: Write-Back erhält Fremdfelder, schreibt die 5 neuen ─────────────────

test('#619 AC-4: buildMailElementWrite erhält unbekannte Felder', () => {
	const original = {
		enabled: true,
		morning_time: '07:00:00',
		change_threshold_temp_c: 5.0,
		custom_unknown_field: 'preserve-me',
	};
	const merged = buildMailElementWrite(original, {
		show_stage_stats: false,
		show_quick_take_tags: true,
		show_stability: true,
		show_highlights: false,
		daily_summary_metrics: ['precipitation', 'thunder'],
	});

	// Fremdfelder erhalten
	assert.equal((merged as Record<string, unknown>).custom_unknown_field, 'preserve-me');
	assert.equal(merged.change_threshold_temp_c, 5.0);
	assert.equal(merged.enabled, true);
	assert.equal(merged.morning_time, '07:00:00');

	// Die 5 neuen Felder geschrieben
	assert.equal(merged.show_stage_stats, false);
	assert.equal(merged.show_quick_take_tags, true);
	assert.equal(merged.show_stability, true);
	assert.equal(merged.show_highlights, false);
	assert.deepEqual(merged.daily_summary_metrics, ['precipitation', 'thunder']);
});
