// TDD RED — Issue #3332 (Teil D1 von #3307, Epic #3122): Reiter „Zustellung“ beim Trip-Anlegen,
// Weg Reiter -> Editor -> der eine Anlege-POST. Spec docs/specs/modules/feat_3332_zustellung_anlegen_trip.md,
// Test Plan Nr. 2, 3, 4 und 7 (AC-2, AC-3, AC-4, AC-5, AC-6, AC-7) — gemessen dort, wo es WIRKT.
//
// Messaufbau (Muster trip_anlegen_karte_verdrahtung_3305.test.ts): das ECHTE Instanz-Skript von
// TripNewEditor.svelte und das ECHTE Instanz-Skript von ZustellungTab.svelte (svelteInstanzPruefstand.ts),
// verbunden über die ECHTEN Attribut-Ausdrücke der `<ZustellungTab …>`-Einbettungen im Editor (0 = Desktop,
// 1 = Mobil), ausgewertet in der Umgebung des Editor-Skripts. Bedient wird der Reiter über den echten
// `onaendern`-Rückruf, den er seinen Bausteinen (Kanal-Tabelle) reicht — genau das, was ein Klick auslöst.
// Der POST läuft über den echten `buildAndSave` -> `buildCreateTripPayload` und wird am gesäten `api.post`
// mitgeschnitten. Kein Mock-Theater: gesät sind nur Netz-Endpunkte (die nichts entscheiden).
//
// FESTGELEGTE SCHNITTSTELLE (Spec, Implementation Details):
//   ZustellungTab-Props `createMode`, `zustellungStart`, `onAnlegeStand` (Meldung `{ stand, nutzlast }`);
//   im Editor `zustellungStand` ($state) und `handleZustellungAnlegeStand`.
//
// REFERENZ für AC-4 (bitgleich zu heute): fixtures/trip_anlegen_ohne_zustellung_3332.json — der POST-Körper
// (report_config, Alarm-Felder, display_config.channels) des HEUTIGEN Codes ohne jede Bedienung, erzeugt aus
// dem echten Editor-Speicherweg und den echten Instanz-Skripten der heute im Schritt Zustellung dauerhaft
// gemounteten Bausteine VersandTab und MailInhaltCard (beide an `bind:reportConfig`, Reihenfolge wie im
// Browser, Muster standardwerte_payload_paritaet_trip.test.ts). Ohne das Tagesfenster des Reiters Wetter
// (von #3332 unberührt). Neu erzeugen NUR bei bewusster Rumpf-Änderung:
//   cd frontend && GZ_FIXTURE_SCHREIBEN=1 npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_zustellung_verdrahtung_3332.test.ts
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_zustellung_verdrahtung_3332.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, findeKomponenten, ohneTypen, werte, effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { editorUmgebung, derivedNeu, TRIP_EDITOR, type EditorUmgebung } from '../../shared/__tests__/standardwerteEditorPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..', '..', 'shared');
const ZUSTELLUNG_TAB = join(SHARED, 'zustellung-tab', 'ZustellungTab.svelte');
const VERSAND_TAB = join(SHARED, 'VersandTab.svelte');
const MAIL_KARTE = join(SHARED, 'MailInhaltCard.svelte');
const FIXTURE = join(HIER, 'fixtures', 'trip_anlegen_ohne_zustellung_3332.json');

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const klon = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

