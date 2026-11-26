// Gemeinsamer Pruefstand der Mehrreiter-Tests auf der Trip-Seite (Issue #1433,
// Spec docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md). KEINE Testdatei
// (kein `.test.ts`) — nur Aufbauhilfen.
//
// Prinzip (wie compare_kopf_nutzlast_teilfeld.test.ts): die Zusicherung wirkt
// dort, wo sie wirkt. Gemessen wird deshalb
//   - mit den ECHTEN Instanz-Skripten der Reiter (`umgebungFuer`, AST-Auswertung
//     der .svelte-Dateien) und ihren echten Handlern/Effekten,
//   - ueber das ECHTE `api` (Registry, Warteschlange, If-Match) und eine ECHTE
//     `SaveStatus`-Instanz,
//   - gegen den Ersatz-Server im Merge-Modus (`fakeTripServer.ts`, Go-Semantik),
//   - und gelesen wird der SERVER-STAND nach dem Zusammenspiel mehrerer Schreiber.
//
// Importiert bewusst KEINEN der neuen Exporte der Spec (pickEigenfelder,
// markiereKonflikt, meldeKonflikt …): der Pruefstand muss HEUTE laden, damit das
// Rot der Tests an der Zusicherung liegt und nicht am Aufbau.
//
// Pfadregel #1409: Aufrufer loesen Dateipfade relativ zur EIGENEN Testdatei auf.
//
// Issue #2284 S2 (AC-17): Kopf (Name, NEU Region) und Aktivitaet laufen ueber
// `TripHeader.onSaveField` — Schnittstelle siehe `kopfReiter` weiter unten.

