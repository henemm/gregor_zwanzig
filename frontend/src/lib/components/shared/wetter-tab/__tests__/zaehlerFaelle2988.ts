// Pruefstand #2988 S1: Faelle fuer Zaehler, eigene Vorlage und Speicher-Ruempfe.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (AC-2, AC-3, AC-14).
//
// Keine .test.ts-Datei. Die Faelle benutzen nur Funktionen, die nach dem Umbau bleiben
// (`mitVorlage`, `mitMetrik`, `ohneMetrik`, `mitAlarmAb`, `mitEntwurf`), und die Vorlagen, den
// Vergleichs-Katalog und die aufgeloesten Fixture-Ampeln aus der eingefrorenen Referenz
// `tests/fixtures/ampel_zaehler_referenz_2988.json` — kein Spiegel, kein Netz, kein Python.
// Die Sollwerte darin stammen aus dem Code VOR dem Umbau (Stand siehe `_quelle` der Fixture) und
// werden nie aus dem neuen Code nacherzeugt.

import { fixture, type Json } from './wetterTabDaten.ts';
import { mitAlarmAb, mitEntwurf, mitMetrik, mitVorlage, ohneMetrik, type WetterStand } from '../wetterZustand.ts';
import { AUSWAHL_ABLEITUNG, type Kontext } from '../ampelModell.ts';

export const KONTEXTE: Kontext[] = ['route', 'vergleich'];

export type Grundlage = { vorlagen: Json; altSchluessel: Json; abweichungsFaelle: { name: string; ampel: Json }[] };
export type Fall = { name: string; context: Kontext; alt: Json; stand: WetterStand };

export const referenz = (): Json => fixture('ampel_zaehler_referenz_2988.json');

const leer = (vorlageId: string): WetterStand => ({
	vorlageId,
	ampel: { template: vorlageId, metrics: {}, thunder: {} },
	auswahl: [],
	warnungenAn: true,
	radarAn: false,
	tagesfenster: { start: 6, end: 20 }
});

type Geste = (s: WetterStand, context: Kontext, g: Grundlage) => WetterStand;
const grenze = (id: string, upper: Json) => (s: WetterStand) => mitEntwurf(s, { id, upper });
const andereStufe = (s: WetterStand, id: string) => (s.ampel.metrics?.[id]?.alarm_ab === 'red' ? 'orange' : 'red');
const erste = (s: WetterStand) => s.auswahl[0];
const mittel = (s: WetterStand) => (s.ampel.thunder?.mittel === 'red' ? 'orange' : 'red');

export const altFuer = (c: Kontext, g: Grundlage): Json => ({ route: {}, vergleich: g.altSchluessel })[c];

/** Aenderungsarten des Reiters; jede laeuft je Vorlage und Kontext. */
export const GESTEN: Record<string, Geste> = {
	unveraendert: (s) => s,
	grenze_geaendert: grenze('gust', { yellow: 41, orange: 61, red: 77 }),
	grenze_geoeffnet: grenze('gust', {}),
	grenze_teilweise_offen: grenze('gust', { yellow: null, orange: 61, red: 77 }),
	grenze_unten: (s) => mitEntwurf(s, { id: 'temperature', lower: { red: -31, orange: -21, yellow: -11 } }),
	alarm_ab: (s) => mitAlarmAb(s, 'gust', andereStufe(s, 'gust')),
	alarm_ab_ohne_vorlagenzeile: (s) => mitAlarmAb(s, 'gibt_es_nicht', 'red'),
	alarm_ab_never_ohne_vorlagenzeile: (s) => mitAlarmAb(s, 'gibt_es_nicht', 'never'),
	metrik_weg: (s) => ohneMetrik(s, erste(s)),
	metrik_weg_und_wieder_da: (s, c) => mitMetrik(ohneMetrik(s, erste(s)), erste(s), c),
	metrik_dazu: (s, c) => mitMetrik(s, 'dewpoint', c),
	metrik_dazu_ohne_vorlagenzeile: (s, c) => mitMetrik(s, 'pressure', c),
	elter_weg: (s) => ohneMetrik(s, 'temperature'),
	elter_weg_und_wieder_da: (s, c) => mitMetrik(ohneMetrik(s, 'temperature'), 'temperature', c),
	kind_weg: (s) => ohneMetrik(s, 'temperature_day_low'),
	kind_dazu: (s, c) => mitMetrik(s, 'wind_chill_day_low', c),
	nicht_ausgebbar_dazu: (s, c) => mitMetrik(s, 'temperature_night', c),
	gewitter: (s) => mitEntwurf(s, { id: 'thunder', thunder: { mittel: mittel(s) } }),
	gewitter_beide: (s) => mitEntwurf(s, { id: 'thunder', thunder: { mittel: 'yellow', hoch: 'orange' } }),
	mehrere_arten_eine_metrik: (s) => mitAlarmAb(grenze('gust', { yellow: 41, orange: 61, red: 77 })(s), 'gust', andereStufe(s, 'gust')),
	kombination: (s, c) =>
		mitMetrik(ohneMetrik(mitAlarmAb(grenze('gust', { yellow: 41 })(s), 'wind', andereStufe(s, 'wind')), 'precipitation'), 'dewpoint', c),
	vorlage_gewechselt: (s, c, g) =>
		mitVorlage(mitAlarmAb(s, 'gust', 'red'), s.vorlageId === 'wandern' ? 'skitouren' : 'wandern', g.vorlagen, c, altFuer(c, g)),
	zurueckgesetzt: (s, c, g) => mitVorlage(ohneMetrik(mitAlarmAb(s, 'gust', 'red'), erste(s)), s.vorlageId, g.vorlagen, c, altFuer(c, g))
};

