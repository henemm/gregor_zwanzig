// TDD RED — Issue #2277 Scheibe S5: Karte "E-Mail-Inhalt" als geteilter Baustein.
// Spec: docs/specs/modules/feat_2277_s5_reportconfig_rueckbau.md — AC-1, AC-2, AC-5.
//
// Prueflinge: shared/MailInhaltCard.svelte (NEU, existiert noch nicht) und die
// Read-Modify-Write-Regel baueReportConfigPayload (shared/versand-tab).
//
// Messbarkeit (Kern-Suite ist SSR-only, kein DOM, `$effect`/`onMount` laufen nie):
//   - Der STARTZUSTAND wird per SSR gemessen. Er muss also schon beim ERZEUGEN
//     der Komponente aus dem Blob stehen (untrack-Initialisierung wie bei den
//     Kanal-Flags der alten Section), nicht erst in onMount — sonst zeigte der
//     Server-Render immer "Ausfuehrlich" (so ist es in EditReportConfigSection
//     heute: email_format/show_outlook werden nur in onMount uebernommen).
//   - Der SCHREIBPFAD (`$effect`) laeuft im Test nicht. Gemessen wird er an
//     zwei Stellen: (a) die Regel selbst (baueReportConfigPayload mit den
//     Gating-Schaltern des Bausteins), (b) per AST des Bausteins, WIE der
//     `$effect` die Regel aufruft (showSchedule=false, showChannels=false,
//     lebender Blob als Basis). (b) ist keine String-Presence: es wird der
//     Aufruf-Ausdruck des Effekts als Syntaxbaum gelesen.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/mail_inhalt_card.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const BAUSTEIN = path.join(HERE, '..', 'MailInhaltCard.svelte');