import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { parse } from 'svelte/compiler';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { api } from '../../../api.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import type { ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';
import { aufloesungPost, live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import {
	findeKomponenten,
	ohneTypen,
	werte,
	umgebungFuer,
	effekteVon,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
export const FRONTEND = resolve(HIER, '../../../../..');
const KOMPONENTEN = join(FRONTEND, 'src/lib/components');

export const DATEI = {
	alarme: join(KOMPONENTEN, 'shared/AlarmeTab.svelte'),
	// #3020: lebende Reiter Wetter (samt Karte „Was steht wo“) und Zustellung.
	wetter: join(KOMPONENTEN, 'organisms/wetter-tab/WetterTabInhalt.svelte'),
	karte: join(KOMPONENTEN, 'organisms/wetter-tab/WasStehtWoKarte.svelte'),
	zustellung: join(KOMPONENTEN, 'shared/zustellung-tab/ZustellungTab.svelte'),
	kopf: join(KOMPONENTEN, 'trip-detail/TripHeader.svelte'),
	tabs: join(KOMPONENTEN, 'trip-detail/TripTabs.svelte'),
	etappen: join(KOMPONENTEN, 'edit/EditStagesPanelNew.svelte'),
	seite: join(FRONTEND, 'src/routes/trips/[id]/+page.svelte')
} as const;

// `$lib/x.js`-Importe der Komponenten (SvelteKit-Konvention) auf die .ts-Dateien
// aufloesen — sonst fehlt `api` in der Umgebung und der Test scheitert am Aufbau.
let hooksRegistriert = false;
export function registriereHooks(): void {
	if (hooksRegistriert) return;
	hooksRegistriert = true;
	register(
		pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
		pathToFileURL(FRONTEND + '/').href
	);
}

export const TRIP_ID = 't-1433';
export const TRIP_PFAD = `/api/trips/${TRIP_ID}`;

/**
 * Ein Trip, in dem JEDER Schluessel der Feld-Eigentuemer-Tabelle (Spec §2) mit
 * einem unterscheidbaren Wert belegt ist — auch die Python-eigenen und die ohne
 * Reiter-Eigentuemer. Nur so faellt ein Fremdfeld im PUT-Rumpf auf: fehlte z. B.
 * `skip_next` im lokalen Altstand, schickte auch die heutige Vollkopie es nicht,
 * und ein Test auf dessen Erhalt wuerde nichts beweisen.
 */
export function vollerTrip(id = TRIP_ID): Record<string, unknown> {
	return {
		id,
		name: 'Trip 1433',
		activity: 'trekking',
		// #3196: Go liefert tempo immer (gespeichert oder aus activity abgeleitet).
		tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 },
		region: 'Korsika',
		stages: [
			{
				id: 'T1',
				name: 'Etappe 1',
				date: '2026-10-10',
				waypoints: [{ id: 'G1', name: 'Start', lat: 42.1, lon: 9.1, elevation_m: 100 }]
			}
		],
		corridors: [{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true }],
		official_warnings: { enabled: true, sources: ['meteoalarm'] },
		official_alerts_enabled: true,
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'HIGH' },
		display_config: {
			// Eigentuemer Alarme
			metric_alert_levels: { wind_max_kmh: 'standard', precipitation: 'sensibel' },
			// Eigentuemer Wetter-Metriken
			metrics: [
				{ metric_id: 'temperature', enabled: true, aggregations: ['min', 'max'] },
				{ metric_id: 'wind', enabled: true, aggregations: ['max'] }
			],
			channel_layouts: { email: [{ metric_id: 'temperature', enabled: true, order: 0, bucket: 'primary' }] },
			preset_name: 'wandern',
			telegram_kurzform: false,
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true },
			// kein Reiter-Eigentuemer (Python-eigen / Spread-Altlast)
			channel_layouts_per_report: { morning: { email: ['temperature'] } },
			show_night_block: true,
			night_interval_hours: 2,
			thunder_forecast_days: 2,
			sms_metrics: ['wind'],
			multi_day_trend_reports: ['evening'],
			alert_preset: 'standard',
			trip_id: id,
			updated_at: '2026-10-01T08:00:00Z'
		},
		report_config: {
			// Eigentuemer Versand
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00',
			multi_day_trend_morning: false,
			multi_day_trend_evening: true,
			multi_day_trend_reports: ['evening'],
			send_email: true,
			send_telegram: true,
			send_sms: false,
			send_premium_sms: false,
			telegram_style: 'rich',
			// Eigentuemer Wetter-Metriken (Inhalt + Tagesfenster)
			show_compact_summary: true,
			wind_exposition_min_elevation_m: 1500,
			show_stage_stats: true,
			show_metrics_summary: true,
			show_outlook: true,
			email_format: 'full',
			show_yesterday_comparison: false,
			day_window_start_hour: 5,
			day_window_end_hour: 18,
			// unklarer Eigentuemer (UI seit #723 entfernt)
			show_quick_take_tags: true,
			show_stability: true,
			show_highlights: true,
			daily_summary_metrics: ['temperature'],
			alert_on_changes: true,
			// kein Reiter-Eigentuemer (Legacy/Python)
			change_threshold_temp_c: 5,
			change_threshold_wind_kmh: 20,
			change_threshold_precip_mm: 3,
			trip_id: id,
			// Python-eigen, nie vom Client gesendet
			skip_next: false,
			paused_until: '2026-09-01T00:00:00Z',
			updated_at: '2026-10-01T08:00:00Z'
		}
	};
}

/** Schluessel, die nur Python schreibt — kein Reiter darf sie je senden (AC-16). */
export const PYTHON_EIGEN_REPORT = ['skip_next', 'paused_until', 'updated_at'] as const;
export const NIE_GESENDET_REPORT = [
	...PYTHON_EIGEN_REPORT,
	'change_threshold_temp_c',
	'change_threshold_wind_kmh',
	'change_threshold_precip_mm',
	'trip_id',
	'show_quick_take_tags',
	'show_stability',
	'show_highlights',
	'daily_summary_metrics',
	'alert_on_changes'
] as const;

/** Spec §2.3 — Versand-Schluessel in `report_config`. */
export const REPORT_VERSAND = [
	'enabled',
	'morning_enabled',
	'evening_enabled',
	'morning_time',
	'evening_time',
	'send_email',
	'send_telegram',
	'send_sms',
	'send_premium_sms',
	'telegram_style'
] as const;

/** Spec §2.3 — Inhalt- und Tagesfenster-Schluessel (Wetter-Metriken). */
export const REPORT_WETTER_METRIKEN = [
	'show_compact_summary',
	'wind_exposition_min_elevation_m',
	'show_stage_stats',
	'show_metrics_summary',
	'email_format',
	'show_yesterday_comparison',
	'day_window_start_hour',
	'day_window_end_hour'
] as const;