// ── Netz: nur Mitschrift ─────────────────────────────────────────────────────
type Aufruf = { methode: string; pfad: string };
let netz: Aufruf[] = [];
const echtesFetch = globalThis.fetch;
beforeEach(() => {
	netz = [];
	globalThis.fetch = (async (url: unknown, init?: { method?: string }) => {
		netz.push({ methode: init?.method ?? 'GET', pfad: String(url) });
		return { ok: true, json: async () => ({ mail_to: 'a@example.com', telegram_chat_id: 'chat-a', tier: 'standard' }) } as Response;
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = echtesFetch;
});
/** api-Attrappe des Reiters: schreibt nur mit, was er aufruft (im Anlegen darf er nichts aufrufen). */
function reiterApi(): Knoten {
	const auf = (methode: string) => async (pfad: string) => (netz.push({ methode, pfad }), {});
	return { get: auf('GET'), post: auf('POST'), put: auf('PUT'), patch: auf('PATCH'), delete: auf('DELETE') };
}

// ── Editor ───────────────────────────────────────────────────────────────────
type Ed = EditorUmgebung & { gesendet: Array<{ url: string; payload: J }>; speichern: () => Promise<J> };
async function editor(): Promise<Ed> {
	const gesendet: Array<{ url: string; payload: J }> = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: undefined,
		api: {
			post: async (url: string, payload: J) => (gesendet.push({ url, payload: klon(payload) }), { id: 'neu-1' }),
			get: async () => ({}),
			put: async (url: string) => (netz.push({ methode: 'PUT', pfad: url }), {})
		}
	});
	const speichern = async () => {
		e.u.ready = true; // hängt am GPX-Upload, für den Speicherweg ohne Belang
		e.u.savedTripId = null;
		gesendet.length = 0;
		assert.equal(await e.u.buildAndSave(), 'neu-1', `buildAndSave scheiterte: ${e.u.saveError}`);
		assert.equal(gesendet.length, 1, 'genau ein Anlege-POST');
		assert.equal(gesendet[0].url, '/api/trips');
		return gesendet[0].payload;
	};
	return { ...e, gesendet, speichern };
}

/** Wert eines Attributs an einer echten Einbettung, ausgewertet in der Umgebung des Eltern-Skripts. */
function attrWert(a: Knoten, quelle: string, u: Knoten): unknown {
	if (a.value === true) return true;
	if (Array.isArray(a.value)) return a.value.map((t: Knoten) => (t.type === 'Text' ? t.data : werte(ohneTypen(quelle, t.expression), u))).join('');
	if (a.value?.type === 'ExpressionTag') return werte(ohneTypen(quelle, a.value.expression), u);
	return werte(a.name, u);
}
function alleAttribute(einbettung: Knoten, quelle: string, u: Knoten): Knoten {
	const props: Knoten = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) if (a.type === 'Attribute') props[a.name] = attrWert(a, quelle, u);
	return props;
}

/** Reiter Zustellung, gemountet wie die `i`-te `<ZustellungTab>`-Einbettung im Editor (0 = Desktop, 1 = Mobil). */
async function reiter(ed: Ed, i: number) {
	derivedNeu(ed); // Svelte rechnet die Herleitungen vor jedem Neuaufbau neu
	const einb = findeKomponenten(ed.ast, 'ZustellungTab');
	assert.equal(einb.length, 2, `TripNewEditor bettet ${einb.length} statt 2 ZustellungTab ein (Desktop + Mobil, AC-1)`);
	const props = alleAttribute(einb[i], ed.quelle, ed.u);
	assert.equal(props.context, 'route');
	assert.equal(props.createMode, true, 'ZustellungTab im Anlegen ohne createMode');
	assert.equal(typeof props.onAnlegeStand, 'function', 'ZustellungTab im Anlegen ohne Rückkanal onAnlegeStand');
	const mounts: Array<() => unknown> = [];
	const t = await umgebungFuer(
		ZUSTELLUNG_TAB,
		{ ...props, panel: { ...props }, untrack: (fn: () => unknown) => fn(), onMount: (fn: () => unknown) => void mounts.push(fn), api: reiterApi() },
		{ jsAlsTs: true }
	);
	for (const stmt of t.ast.instance.content.body as Knoten[]) {
		const x = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (x?.type === 'CallExpression' && x.callee?.name === 'onMount') werte(ohneTypen(t.quelle, x), t.u);
	}
	for (const m of mounts) m();
	await new Promise((r) => setImmediate(r));
	const kt = findeKomponenten(t.ast, 'KanalTabelle')[0];
	assert.ok(kt, 'Messaufbau: KanalTabelle im Reiter fehlt');
	const kanalProps = alleAttribute(kt, t.quelle, t.u);
	assert.equal(typeof kanalProps.onaendern, 'function', 'Messaufbau: onaendern der Kanal-Tabelle nicht auswertbar');
	return {
		u: t.u,
		/** Stand, den der Reiter seinen Bausteinen zeigt. */
		stand: () => klon(alleAttribute(kt, t.quelle, t.u).stand as J),
		/** Eine Geste in der Kanal-Tabelle (bzw. Zeiten/Stille): neuer Gesamtstand an den Reiter. */
		aendern: (f: (s: J) => J) => (alleAttribute(kt, t.quelle, t.u).onaendern as (s: J) => void)(f(klon(alleAttribute(kt, t.quelle, t.u).stand as J)))
	};
}

