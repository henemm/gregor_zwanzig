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
const BAUSTEIN = path.join(HERE, '..', 'MailInhaltCard.svelte');

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
	});

	const DEFAULTS = {
		email_format: 'full',
		show_outlook: true,
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
			show_yesterday_comparison: null,
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

describe('MailInhaltCard: Verdrahtung von Restore und Write-Back (AST)', () => {
	const ast = parse(readFileSync(BAUSTEIN, 'utf-8'), { modern: true }) as Knoten;
	function aufrufe(name: string): Knoten[] {
		const r: Knoten[] = [];
		alle(ast.instance, (k) => {
			if (k.type === 'CallExpression' && k.callee?.name === name) r.push(k);
		});
		return r;
	}

	test('onMount_ruft_ladeMailZustand_auf', () => {
		const onMount = aufrufe('onMount');
		assert.equal(onMount.length, 1, 'Genau ein onMount erwartet.');
		let ruft = false;
		alle(onMount[0].arguments?.[0], (k) => {
			if (k.type === 'CallExpression' && k.callee?.name === 'ladeMailZustand') ruft = true;
		});
		assert.ok(ruft, 'onMount stellt den gespeicherten Zustand nicht per ladeMailZustand wieder her.');
	});

	// F005: Verdrahtung des onMount-Restore (SSR fuehrt onMount nie aus -> per AST).
	function onMountKoerper(): Knoten[] {
		const fn = aufrufe('onMount')[0].arguments?.[0];
		return fn?.body?.body ?? [];
	}

	test('onMount_hat_guard_if_nicht_reportConfig_return_vor_dem_restore', () => {
		const guard = onMountKoerper().find((st) => st.type === 'IfStatement');
		assert.ok(guard, 'onMount: Guard `if (!reportConfig) return;` fehlt.');
		assert.equal(guard.test?.type, 'UnaryExpression');
		assert.equal(guard.test?.operator, '!');
		assert.equal(guard.test?.argument?.name, 'reportConfig');
		const ret = guard.consequent?.type === 'BlockStatement' ? guard.consequent.body?.[0] : guard.consequent;
		assert.equal(ret?.type, 'ReturnStatement', 'Guard muss mit return abbrechen.');
		assert.equal(onMountKoerper().indexOf(guard), 0, 'Guard muss die erste Anweisung sein.');
	});

	test('onMount_uebergibt_den_blob_originalReportConfig_an_ladeMailZustand', () => {
		const decl = onMountKoerper().flatMap((st) => (st.type === 'VariableDeclaration' ? st.declarations : []));
		const z = decl.find((d: Knoten) => d.id?.name === 'z');
		const call = unwrap(z?.init);
		assert.equal(call?.type, 'CallExpression');
		assert.equal(call.callee?.name, 'ladeMailZustand');
		assert.equal(call.arguments?.length, 1);
		assert.equal(call.arguments[0]?.name, 'originalReportConfig', 'ladeMailZustand muss den Blob (originalReportConfig) bekommen, nicht {}.');
		const kopie = onMountKoerper().find(
			(st) => st.type === 'ExpressionStatement' && st.expression?.left?.name === 'originalReportConfig'
		);
		assert.ok(kopie, 'onMount muss originalReportConfig aus reportConfig setzen.');
	});

	test('onMount_weist_JEDEM_Feld_von_ladeMailZustand_seinen_State_aus_z_zu', () => {
		const felder = Object.keys(ladeMailZustand({}));
		assert.ok(felder.length >= 11, 'ladeMailZustand liefert weniger Felder als erwartet.');
		const zuweisungen = new Map<string, string>();
		for (const st of onMountKoerper()) {
			const e = st.type === 'ExpressionStatement' ? st.expression : undefined;
			if (e?.type !== 'AssignmentExpression') continue;
			const r = unwrap(e.right);
			if (r?.type === 'MemberExpression' && r.object?.name === 'z' && r.computed === false) {
				zuweisungen.set(e.left?.name, r.property?.name);
			}
		}
		// Feld -> State-Name: snake_case des Blobs, nur daily_summary_metrics heisst im Baustein camelCase.
		const stateVon = (f: string) => (f === 'daily_summary_metrics' ? 'dailySummaryMetrics' : f);
		for (const f of felder) {
			assert.equal(zuweisungen.get(stateVon(f)), f, `onMount: Zuweisung \`${stateVon(f)} = z.${f}\` fehlt (Bestandsfeld wuerde nicht wiederhergestellt).`);
		}
	});

	test('startzustand_nutzt_ladeMailZustand_per_untrack', () => {
		const start = aufrufe('ladeMailZustand').filter((k) => {
			let untracked = false;
			alle(k.arguments, (x) => {
				if (x.type === 'CallExpression' && x.callee?.name === 'untrack') untracked = true;
			});
			return untracked;
		});
		assert.equal(start.length, 1, 'Startzustand muss ladeMailZustand(untrack(...)) nutzen.');
	});

	test('effect_weist_reportConfig_den_payload_zu__kein_void', () => {
		const effekte = aufrufe('$effect');
		assert.equal(effekte.length, 1, 'Genau ein $effect erwartet.');
		let zugewiesen = false;
		alle(effekte[0].arguments?.[0], (k) => {
			if (k.type === 'AssignmentExpression' && k.left?.name === 'reportConfig') {
				const r = unwrap(k.right);
				if (r?.type === 'CallExpression' && r.callee?.name === 'baueReportConfigPayload') zugewiesen = true;
			}
		});
		assert.ok(zugewiesen, 'Der $effect schreibt baueReportConfigPayload nicht in reportConfig zurueck (Karte wirkungslos).');
	});

	// F007: Werte des Write-Back (`eigene`) — sonst ueberschreibt die Karte beim ersten
	// Effekt-Lauf gespeicherte Werte (Datenverlust).
	function payloadArgument(): Knoten {
		const call = aufrufe('baueReportConfigPayload')[0];
		assert.ok(call, 'baueReportConfigPayload-Aufruf fehlt.');
		const obj = unwrap(call.arguments?.[0]);
		assert.equal(obj?.type, 'ObjectExpression');
		return obj;
	}
	function eigenschaft(obj: Knoten, name: string): Knoten | undefined {
		return obj.properties?.find((p: Knoten) => p.type === 'Property' && p.key?.name === name);
	}

	test('eigene_hat_exakt_die_Felder_von_ladeMailZustand', () => {
		const felder = Object.keys(ladeMailZustand({})).sort();
		const eigene = unwrap(eigenschaft(payloadArgument(), 'eigene')?.value);
		assert.equal(eigene?.type, 'ObjectExpression', '`eigene` muss ein Objektliteral sein.');
		assert.ok(
			eigene.properties.every((p: Knoten) => p.type === 'Property' && !p.computed),
			'`eigene` darf keine Spreads/berechneten Schluessel enthalten.'
		);
		const schluessel = eigene.properties.map((p: Knoten) => p.key?.name).sort();
		assert.deepEqual(schluessel, felder, '`eigene` deckt die Felder von ladeMailZustand nicht exakt ab.');
	});

	test('eigene_Werte_sind_der_State_gleichen_Namens__kein_Literal_kein_anderer_Identifier', () => {
		const eigene = unwrap(eigenschaft(payloadArgument(), 'eigene')?.value) as Knoten;
		const felder = Object.keys(ladeMailZustand({}));
		assert.ok(felder.length >= 11);
		for (const f of felder) {
			const p = eigenschaft(eigene, f);
			assert.ok(p, `eigene.${f} fehlt.`);
			const w = unwrap(p.value);
			if (f === 'daily_summary_metrics') {
				assert.equal(w?.type, 'ArrayExpression', 'daily_summary_metrics muss eine Array-Kopie sein.');
				assert.equal(w.elements?.length, 1);
				assert.equal(w.elements[0]?.type, 'SpreadElement');
				assert.equal(w.elements[0].argument?.name, 'dailySummaryMetrics');
			} else {
				assert.equal(w?.type, 'Identifier', `eigene.${f} muss ein Identifier sein (kein Literal).`);
				assert.equal(w.name, f, `eigene.${f} muss den State \`${f}\` schreiben, nicht \`${w.name}\`.`);
			}
		}
	});

	test('snapshot_ist_originalReportConfig_und_live_ist_untrack_reportConfig', () => {
		const obj = payloadArgument();
		const snap = unwrap(eigenschaft(obj, 'snapshot')?.value);
		assert.equal(snap?.type, 'Identifier', 'snapshot darf kein Literal sein.');
		assert.equal(snap.name, 'originalReportConfig');
		const live = unwrap(eigenschaft(obj, 'live')?.value);
		assert.equal(live?.type, 'CallExpression');
		assert.equal(live.callee?.name, 'untrack');
		const inner = live.arguments?.[0];
		assert.equal(inner?.type, 'ArrowFunctionExpression');
		assert.equal(unwrap(inner.body)?.name, 'reportConfig');
	});
});
