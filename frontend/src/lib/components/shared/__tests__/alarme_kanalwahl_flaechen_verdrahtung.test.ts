// #1895 S3b1 Fix-Loop 1 (Adversary F002/F003/F005): der Weg Block → AlarmeTab → Editor → Nutzlast
// auf allen vier Flächen, ohne DOM über den svelteInstanzPruefstand. Ausgewertet werden die ECHTEN
// Einbettungs-Ausdrücke (onChange, premiumSmsGate, onAlertMetricChannelChange, {...alarmePropsAus(wiz)})
// und die echten Funktionen/Effekte der Komponenten — kein Quelltext-Grep, keine Attrappe des Wegs.
// Spec alert_metric_channels.md AC-43/45/46/51/53/54/55.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { register } from 'node:module';
import { parse } from 'svelte/compiler';
import { KANAELE, baueDiff, ladeKanalSchluessel, _resetKanalSchluesselCache } from '../alarme-tab/alertMetricChannels.ts';
import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';
import type { ComparePreset } from '../../../types.ts';
import { alarmSnapshotAus, baueAlarmNutzlast } from '../alarmeVergleichSpeicherung.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { buildNewComparePresetPayload, compareFeldsatzStandard } from '../../compare/compareEditorSave.ts';
import { buildCreateTripPayload, initialCreateTripAlarmState } from '../../trip-new/tripNewLogic.ts';
import { derivePremiumSmsAlarmGate } from '../alarme-tab/premiumSmsAlarmGate.ts';
import { umgebungFuer, effekteVon, findeKomponenten, attributAusdruck, werte, ohneTypen, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TAB = join(HIER, '..', 'AlarmeTab.svelte');
const BLOCK = join(HIER, '..', '..', 'alerts-tab', 'AlertMetricChannelsBlock.svelte');
const TRIPNEW = join(HIER, '..', '..', 'trip-new', 'TripNewEditor.svelte');
const ANLEGE = join(HIER, '..', '..', 'compare-new', 'CompareNewEditor.svelte');
const TG = { email: false, telegram: true, sms: false, premium_sms: false };
const MAIL = { email: true, telegram: false, sms: false, premium_sms: false };
const AUS = { email: false, telegram: false, sms: false, premium_sms: false };
const untrack = (fn: () => unknown) => fn();
const KATALOG = join(HIER, '..', 'weather-metrics-tab', '__tests__', 'fixtures', 'f5_compare_metrics.json');
const FRONTEND = join(HIER, '..', '..', '..', '..', '..');
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

/** AlarmeTab mit Saat; liefert den ausgewerteten onChange-Ausdruck der EINEN Block-Einbettung. */
async function tab(saat: Knoten) {
	const env = await umgebungFuer(TAB, { untrack, profileOverride: { premium_sms_allowed: false }, metricLevels: {},
		existingChannels: null, existingChannelThresholds: null, createMode: undefined, activeMetricKeys: undefined, ...saat });
	const block = findeKomponenten(env.ast, 'AlertMetricChannelsBlock');
	assert.strictEqual(block.length, 1, 'AlarmeTab bettet den Block nicht genau einmal ein');
	const attr = (name: string) => werte(attributAusdruck(block[0], env.quelle, name)!, env.u);
	return { ...env, attr, onChange: attr('onChange') as (k: string, e: unknown) => void };
}
const vergleichSaat = (z: Knoten) => ({ context: 'vergleich', trip: undefined, catalog: [], ...alarmePropsAus(z) });
function preset(amc: Record<string, unknown>): ComparePreset {
	return { id: 'cmp-1', name: 'V', location_ids: ['a', 'b', 'c'], display_config: {}, alert_channels: MAIL,
		official_warnings: { enabled: false }, alert_metric_channels: amc } as unknown as ComparePreset;
}
/** Die Einbettungen von AlarmeTab in einer Editor-Datei. */
function einbettungen(datei: string) {
	const quelle = readFileSync(datei, 'utf-8');
	return { quelle, treffer: findeKomponenten(parse(quelle, { modern: true }), 'AlarmeTab') };
}

test('AC-46/AC-54 Trip-Hub (Ablauf): speichern, Trip-Prop zieht nach, zurück auf „wie Abo" ⇒ {thunder: null}', async () => {
	const gebaut: unknown[][] = [];
	const t = await tab({ context: 'route', trip: { id: 't-1', display_config: {} }, existingAlertMetricChannels: {},
		activeMetrics: ['thunder_level'], baueTripSpeicherung: (...a: unknown[]) => (gebaut.push(a), async () => {}),
		saveController: { schedule: () => {} } });
	const effekte = effekteVon(t.ast, t.quelle, t.u, 'routeAlertMetricChannels');
	const speichern = () => effekte.forEach((e) => e());
	t.onChange('thunder', TG);
	speichern();
	assert.deepStrictEqual((gebaut.at(-1)?.[2] as Knoten).alert_metric_channels, { thunder: TG });
	t.u.existingAlertMetricChannels = { thunder: TG }; // onTripUpdate ⇒ der Hub reicht den neuen Trip durch
	t.onChange('thunder', null);
	speichern();
	assert.deepStrictEqual((gebaut.at(-1)?.[2] as Knoten).alert_metric_channels, { thunder: null },
		'der Rückweg muss gegen den gespeicherten Stand diffen, nicht gegen den Stand beim Laden');
});

test('AC-54 Trip-Hub (F002 R5): bloßes Öffnen des Reiters speichert nicht — Mount-Lauf des Dirty-Effekts, mit und ohne Bestand', async () => {
	for (const bestand of [undefined, {}, { thunder: TG }]) {
		const gebaut: unknown[][] = [];
		const geplant: unknown[] = [];
		const t = await tab({ context: 'route', trip: { id: 't-1', display_config: {} }, existingAlertMetricChannels: bestand,
			activeMetrics: ['thunder_level'], baueTripSpeicherung: (...a: unknown[]) => (gebaut.push(a), async () => {}),
			saveController: { schedule: (fn: unknown) => geplant.push(fn) } });
		const effekte = effekteVon(t.ast, t.quelle, t.u, 'routeAlertMetricChannels');
		assert.ok(effekte.length > 0, 'Messaufbau: kein Dirty-Effekt registriert');
		effekte.forEach((e) => e()); // Mount-Lauf, ohne jede Nutzeränderung
		assert.deepStrictEqual([geplant.length, gebaut.length], [0, 0], `Bestand ${JSON.stringify(bestand)}: Öffnen löst Speichern aus`);
	}
});

test('AC-55 Ortsvergleich-Hub: Block-onChange erreicht den Zustand und die Alarm-Nutzlast', async () => {
	const p = preset({ snowfall_limit: MAIL });
	const z: Knoten = {};
	hydrateAlarmFieldsFromPreset(z, p, []);
	const t = await tab(vergleichSaat(z));
	t.onChange('thunder', TG);
	assert.deepStrictEqual(z.alertMetricChannels, { snowfall_limit: MAIL, thunder: TG }, 'Wahl landet nicht im Zustand');
	assert.deepStrictEqual((baueAlarmNutzlast(p, alarmSnapshotAus(z)).body as Knoten).alert_metric_channels, { thunder: TG });
});

test('AC-53 am Nutzerweg: AlarmeTab reicht das Premium-SMS-Gate des Profils an den Block', async () => {
	for (const [erlaubt, gesperrt] of [[false, true], [true, false]] as const) {
		const t = await tab({ context: 'route', trip: { id: 't-1' }, existingAlertMetricChannels: {}, activeMetrics: [],
			profileOverride: { premium_sms_allowed: erlaubt } });
		const gate = t.attr('premiumSmsGate') as { disabled: boolean; hint: string | null };
		assert.deepStrictEqual(gate, derivePremiumSmsAlarmGate({ premium_sms_allowed: erlaubt }));
		assert.strictEqual(gate.disabled, gesperrt, `premium_sms_allowed=${erlaubt}`);
	}
});

test('AC-54 Trip-Anlegen: beide Einbettungen (Desktop, Mobil) tragen die Wahl in den Anlege-Payload', async () => {
	const { quelle, treffer } = einbettungen(TRIPNEW);
	assert.strictEqual(treffer.length, 2, 'erwartet Desktop- und Mobil-Einbettung');
	const editor = await umgebungFuer(TRIPNEW, { untrack });
	for (const einbettung of treffer) {
		editor.u.alarm = initialCreateTripAlarmState();
		const ausdruck = attributAusdruck(einbettung, quelle, 'onAlertMetricChannelChange');
		assert.ok(ausdruck, 'Einbettung ohne onAlertMetricChannelChange');
		const t = await tab({ context: 'route', trip: { id: 'stub' }, createMode: true, activeMetrics: ['thunder_level'],
			onAlertMetricChannelChange: werte(ausdruck!, editor.u) });
		t.onChange('thunder', TG);
		const trip = buildCreateTripPayload({ name: 'T', startDate: '2026-11-03', stages: [{ id: 1, name: 'E1' }],
			channels: { email: true, telegram: false, sms: false }, alarm: editor.u.alarm } as never) as unknown as Knoten;
		assert.deepStrictEqual(trip.alert_metric_channels, { thunder: TG });
	}
});

test('AC-54 Trip-Anlegen (F002): zwei Wahlen nacheinander — beide Einbettungen behalten beide im Anlege-Payload', async () => {
	const { quelle, treffer } = einbettungen(TRIPNEW);
	assert.strictEqual(treffer.length, 2, 'erwartet Desktop- und Mobil-Einbettung');
	const editor = await umgebungFuer(TRIPNEW, { untrack });
	for (const einbettung of treffer) {
		editor.u.alarm = initialCreateTripAlarmState();
		const t = await tab({ context: 'route', trip: { id: 'stub' }, createMode: true, activeMetrics: ['thunder_level', 'wind_gust'],
			onAlertMetricChannelChange: werte(attributAusdruck(einbettung, quelle, 'onAlertMetricChannelChange')!, editor.u) });
		t.onChange('thunder', TG);
		t.onChange('gust', MAIL);
		const trip = buildCreateTripPayload({ name: 'T', startDate: '2026-11-03', stages: [{ id: 1, name: 'E1' }],
			channels: { email: true, telegram: false, sms: false }, alarm: editor.u.alarm } as never) as unknown as Knoten;
		assert.deepStrictEqual(trip.alert_metric_channels, { thunder: TG, gust: MAIL }, 'die erste Wahl darf die zweite nicht überschreiben');
	}
});

test('AC-55 Ortsvergleich-Anlegen: Block → {...alarmePropsAus(wiz)} → POST trägt die Wahl', async () => {
	const { quelle, treffer } = einbettungen(ANLEGE);
	assert.ok(treffer.length >= 1, 'keine AlarmeTab-Einbettung in CompareNewEditor');
	for (const einbettung of treffer) {
		const gepostet: Knoten[] = [];
		const editor = await umgebungFuer(ANLEGE, { untrack, wiz: { ...compareFeldsatzStandard(), name: 'Neu', pickedIds: ['a', 'b'] },
			api: { post: async (_u: string, b: Knoten) => (gepostet.push(b), { id: 'n' }) }, goto: async () => {} });
		const spread = (einbettung.attributes as Knoten[]).find((a) => a.type === 'SpreadAttribute');
		const buendel = werte(quelle.slice(spread!.expression.start, spread!.expression.end), editor.u) as Knoten;
		const t = await tab({ context: 'vergleich', trip: undefined, catalog: [], ...buendel });
		t.onChange('thunder', TG);
		await (editor.u.speichereNeuenVergleich as () => Promise<void>)();
		assert.deepStrictEqual(gepostet[0]?.alert_metric_channels, { thunder: TG });
	}
});

/** Saat aus den ECHTEN Attributen einer Einbettung, ausgewertet in der Umgebung des Elternteils. */
function saatAus(einbettung: Knoten, quelle: string, u: Knoten): Knoten {
	const saat: Knoten = {};
	for (const a of einbettung.attributes as Knoten[]) {
		if (a.type !== 'Attribute') continue;
		const text = Array.isArray(a.value) && a.value[0]?.type === 'Text' ? a.value[0].data : null;
		saat[a.name] = text ?? werte(attributAusdruck(einbettung, quelle, a.name)!, u);
	}
	return saat;
}

/** Gemessene Endpunkt-Antwort (Auszug, S3a) für die Zeilen des Blocks. */
const SCHLUESSEL = { keys: { thunder_level: ['thunder'], wind_gust: ['gust'] }, accepted: ['gust', 'thunder', 'wind'] };
/** Rendert den Block (SSR) mit den Props, die AlarmeTab an der ECHTEN Einbettung übergibt.
 *  Liefert je Zeile die angehakten Kanäle. */
async function blockAusTab(t: Awaited<ReturnType<typeof tab>>): Promise<Record<string, string[]>> {
	const { render } = await import('svelte/server');
	const Block = (await import(pathToFileURL(BLOCK).href)).default;
	const props = Object.fromEntries(['aktiveMetriken', 'eintraege', 'aboKanaele', 'premiumSmsGate', 'onChange'].map((n) => [n, t.attr(n)]));
	assert.ok((props.aktiveMetriken as unknown[]).length > 0, 'Messaufbau: AlarmeTab reicht keine aktiven Alarm-Zeilen durch');
	const h = render(Block, { props: { ...props, schluesselOverride: SCHLUESSEL } }).body;
	const zeilen: Record<string, string[]> = {};
	for (const m of h.matchAll(/data-testid="kanal-zeile-([a-z_]+)"/g)) zeilen[m[1]] = [];
	for (const m of h.matchAll(/data-testid="kanal-schalter-([a-z_]+?)-(email|telegram|sms|premium_sms)"[^]*?<input([^>]*)>/g))
		if (/\schecked/.test(m[3])) zeilen[m[1]].push(m[2]);
	return zeilen;
}

test('AC-55 Anzeige Ortsvergleich: aktive Alarm-Zeilen erscheinen im Block mit gespeichertem Stand und Abo-Satz', async () => {
	const p = preset({ thunder: TG });
	(p as unknown as Knoten).alert_channels = { email: false, telegram: false, sms: true, premium_sms: false };
	const katalog = toCompareSelectionEntries(JSON.parse(readFileSync(KATALOG, 'utf-8')) as never) as unknown as Knoten[];
	const z: Knoten = {};
	hydrateAlarmFieldsFromPreset(z, p, katalog as never);
	z.activeMetricKeys = ['thunder_level_max', 'gust_max_kmh'];
	const t = await tab({ ...vergleichSaat(z), catalog: katalog });
	assert.deepStrictEqual(await blockAusTab(t), { gust: [], thunder: ['telegram'] }, 'nach dem Neuladen muss die Wahl sichtbar sein');
	assert.deepStrictEqual(t.attr('aboKanaele'), { email: false, telegram: false, sms: true, premium_sms: false });
});

test('AC-43/AC-51 Anzeige Trip-Hub: AlarmeScheduleTab → AlarmeTab → Block zeigt gespeicherte Wahl und Abo-Satz', async () => {
	const trip = { id: 't-1', display_config: {}, alert_channels: { email: false, telegram: false, sms: true, premium_sms: false },
		alert_metric_channels: { thunder: TG } };
	const halter = join(HIER, '..', '..', 'trip-detail', 'AlarmeScheduleTab.svelte');
	const { quelle, treffer } = einbettungen(halter);
	// `metricLevels` gesät: ohneTypen() schneidet bei `(x) as T` die schließende Klammer mit ab (Prüfstand-Grenze).
	// `activeMetrics` gesät: die Herleitung aus dem Trip-Katalog ist nicht Gegenstand (eigene Tests #1544/#1545).
	const eltern = await umgebungFuer(halter, { trip, metricsCatalog: null, onTripUpdate: undefined, saveController: undefined,
		metricLevels: {}, activeMetrics: ['thunder_level', 'wind_gust'] });
	const t = await tab(saatAus(treffer[0], quelle, eltern.u));
	assert.deepStrictEqual(await blockAusTab(t), { gust: [], thunder: ['telegram'] }, 'Trip-Hub zeigt die gespeicherte Wahl nicht');
	assert.deepStrictEqual(t.attr('aboKanaele'), trip.alert_channels, 'Vorbelegung/Hinweis brauchen den echten Abo-Satz');
});

/** Wertet die `$derived`-Deklaration `name` der Komponente neu aus (der Prüfstand rechnet sie sonst nur einmal). */
function neuHerleiten(env: { ast: Knoten; quelle: string; u: Knoten }, name: string): void {
	for (const stmt of env.ast.instance.content.body as Knoten[])
		for (const d of (stmt.type === 'VariableDeclaration' ? stmt.declarations : []) as Knoten[])
			if (d.id?.name === name) return void (env.u[name] = werte(ohneTypen(env.quelle, d.init), env.u));
	assert.fail(`Deklaration ${name} fehlt`);
}

test('AC-43/AC-54 Trip-Hub (F002): Bestandszeile plus neue Zeile — Anzeige zeigt beide, Payload nur die neue', async () => {
	const gebaut: unknown[][] = [];
	const t = await tab({ context: 'route', trip: { id: 't-1', display_config: {} }, existingAlertMetricChannels: { thunder: TG },
		activeMetrics: ['thunder_level', 'wind_gust'], baueTripSpeicherung: (...a: unknown[]) => (gebaut.push(a), async () => {}),
		saveController: { schedule: () => {} } });
	const effekte = effekteVon(t.ast, t.quelle, t.u, 'routeAlertMetricChannels');
	t.onChange('gust', MAIL);
	effekte.forEach((e) => e());
	assert.deepStrictEqual((gebaut.at(-1)?.[2] as Knoten).alert_metric_channels, { gust: MAIL }, 'nur der Diff, nie der Bestand');
	neuHerleiten(t, 'displayAlertMetricChannels');
	assert.deepStrictEqual(await blockAusTab(t), { gust: ['email'], thunder: ['telegram'] }, 'die Bestandszeile darf nicht verschwinden');
});

test('AC-54 Trip-Hub (F002): zwei neue Wahlen nacheinander — beide stehen im Payload', async () => {
	const gebaut: unknown[][] = [];
	const t = await tab({ context: 'route', trip: { id: 't-1', display_config: {} }, existingAlertMetricChannels: {},
		activeMetrics: ['thunder_level', 'wind_gust'], baueTripSpeicherung: (...a: unknown[]) => (gebaut.push(a), async () => {}),
		saveController: { schedule: () => {} } });
	const effekte = effekteVon(t.ast, t.quelle, t.u, 'routeAlertMetricChannels');
	t.onChange('thunder', TG);
	t.onChange('gust', MAIL);
	effekte.forEach((e) => e());
	assert.deepStrictEqual((gebaut.at(-1)?.[2] as Knoten).alert_metric_channels, { thunder: TG, gust: MAIL });
});

test('AC-41/AC-49 Block lädt die Schlüssel beim Mounten selbst (F001): onMount ruft den Abruf, Antwort landet im Zustand', async () => {
	const antwort = { keys: { thunder_level: ['thunder'] }, accepted: ['thunder'] };
	const echtesFetch = globalThis.fetch;
	const urls: string[] = [];
	globalThis.fetch = (async (url: string) => (urls.push(url), new Response(JSON.stringify(antwort)))) as typeof fetch;
	try {
		_resetKanalSchluesselCache();
		const beimMounten: Array<() => void> = [];
		const env = await umgebungFuer(BLOCK, { untrack, onMount: (fn: () => void) => beimMounten.push(fn), schluesselOverride: undefined,
			aktiveMetriken: ['thunder_level'], eintraege: {}, aboKanaele: TG, onChange: () => {},
			premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: true }) });
		for (const stmt of env.ast.instance.content.body as Knoten[])
			if (stmt.type === 'ExpressionStatement' && stmt.expression.callee?.name === 'onMount') werte(ohneTypen(env.quelle, stmt.expression), env.u);
		assert.strictEqual(beimMounten.length, 1, 'der Block registriert keinen onMount-Rückruf');
		assert.strictEqual(env.u.antwort, undefined, 'vor dem Mounten: lädt');
		beimMounten[0]();
		await ladeKanalSchluessel();
		assert.deepStrictEqual(urls, ['/api/alert-metric-channel-keys'], 'ohne Override muss der Block den Endpunkt abrufen');
		assert.deepStrictEqual(env.u.antwort, antwort, 'die Antwort muss den Zustand des Blocks erreichen');
	} finally {
		globalThis.fetch = echtesFetch;
		_resetKanalSchluesselCache();
	}
});