/** #3020: `report_config`-Schluessel des lebenden Reiters Zustellung (Teil `versand`). */
export const REPORT_ZUSTELLUNG = [
	'enabled', 'morning_enabled', 'evening_enabled', 'morning_time', 'evening_time',
	'send_email', 'send_telegram', 'send_sms', 'send_premium_sms'
] as const;

/** #3020: Schalter der Karte „Was steht wo“ unter `report_config` mit einem Wert ungleich `vollerTrip()`
 *  (`show_stability` ist seit #3036 ihr Eigenfeld). */
export const KARTE_REPORT: Record<string, unknown> = {
	show_compact_summary: false,
	show_stage_stats: false,
	show_yesterday_comparison: true,
	show_stability: false,
	email_format: 'compact',
	telegram_style: 'kurzform'
};

/** Spec §2.2 — display_config-Schluessel der Wetter-Metriken (`/weather-config`). */
export const DISPLAY_WETTER_METRIKEN = [
	'metrics',
	'channel_layouts',
	'preset_name',
	'telegram_kurzform',
	'outlook_metrics',
	'outlook_metric_formats',
	// Issue #1721: Schalter "Nacht-Stundentabelle in der Mail zeigen"
	'show_night_block'
] as const;

/** Spec §2.1 — Alarme: Top-Level-Felder (ohne `display_config`). */
export const TOP_ALARME = [
	'official_warnings',
	'alert_cooldown_minutes',
	'alert_quiet_from',
	'alert_quiet_to',
	'alert_channels',
	'alert_channel_thresholds'
] as const;

export const sortiert = (o: unknown): string[] =>
	Object.keys((o as Record<string, unknown>) ?? {}).sort();

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Feldinitialisierer laufen
 *  ausserhalb des Compilers nicht), MIT Kennung — sonst laeuft `retryConflict()`
 *  leer. `_lastFailed` bleibt bewusst `null` wie in allen Bestandstests: die
 *  Umsetzung muss `null`/`undefined` als „leere Liste" lesen (AC-21). */
export function erstelleController(id = TRIP_ID, art: 'trip' | 'vergleich' = 'trip'): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = id;
	f._resourceKind = art;
	return inst;
}

/** Eine ausgewertete Komponente: Umgebung + AST (fuer Effekte). */
export interface Instanz {
	u: Knoten;
	ast: Knoten;
	quelle: string;
}

/** Namen aus `let { a, b = 1 } = $props()` — jede nicht gesaete Prop wird als
 *  `undefined` angelegt, sonst scheitert der Zugriff im `with`-Rahmen mit einem
 *  ReferenceError, und Props mit Quelltext-Default bekommen ihn von
 *  `umgebungFuer` (Default greift bei `undefined`). */
function propNamen(datei: string): string[] {
	const ast = parse(readFileSync(datei, 'utf-8'), { modern: true }) as Knoten;
	const namen: string[] = [];
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'ObjectPattern') continue;
			for (const p of (d.id.properties as Knoten[]) ?? []) {
				const n = p.key?.name as string | undefined;
				if (n) namen.push(n);
			}
		}
	}
	return namen;
}

export async function bauen(datei: string, saat: Knoten): Promise<Instanz> {
	registriereHooks();
	const voll: Knoten = {};
	for (const n of propNamen(datei)) voll[n] = undefined;
	const { u, ast, quelle } = await umgebungFuer(datei, { ...voll, ...saat });
	return { u, ast, quelle };
}

/** Alle Trip-Reiter bekommen denselben Controller und dieselbe (veraltete) Kopie
 *  `trip` — wie in der echten Seite, in der `+page.svelte` den Trip haelt. */
export interface Aufbau {
	trip: Record<string, unknown>;
	ctl: SaveStatus;
	/** Server-Antworten, die der Reiter nach oben meldet (`onTripUpdate`). */
	updates: Array<Record<string, unknown>>;
}

export function neuerAufbau(trip: Record<string, unknown> = vollerTrip(), ctl?: SaveStatus): Aufbau {
	const id = trip.id as string;
	return { trip, ctl: ctl ?? erstelleController(id), updates: [] };
}

export function gemeinsam(a: Aufbau): Knoten {
	return {
		trip: a.trip,
		saveController: a.ctl,
		onTripUpdate: (t: Record<string, unknown>) => {
			a.updates.push(t);
		}
	};
}