/** Gesten je Vorlage und Kontext, dazu die 22 Fixture-Faelle als Stand (Ampel von Python aufgeloest). */
export function alleFaelle(g: Grundlage): Fall[] {
	const aus: Fall[] = [];
	for (const context of KONTEXTE) {
		const alt = altFuer(context, g);
		for (const v of Object.keys(g.vorlagen)) {
			for (const [geste, f] of Object.entries(GESTEN)) {
				const start = mitVorlage(leer(v), v, g.vorlagen, context, alt);
				aus.push({ name: `${context}|${v}|${geste}`, context, alt, stand: f(start, context, g) });
			}
		}
		for (const { name, ampel } of g.abweichungsFaelle) {
			const aktiv = Object.entries(ampel.metrics as Json).filter(([, e]) => (e as Json).enabled).map(([id]) => id);
			const auswahl = AUSWAHL_ABLEITUNG[context](aktiv);
			aus.push({ name: `${context}|fixture|${name}`, context, alt, stand: { ...leer(ampel.template), ampel: structuredClone(ampel), auswahl } });
		}
	}
	// Vergleich ohne bekannten Katalog: Basis bleibt die Rohvorlage.
	aus.push({ name: 'vergleich|wandern|ohne_katalog', context: 'vergleich', alt: {}, stand: mitVorlage(leer('wandern'), 'wandern', g.vorlagen, 'vergleich', {}) });
	return aus;
}

/** Vergleichsform: offene (null) Grenzen und fehlende Seiten sind gleich (Spec: „offene Grenzen als leere Seite“). */
export function normal(ampel: Json): Json {
	const k = structuredClone(ampel);
	for (const e of Object.values((k?.metrics ?? {}) as Record<string, Json>)) {
		for (const seite of ['lower', 'upper']) {
			e[seite] = Object.fromEntries(Object.entries(e[seite] ?? {}).filter(([, v]) => v !== null && v !== undefined));
		}
	}
	return k;
}

const sortiert = (o: Json): Json =>
	o && typeof o === 'object' && !Array.isArray(o) ? Object.fromEntries(Object.keys(o).sort().map((k) => [k, sortiert(o[k])])) : o;

/** Kleine Darstellung einer Ampel gegen ihre Rohvorlage (haelt die Referenz lesbar); Umkehrung `entpacke`. */
export function packe(ampel: Json, vorlage: Json): Json {
	const a = normal(ampel);
	const v = normal(vorlage);
	const metrics: Json = {};
	for (const [id, e] of Object.entries(a.metrics)) {
		if (JSON.stringify(sortiert(e)) !== JSON.stringify(sortiert(v.metrics[id]))) metrics[id] = e;
	}
	return { template: a.template, metrics, fehlt: Object.keys(v.metrics).filter((id) => !(id in a.metrics)), thunder: a.thunder };
}

export function entpacke(p: Json, vorlage: Json): Json {
	const v = normal(vorlage);
	for (const id of p.fehlt) delete v.metrics[id];
	return { template: p.template, metrics: { ...v.metrics, ...structuredClone(p.metrics) }, thunder: p.thunder };
}

/** Abo mit Feldern, die der Reiter nicht anfasst (Read-Modify-Write, #102). */
export function aboMitFremdfeldern(context: Kontext): Json {
	const dc = { preset_name: 'wandern', show_night_block: true, fremd: { tief: [1, 2] }, ampel: { template: 'wandern' } };
	const gemeinsam = { official_warnings: { enabled: true, sources: ['x'] }, official_alerts_enabled: true, radar_alert_enabled: false };
	const je: Record<Kontext, Json> = {
		route: {
			id: 't-2988',
			name: 'T',
			...gemeinsam,
			stages: [],
			report_config: { send_evening: true, day_window_start_hour: 6, day_window_end_hour: 20 },
			display_config: {
				...dc,
				metrics: [
					{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 3, eigen: 'bleibt' },
					{ metric_id: 'temperature', enabled: false, order: 1 }
				]
			}
		},
		vergleich: {
			id: 'p-2988',
			name: 'P',
			...gemeinsam,
			location_ids: ['a'],
			day_window_start_hour: 6,
			day_window_end_hour: 20,
			display_config: {
				...dc,
				active_metrics: [
					{ metric_id: 'gust', aggregation: 'max', eigen: 'bleibt' },
					{ metric_id: 'wind', aggregation: 'max' }
				]
			}
		}
	};
	return je[context];
}

/** Vorlagen, fuer die die Speicher-Ruempfe eingefroren sind (Trip und Vergleich, je alle Gesten). */
export const PAYLOAD_VORLAGEN = ['wandern', 'radtour'];