// ── Referenz „heute“ ─────────────────────────────────────────────────────────
const ALARM_FELDER = ['alert_channels', 'alert_channel_thresholds', 'alert_quiet_from', 'alert_quiet_to', 'alert_cooldown_minutes', 'official_warnings', 'official_alerts_enabled'];
function auswahl(p: J): J {
	const r: J = { report_config: p.report_config ?? null, display_config_channels: p.display_config?.channels ?? null };
	for (const k of ALARM_FELDER) r[k] = p[k] === undefined ? '<fehlt>' : p[k];
	return klon(r);
}

/** POST-Körper des heutigen Codes ohne Bedienung: Editor + VersandTab + MailInhaltCard an `bind:reportConfig`. */
async function heutigerRumpf(): Promise<J> {
	const ed = await editor();
	const start = klon(ed.u.reportConfig);
	const versand = await editorUmgebung(VERSAND_TAB, { reportConfig: klon(start), context: 'route' });
	const mail = await editorUmgebung(MAIL_KARTE, { reportConfig: klon(start) });
	for (const fn of versand.mounts) fn();
	const ve = effekteVon(versand.ast, versand.quelle, versand.u, 'baueReportConfigPayload');
	assert.ok(ve.length >= 1, 'Messaufbau: VersandTab-Effekt nicht gefunden');
	for (const fn of ve) fn();
	mail.u.reportConfig = versand.u.reportConfig;
	for (const fn of mail.mounts) fn();
	const me = effekteVon(mail.ast, mail.quelle, mail.u, 'baueReportConfigPayload');
	assert.ok(me.length >= 1, 'Messaufbau: MailInhaltCard-Effekt nicht gefunden');
	for (const fn of me) fn();
	ed.u.reportConfig = mail.u.reportConfig;
	return auswahl(await ed.speichern());
}

function referenz(): J {
	assert.ok(fs.existsSync(FIXTURE), `Referenz-Fixture fehlt: ${FIXTURE}`);
	return JSON.parse(fs.readFileSync(FIXTURE, 'utf-8'));
}

describe('#3332 Referenz-Fixture (Messaufbau)', () => {
	test('Fixture liegt vor und trägt Versand-, Mail- und Alarm-Felder (nicht leer)', async () => {
		if (process.env.GZ_FIXTURE_SCHREIBEN === '1') {
			fs.mkdirSync(dirname(FIXTURE), { recursive: true });
			fs.writeFileSync(FIXTURE, JSON.stringify(await heutigerRumpf(), null, 2) + '\n', 'utf-8');
		}
		const ref = referenz();
		for (const f of ['morning_enabled', 'morning_time', 'evening_enabled', 'evening_time', 'send_email', 'multi_day_trend_reports', 'email_format', 'show_stability'])
			assert.ok(f in ref.report_config, `Fixture ohne report_config.${f}`);
		assert.equal(ref.alert_channels.email, true);
	});
});

describe('#3332 Test 3 (AC-4): Reiter nie bedient — POST bitgleich zu heute', () => {
	test('report_config, Alarm-Felder und display_config.channels gleichen der Referenz', async () => {
		const ed = await editor();
		assert.deepEqual(auswahl(await ed.speichern()), referenz());
	});

	test('Reiter geöffnet (Desktop und Mobil gebaut, Profil geladen), aber nicht bedient: POST unverändert, keine Meldung nötig', async () => {
		const ed = await editor();
		await reiter(ed, 0);
		await reiter(ed, 1);
		assert.deepEqual(auswahl(await ed.speichern()), referenz());
	});

	test('Startstand des Reiters = was der POST ohne Bedienung sendet (Zeiten, Kanäle, Alarm-Kanäle, Dringlichkeit, Stille)', async () => {
		const ref = referenz();
		const rc = ref.report_config;
		const s = (await reiter(await editor(), 0)).stand();
		assert.equal(s.morgenAn, rc.morning_enabled, 'Morgen-Schalter');
		assert.equal(s.abendAn, rc.evening_enabled, 'Abend-Schalter');
		assert.equal(s.morgenZeit, String(rc.morning_time).slice(0, 5));
		assert.equal(s.abendZeit, String(rc.evening_time).slice(0, 5));
		for (const k of ['email', 'telegram', 'sms', 'premium_sms']) {
			assert.equal(s.briefing[k], rc[`send_${k}`] === true, `Briefing-Kanal ${k}`);
			assert.equal(s.alarme[k], ref.alert_channels[k], `Alarm-Kanal ${k}`);
			assert.equal(s.dringlichkeit[k], ref.alert_channel_thresholds[k], `Dringlichkeit ${k}`);
		}
		assert.equal(s.stilleAn, ref.alert_quiet_from !== null, 'Stille Stunden');
	});
});