/** Alarme-Reiter (route), gespeist wie der fruehere Container `AlarmeScheduleTab.svelte` (entfernt, #3047). */
export async function alarmeReiter(a: Aufbau): Promise<{
	inst: Instanz;
	/** Alarm-Empfindlichkeit einer Metrik aendern und den Speicher-Effekt laufen lassen. */
	empfindlichkeitAendern(metric: string, stufe: string): void;
	kanalUmschalten(kind: string): void;
	cooldownAendern(minuten: number | undefined): void;
	ruhezeitAendern(von: string | undefined, bis: string | undefined): void;
	amtlicheWarnungenUmschalten(an: boolean): void;
	schwelleAendern(kind: string, stufe: string): void;
}> {
	const tripDc = (a.trip.display_config ?? {}) as Record<string, unknown>;
	const inst = await bauen(DATEI.alarme, {
		...gemeinsam(a),
		context: 'route',
		createMode: false,
		activeMetrics: ['wind', 'precipitation'],
		metricLevels: tripDc.metric_alert_levels ?? {},
		existingChannels: a.trip.alert_channels ?? null,
		existingChannelThresholds: a.trip.alert_channel_thresholds ?? null,
		profileOverride: { premium_sms_allowed: true }
	});
	const effekt = (): void => {
		for (const e of effekteVon(inst.ast, inst.quelle, inst.u, '_prevAlarmeJson')) e();
	};
	const rufe = (name: string, ...args: unknown[]): void => {
		const fn = inst.u[name] as ((...x: unknown[]) => void) | undefined;
		if (typeof fn !== 'function') throw new Error(`Messaufbau: AlarmeTab.${name} nicht herleitbar`);
		fn(...args);
		effekt();
	};
	return {
		inst,
		empfindlichkeitAendern: (m, s) => rufe('handleMetricLevelChange', m, s),
		kanalUmschalten: (k) => rufe('handleChannelToggle', k),
		cooldownAendern: (m) => rufe('handleCooldownChange', m),
		ruhezeitAendern: (von, bis) => {
			(inst.u.handleQuietFromChange as (v: unknown) => void)(von);
			rufe('handleQuietToChange', bis);
		},
		amtlicheWarnungenUmschalten: (an) => rufe('handleOfficialWarningsToggle', an),
		schwelleAendern: (k, s) => rufe('handleThresholdChange', k, s)
	};
}

/** Was der Instanz-Pruefstand nicht aus dem Quelltext bindet (`svelte`-Importe); `api` ist das ECHTE Modul. */
export const LAUFZEIT = { api, untrack: (fn: () => unknown) => fn(), onMount: () => {} };

/** Antworten der drei Lese-Endpunkte des Reiters Wetter aus dem Python-Kern (der Ersatz-Server fuehrt nur Abos).
 *  #2988: Vorlagen und aufgeloeste Ampel kommen aus derselben Quelle, sonst maesse der Reiter gegen eine fremde Vorlage. */
const wetterDaten = (): Record<string, unknown> => ({
	'/api/metrics': live().metrics,
	'/api/templates': live().templates,
	'/api/metric-presets': []
});

