// TDD RED: Issue #693 — E-Mail-Inhalt aufräumen (einklappbare Gruppen + Erklärungen).
//
// Spec: docs/specs/modules/issue_693_email_config_cleanup.md
//
// Diese Tests sind ABSICHTLICH ROT, bis reportConfigWrite.ts die neuen pure
// Helper exportiert (dailySummaryMetricLabel, dailySummaryMetricsSummary,
// countActiveContentModules, CONTENT_MODULE_DESCRIPTIONS) und
// EditReportConfigSection.svelte sie nutzt.
//
// Sie prüfen ECHTES Laufzeitverhalten importierter pure Funktionen — kein
// Datei-Inhalt-Check. Vorbild: issue_619_report_config_write.test.ts.
//
// Abgedeckte ACs (Unit-Ebene):
//   AC-5: Ein-/Ausklappen ist reiner UI-State — buildMailElementWrite erhält
//         alle Fremdfelder und schreibt nur die bekannten Konfig-Felder, kein
//         Collapse-State sickert in die Persistenz.
//   AC-6: dailySummaryMetricsSummary (Labels in Katalog-Reihenfolge, "Keine"
//         bei leer) + countActiveContentModules (korrekte Anzahl aktiver Schalter)
//         + dailySummaryMetricLabel (zentrale Label-Map).
//
// AC-1..AC-4 (einklappbare Gruppen, Header-Zähler/-Zusammenfassung, sichtbare
// Erklärungen) werden per staging-validator (Playwright) gegen Staging als
// eingeloggter Nutzer verifiziert.
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/components/edit/issue_693_email_config_cleanup.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	DAILY_SUMMARY_METRICS,
	buildMailElementWrite,
	dailySummaryMetricLabel,
	dailySummaryMetricsSummary,
	countActiveContentModules,
	CONTENT_MODULE_DESCRIPTIONS,
	type MailElementUi,
} from './reportConfigWrite.ts';

// ── AC-6: Label-Map ───────────────────────────────────────────────────────────

test('#693: dailySummaryMetricLabel liefert deutsche Labels für alle Katalog-IDs', () => {
	assert.equal(dailySummaryMetricLabel('precipitation'), 'Niederschlag');
	assert.equal(dailySummaryMetricLabel('wind'), 'Wind');
	assert.equal(dailySummaryMetricLabel('visibility'), 'Sicht');
	assert.equal(dailySummaryMetricLabel('thunder'), 'Gewitter');
	assert.equal(dailySummaryMetricLabel('temperature'), 'Temperatur');
});

test('#693: dailySummaryMetricLabel deckt jede Katalog-ID ab (kein leeres Label)', () => {
	for (const id of DAILY_SUMMARY_METRICS) {
		const label = dailySummaryMetricLabel(id);
		assert.ok(label && label.length > 0, `Label fehlt für ${id}`);
	}
});

// ── AC-6: Zusammenfassung der aktiven Kennzahlen ──────────────────────────────

test('#693: dailySummaryMetricsSummary verbindet aktive Labels mit " · " in Katalog-Reihenfolge', () => {
	// Eingabe-Reihenfolge absichtlich verdreht → Ausgabe muss Katalog-Reihenfolge sein.
	const summary = dailySummaryMetricsSummary(['thunder', 'precipitation', 'wind']);
	assert.equal(summary, 'Niederschlag · Wind · Gewitter');
});

test('#693: dailySummaryMetricsSummary liefert "Keine" bei leerer Auswahl', () => {
	assert.equal(dailySummaryMetricsSummary([]), 'Keine');
});

test('#693: dailySummaryMetricsSummary bei Voll-Auswahl listet alle 5 Labels', () => {
	const summary = dailySummaryMetricsSummary([...DAILY_SUMMARY_METRICS]);
	assert.equal(summary, 'Niederschlag · Wind · Sicht · Gewitter · Temperatur');
});

test('#693: dailySummaryMetricsSummary ignoriert unbekannte IDs', () => {
	const summary = dailySummaryMetricsSummary(['wind', 'bogus_metric']);
	assert.equal(summary, 'Wind');
});

// ── AC-6: Zählung aktiver Inhalts-Bausteine (Issue #723 + #785: 4-Bausteine-Modell) ──
// #785 (closed, commit 99433806) ergänzte show_yesterday_comparison als 4. Baustein
// (Default true). Die Fixtures setzen ihn hier explizit auf false, um die
// ursprüngliche Testabsicht (isolierte Zählung der übrigen Bausteine) zu erhalten.

