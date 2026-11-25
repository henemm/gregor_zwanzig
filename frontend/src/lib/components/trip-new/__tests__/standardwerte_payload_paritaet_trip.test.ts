// TDD RED — Onboarding S3 (Issue #2521), AC-6 (+ Trip-Teil von AC-9/AC-11 lokal):
// „Mit Standardwerten speichern" erzeugt im Trip dieselbe `report_config` wie das
// unveraenderte Durchklicken aller Reiter.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// VERGLEICHSMASSSTAB (#2987, Spec refactor_2987_standardwerte_eine_quelle.md): feste Werte (VERSAND, MAIL),
// nie eine zweite Berechnung. Bis #2987 war es der Code von VersandTab/MailInhaltCard; beide sind nicht
// mehr sichtbar und fallen mit #3020.
//
// Vertrag (Spec: „reiner Ergaenzer in tripNewLogic.ts"):
//   ergaenzeStandardwerteReportConfig(rc: ReportConfig | undefined): ReportConfig
//   — ergaenzt fehlende Felder, ueberschreibt nichts Gesetztes, schreibt
//     `multi_day_trend_reports` wie der Versand-Reiter.
//
// #3155 (Spec feat_3155_ein_name_ausblick.md, Entscheidung 4, AC-7; Ober-Spec
// feat_3122 Nr. 6 / AC-9): die Karte „Mehrtages-Trend" entfaellt; die Anlage
// belegt den 3-Tages-Ausblick nach der EINEN Regel vor: allein das Morgen-
// Briefing eingeschaltet -> ["morning"], sonst ["evening"]; ein vorhandener
// Wert gewinnt. Keine Trend-Felder (`multi_day_trend_morning/_evening`) mehr.
// Die Vorbelegung gilt NUR bei der Anlage; das Speichern eines bestehenden Trips
// setzt die Liste nie neu (Tech-Lead-Entscheidung, AC-13).
//
// Mutationen, die hier rot werden muessen (Spec AC-6, #3155 AC-7):
//   „Ergaenzer laesst den Mail-Baustein weg", „Ergaenzer setzt
//   multi_day_trend_reports nicht", „Vorbelegung immer ['evening']",
//   „Vorbelegung ueberschreibt einen gespeicherten Wert".
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import * as logik from '../tripNewLogic.ts';
import { baueReportConfigPayload, ladeReportZustand } from '../../shared/versand-tab/reportConfigPayload.ts';
import type { Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	TRIP_EDITOR,
	editorUmgebung,
	knopfEinbettungen,
	knopfAttribut,
	ruhe,
	derivedNeu
} from '../../shared/__tests__/standardwerteEditorPruefstand.ts';

/** Was /trips/new vor dem ersten Versand-Besuch in report_config haelt: nur das
 *  Tagesfenster aus dem (dauerhaft gemounteten) Wetter-Metriken-Reiter. */
const VOR_VERSAND = { day_window_start_hour: 4, day_window_end_hour: 19 };

function klon<T>(v: T): T {
	return v === undefined ? v : JSON.parse(JSON.stringify(v));
}

/** Feste Standardwerte in der Reihenfolge des Anlege-Koerpers (Versand, dann Mail-Inhalt). */
const VERSAND = {
	telegram_style: 'rich', enabled: true, morning_enabled: true, evening_enabled: true,
	morning_time: '07:00:00', evening_time: '18:00:00', multi_day_trend_reports: ['evening'],
	send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false
};
const MAIL = {
	email_format: 'full', show_outlook: true, show_stage_stats: true, show_yesterday_comparison: true,
	show_compact_summary: true, wind_exposition_min_elevation_m: null, show_quick_take_tags: true, show_stability: true,
	show_highlights: true, daily_summary_metrics: ['precipitation', 'wind', 'visibility', 'thunder'], show_metrics_summary: false
};
/** Felder der Eingabe zuerst (Read-Modify-Write), dann Standard, dann die Abweichungen des Falls. */
const erwartet = (blob: Knoten, abweichung: Knoten = {}): Knoten => ({ ...blob, ...VERSAND, ...MAIL, ...abweichung });