test('AC-43 Anzeige Block: gewählte Kanäle stehen als angehakt im Markup, andere nicht', async () => {
	const { render } = await import('svelte/server');
	const Block = (await import(pathToFileURL(BLOCK).href)).default;
	const h = render(Block, { props: { aktiveMetriken: ['thunder_level'], eintraege: { thunder: TG }, aboKanaele: TG,
		premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: true }), onChange: () => {},
		schluesselOverride: { keys: { thunder_level: ['thunder'] }, accepted: ['thunder'] } } }).body;
	const schalter = (k: string) => {
		const i = h.indexOf(`data-testid="kanal-schalter-thunder-${k}"`);
		assert.notEqual(i, -1, `Schalter ${k} fehlt`);
		return /<input[^>]*\schecked/.test(h.slice(i, h.indexOf('</div>', i)));
	};
	assert.deepStrictEqual(KANAELE.map(schalter), [false, true, false, false], 'email, telegram, sms, premium_sms');
});

test('AC-42/AC-47 Anlegen: beide Anlege-Nutzlasten senden nur den Diff (kein null-Eintrag, immer vier Flags)', () => {
	const wahl = { thunder: { telegram: true }, gust: null } as never;
	const trip = buildCreateTripPayload({ name: 'T', startDate: '2026-11-03', stages: [{ id: 1, name: 'E1' }],
		channels: { email: true, telegram: false, sms: false }, alarm: { ...initialCreateTripAlarmState(), metricChannels: wahl } } as never) as unknown as Knoten;
	assert.deepStrictEqual(trip.alert_metric_channels, { thunder: TG }, 'Trip');
	const neu = buildNewComparePresetPayload({ ...compareFeldsatzStandard(), name: 'N', pickedIds: ['a', 'b'], alertMetricChannels: wahl } as never);
	assert.deepStrictEqual(neu.alert_metric_channels, { thunder: TG }, 'Vergleich');
});

