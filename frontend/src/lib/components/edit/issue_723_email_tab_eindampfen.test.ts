// Issue #723 — E-Mail-Inhalt-Tab UI eindampfen (Slice 3 von #709).
//
// Spec: docs/specs/modules/issue_723_email_tab_eindampfen.md
//
// Prüft das aktuelle Soll-Verhalten von reportConfigWrite.ts:
//   1. MailElementUi kennt das Feld `show_outlook` (Ausblick-Baustein, #721).
//   2. countActiveContentModules zählt die 4 Inhalts-Bausteine
//      (show_stage_stats, show_metrics_summary, show_outlook,
//      show_yesterday_comparison — Issue #785, commit 99433806). Die mit
//      #723 entfernten Schalter (quick_take, stability, highlights) zählen
//      NICHT mehr mit.
//   3. buildMailElementWrite schreibt `show_outlook` (Default true wenn fehlt)
//      ins Persistenz-Objekt und erhält alle Fremdfelder via Spread (entfernte
//      Felder bleiben im Modell — Bestandsdaten-Schutz, CLAUDE.md).
//
// Sie prüfen ECHTES Laufzeitverhalten importierter pure Funktionen — kein
// Datei-Inhalt-Check. Vorbild: issue_693_email_config_cleanup.test.ts.
//
// AC-1/AC-4 (UI-Sichtbarkeit, Kompakt-Deaktivierung) + AC-5 (Persistenz über
// Reload) werden per Playwright gegen Staging verifiziert
// (issue-723-email-tab-eindampfen.spec.ts).
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/components/edit/issue_723_email_tab_eindampfen.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildMailElementWrite,
	countActiveContentModules,
	type MailElementUi,
} from './reportConfigWrite.ts';

// ── AC-1/AC-6: genau 4 Inhalts-Bausteine zählen (#723 Basis + #785 Vortag-Vergleich) ──

test('#723/#785: countActiveContentModules zählt die 4 verbleibenden Bausteine', () => {
	const ui: MailElementUi = {
		show_stage_stats: true,
		show_metrics_summary: true,
		show_outlook: true,
		show_yesterday_comparison: true,
		// entfernte Bausteine — dürfen NICHT mehr mitzählen:
		show_quick_take_tags: true,
		show_stability: true,
		show_highlights: true,
		daily_summary_metrics: ['wind'],
	};
	// stage_stats + metrics_summary + outlook + yesterday_comparison = 4
	assert.equal(countActiveContentModules(ui), 4);
});

test('#723: countActiveContentModules ignoriert entfernte Schalter (quick_take/stability/highlights)', () => {
	const ui: MailElementUi = {
		show_stage_stats: false,
		show_metrics_summary: false,
		show_outlook: false,
		show_yesterday_comparison: false,
		// nur entfernte Schalter aktiv → Zähler muss 0 sein:
		show_quick_take_tags: true,
		show_stability: true,
		show_highlights: true,
		daily_summary_metrics: ['precipitation', 'thunder'],
	};
	assert.equal(countActiveContentModules(ui), 0);
});

test('#723: countActiveContentModules zählt show_outlook einzeln', () => {
	const ui: MailElementUi = {
		show_stage_stats: false,
		show_metrics_summary: false,
		show_outlook: true,
		show_yesterday_comparison: false,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		daily_summary_metrics: [],
	};
	assert.equal(countActiveContentModules(ui), 1);
});

// ── AC-5: show_outlook landet im Write-Back, Fremdfelder bleiben erhalten ──────

test('#723: buildMailElementWrite schreibt show_outlook ins Persistenz-Objekt', () => {
	const original = {
		change_threshold_wind: 30,
		custom_unknown_field: 'erhalten',
		enabled: true,
	};
	const ui: MailElementUi = {
		show_stage_stats: true,
		show_metrics_summary: true,
		show_outlook: false,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		daily_summary_metrics: [],
	};
	const result = buildMailElementWrite(original, ui);

	assert.equal(result.show_outlook, false, 'show_outlook muss geschrieben werden');
	// Fremdfelder unangetastet
	assert.equal(result.change_threshold_wind, 30);
	assert.equal(result.custom_unknown_field, 'erhalten');
	assert.equal(result.enabled, true);
});

// ── AC-3: fehlendes show_outlook → Default true ───────────────────────────────

test('#723: buildMailElementWrite setzt show_outlook=true wenn UI-Feld undefined', () => {
	const ui = {
		show_stage_stats: true,
		show_metrics_summary: false,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		daily_summary_metrics: [],
		// show_outlook absichtlich weggelassen
	} as MailElementUi;
	const result = buildMailElementWrite({}, ui);
	assert.equal(result.show_outlook, true, 'Default für show_outlook ist true (Ausblick an)');
});

// ── AC-2: entfernte Felder bleiben via original-Spread erhalten ────────────────

test('#723: buildMailElementWrite erhält aus dem UI entfernte Felder via original-Spread', () => {
	// Diese Felder hat das UI nicht mehr — sie müssen byte-identisch überleben.
	// (Issue #1224: show_daylight wurde als Beispielfeld hier durch
	// telegram_style ersetzt — der Toggle selbst wurde entfernt, nicht bloß
	// verlagert, daher taugt er nicht mehr als "vom UI entfernt"-Beispiel.)
	const original = {
		telegram_style: 'kurzform',
		wind_exposition_min_elevation_m: 1500,
		show_compact_summary: false,
		// vom UI weiterhin gepflegte, aber hier mit Altwert:
		show_stage_stats: false,
	};
	const ui: MailElementUi = {
		show_stage_stats: true,
		show_metrics_summary: true,
		show_outlook: true,
		show_quick_take_tags: false,
		show_stability: false,
		show_highlights: false,
		daily_summary_metrics: [],
	};
	const result = buildMailElementWrite(original, ui);

	// Entfernte Felder unverändert erhalten:
	assert.equal(result.telegram_style, 'kurzform', 'telegram_style darf nicht verloren gehen');
	assert.equal(result.wind_exposition_min_elevation_m, 1500, 'Wind-Exposition-Höhe erhalten');
	assert.equal(result.show_compact_summary, false, 'show_compact_summary erhalten');
	// Vom UI gepflegtes Feld überschrieben:
	assert.equal(result.show_stage_stats, true);
});
