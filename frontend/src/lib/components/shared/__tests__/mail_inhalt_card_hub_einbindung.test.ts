// TDD RED — Issue #2277 Scheibe S5: Hub-Wirkstelle der Mail-Inhalt-Karte.
// Spec: docs/specs/modules/feat_2277_s5_reportconfig_rueckbau.md — AC-1, AC-2, AC-6.
//
// Warum AST statt SSR-Render des Hubs: WeatherMetricsTab rendert im Server-Render
// nur die Huelle "Lade Metriken…" (catalogLoaded wird erst in onMount per fetch
// gesetzt, onMount laeuft unter svelte/server nie) — die Karte ist dort nie im
// Dokument. Die Zusicherungen AC-1/AC-6 haengen aber an der VERDRAHTUNG im Hub
// ("Zusicherung an der Stelle pruefen, an der sie wirkt"). Deshalb wird der
// Syntaxbaum der echten Hub-Komponente gelesen (svelte/compiler parse):
//   - welche Komponente an der Stelle gemountet wird,
//   - in welchem Container (report-config-touch-scope mit allen vier
//     Capture-Handlern) und unter welchem Gate (!createMode),
//   - mit welcher Bindung (bind:reportConfig, derselbe $state wie der Hub).
// Das Dirty-VERHALTEN selbst (Mount-Normalisierung != Nutzeraenderung) wird als
// echter Funktionsaufruf von reportConfigChangedByUser + weatherSaveGate
// gemessen, mit der Payload-Form, die der Baustein beim Mounten schreibt.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/mail_inhalt_card_hub_einbindung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const HUB = path.join(HERE, '..', 'WeatherMetricsTab.svelte');

const { reportConfigChangedByUser } = await import('../reportConfigDirty.ts');
const { weatherSaveGate } = await import('../../trip-detail/weatherSaveGate.ts');
const { baueReportConfigPayload } = await import('../versand-tab/reportConfigPayload.ts');

type Knoten = Record<string, any>;

function laufe(n: unknown, ahnen: Knoten[], f: (k: Knoten, ahnen: Knoten[]) => void): void {
	if (n === null || typeof n !== 'object') return;
	if (Array.isArray(n)) return n.forEach((x) => laufe(x, ahnen, f));
	const k = n as Knoten;
	if (typeof k.type === 'string') f(k, ahnen);
	const neu = typeof k.type === 'string' ? [...ahnen, k] : ahnen;
	for (const [feld, v] of Object.entries(k)) if (feld !== 'metadata') laufe(v, neu, f);
}

const hub = () => parse(readFileSync(HUB, 'utf-8'), { modern: true }) as Knoten;
const attr = (el: Knoten, name: string) => el.attributes?.find((a: Knoten) => a.name === name);
const klasse = (el: Knoten): string => {
	const a = attr(el, 'class');
	const v = Array.isArray(a?.value) ? a.value[0] : a?.value;
	return (v?.data ?? v?.raw ?? '') as string;
};

function mounts(name: string): { k: Knoten; ahnen: Knoten[] }[] {
	const out: { k: Knoten; ahnen: Knoten[] }[] = [];
	laufe(hub().fragment, [], (k, ahnen) => {
		if (k.type === 'Component' && k.name === name) out.push({ k, ahnen });
	});
	return out;
}

describe('AC-1: die Karte kommt im Hub vom Baustein, nicht von der Section', () => {
	test('hub_mountet_MailInhaltCard_genau_einmal', () => {
		const m = mounts('MailInhaltCard');
		assert.equal(m.length, 1, `AC-1: ${m.length} MailInhaltCard-Mounts im Hub (erwartet genau 1).`);
	});

	test('hub_importiert_den_baustein_aus_shared_und_nicht_mehr_die_section', () => {
		const quelle = readFileSync(HUB, 'utf-8');
		const ast = parse(quelle, { modern: true }) as Knoten;
		const importe: string[] = [];
		laufe(ast.instance, [], (k) => {
			if (k.type === 'ImportDeclaration') importe.push(String(k.source.value));
		});
		assert.ok(
			importe.some((p) => /MailInhaltCard\.svelte$/.test(p)),
			'AC-1: WeatherMetricsTab importiert MailInhaltCard.svelte nicht.'
		);
		assert.ok(
			!importe.some((p) => /EditReportConfigSection/.test(p)),
			'AC-1: WeatherMetricsTab importiert noch EditReportConfigSection (Rueckbau, Ticket-AC-5).'
		);
		assert.equal(mounts('EditReportConfigSection').length, 0, 'Section ist im Hub noch gemountet.');
	});

	test('mount_bindet_denselben_reportConfig_state_wie_der_hub', () => {
		const m = mounts('MailInhaltCard')[0];
		assert.ok(m, 'Kein MailInhaltCard-Mount im Hub.');
		const bind = m.k.attributes.find((a: Knoten) => a.type === 'BindDirective' && a.name === 'reportConfig');
		assert.ok(bind, 'AC-2: kein bind:reportConfig — die Karte schriebe ins Leere, der Hub speichert nichts.');
	});

	test('mount_uebergibt_keine_kanal_oder_zeitplan_props', () => {
		const m = mounts('MailInhaltCard')[0];
		assert.ok(m, 'Kein MailInhaltCard-Mount im Hub.');
		const namen = m.k.attributes.map((a: Knoten) => a.name);
		for (const verboten of ['weatherChannels', 'onChannelChange', 'profileOverride', 'mode', 'showChannels', 'showSchedule']) {
			assert.ok(!namen.includes(verboten), `Spec Entscheidung 2: Prop "${verboten}" gehoert nicht an den Baustein.`);
		}
	});
});