/** #2988: Aufloesung der Ampel (lesender POST, schreibt nichts) mit echtem Python; jede andere Anfrage `null`. */
export async function aufloesungAntwort(input: unknown, init?: RequestInit): Promise<Response | null> {
	if (String(input) !== '/api/ampel/aufloesung' || init?.method !== 'POST') return null;
	const antwort = await aufloesungPost()('/api/ampel/aufloesung', JSON.parse(String(init.body)));
	return new Response(JSON.stringify(antwort), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

/** Beantwortet die Lese-Endpunkte `daten` und die Ampel-Aufloesung waehrend `lauf`; alles andere geht an den Ersatz-Server. */
export async function mitAntworten<T>(daten: Record<string, unknown>, lauf: () => Promise<T>): Promise<T> {
	const basis = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) =>
		String(input) in daten
			? new Response(JSON.stringify(daten[String(input)]), { status: 200, headers: { 'Content-Type': 'application/json' } })
			: ((await aufloesungAntwort(input, init)) ?? basis(input as never, init));
	try {
		return await lauf();
	} finally {
		(globalThis as { fetch: unknown }).fetch = basis;
	}
}

/** Antwort des Lese-Endpunkts der Tabelle „Was steht wo“ zu einem Abo-Stand (`stored` = Tabelle gespeichert). */
export function tabellenAntwort(kind: 'route' | 'vergleich', dc: Knoten, ids: string[], blocks: Knoten = {}): Knoten {
	const zeilen = ids.map((metric_id) => ({ metric_id }));
	const placements = dc.placements ?? { version: 1, rows: zeilen, outlook_reports: ['evening'] };
	return {
		kind,
		stored: dc.placements !== undefined,
		placements: JSON.parse(JSON.stringify(placements)),
		rows: (placements.rows as Knoten[]).map((z) => ({ metric_id: z.metric_id, cells: {} })),
		outlook_reports: placements.outlook_reports ?? [],
		blocks
	};
}

/** Wert eines Attributs der Einbettung, ausgewertet in der Umgebung des Eltern-Skripts. */
function einbettungsWert(a: Knoten, quelle: string, u: Knoten): unknown {
	if (a.value === true) return true;
	const tag = Array.isArray(a.value) ? a.value.find((x: Knoten) => x.type === 'ExpressionTag') : a.value;
	if (tag?.type === 'ExpressionTag') return werte(ohneTypen(quelle, tag.expression), u);
	return (a.value as Knoten[]).map((x) => x.data).join('');
}

/** #3020 (Adversary F1): die Karte „Was steht wo“ so im Reiter Wetter binden, wie dessen Markup sie einbettet
 *  (echte Attribut-Ausdruecke, echtes `bind:this`), echt geladen. `lesen` beantwortet nur das GET der Tabelle;
 *  ohne `lesen` geht auch dieses GET ueber das echte `api`. */
export async function karteImReiter(wt: Instanz, lesen?: (pfad: string) => Knoten): Promise<Instanz> {
	const e = findeKomponenten(wt.ast, 'WasStehtWoKarte')[0];
	if (!e) throw new Error('Messaufbau: Einbettung der Karte fehlt im Reiter Wetter');
	const props: Knoten = {};
	for (const a of e.attributes as Knoten[]) if (a.type === 'Attribute') props[a.name] = einbettungsWert(a, wt.quelle, wt.u);
	const karte = await bauen(DATEI.karte, {
		...LAUFZEIT,
		api: { ...api, get: async (pfad: string) => (lesen && pfad.includes('/placements') ? lesen(pfad) : api.get(pfad)) },
		...props
	});
	await (karte.u.laden as () => Promise<void>)();
	if (karte.u.phase !== 'bereit') throw new Error('Messaufbau: Karte im Reiter Wetter hat nicht geladen');
	const bindung = (e.attributes as Knoten[]).find((a) => a.type === 'BindDirective' && a.name === 'this');
	if (bindung) wt.u[wt.quelle.slice(bindung.expression.start, bindung.expression.end)] = karte.u;
	return karte;
}

/** Reiter Wetter (`WetterTabInhalt`, route) mit gebundener Karte „Was steht wo“ wie im Hub: echtes Laden, echte
 *  Handler, echter Speicherer (`wetterTabSpeicherung`: /weather-config, danach Trip-PUT). Ist am Trip eine Tabelle
 *  gespeichert (`display_config.placements`), traegt /weather-config sie mit; sonst fehlt der Schluessel. */
export async function wetterReiter(a: Aufbau, lesen?: (pfad: string) => Knoten): Promise<{
	inst: Instanz;
	karte: Instanz;
	/** „−“ / „+“ einer Metrik (Grundauswahl). */
	abwaehlen(id: string): void;
	hinzufuegen(id: string): void;
	/** Systemvorlage uebernehmen. */
	vorlage(id: string): void;
	/** Tagesfenster, Warnungen, Radar: Teil des Bearbeitungsstands (Karten des Reiters). */
	aendern(teil: Record<string, unknown>): void;
}> {
	const inst = await bauen(DATEI.wetter, { ...gemeinsam(a), ...LAUFZEIT, context: 'route', createMode: false });
	await mitAntworten(wetterDaten(), () => (inst.u.laden as () => Promise<void>)());
	if (inst.u.phase !== 'bereit') throw new Error('Messaufbau: Reiter Wetter hat nicht geladen');
	const u = inst.u;
	const dc = (a.trip.display_config ?? {}) as Knoten;
	const rc = (a.trip.report_config ?? {}) as Knoten;
	const karte = await karteImReiter(
		inst,
		lesen ?? (() => tabellenAntwort('route', dc, [...(u.stand.auswahl as string[])], { ...rc, show_night_block: dc.show_night_block }))
	);
	return {
		inst,
		karte,
		abwaehlen: (id) => u.entfernen(id),
		hinzufuegen: (id) => u.hinzufuegen(id),
		vorlage: (id) => u.vorlageSetzen(u.Z.mitVorlage(u.stand, id, u.daten.vorlagen, 'route', {})),
		aendern: (teil) => u.aendern({ ...u.stand, ...teil })
	};
}

/** Karte „Was steht wo“ (route) allein: Schalter (`feld`, Teilfeld-PUT auf den Trip) und Tabelle
 *  (`placements`). Antwort des Lese-Endpunkts aus dem Trip gebildet wie im Python-Kern (`blocks`). */
export async function karteWasStehtWo(a: Aufbau): Promise<{
	inst: Instanz;
	schalten(feld: string, wert: unknown): void;
	haken(metrik: string, stelle: string, an: boolean): void;
	format(metrik: string, stelle: string, form: 'raw' | 'simplified'): void;
	ausblick(bericht: 'morning' | 'evening', an: boolean): void;
}> {
	const rc = (a.trip.report_config ?? {}) as Record<string, unknown>;
	const dc = (a.trip.display_config ?? {}) as Record<string, unknown>;
	const zeilen = ((dc.metrics ?? []) as Array<{ metric_id: string }>).map((m) => ({ metric_id: m.metric_id }));
	const antwort = {
		kind: 'route',
		stored: true,
		placements: { version: 1, rows: zeilen, outlook_reports: ['evening'] },
		rows: zeilen.map((z) => ({ ...z, cells: {} })),
		outlook_reports: ['evening'],
		blocks: { ...rc, show_night_block: dc.show_night_block }
	};
	// Nur das Lesen der Tabelle (fuehrt der Ersatz-Server nicht) liefert den Stand; Schreiben laeuft ueber `api`.
	const lesen = async (pfad: string): Promise<unknown> =>
		pfad.includes('/placements') ? { ...antwort, placements: JSON.parse(JSON.stringify(inst.u.lokal)) } : api.get(pfad);
	const inst = await bauen(DATEI.karte, {
		...LAUFZEIT,
		api: { ...api, get: lesen },
		context: 'route',
		id: a.trip.id,
		saveController: a.ctl,
		onUebernahme: gemeinsam(a).onTripUpdate,
		antwort,
		lokal: JSON.parse(JSON.stringify(antwort.placements)),
		phase: 'bereit'
	});
	const u = inst.u;
	/** `$derived` wertet der Pruefstand nur einmal aus: vor jeder Geste wie im Baustein neu bestimmen. */
	const geste = (fn: () => void) => {
		u.aktFelder = u.felder ?? u.felderAusAntwort(antwort);
		u.ausblickBerichte = u.lokal.outlook_reports;
		fn();
	};
	return {
		inst,
		schalten: (feld, wert) => geste(() => u.feld(feld, wert)),
		haken: (metrik, stelle, an) => geste(() => u.haken({ metrik, stelle, an })),
		format: (metrik, stelle, form) => geste(() => u.format({ metrik, stelle, format: form })),
		ausblick: (bericht, an) => geste(() => u.ausblick(bericht, an))
	};
}

/** Reiter Zustellung (`ZustellungTab`, route): Briefing-Zeiten und Kanaele (Teil `versand`), Alarm-Kanaele,
 *  Stille Stunden (Teil `alarme`) ueber den EINEN Speicherer (`zustellungSpeicherung`). */
export async function zustellungReiter(a: Aufbau): Promise<{
	inst: Instanz;
	/** Eine Geste der Organismen: neuer Formularstand an `aendern` des Reiters. */
	aendern(teil: Partial<ZustellungStand>): void;
}> {
	const inst = await bauen(DATEI.zustellung, { ...LAUFZEIT, context: 'route', panel: gemeinsam(a) });
	const u = inst.u;
	if (!u.speicherung) throw new Error('Messaufbau: ZustellungTab.speicherung nicht herleitbar');
	return { inst, aendern: (teil) => u.aendern({ ...u.stand, ...teil }) };
}

// #2794 S3a Teil-PR 4a (AC-31): `wertebereicheReiter` (CorridorEditor/CorridorEditorMobile)
// entfaellt mit der Oberflaeche.

/**
 * Issue #2284 S2 — SCHNITTSTELLE, die der Kopf ab S2 bauen muss (AC-6, AC-8, AC-9, AC-17):
 *
 * `TripHeader.svelte` deklariert in seinem Instanz-Skript (top-level, wie
 * `routes/compare/[id]/+page.svelte` in S1) die Speicherfunktion, die es dem Baustein
 * `SubscriptionHeader` als Prop `onSaveField` uebergibt:
 *
 *   async function onSaveField(
 *     field: 'name' | 'region' | 'profile',   // 'profile' seit #3196 ohne Wirkung (keine Chips mehr)
 *     value: string,
 *     schliessen: () => void
 *   ): Promise<void>
 *
 * - Rumpf NUR das Eigenfeld: name ⇒ `{ name }`, region ⇒ `{ region }` (Leeren = `{ region: "" }`,
 *   der Schluessel bleibt im JSON). Kein Spread von `trip`.
 * - Konflikt-Schluessel je Feld: `kopf-name` / `kopf-region` (Entscheidung 9),
 *   ueber `baueTripSpeicherung(..., schluessel)` und `speichereOderMeldeKonflikt(fn, saveController)`.
 * - Drei Ausgaenge (S1-Vertrag des Bausteins): gespeichert ⇒ `onTripUpdate(antwort)` + `schliessen()`;
 *   412 ⇒ am Controller gemeldet, Promise erfuellt OHNE `schliessen()` (erst der erfolgreiche
 *   Retry ruft `schliessen()` und ersetzt den Seitenstand, KEIN `imWiederholen`-Guard,
 *   Entscheidung 10); jeder andere Fehler ⇒ wirft (der Baustein zeigt die Meldung).
 *
 * Der Pruefstand erreicht die Funktion wie zuvor `makeNameSaveHandler`: ueber die AST-Auswertung
 * des echten Instanz-Skripts (`inst.u.onSaveField`) — kein neuer Export noetig.
 */
// Issue #3196 (ADR-0108 Nr. 3): die Aktivitaet hat den Kopf verlassen ('profile' entfaellt);
// Fortbewegung + Grundtempo schreibt der Reiter Etappen (`tempoReiter` unten).
export type KopfFeld = 'name' | 'region';

export interface KopfReiter {
	inst: Instanz;
	/** Wie oft der Kopf je Feld `schliessen()` aufgerufen hat (Feld zu = gespeichert). */
	geschlossen: Record<KopfFeld, number>;
	/** Roher Aufruf von `onSaveField` — eine Ablehnung schlaegt bis zum Test durch. */
	speichereFeld(field: KopfFeld, value: string): Promise<void>;
	umbenennen(name: string): Promise<void>;
	regionAendern(region: string): Promise<void>;
}

/** Kopf (TripHeader): Name und Region ueber `onSaveField` (s. o.). */
export async function kopfReiter(a: Aufbau): Promise<KopfReiter> {
	const inst = await bauen(DATEI.kopf, { ...gemeinsam(a), now: new Date('2026-10-02T08:00:00Z') });
	const geschlossen: Record<KopfFeld, number> = { name: 0, region: 0 };
	const speichereFeld = async (field: KopfFeld, value: string): Promise<void> => {
		const fn = inst.u.onSaveField as
			| ((f: KopfFeld, v: string, schliessen: () => void) => Promise<void>)
			| undefined;
		if (typeof fn !== 'function') throw new Error('Messaufbau: TripHeader.onSaveField nicht herleitbar');
		await fn(field, value, () => {
			geschlossen[field] += 1;
		});
	};
	return {
		inst,
		geschlossen,
		speichereFeld,
		umbenennen: (name) => speichereFeld('name', name),
		regionAendern: (region) => speichereFeld('region', region)
	};
}

/** Issue #3196: Tempo-Karte im Reiter Etappen — `EditStagesPanelNew.tempoAendern(neu)` merkt den
 *  Stand vor und plant das Speichern am Controller (Rumpf `{ stages, tempo }`); `aendern` wartet,
 *  bis der Controller fertig ist. Bei 412 meldet der Controller den Konflikt (Retry-Eintrag 'etappen'). */
export async function tempoReiter(a: Aufbau): Promise<{
	inst: Instanz;
	aendern(tempo: { fortbewegung: string; grundtempo_kmh: number }): Promise<void>;
}> {
	const inst = await bauen(DATEI.etappen, {
		...gemeinsam(a),
		tripId: a.trip.id,
		stages: a.trip.stages,
		tempo: a.trip.tempo
	});
	return {
		inst,
		async aendern(tempo) {
			const fn = inst.u.tempoAendern as ((t: unknown) => void) | undefined;
			if (typeof fn !== 'function') throw new Error('Messaufbau: EditStagesPanelNew.tempoAendern nicht herleitbar');
			fn(tempo);
			await fertig(a.ctl);
		}
	};
}

/** Etappen (EditStagesPanelNew): Speichern ueber den Controller. */
export async function etappenReiter(a: Aufbau): Promise<{
	inst: Instanz;
	speichern(stages: unknown): void;
}> {
	const inst = await bauen(DATEI.etappen, {
		...gemeinsam(a),
		tripId: a.trip.id,
		stages: a.trip.stages,
		tempo: a.trip.tempo
	});
	return {
		inst,
		speichern(stages) {
			inst.u.stages = stages;
			(inst.u.scheduleSave as () => void)();
		}
	};
}

/**
 * Die Trip-Detailseite (`routes/trips/[id]/+page.svelte`): Pausieren/Archivieren.
 * `createSaveStatus` ist unter node nicht herleitbar (Runen) — der Controller
 * wird gesaet, wie die Seite ihn haelt. `trip` ist der veraltete lokale Stand.
 */
export async function tripSeite(
	a: Aufbau,
	/** der Ersatz-Server — an ihm wird das Ende des `void`-Klick-Handlers erkannt */
	server: { calls: Array<{ method: string; path: string; finishedAt: number }> },
	/** Stempel aus der Server-Naht (`data.etag`) — frischer Seitenaufbau (#1433 F003) */
	etag?: string,
	/** Fix-Loop 2 (F105): `false` = Server-Rendering (der Kopf darf die Registry nicht beschreiben) */
	imBrowser = true
): Promise<{
	inst: Instanz;
	pausieren(): Promise<void>;
	archivieren(): Promise<void>;
	/** aktueller lokaler `trip` der Seite */
	trip(): Record<string, unknown>;
}> {
	const inst = await bauen(DATEI.seite, {
		data: { trip: a.trip, etag },
		browser: imBrowser,
		tripSaveCtl: a.ctl
	});
	/** Klick-Handler laufen `void`. Das Ende ist erreicht, wenn der PATCH beim Server
	 *  angekommen ist, `isLoading` wieder false ist und keine Anfrage mehr unterwegs
	 *  ist (haengt NICHT davon ab, ob die Umsetzung `isLoading` vor oder nach einem
	 *  Flush setzt). Deckel: 3 s — fehlt der PATCH ganz, ist der Test ohnehin rot. */
	const abwarten = async (vorher: number): Promise<void> => {
		const ende = Date.now() + 3000;
		for (;;) {
			await new Promise((r) => setTimeout(r, 10));
			const neu = server.calls.slice(vorher);
			const patch = neu.some((c) => c.method === 'PATCH');
			const unterwegs = neu.some((c) => Number.isNaN(c.finishedAt));
			if (patch && !unterwegs && inst.u.isLoading !== true) break;
			if (Date.now() > ende) break;
		}
		await new Promise((r) => setTimeout(r, 30));
	};
	return {
		inst,
		async pausieren() {
			const vorher = server.calls.length;
			// #2278: das Lebenszyklus-Menue ruft handleHubAction('pause') (frueher handlePauseClick).
			(inst.u.handleHubAction as (id: string) => void)('pause');
			await abwarten(vorher);
		},
		async archivieren() {
			const vorher = server.calls.length;
			(inst.u.handleArchiveConfirm as () => void)();
			await abwarten(vorher);
		},
		trip: () => inst.u.trip as Record<string, unknown>
	};
}

/** Warte, bis ein Speichervorgang des Controllers fertig ist (Debounce-Timer
 *  vorziehen, laufenden Vorgang abwarten). */
export async function fertig(ctl: SaveStatus): Promise<void> {
	await ctl.flush();
	const laufend = ctl.laufendeSpeicherung;
	if (laufend) await laufend;
}