describe('#3332 AC-10: Mail-Inhalt ohne MailInhaltCard — Karte „Was steht wo“ wirkt, Bestandsfelder behalten den Standard', () => {
	const START_FELDER = { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', hourly_enabled: true };
	test('Karte nicht bedient: E-Mail-Format, Etappen-Statistik, Vortagesvergleich, Großwetterlage wie heute', async () => {
		const ref = referenz().report_config;
		const p = await (await editor()).speichern();
		for (const f of ['email_format', 'show_stage_stats', 'show_yesterday_comparison', 'show_stability', 'show_compact_summary', 'show_highlights', 'daily_summary_metrics'])
			assert.deepEqual(p.report_config[f], ref[f], `report_config.${f} weicht vom heutigen Körper ab`);
	});

	test('Karte bedient (Kompakt, Etappen-Statistik aus, Nacht-Block aus): genau diese Werte, show_stability bleibt Standard', async () => {
		const ref = referenz().report_config;
		const ed = await editor();
		ed.u.karteStand = {
			placements: { version: 1, rows: [{ metric_id: 'wind' }] },
			felder: { ...START_FELDER, email_format: 'compact', show_stage_stats: false, show_night_block: false },
			felderStart: { ...START_FELDER }
		};
		const p = await ed.speichern();
		assert.equal(p.report_config.email_format, 'compact', 'E-Mail-Format der Karte wirkt nicht');
		assert.equal(p.report_config.show_stage_stats, false);
		assert.equal(p.display_config.show_night_block, false);
		assert.equal(p.report_config.show_stability, ref.show_stability, 'Großwetterlage nicht auf dem Standard');
		assert.equal(p.report_config.show_yesterday_comparison, ref.show_yesterday_comparison);
	});
});

const BEDIENT = (s: J): J => ({
	...s,
	morgenZeit: '06:45',
	abendAn: false,
	briefing: { ...s.briefing, telegram: true, sms: true },
	alarme: { ...s.alarme, sms: true },
	dringlichkeit: { ...s.dringlichkeit, telegram: 'HIGH' },
	stilleAn: true,
	stilleVon: '22:30',
	stilleBis: '06:15',
	cooldown: 45
});

describe('#3332 Test 2 (AC-2, AC-3, AC-5): Bedienung im Reiter -> genau der eine POST trägt sie', () => {
	test('Zeiten, Kanäle, Dringlichkeit HIGH, Stille, Cooldown stehen im POST; kein PUT, kein Schreibaufruf', async () => {
		const ed = await editor();
		ed.u.reportConfig = { day_window_start_hour: 4, day_window_end_hour: 19 }; // Bericht des Reiters Wetter
		const r = await reiter(ed, 0);
		r.aendern(BEDIENT);
		assert.deepEqual(netz.filter((x) => x.methode !== 'GET'), [], 'AC-5: Schreibaufruf vor dem Anlegen');
		const p = await ed.speichern();
		const rc = p.report_config;
		assert.equal(rc.morning_time, '06:45:00', 'AC-2: Morgen-Zeit');
		assert.equal(rc.morning_enabled, true);
		assert.equal(rc.evening_enabled, false, 'AC-2: Abend-Schalter');
		assert.equal(rc.enabled, true, 'Gesamtschalter folgt den Slots');
		assert.equal(rc.send_email, true);
		assert.equal(rc.send_telegram, true, 'AC-2: Briefing-Kanal Telegram');
		assert.equal(rc.send_sms, true, 'AC-2: Briefing-Kanal SMS');
		assert.equal(rc.send_premium_sms, false);
		assert.deepEqual(rc.multi_day_trend_reports, ['morning'], '3-Tages-Ausblick folgt den eingestellten Briefings (nur Morgen an, #3155)');
		assert.equal(rc.day_window_start_hour, 4, 'Read-Modify-Write: Tagesfenster des Reiters Wetter verloren');
		assert.equal(rc.day_window_end_hour, 19);
		assert.equal(p.alert_channels.sms, true, 'AC-3: Alarm-Kanal SMS');
		assert.equal(p.alert_channels.email, true);
		assert.equal(p.alert_channel_thresholds.telegram, 'HIGH', 'AC-3: Dringlichkeit Telegram');
		assert.equal(p.alert_quiet_from, '22:30', 'AC-2: Stille von');
		assert.equal(p.alert_quiet_to, '06:15', 'AC-2: Stille bis');
		assert.equal(p.alert_cooldown_minutes, 45, 'AC-3: Cooldown');
		assert.equal(p.official_warnings?.enabled, true, 'amtliche Warnungen unverändert');
		assert.deepEqual(netz.filter((x) => x.methode !== 'GET'), [], 'AC-5: Schreibaufruf des Reiters');
		assert.deepEqual(netz.filter((x) => x.methode === 'GET').map((x) => x.pfad), ['/api/auth/profile'], 'nur der eine Profil-Abruf');
	});

	test('Stille Stunden wieder aus: POST ohne Stille (null), Rest bleibt', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern(BEDIENT);
		r.aendern((s) => ({ ...s, stilleAn: false }));
		const p = await ed.speichern();
		assert.equal(p.alert_quiet_from, null);
		assert.equal(p.alert_quiet_to, null);
		assert.equal(p.report_config.morning_time, '06:45:00');
	});
});