type Ergaenzer = (rc: Knoten | undefined) => Knoten;
function ergaenzer(): Ergaenzer {
	const f = (logik as Record<string, unknown>).ergaenzeStandardwerteReportConfig;
	assert.equal(
		typeof f,
		'function',
		'tripNewLogic.ts exportiert keinen reinen Ergaenzer `ergaenzeStandardwerteReportConfig` (Spec Teil A)'
	);
	return f as Ergaenzer;
}

describe('AC-6: Ergaenzer gegen feste Koerper', () => {
	const AUS = { enabled: false, morning_enabled: false, evening_enabled: false };
	const BESTAND = {
		trip_id: 'bestand-2987', change_threshold_temp: 3, enabled: true, morning_enabled: true, evening_enabled: false,
		morning_time: '06:30:00', evening_time: '20:15:00', send_email: false, send_telegram: true, send_sms: true,
		send_premium_sms: true, multi_day_trend_reports: ['morning', 'evening'], show_outlook: false, daily_summary_metrics: ['wind']
	};
	for (const [fall, blob, abweichung] of [
		['undefined', undefined, {}],
		['leer', {}, {}],
		['nur Tagesfenster', VOR_VERSAND, {}],
		['enabled:false', { enabled: false }, AUS],
		['unbekannte Felder', { zukunft: { a: [1, null] }, change_threshold_wind: 20 }, {}],
		['Kurzform', { telegram_style: 'kurzform' }, { telegram_style: 'kurzform' }],
		['Zeiten null', { morning_time: null, evening_time: null }, {}],
		['nur Abendzeit', { evening_time: '19:15' }, { evening_time: '19:15:00' }],
		['AC-7: gesetzte und unbekannte Felder gewinnen', BESTAND, BESTAND],
		['AC-3: Zeiten leer', { morning_time: '', evening_time: '' }, {}],
		['AC-3: Zeiten ungueltig', { morning_time: 'abc', evening_time: '6:00' }, {}]
	] as Array<[string, Knoten | undefined, Knoten]>) {
		test(`#2987 AC-5 zeichengleich inkl. Schluesselreihenfolge, Eingabe unveraendert: ${fall}`, () => {
			const ein = klon(blob);
			const rc = ergaenzer()(ein);
			assert.equal(JSON.stringify(rc), JSON.stringify(erwartet(blob ?? {}, abweichung)));
			rc.daily_summary_metrics.push('x'); // Kopie: weder Eingabe noch Standardliste duerfen mitwachsen
			assert.deepEqual(ein, blob);
			assert.deepEqual(ergaenzer()({}).daily_summary_metrics, MAIL.daily_summary_metrics);
		});
	}

	test('#3155 AC-7: Morgen- und Abend-Briefing an -> 3-Tages-Ausblick nur abends (multi_day_trend_reports ["evening"])', () => {
		const rc = ergaenzer()(klon(VOR_VERSAND));
		assert.ok('multi_day_trend_reports' in rc, 'Feld fehlt — die Vorbelegung muss ausdruecklich geschrieben werden');
		assert.deepEqual(rc.multi_day_trend_reports, ['evening']);
	});

	test('#3155 AC-7: nur Morgen-Briefing an -> 3-Tages-Ausblick im Morgen-Briefing (["morning"])', () => {
		const nurMorgen = { ...VOR_VERSAND, morning_enabled: true, evening_enabled: false };
		const rc = ergaenzer()(klon(nurMorgen));
		assert.deepEqual(klon(rc), erwartet(nurMorgen, { evening_enabled: false, multi_day_trend_reports: ['morning'] }));
	});

	test('#3155 AC-7: nur Abend-Briefing an -> ["evening"]', () => {
		const nurAbend = { ...VOR_VERSAND, morning_enabled: false, evening_enabled: true };
		assert.deepEqual(ergaenzer()(klon(nurAbend)).multi_day_trend_reports, ['evening']);
	});

	for (const vorhanden of [['morning', 'evening'], ['morning'], []]) {
		test(`#3155 AC-7: vorhandener Wert gewinnt (${JSON.stringify(vorhanden)})`, () => {
			const gesetzt = { ...VOR_VERSAND, multi_day_trend_reports: vorhanden };
			assert.deepEqual(ergaenzer()(klon(gesetzt)).multi_day_trend_reports, vorhanden, 'Ergaenzer ueberschreibt die gespeicherte Einstellung');
		});
	}

	test('#3155: keine Trend-Felder der entfallenen Karte im neuen report_config', () => {
		const rc = ergaenzer()(klon(VOR_VERSAND));
		for (const feld of ['multi_day_trend_morning', 'multi_day_trend_evening']) {
			assert.ok(!(feld in rc), `Ergaenzer schreibt noch ${feld}`);
		}
	});

	// Tech-Lead-Entscheidung #3155 (AC-13, Known Limitation „spaetere Aenderungen aendern eine
	// Vorbelegung nicht"): die Vorbelegung gilt NUR bei der Anlage. Speichern eines BESTEHENDEN
	// Trips (Speicherweg baueReportConfigPayload mit geladenem Blob, wie Golden D) setzt
	// multi_day_trend_reports nie neu: fehlt die Liste, bleibt es beim Stand vor B4 (fehlend
	// bzw. []), nie ["morning"]/["evening"].
	for (const [fall, aenderung] of [
		['ohne Aenderung', {}],
		['mit geaenderter Morgen-Zeit', { morning_time: '08:00' }]
	] as const) {
		test(`#3155 AC-13: bestehender Trip nur mit Morgen, ohne Liste — Speichern ${fall} schreibt keine Vorbelegung`, () => {
			const bestand = {
				trip_id: 'bestand-3155', enabled: true, morning_enabled: true, evening_enabled: false,
				morning_time: '06:00:00', evening_time: '20:00:00', send_email: true
			};
			const zustand = { ...ladeReportZustand(klon(bestand)), ...aenderung };
			const nach = baueReportConfigPayload({ snapshot: klon(bestand), live: klon(bestand), zustand });
			const wert = nach.multi_day_trend_reports;
			assert.ok(
				wert === undefined || (Array.isArray(wert) && wert.length === 0),
				`bestehender Trip bekommt beim Speichern eine Ausblick-Vorbelegung: ${JSON.stringify(wert)}`
			);
		});
	}

	test('#3155 AC-13: bestehender Trip mit gespeicherter Liste — Speichern laesst sie unveraendert', () => {
		for (const liste of [['morning'], ['evening'], ['morning', 'evening'], []]) {
			const bestand = { enabled: true, morning_enabled: true, evening_enabled: true, send_email: true, multi_day_trend_reports: liste };
			const nach = baueReportConfigPayload({ snapshot: klon(bestand), live: klon(bestand), zustand: ladeReportZustand(klon(bestand)) });
			assert.deepEqual(nach.multi_day_trend_reports, liste);
		}
	});

	// Adversary F001 (Fix-Loop 1): in der Anlage traegt der LEBENDE Blob die eigene
	// Vorbelegung des vorigen $effect-Laufs (VersandTab.svelte: `live` = reportConfig
	// nach dem letzten Lauf). Schaltet der Nutzer danach von „beide Briefings" auf
	// „nur Morgen", muss die Vorbelegung neu nach der Regel entstehen -- die alte
	// Vorbelegung aus `live` darf nicht als „gespeicherter Wert" gewinnen.
	for (const [fall, snapshot] of [
		['ohne Schnappschuss', undefined],
		['Schnappschuss = Blob vor dem Versand-Besuch', VOR_VERSAND]
	] as const) {
		test(`#3155 AC-7 (F001): Anlage beide Briefings -> nur Morgen, verkettet (${fall}) -> ["morning"]`, () => {
			const beide = { ...ladeReportZustand(klon(VOR_VERSAND)), morning_enabled: true, evening_enabled: true };
			const lauf1 = baueReportConfigPayload({
				snapshot: snapshot ? klon(snapshot) : undefined,
				live: klon(VOR_VERSAND),
				zustand: beide,
				ausblickVorbelegung: true
			});
			assert.deepEqual(lauf1.multi_day_trend_reports, ['evening'], 'Messaufbau: erster Lauf belegt nicht abends vor');
			const lauf2 = baueReportConfigPayload({
				snapshot: snapshot ? klon(snapshot) : undefined,
				live: klon(lauf1),
				zustand: { ...beide, evening_enabled: false },
				ausblickVorbelegung: true
			});
			assert.deepEqual(
				lauf2.multi_day_trend_reports,
				['morning'],
				'Vorbelegung des vorigen Laufs (im lebenden Blob) bleibt nach Umschalten auf „nur Morgen" stehen'
			);
		});
	}

	test('ueberschreibt nichts Gesetztes: vorhandene Werte gewinnen', () => {
		const gesetzt = {
			...VOR_VERSAND,
			morning_time: '06:30:00',
			send_telegram: true,
			email_format: 'compact',
			show_outlook: false,
			change_threshold_temp: 3
		};
		const rc = ergaenzer()(klon(gesetzt));
		assert.equal(rc.email_format, 'compact');
		assert.equal(rc.show_outlook, false);
		assert.equal(rc.send_telegram, true);
		assert.equal(rc.change_threshold_temp, 3, 'unbekanntes Bestandsfeld geht verloren');
		assert.deepEqual(klon(rc), erwartet(gesetzt, gesetzt));
	});

	test('rein: Eingabe wird nicht veraendert', () => {
		const ein = klon(VOR_VERSAND);
		ergaenzer()(ein);
		assert.deepEqual(ein, VOR_VERSAND);
	});
});