test('baueDiff: ein Eintrag ohne Kanal im Bestand ist nicht „erbt" — Rückweg auf null wird gesendet', () => {
	assert.deepStrictEqual(baueDiff({ thunder: AUS }, { thunder: null }), { thunder: null });
	assert.deepStrictEqual(baueDiff({ thunder: null }, { thunder: AUS as never }), { thunder: null });
});

test('AC-51/E5 leerer Abo-Satz: „eigene Wahl" bleibt offen, gespeichert wird erst mit einem Kanal', async () => {
	const rufe: unknown[][] = [];
	const { u } = await umgebungFuer(BLOCK, { aktiveMetriken: ['thunder_level'], eintraege: {}, aboKanaele: AUS,
		premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: true }), onChange: (...a: unknown[]) => rufe.push(a) });
	u.eigeneWahl('thunder', true);
	assert.deepStrictEqual(rufe, [], 'ohne gewählten Kanal wird nichts (auch kein {}) gespeichert');
	assert.strictEqual(u.schalterSichtbar('thunder'), true, 'die vier Kanal-Schalter müssen sichtbar bleiben');
	u.kanalSetzen('thunder', 'telegram', true);
	assert.deepStrictEqual(rufe, [['thunder', TG]], 'Telegram ausserhalb des Abo-Satzes wird gespeichert (AC-51)');
	u.eigeneWahl('thunder', false);
	assert.strictEqual(u.schalterSichtbar('thunder'), false);
	assert.deepStrictEqual(rufe.at(-1), ['thunder', null], 'Rückweg erbt wieder');
});
