// Issue #2277 S5 (Fix-Loop 1, F002) — Restore-Logik der Karte "E-Mail-Inhalt".
// onMount/$effect laufen in der SSR-Kern-Suite nie; deshalb (a) die reine Funktion
// ladeMailZustand direkt, (b) per AST, dass der Baustein sie in onMount aufruft und
// der $effect den Write-Back wirklich ZUWEIST (nicht `void ...`).
// Handler (onchange) sind im Kern NICHT messbar -> Live-E2E (siehe test-zuordnung.md).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/mail_inhalt_zustand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';
import { ladeMailZustand } from '../mailInhaltZustand.ts';
import { DEFAULT_DAILY_SUMMARY_METRICS } from '../mailInhaltKonstanten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));

describe('ladeMailZustand: Restore der gespeicherten Werte', () => {
	test('gespeicherte_werte_inkl_nicht_angezeigter_bestandsfelder_bleiben_erhalten', () => {
		const z = ladeMailZustand({
			email_format: 'compact',
			show_outlook: false,
			show_stage_stats: false,
			show_yesterday_comparison: false,
			show_compact_summary: false,
			wind_exposition_min_elevation_m: 1800,
			show_quick_take_tags: false,
			show_stability: false,
			show_highlights: false,
			daily_summary_metrics: ['temp'],
			show_metrics_summary: true
		});
		assert.deepEqual(z, {
			email_format: 'compact',
			show_stage_stats: false,
			show_yesterday_comparison: false,
			show_compact_summary: false,
			wind_exposition_min_elevation_m: 1800,
			show_quick_take_tags: false,
			show_stability: false,
			show_highlights: false,
			daily_summary_metrics: ['temp'],
			show_metrics_summary: true
		});
	});

	const DEFAULTS = {
		email_format: 'full',
		show_stage_stats: true,
		show_yesterday_comparison: true,
		show_compact_summary: true,
		wind_exposition_min_elevation_m: null,
		show_quick_take_tags: true,
		show_stability: true,
		show_highlights: true,
		daily_summary_metrics: [...DEFAULT_DAILY_SUMMARY_METRICS],
		show_metrics_summary: false
	};

	test('defaults_bei_fehlenden_feldern', () => {
		assert.deepEqual(ladeMailZustand({}), DEFAULTS);
		assert.deepEqual(ladeMailZustand(null), DEFAULTS);
		assert.deepEqual(ladeMailZustand(undefined), DEFAULTS);
	});

	test('falsche_typen_werden_ignoriert__default_statt_wert', () => {
		const z = ladeMailZustand({
			show_outlook: 'nein',
			show_stage_stats: 0,
			// #3047 AC-26 (Spec-Nachtrag Runde 7, Befund E8): `null` ist kein falscher Typ mehr, Python liest
			// es als None und der Block fehlt (eigener Test unten). Hier ein echter falscher Typ.
			show_yesterday_comparison: 'ja',
			show_compact_summary: 'false',
			show_quick_take_tags: 1,
			show_stability: {},
			show_highlights: [],
			show_metrics_summary: 'true',
			wind_exposition_min_elevation_m: '1800',
			daily_summary_metrics: 'temp'
		});
		assert.deepEqual(z, DEFAULTS);
	});

	test('ac26_e8_null_zusatzblock_ist_aus_wie_in_der_mail', () => {
		const z = ladeMailZustand({ show_stage_stats: null, show_yesterday_comparison: null });
		assert.equal(z.show_stage_stats, false);
		assert.equal(z.show_yesterday_comparison, false);
	});

	test('email_format_nur_full_oder_compact', () => {
		assert.equal(ladeMailZustand({ email_format: 'compact' }).email_format, 'compact');
		assert.equal(ladeMailZustand({ email_format: 'full' }).email_format, 'full');
		for (const falsch of ['html', 'COMPACT', 1, true, null]) {
			assert.equal(ladeMailZustand({ email_format: falsch }).email_format, 'full', `Wert ${String(falsch)}`);
		}
	});

	test('wind_exposition_nur_number__0_bleibt_0', () => {
		assert.equal(ladeMailZustand({ wind_exposition_min_elevation_m: 0 }).wind_exposition_min_elevation_m, 0);
		assert.equal(ladeMailZustand({ wind_exposition_min_elevation_m: null }).wind_exposition_min_elevation_m, null);
	});

	test('false_bleibt_false__nicht_auf_default_true_gekippt', () => {
		const z = ladeMailZustand({ show_stability: false, show_highlights: false });
		assert.equal(z.show_stability, false);
		assert.equal(z.show_highlights, false);
	});
});

type Knoten = Record<string, any>;
function alle(n: unknown, f: (k: Knoten) => void): void {
	if (n === null || typeof n !== 'object') return;
	if (Array.isArray(n)) return n.forEach((x) => alle(x, f));
	f(n as Knoten);
	for (const v of Object.values(n as Knoten)) alle(v, f);
}
const unwrap = (k: Knoten | undefined): Knoten | undefined =>
	k && (k.type === 'TSAsExpression' || k.type === 'TSNonNullExpression') ? unwrap(k.expression) : k;

// #3297/#3020: „MailInhaltCard: Verdrahtung“ entfaellt — die Karte ist geloescht.