register(
	pathToFileURL(path.join(HERE, '..', '..', 'trip-new', '__tests__', 'ssrRunesHook.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const { baueReportConfigPayload } = await import('../versand-tab/reportConfigPayload.ts');

/** Lazy, damit JEDER Test einzeln an der fehlenden Datei scheitert. */
async function renderKarte(reportConfig: Record<string, unknown>): Promise<string> {
	const mod = await import(pathToFileURL(BAUSTEIN).href);
	return render(mod.default, { props: { reportConfig } }).body;
}

function inputTagNach(html: string, testid: string): string {
	const mi = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(mi, -1, `Testid "${testid}" fehlt im Render des Bausteins.`);
	// Die Radios tragen das Testid am <input> SELBST (e2e: `.check()` auf dem Testid),
	// die Checkboxen an einem Wrapper-<span> davor. Beide Faelle abdecken.
	const eigenerTag = html.lastIndexOf('<', mi);
	const start = html.startsWith('<input', eigenerTag) ? eigenerTag : html.indexOf('<input', mi);
	assert.notEqual(start, -1, `Kein <input> hinter Testid "${testid}".`);
	return html.slice(start, html.indexOf('>', start) + 1);
}
const hat = (tag: string, name: string) => new RegExp(`\\b${name}(=""|(?=[\\s/>]))`).test(tag);

const SCHALTER = ['report-show-outlook', 'report-show-stage-stats', 'report-show-yesterday-comparison'];

// ─── AC-1: Startzustand aus dem Blob ─────────────────────────────────────────

describe('AC-1: Startzustand der Karte kommt aus dem Blob', () => {
	test('compact_und_ausblick_aus__hinweis_kompakt_gewaehlt_alle_schalter_deaktiviert', async () => {
		const html = await renderKarte({ email_format: 'compact', show_outlook: false });

		assert.ok(html.includes('data-testid="report-mail-content"'), 'Karte report-mail-content fehlt.');
		assert.ok(
			html.includes('data-testid="report-compact-hint"'),
			'AC-1: Im Kompakt-Modus fehlt der Hinweis report-compact-hint. Der Server-Render zeigt ' +
				'"Ausfuehrlich", weil email_format erst in onMount aus dem Blob uebernommen wird — ' +
				'der Startzustand muss beim Erzeugen stehen.'
		);
		assert.ok(hat(inputTagNach(html, 'report-email-format-compact'), 'checked'), 'Kompakt nicht gewaehlt.');
		const hinweis = html.slice(html.indexOf('data-testid="report-compact-hint"'));
		assert.ok(
			hinweis.slice(0, hinweis.indexOf('</p>')).includes(
				'Im Kompakt-Modus werden fix Metriken-Überblick + Ausblick gezeigt. Die Inhalts-Bausteine unten sind deaktiviert.'
			),
			'F006: Wortlaut des Kompakt-Hinweises weicht vom Original ab.'
		);
		assert.ok(!hat(inputTagNach(html, 'report-email-format-full'), 'checked'), 'Ausfuehrlich faelschlich gewaehlt.');
		for (const id of SCHALTER) {
			assert.ok(hat(inputTagNach(html, id), 'disabled'), `AC-1: Schalter ${id} ist im Kompakt-Modus nicht deaktiviert.`);
		}
		assert.ok(!hat(inputTagNach(html, 'report-show-outlook'), 'checked'), 'AC-1: "Ausblick" muss aus sein (show_outlook=false).');
		assert.ok(hat(inputTagNach(html, 'report-show-stage-stats'), 'checked'), 'Etappen-Kennzahlen: Default an.');
	});

	test('ausfuehrlich_und_vortag_aus__kein_hinweis_schalter_bedienbar', async () => {
		// Gegenprobe mit ANDEREM Blob-Zustand: der Startzustand ist nicht festverdrahtet.
		const html = await renderKarte({ email_format: 'full', show_yesterday_comparison: false });

		assert.ok(!html.includes('data-testid="report-compact-hint"'), 'Hinweis darf im Modus "Ausfuehrlich" nicht stehen.');
		assert.ok(hat(inputTagNach(html, 'report-email-format-full'), 'checked'), 'Ausfuehrlich nicht gewaehlt.');
		for (const id of SCHALTER) {
			assert.ok(!hat(inputTagNach(html, id), 'disabled'), `Schalter ${id} darf im Modus "Ausfuehrlich" nicht deaktiviert sein.`);
		}
		assert.ok(!hat(inputTagNach(html, 'report-show-yesterday-comparison'), 'checked'), 'AC-1: "Vortag-Vergleich" muss aus sein.');
		assert.ok(hat(inputTagNach(html, 'report-show-outlook'), 'checked'), 'Ausblick: Default an, wenn Feld fehlt.');
	});

	test('schalter_wrapper_ist_im_compact_modus_gedimmt_und_im_full_modus_nicht', async () => {
		// F003: disabled allein genuegt nicht — der Wrapper traegt die sichtbare Sperre.
		const STIL = 'opacity:0.45;pointer-events:none';
		const compact = await renderKarte({ email_format: 'compact' });
		const full = await renderKarte({ email_format: 'full' });
		const wrapperStil = (html: string) => {
			const i = html.indexOf('data-testid="report-content-modules-body"');
			assert.notEqual(i, -1);
			const wrapperStart = html.lastIndexOf('<div', html.lastIndexOf('<div', i) - 1);
			return html.slice(wrapperStart, html.indexOf('>', wrapperStart) + 1);
		};
		assert.ok(wrapperStil(compact).includes(STIL), 'Compact: Schalter-Wrapper muss gedimmt/gesperrt sein.');
		assert.ok(!wrapperStil(full).includes(STIL), 'Full: Schalter-Wrapper darf nicht gedimmt sein.');
	});

	test('leerer_blob__defaults_ausfuehrlich_alle_drei_schalter_an', async () => {
		const html = await renderKarte({});
		assert.ok(hat(inputTagNach(html, 'report-email-format-full'), 'checked'));
		for (const id of SCHALTER) assert.ok(hat(inputTagNach(html, id), 'checked'), `Default von ${id} ist "an".`);
	});

	test('karte_kennt_weder_kanaele_noch_zeitplan', async () => {
		const html = await renderKarte({ send_premium_sms: true, morning_time: '06:30:00' });
		for (const fremd of ['channel-email', 'channel-telegram', 'channel-sms', 'channel-premium-sms', 'morning-master-switch', 'versand-tab']) {
			assert.ok(!html.includes(`data-testid="${fremd}"`), `Der Baustein rendert Fremdbereich "${fremd}" (Spec Entscheidung 2: nur Mail-Felder).`);
		}
	});
});

// ─── AC-2 / AC-5: Schreibregel (Read-Modify-Write, Fremdfeld-Schutz) ─────────

const ZUSTAND_NEUTRAL = {
	morning_enabled: false,
	evening_enabled: false,
	morning_time: '07:00',
	evening_time: '18:00',
	send_email: true,
	send_telegram: false,
	send_sms: false,
	send_premium_sms: false,
	multi_day_trend_morning: false,
	multi_day_trend_evening: true
};
const EIGENE = {
	show_compact_summary: true,
	wind_exposition_min_elevation_m: null,
	show_stage_stats: true,
	show_quick_take_tags: true,
	show_stability: true,
	show_highlights: true,
	daily_summary_metrics: ['temp', 'wind'],
	show_metrics_summary: false,
	show_outlook: true,
	email_format: 'full',
	show_yesterday_comparison: false
};
const FREMDFELDER = [
	'send_email', 'send_telegram', 'send_sms', 'send_premium_sms', 'telegram_style', 'enabled',
	'morning_enabled', 'evening_enabled', 'morning_time', 'evening_time',
	'multi_day_trend_morning', 'multi_day_trend_evening', 'multi_day_trend_reports'
];

function schreibe(live: Record<string, unknown>, eigene: Record<string, unknown>) {
	// Genau die Gating-Werte, die der Baustein verwenden MUSS (AC-5).
	return baueReportConfigPayload({
		snapshot: {},
		live,
		eigene,
		showSchedule: false,
		showChannels: false,
		zustand: ZUSTAND_NEUTRAL
	});
}

describe('AC-2/AC-5: der Baustein schreibt nur Mail-Felder, Rest bleibt byte-gleich', () => {
	const BLOB_A = {
		send_email: false, send_telegram: true, send_sms: true, send_premium_sms: true, telegram_style: 'kurzform',
		enabled: true, morning_enabled: true, evening_enabled: false, morning_time: '06:30:00', evening_time: '19:45:00',
		multi_day_trend_morning: true, multi_day_trend_evening: false, multi_day_trend_reports: ['morning'],
		change_threshold_temp_c: 4.5, custom_unknown_x: { a: 1 }
	};
	// Abweichender Nachbarwert: alles andersherum — ein Baustein, der Kanal/Zeitplan
	// aus seinem (neutralen) Zustand schriebe, wuerde BEIDE Zustaende kippen.
	const BLOB_B = {
		send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false, telegram_style: 'rich',
		enabled: false, morning_enabled: false, evening_enabled: true, morning_time: '05:15:00', evening_time: '21:00:00',
		multi_day_trend_morning: false, multi_day_trend_evening: true, multi_day_trend_reports: ['evening'],
		change_threshold_wind_kmh: 12, custom_unknown_y: [1, 2, 3]
	};

	for (const [name, blob] of [['Blob A', BLOB_A], ['Blob B (abweichender Nachbarwert)', BLOB_B]] as const) {
		test(`fremdfelder_bleiben_gleich__${name.replace(/\W+/g, '_')}`, () => {
			const neu = schreibe(blob, { ...EIGENE, email_format: 'compact', show_yesterday_comparison: false });
			for (const f of [...FREMDFELDER, ...Object.keys(blob).filter((k) => k.startsWith('change_') || k.startsWith('custom_'))]) {
				if (!(f in blob)) continue;
				assert.deepEqual(
					(neu as Record<string, unknown>)[f], (blob as Record<string, unknown>)[f],
					`AC-5: Fremdfeld "${f}" wurde veraendert (Zeitplan/Kanal/telegram_style gehoeren VersandTab).`
				);
			}
			assert.equal(neu.email_format, 'compact');
			assert.equal(neu.show_yesterday_comparison, false);
		});
	}

	test('eigene_felder_ueberschreiben_nur_ihre_gegenstuecke__rest_des_blobs_unberuehrt', () => {
		const neu = schreibe(BLOB_A, { ...EIGENE, email_format: 'full', show_yesterday_comparison: false });
		const erwartet = { ...BLOB_A, ...EIGENE, email_format: 'full', show_yesterday_comparison: false };
		assert.deepEqual(neu, erwartet, 'AC-2: Payload weicht vom Blob + Eigenfeldern ab (Datenverlust oder Fremdschreiben).');
	});
});

// ─── AC-5 (Wirkstelle): WIE ruft der Baustein die Regel auf? ─────────────────

type Knoten = Record<string, any>;
function alle(n: unknown, f: (k: Knoten) => void): void {
	if (n === null || typeof n !== 'object') return;
	if (Array.isArray(n)) return n.forEach((x) => alle(x, f));
	f(n as Knoten);
	for (const v of Object.values(n as Knoten)) alle(v, f);
}

describe('AC-2/AC-5: der $effect des Bausteins ruft baueReportConfigPayload mit Fremdfeld-Schutz auf', () => {
	function aufrufArgumente(): Knoten {
		const quelle = readFileSync(BAUSTEIN, 'utf-8'); // Datei fehlt heute -> ENOENT = RED
		const ast = parse(quelle, { modern: true }) as Knoten;
		let args: Knoten | undefined;
		alle(ast.instance, (k) => {
			if (k.type === 'CallExpression' && k.callee?.name === 'baueReportConfigPayload') args = k.arguments?.[0];
		});
		assert.ok(args, 'Der Baustein ruft baueReportConfigPayload nicht auf (Read-Modify-Write fehlt).');
		return args as Knoten;
	}
	const prop = (o: Knoten, name: string): Knoten | undefined =>
		o.properties?.find((p: Knoten) => (p.key?.name ?? p.key?.value) === name)?.value;

	test('showSchedule_und_showChannels_sind_literal_false', () => {
		const a = aufrufArgumente();
		for (const n of ['showSchedule', 'showChannels']) {
			const v = prop(a, n);
			assert.ok(v && v.type === 'Literal' && v.value === false,
				`AC-5: ${n} ist nicht literal false — der Baustein schriebe dann Fremdfelder (Fehlerklasse Fix-Loop 4, #1738).`);
		}
	});

	test('basis_ist_der_lebende_blob_per_untrack__nicht_der_mount_schnappschuss', () => {
		const live = prop(aufrufArgumente(), 'live');
		assert.ok(live, 'AC-2: Kein `live`-Argument — Basis waere nur der Mount-Schnappschuss (Last-Write-Wins).');
		let liestReportConfig = false;
		let untracked = false;
		alle(live, (k) => {
			if (k.type === 'Identifier' && k.name === 'reportConfig') liestReportConfig = true;
			if (k.type === 'CallExpression' && k.callee?.name === 'untrack') untracked = true;
		});
		assert.ok(liestReportConfig, 'AC-2: `live` liest nicht den bindbaren reportConfig.');
		assert.ok(untracked, 'AC-2: `live` ist nicht in untrack() — der Effekt triggerte sich selbst.');
	});

	test('eigene_felder_enthalten_email_format_und_die_drei_schalter', () => {
		const eigene = prop(aufrufArgumente(), 'eigene');
		assert.ok(eigene?.properties, 'Keine `eigene`-Felder an baueReportConfigPayload.');
		const namen = eigene.properties.map((p: Knoten) => p.key?.name ?? p.key?.value);
		for (const f of ['email_format', 'show_outlook', 'show_stage_stats', 'show_yesterday_comparison']) {
			assert.ok(namen.includes(f), `AC-2/AC-10: Baustein schreibt "${f}" nicht (Mail-Format/Schalter wirkungslos).`);
		}
		for (const f of ['telegram_style', 'send_email', 'morning_time']) {
			assert.ok(!namen.includes(f), `AC-5: Baustein schreibt Fremdfeld "${f}".`);
		}
	});
});