describe('AC-6: der Mount liegt im Touch-Scope und hinter dem createMode-Gate', () => {
	test('mount_steht_im_container_report_config_touch_scope_mit_allen_vier_capture_handlern', () => {
		const m = mounts('MailInhaltCard')[0];
		assert.ok(m, 'Kein MailInhaltCard-Mount im Hub.');
		const container = [...m.ahnen].reverse().find(
			(a) => a.type === 'RegularElement' && klasse(a).split(/\s+/).includes('report-config-touch-scope')
		);
		assert.ok(
			container,
			'AC-6: Der Baustein steht NICHT im Container .report-config-touch-scope. Dann zaehlt die ' +
				'Mount-Normalisierung des Bausteins als Nutzergeste (Trip beim Oeffnen "geaendert") ODER ' +
				'eine echte Geste speichert nicht (#774, #1234).'
		);
		for (const h of ['onpointerdowncapture', 'onkeydowncapture', 'onchangecapture', 'oninputcapture']) {
			assert.ok(attr(container!, h), `AC-6: Touch-Scope-Container hat keinen Handler ${h}.`);
		}
	});

	test('mount_steht_unter_dem_gate_not_createMode', () => {
		const m = mounts('MailInhaltCard')[0];
		assert.ok(m, 'Kein MailInhaltCard-Mount im Hub.');
		const gates = m.ahnen.filter((a) => a.type === 'IfBlock');
		const quelle = readFileSync(HUB, 'utf-8');
		const tests = gates.map((g) => quelle.slice(g.test.start, g.test.end));
		assert.ok(
			tests.some((t) => /!\s*createMode/.test(t)),
			`AC-6: Kein !createMode-Gate um den Mount (Gates: ${JSON.stringify(tests)}). Im Anlegen ` +
				'gehoert die Karte dem Versand-Reiter (Spec Entscheidung 5) — sonst stehen zwei Instanzen im DOM.'
		);
	});
});

describe('AC-6: Mount-Schreiben ohne Geste ist nicht dirty, Geste speichert', () => {
	// So kommt der Blob vom Server (Altbestand: Zeiten ohne Sekunden, Felder fehlen).
	const GELADEN = {
		enabled: true, morning_time: '07:00', evening_time: '18:00', send_email: true,
		email_format: 'compact', show_outlook: false, change_threshold_temp_c: 4.5
	};
	const EIGENE_MOUNT = {
		show_compact_summary: true, wind_exposition_min_elevation_m: null, show_stage_stats: true,
		show_quick_take_tags: true, show_stability: true, show_highlights: true,
		daily_summary_metrics: ['temp'], show_metrics_summary: false,
		show_outlook: false, email_format: 'compact', show_yesterday_comparison: true
	};
	const mountSchreibt = (live: Record<string, unknown>, eigene: Record<string, unknown>) =>
		baueReportConfigPayload({
			snapshot: {}, live, eigene, showSchedule: false, showChannels: false,
			zustand: {
				morning_enabled: false, evening_enabled: false, morning_time: '07:00', evening_time: '18:00',
				send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false,
				multi_day_trend_morning: false, multi_day_trend_evening: true
			}
		});

	test('normalisierung_beim_mount_ist_keine_nutzeraenderung', () => {
		const nachMount = mountSchreibt(GELADEN, EIGENE_MOUNT) as typeof GELADEN;
		assert.equal(
			reportConfigChangedByUser(GELADEN as any, nachMount as any), false,
			'AC-6: Das Mount-Schreiben des Bausteins (Default-Materialisierung) gilt als Nutzeraenderung.'
		);
	});

	test('erster_schalter_des_nutzers_ist_eine_aenderung', () => {
		const nachMount = mountSchreibt(GELADEN, EIGENE_MOUNT);
		const nachGeste = mountSchreibt(nachMount, { ...EIGENE_MOUNT, email_format: 'full' });
		assert.equal(reportConfigChangedByUser(nachMount as any, nachGeste as any), true,
			'AC-6/AC-2: Format-Wechsel ausfuehrlich wird nicht als Aenderung erkannt (#774).');
		const vortag = mountSchreibt(nachMount, { ...EIGENE_MOUNT, show_yesterday_comparison: false });
		assert.equal(reportConfigChangedByUser(nachMount as any, vortag as any), true,
			'AC-6/AC-2: Vortag-Vergleich aus wird nicht als Aenderung erkannt.');
	});

	test('speicherentscheidung_gate_ohne_geste_skip_mit_geste_save', () => {
		// weatherSaveGate entscheidet im Hub ueber save/skip (Wirkstelle der Geste-Regel).
		assert.equal(weatherSaveGate({ catalogLoaded: true, userTouched: false }), 'skip',
			'AC-6: Mount-Schreiben des Bausteins ohne Geste darf nicht speichern.');
		assert.equal(weatherSaveGate({ catalogLoaded: true, userTouched: true }), 'save',
			'AC-6: erste echte Geste im Touch-Scope muss speichern.');
	});
});