// ── Wirkstelle: Klick im echten TripNewEditor ────────────────────────────────
const GPX = { file: 'a.gpx', km: 10, asc: 500 };

async function editorMitKlickSpion(reportConfig: Knoten = VOR_VERSAND) {
	const posts: Array<{ url: string; body: Knoten }> = [];
	const ziele: string[] = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: {},
		name: 'Trip X',
		startDate: '2026-07-01',
		stages: [1, 2].map((id) => ({ id, name: `E${id}`, gpx: GPX, waypoints: [] })),
		catalogLoaded: true,
		reportConfig: klon(reportConfig),
		goto: async (ziel: string) => {
			ziele.push(ziel);
		},
		api: {
			post: async (url: string, body: Knoten) => {
				posts.push({ url, body: klon(body) });
				return { id: 'neu-1' };
			},
			get: async () => ({})
		}
	});
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 1, 'TripNewEditor bettet <StandardwerteSpeichernKnopf> nicht ein');
	const klick = () => (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)();
	return { e, posts, ziele, klick };
}

describe('AC-6/AC-9/AC-11 an der Wirkstelle: Klick im echten Trip-Editor', () => {
	test('Klick speichert ueber POST /api/trips — report_config == feste Fixture, unbekannte Felder inklusive (#2987 AC-1)', async () => {
		const blob = { ...VOR_VERSAND, change_threshold_temp: 3, zukunft: { a: [1, null] } };
		const { posts, klick } = await editorMitKlickSpion(blob);
		await klick();
		await ruhe();
		assert.equal(posts.length, 1, `erwartet genau einen POST, gesehen ${posts.length}`);
		assert.equal(posts[0].url, '/api/trips');
		assert.deepEqual(posts[0].body.report_config, erwartet(blob));
		// #3155 AC-7: der neue Trip traegt die Ausblick-Vorbelegung (Morgen + Abend an -> abends).
		assert.deepEqual(posts[0].body.report_config.multi_day_trend_reports, ['evening']);
	});
	test('Klick landet auf der Detailseite des neuen Trips', async () => {
		const { ziele, klick } = await editorMitKlickSpion();
		await klick();
		await ruhe();
		assert.ok(ziele.includes('/trips/neu-1'), `Navigation nach dem Speichern: ${JSON.stringify(ziele)}`);
	});
	test('zweiter Klick nach erfolgreichem Speichern erzeugt keinen zweiten POST (savedTripId)', async () => {
		const { posts, klick } = await editorMitKlickSpion();
		await klick();
		await ruhe();
		await klick();
		await ruhe();
		assert.equal(posts.length, 1);
	});
});

