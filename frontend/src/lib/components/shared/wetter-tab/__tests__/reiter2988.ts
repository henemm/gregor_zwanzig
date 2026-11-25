// Pruefstand #2988: der echte Reiter (Instanz-Skript von WetterTabInhalt) mit zaehlendem Client.
// Keine .test.ts-Datei. Aufbau wie fix_3193_vorlage_abweichung_minimal.test.ts: Laden mit den echten
// Python-Antworten, Gesten und Zaehler als die Ausdruecke, die die Komponente an die VorlageKarte gibt.

import assert from 'node:assert/strict';
import path from 'node:path';
import { WETTER_TAB, aufloesungPost, live, vergleichsKatalogFetch, type Json } from './wetterTabDaten.ts';
import { attributAusdruck, findeKomponenten, ohneTypen, umgebungFuer, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import type { Kontext } from '../ampelModell.ts';

const LIVE = live();
const TAB = path.resolve(WETTER_TAB, '../../organisms/wetter-tab/WetterTabInhalt.svelte');
const DATEN: Record<string, unknown> = { '/api/metrics': LIVE.metrics, '/api/templates': LIVE.templates, '/api/metric-presets': [] };

const eingeschaltet = (metrics: Json): string[] => Object.entries(metrics ?? {}).filter(([, e]) => (e as Json).enabled).map(([id]) => id);

export type Optionen2988 = {
	/** Antwort von GET /api/metric-presets. */
	presets?: Json;
	/** Ersatz für den Client-`post` (Standard: Auflösung mit echtem Python, jeder andere POST wirft). */
	post?: (pfad: string, rumpf?: unknown) => Promise<unknown>;
	/** Vollständiges Abo statt des aus `ampel` gebauten. */
	abo?: Json;
	createMode?: boolean;
	onAnlegeStand?: (nutzlast: Json) => void;
	/** Das Laden darf scheitern: der Prüfstand bricht nicht ab (`u.phase` prüft der Test). */
	erwarteFehler?: boolean;
};

/** Reiter mit einem Abo „nach Vorlage“ (`ampel.template`) plus den Abweichungen in `ampel` laden. */
export async function reiter2988(context: Kontext, ampel: Json, opt: Optionen2988 = {}) {
	const aufrufe: string[] = [];
	const post = opt.post ?? aufloesungPost();
	let geplant = 0;
	const verboten = (methode: string) => async (pfad: string) => {
		aufrufe.push(`${methode} ${pfad}`);
		throw new Error(`unerwartet: ${methode} ${pfad}`);
	};
	const api = {
		get: async (pfad: string) => {
			aufrufe.push(`GET ${pfad}`);
			if (pfad === '/api/metric-presets' && opt.presets !== undefined) return structuredClone(opt.presets);
			if (!(pfad in DATEN)) throw new Error(`unerwartet: GET ${pfad}`);
			return structuredClone(DATEN[pfad]);
		},
		post: async (pfad: string, rumpf?: unknown) => {
			aufrufe.push(`POST ${pfad}`);
			return post(pfad, rumpf);
		},
		put: verboten('PUT')
	};
	const vorlage = LIVE.templates.find((t: Json) => t.id === ampel?.template)?.ampel;
	assert.ok(vorlage || opt.abo, `Messaufbau: unbekannte Vorlage ${ampel?.template}`);
	const ids = [...new Set([...eingeschaltet(vorlage?.metrics), ...eingeschaltet(ampel?.metrics)])];
	const abo: Record<Kontext, Json> = {
		route: {
			id: 't',
			name: 'T',
			stages: [],
			report_config: {},
			display_config: { ampel, metrics: ids.map((metric_id) => ({ metric_id, enabled: true })) }
		},
		vergleich: {
			id: 'p',
			name: 'P',
			location_ids: [],
			display_config: { ampel, active_metrics: ids.map((metric_id) => ({ metric_id, aggregation: 'max' })) }
		}
	};
	const { u, ast, quelle } = await umgebungFuer(TAB, {
		context,
		trip: context === 'route' ? (opt.abo ?? abo.route) : undefined,
		preset: context === 'vergleich' ? (opt.abo ?? abo.vergleich) : undefined,
		createMode: opt.createMode ?? false,
		saveController: {
			schedule: () => {
				geplant++;
			}
		},
		enqueueHubWrite: undefined,
		onTripUpdate: undefined,
		onCompareUpdate: undefined,
		onAnlegeStand: opt.onAnlegeStand,
		api
	});
	/** Laden bzw. „Erneut laden“ des Reiters. */
	const laden = async (): Promise<void> => {
		const zurueck = vergleichsKatalogFetch();
		try {
			await u.laden();
		} finally {
			zurueck();
		}
	};
	await laden();
	if (!opt.erwarteFehler) assert.equal(u.phase, 'bereit', 'Messaufbau: Reiter hat nicht geladen');
	const herleitung = (name: string): string => {
		for (const stmt of ast.instance.content.body as Knoten[]) {
			if (stmt.type !== 'VariableDeclaration') continue;
			for (const d of stmt.declarations as Knoten[]) if (d.id?.name === name) return ohneTypen(quelle, d.init.arguments[0]);
		}
		throw new Error(`keine Herleitung ${name}`);
	};
	const karte = findeKomponenten(ast, 'VorlageKarte')[0];
	/** Der Pruefstand wertet `$derived` nur einmal aus: vor jeder Geste und Messung neu rechnen. */
	const frisch = () => {
		for (const n of ['anzeige', 'vorlagen', 'abweichungen', 'aboAmpel']) u[n] = werte(herleitung(n), u);
	};
	const prop = (name: string): Json => {
		frisch();
		return werte(attributAusdruck(karte, quelle, name)!, u);
	};
	const handler = (name: string): Json => {
		frisch();
		const a = (karte.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name)!;
		return werte(ohneTypen(quelle, a.value.expression), u);
	};
	const tippen = (id: string, seite: 'lower' | 'upper', farbe: string, w: number) => {
		u.grenzenUmschalten(id);
		assert.equal(u.offen, id, 'Messaufbau: Grenzfeld nicht offen');
		u.grenzWert(id, seite, farbe, w);
	};
	return {
		u,
		aufrufe,
		laden,
		geplant: () => geplant,
		zahl: (): number => prop('abweichungen'),
		aboAmpel: (): Json => prop('aboAmpel'),
		uebernehmen: (id: string) => handler('onUebernehmen')(id),
		zuruecksetzen: () => handler('onZuruecksetzen')(),
		/** Grenze tippen, Feld bleibt offen. */
		tippen,
		/** Grenze tippen und „Fertig“. */
		grenze: (id: string, seite: 'lower' | 'upper', farbe: string, w: number) => {
			tippen(id, seite, farbe, w);
			assert.equal(u.fertig(), true, 'Messaufbau: Grenze ungueltig');
		}
	};
}
