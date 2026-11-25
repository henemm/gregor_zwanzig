// Pruefstand #2988 S3: der echte Reiter (Instanz-Skript von WetterTabInhalt) mit frei waehlbarem Abo,
// Hub oder Anlegen. Keine .test.ts-Datei. Antworten aus echtem Python (wetterTabDaten.ts); `post` ersetzt
// den Client-post (Fehlerfaelle). Referenz: tests/fixtures/ampel_laden_referenz_2988.json.

import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import * as D from './wetterTabDaten.ts';
import type { Json } from './wetterTabDaten.ts';
import { attributAusdruck, findeKomponenten, ohneTypen, umgebungFuer, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import type { Kontext } from '../ampelModell.ts';

export type { Json };
export const KONTEXTE: Kontext[] = ['route', 'vergleich'];
export const AUFLOESUNG = '/api/ampel/aufloesung';
const TAB = path.resolve(D.WETTER_TAB, '../../organisms/wetter-tab/WetterTabInhalt.svelte');

/** Helfer aus wetterTabDaten.ts; fehlt er, wird der einzelne Test rot statt der ganzen Datei. */
function helfer(name: string): Json {
	const f = (D as Json)[name];
	assert.equal(typeof f, 'function', `TDD RED: wetterTabDaten.${name} fehlt`);
	return f;
}
export const pythonAufloesung = (eintraege: Json[]): Json[] => helfer('pythonAufloesung')(eintraege);
export const aufgeloestVon = (abo: Json): Json => helfer('aufgeloestVon')(abo);
/** Client-post mit echtem Python. */
export const echterPost = async (pfad: string, rumpf: unknown): Promise<Json> => helfer('aufloesungPost')()(pfad, rumpf);

/** Produktmodul dynamisch (Muster `lade`): fehlendes Modul = einzelner roter Test. */
export async function modul(datei: string): Promise<Json> {
	const pfad = path.join(D.WETTER_TAB, datei);
	if (!existsSync(pfad)) assert.fail(`TDD RED: shared/wetter-tab/${datei} fehlt`);
	return import(pathToFileURL(pfad).href);
}
/** Export eines Produktmoduls; fehlt er, roter Test mit klarer Meldung. */
export async function funktion(datei: string, name: string): Promise<Json> {
	const f = (await modul(datei))[name];
	assert.equal(typeof f, 'function', `TDD RED: ${datei} exportiert ${name} nicht`);
	return f;
}

/** Ein Versprechen, das der Test selbst einloest (Reihenfolge und Zwischenstand). */
export function tor<T = void>() {
	let auf!: (w: T) => void;
	let zu!: (e: unknown) => void;
	const versprechen = new Promise<T>((a, z) => ((auf = a), (zu = z)));
	return { versprechen, auf, zu };
}
export const tick = (ms = 10) => new Promise((r) => setTimeout(r, ms));
/** Wie ein Wert ueber die Leitung geht (ohne `undefined`). */
export const json = (x: Json): Json => JSON.parse(JSON.stringify(x));

export type Aufruf = { methode: string; pfad: string; rumpf?: Json };
export type Optionen = {
	createMode?: boolean;
	/** Antwort von GET /api/metric-presets. */
	presets?: Json;
	/** Ersatz fuer den Client-post (Standard: echtes Python). */
	post?: (pfad: string, rumpf: Json) => Promise<Json>;
	/** Echtes `api` fuer alles, was der Pruefstand nicht selbst beantwortet (Abo lesen, speichern). */
	netz?: Json;
	/** Weitere Saat (Controller, Hub-Schlange, Rueckrufe). */
	saat?: Json;
};

/** Baut den Reiter, ohne zu laden. */
export async function baue(context: Kontext, abo: Json, o: Optionen = {}) {
	const aufrufe: Aufruf[] = [];
	const gemeldet: Json[] = [];
	const updates: Json[] = [];
	let geplant = 0;
	const post = { f: o.post ?? echterPost };
	const daten: Record<string, Json> = {
		'/api/metrics': D.live().metrics,
		'/api/templates': D.live().templates,
		'/api/metric-presets': o.presets ?? []
	};
	const api = {
		get: async (pfad: string) => {
			aufrufe.push({ methode: 'GET', pfad });
			if (!(pfad in daten) && o.netz) return o.netz.get(pfad);
			if (!(pfad in daten)) throw new Error(`unerwartet: GET ${pfad}`);
			return structuredClone(daten[pfad]);
		},
		post: async (pfad: string, rumpf: Json) => {
			aufrufe.push({ methode: 'POST', pfad, rumpf: structuredClone(rumpf) });
			return post.f(pfad, rumpf);
		},
		put: async (pfad: string, rumpf: Json, init?: Json) => {
			aufrufe.push({ methode: 'PUT', pfad, rumpf: structuredClone(rumpf) });
			if (o.netz) return o.netz.put(pfad, rumpf, init);
			throw new Error(`unerwartet: PUT ${pfad}`);
		}
	};
	const { u, ast, quelle } = await umgebungFuer(TAB, {
		context,
		trip: context === 'route' ? abo : undefined,
		preset: context === 'vergleich' ? abo : undefined,
		createMode: o.createMode ?? false,
		saveController: { schedule: () => void geplant++ },
		enqueueHubWrite: undefined,
		onTripUpdate: (t: Json) => updates.push(t),
		onCompareUpdate: (p: Json) => updates.push(p),
		onAnlegeStand: (n: Json) => gemeldet.push(structuredClone(n)),
		api,
		...(o.saat ?? {})
	});
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
	return {
		u,
		aufrufe,
		/** Meldungen an die Anlege-Seite. */
		gemeldet,
		/** Uebernahmen an die Seite (onTripUpdate/onCompareUpdate). */
		updates,
		geplant: () => geplant,
		posts: () => aufrufe.filter((a) => a.methode === 'POST'),
		/** Schreibende Aufrufe: alles ausser GET und der Aufloesung. */
		schreibend: () => aufrufe.filter((a) => a.methode !== 'GET' && a.pfad !== AUFLOESUNG),
		setzePost: (f: NonNullable<Optionen['post']>) => void (post.f = f),
		laden: async () => {
			const zurueck = D.vergleichsKatalogFetch();
			try {
				await u.laden();
			} finally {
				zurueck();
			}
		},
		zahl: (): number => prop('abweichungen'),
		eigene: (): Json[] => prop('eigene'),
		aboAmpel: (): Json => prop('aboAmpel'),
		uebernehmen: (id: string) => handler('onUebernehmen')(id),
		eigeneUebernehmen: (id: string) => handler('onEigene')(id),
		zuruecksetzen: () => handler('onZuruecksetzen')(),
		gespeichert: (p: Json) => handler('onGespeichert')(p),
		grenze: (id: string, seite: 'lower' | 'upper', farbe: string, w: number) => {
			u.grenzenUmschalten(id);
			u.grenzWert(id, seite, farbe, w);
			assert.equal(u.fertig(), true, 'Messaufbau: Grenze ungueltig');
		}
	};
}
export type Reiter = Awaited<ReturnType<typeof baue>>;

/** Baut und laedt; der Reiter muss bereit sein. */
export async function oeffne(context: Kontext, abo: Json, o: Optionen = {}): Promise<Reiter> {
	const r = await baue(context, abo, o);
	await r.laden();
	assert.equal(r.u.phase, 'bereit', 'Reiter hat nicht geladen');
	return r;
}

// ── Referenz ────────────────────────────────────────────────────────────────

export const referenzLaden = (): Json => D.fixture('ampel_laden_referenz_2988.json');
const REF_VORLAGEN: Json = D.fixture('ampel_aufloesung_2988.json').vorlagen;
export const refVorlagen = (): Json => structuredClone(REF_VORLAGEN);

/** Vollstaendige Soll-Ampel aus der Kurzform (Vorlage + abweichende Zeilen). */
export function sollAmpel(s: Json): Json {
	const a = structuredClone(REF_VORLAGEN[s.vorlageId]);
	Object.assign(a.metrics, structuredClone(s.zeilen));
	a.thunder = structuredClone(s.thunder);
	a.template = s.vorlageId;
	return a;
}