describe('#3332 Test 4 (AC-7): rasterfremde Uhrzeit — der POST trägt die letzte gültige', () => {
	test('06:45, dann 06:50 eingegeben: POST morning_time 06:45:00', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern((s) => ({ ...s, morgenZeit: '06:45' }));
		r.aendern((s) => ({ ...s, morgenZeit: '06:50' }));
		const p = await ed.speichern();
		assert.equal(p.report_config.morning_time, '06:45:00', 'letzte gültige Zeit nicht im POST');
	});

	test('nur 06:50 eingegeben: POST behält die Startzeit, nie 06:50', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern((s) => ({ ...s, morgenZeit: '06:50', cooldown: 30 }));
		const p = await ed.speichern();
		assert.equal(p.report_config.morning_time, referenz().report_config.morning_time);
		assert.ok(!JSON.stringify(p).includes('06:50'), 'rasterfremde Uhrzeit im POST (Server antwortet 400)');
		assert.equal(p.alert_cooldown_minutes, 30, 'gültige Änderung derselben Geste geht verloren');
	});
});

describe('#3332 Test 7 (AC-6): Neuaufbau (Wechsel Desktop <-> Mobil, Schritte) behält den Stand', () => {
	for (const [von, nach, name] of [[0, 1, 'Desktop -> Mobil'], [1, 0, 'Mobil -> Desktop'], [0, 0, 'Desktop neu aufgebaut']] as const) {
		test(name, async () => {
			const ed = await editor();
			const r1 = await reiter(ed, von);
			r1.aendern(BEDIENT);
			const erwartet = r1.stand();
			const r2 = await reiter(ed, nach);
			assert.deepEqual(r2.stand(), erwartet, 'neu aufgebauter Reiter fällt auf die Standardwerte zurück');
			// Eine Geste nach dem Neuaufbau verliert die frühere nicht.
			r2.aendern((s) => ({ ...s, cooldown: 90 }));
			const p = await ed.speichern();
			assert.equal(p.report_config.morning_time, '06:45:00', 'Änderung vor dem Neuaufbau fehlt im POST');
			assert.equal(p.alert_channel_thresholds.telegram, 'HIGH');
			assert.equal(p.alert_cooldown_minutes, 90);
		});
	}
});