// ── Adversary F001: defaultsBereit kommt ueber den ECHTEN Rueckkanal ──────────
// `catalogLoaded` wird hier NICHT gesaet: der Editor-Handler, den der
// Wetter-Metriken-Reiter nach seinem Katalog-Laden bedient
// (`onWeatherMetricsChange={handleWeatherMetricsChange}`), muss den Knopf
// freischalten.
async function editorOhneKatalogSaat() {
	const posts: string[] = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: {},
		name: 'Trip X',
		startDate: '2026-07-01',
		stages: [1, 2].map((id) => ({ id, name: `E${id}`, gpx: GPX, waypoints: [] })),
		reportConfig: klon(VOR_VERSAND),
		api: {
			post: async (url: string) => {
				posts.push(url);
				return { id: 'neu-1' };
			},
			get: async () => ({})
		}
	});
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 2, 'TripNewEditor bettet <StandardwerteSpeichernKnopf> nicht Desktop UND mobil ein');
	const aktiv = () => knoepfe.map((k) => Boolean(knopfAttribut(k, e, 'enabled')));
	return { e, posts, aktiv, klick: () => (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)() };
}

describe('F001: Rueckkanal des Wetter-Metriken-Reiters schaltet den Standardwerte-Knopf frei', () => {
	test('vor der Meldung des Reiters gesperrt, danach aktiv; Klick speichert genau einmal', async () => {
		const { e, posts, aktiv, klick } = await editorOhneKatalogSaat();
		assert.ok(aktiv().every((a) => a === false), 'Knopf aktiv, bevor der Reiter seine Standardauswahl gemeldet hat');
		assert.equal(typeof e.u.handleWeatherMetricsChange, 'function', 'Messaufbau: handleWeatherMetricsChange fehlt');
		e.u.handleWeatherMetricsChange([{ metric_id: 'temperature', enabled: true }]);
		derivedNeu(e);
		// #2347 S4 (AC-20, Race): mit aktiver Metrik wartet der Knopf zusaetzlich auf
		// die Wertebereiche-Vorbelegung (CorridorEditor → onVorbelegungFertig).
		assert.ok(aktiv().every((a) => a === false), 'Knopf frei, bevor die Wertebereiche vorbelegt sind');
		assert.equal(typeof e.u.handleVorbelegungFertig, 'function', 'Messaufbau: handleVorbelegungFertig fehlt');
		e.u.handleVorbelegungFertig();
		derivedNeu(e);
		assert.ok(aktiv().every((a) => a === true), 'Meldung des Reiters + Vorbelegung schalten den Knopf nicht frei');
		await klick();
		await ruhe();
		assert.deepEqual(posts, ['/api/trips']);
	});
});

// ── Adversary F002: beide Trip-Guards einzeln ────────────────────────────────
describe('F002: gesperrtes Gate — jeder Trip-Guard wirkt fuer sich', () => {
	test('Klick-Handler bei gesperrtem Gate ruft buildAndSave gar nicht auf', async () => {
		const { e, klick } = await editorOhneKatalogSaat();
		let aufrufe = 0;
		e.u.buildAndSave = async () => {
			aufrufe++;
			return null;
		};
		await klick();
		await ruhe();
		assert.equal(aufrufe, 0, 'Klick-Handler ignoriert das gesperrte Standardwerte-Gate');
	});
	test('buildAndSave(true) bei gesperrtem Gate speichert nichts', async () => {
		const { e, posts } = await editorOhneKatalogSaat();
		const id = await e.u.buildAndSave(true);
		await ruhe();
		assert.equal(id, null);
		assert.deepEqual(posts, [], 'buildAndSave(mitStandardwerten) ignoriert das gesperrte Gate');
	});
});