test('#693: countActiveContentModules zählt nur die verbleibenden Bausteine', () => {
	const ui: MailElementUi = {
		show_stage_stats: true,
		// entfernte Felder (dürfen NICHT mitzählen):
		show_quick_take_tags: true,
		show_stability: false,
		show_highlights: true,
		show_metrics_summary: false,
		show_outlook: false,
		show_yesterday_comparison: false,
		daily_summary_metrics: ['wind'],
	};
	// stage_stats=true, metrics_summary=false, outlook=false, yesterday_comparison=false → 1 aktiv
	assert.equal(countActiveContentModules(ui), 1);
});

test('#693: countActiveContentModules zählt show_metrics_summary mit', () => {
	const ui: MailElementUi = {
		show_stage_stats: false,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		show_metrics_summary: true,
		show_outlook: false,
		show_yesterday_comparison: false,
		daily_summary_metrics: [],
	};
	assert.equal(countActiveContentModules(ui), 1);
});

test('#693: countActiveContentModules = 0 wenn alle Bausteine aus', () => {
	const ui: MailElementUi = {
		show_stage_stats: false,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		show_metrics_summary: false,
		show_outlook: false,
		show_yesterday_comparison: false,
		daily_summary_metrics: [],
	};
	assert.equal(countActiveContentModules(ui), 0);
});

test('#693: countActiveContentModules ignoriert daily_summary_metrics (keine Bausteine)', () => {
	const ui: MailElementUi = {
		show_stage_stats: true,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		show_metrics_summary: false,
		show_outlook: false,
		show_yesterday_comparison: false,
		daily_summary_metrics: ['precipitation', 'wind', 'visibility', 'thunder', 'temperature'],
	};
	// Nur 1 Baustein aktiv (stage_stats), die 5 Kennzahlen zählen NICHT als Baustein.
	assert.equal(countActiveContentModules(ui), 1);
});

// ── AC-3/AC-4: Erklärungs-Map vollständig (aktive Bausteine erklärt, Issue #723) ─

test('#693: CONTENT_MODULE_DESCRIPTIONS erklärt die 3 aktiven Bausteine inkl. show_outlook', () => {
	// Mindest-Anforderung: die 3 verbleibenden Bausteine + show_outlook müssen vorhanden sein.
	for (const key of ['show_stage_stats', 'show_metrics_summary', 'show_outlook']) {
		const entry = CONTENT_MODULE_DESCRIPTIONS[key];
		assert.ok(entry, `Eintrag fehlt für ${key}`);
		assert.ok(entry.label && entry.label.length > 0, `Label fehlt für ${key}`);
		assert.ok(entry.description && entry.description.length >= 10, `Erklärung zu kurz/fehlt für ${key}`);
	}
});

// ── AC-5: Collapse-State sickert NICHT in die Persistenz ──────────────────────

test('#693: buildMailElementWrite erhält Fremdfelder und schreibt nur bekannte Konfig-Felder', () => {
	const original = {
		change_threshold_wind: 30,
		change_threshold_precip: 5,
		custom_unknown_field: 'erhalten',
		enabled: true,
		morning_time: '07:00:00',
		// veraltete Werte, die durch UI überschrieben werden:
		show_stage_stats: false,
	};
	const ui: MailElementUi = {
		show_stage_stats: true,
		show_quick_take_tags: false,
		show_stability: true,
		show_highlights: true,
		show_metrics_summary: false,
		daily_summary_metrics: ['wind', 'thunder'],
	};
	const result = buildMailElementWrite(original, ui);

	// Fremdfelder erhalten
	assert.equal(result.change_threshold_wind, 30);
	assert.equal(result.change_threshold_precip, 5);
	assert.equal(result.custom_unknown_field, 'erhalten');
	assert.equal(result.enabled, true);
	assert.equal(result.morning_time, '07:00:00');

	// UI-Felder geschrieben
	assert.equal(result.show_stage_stats, true);
	assert.equal(result.show_quick_take_tags, false);
	assert.deepEqual(result.daily_summary_metrics, ['wind', 'thunder']);

	// KEIN Collapse-/UI-State in der Persistenz
	assert.ok(!('contentModulesExpanded' in result), 'Collapse-State darf nicht persistiert werden');
	assert.ok(!('dailySummaryExpanded' in result), 'Collapse-State darf nicht persistiert werden');
});
