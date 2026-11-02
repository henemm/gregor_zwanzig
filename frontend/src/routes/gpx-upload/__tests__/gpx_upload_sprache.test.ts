// Issue #2657 (i18n F8, Epic #2644) — AC-5: die GPX-Upload-Seite spricht die
// Sprache des Nutzers. Echte SSR-Renders der Seite (svelte/server) in den Zustaenden
// Start, Vorschau (nach dem Hochladen), gespeichert und Fehler — die Zustaende,
// die die Seite erst im Klick-Handler setzt, lenkt der Pruefstand
// (layout-tab/__tests__/f8Pruefstand.ts, Hook f8VarianteHook.mjs) auf feste Werte.
// Hochladen und Speichern laufen ueber die echten Helfer der Seite (gpxTrip.ts);
// ersetzt ist nur die Netzgrenze (fetch). Der gespeicherte Trip traegt den vom
// Nutzer eingegebenen Namen unveraendert, in beiden Sprachen dieselbe Nutzlast.
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en.
// Spec: docs/specs/modules/i18n_f8_layout_korridor_2657.md
//
//   cd frontend && npm test -- src/routes/gpx-upload/__tests__/gpx_upload_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import { GPX_ETAPPE, GPX_SEITE, locale, trFor, gpxRendern } from '../../../lib/components/shared/layout-tab/__tests__/f8Pruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const gpxTrip = () => import(pathToFileURL(path.join(HERE, '..', 'gpxTrip.ts')).href);

afterEach(() => locale.set('de'));

const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<(?:"[^"]*"|'[^']*'|[^'">])*>/g, ' ').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 2500)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);

function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

const DEUTSCH = ['GPX hochladen', 'GPX-Datei', 'Datum (optional)', 'Startzeit', 'Hochladen', 'Etappen-Vorschau', 'Höhe', 'Zeitfenster', 'Als Trip speichern', 'Trip-Name', 'erfolgreich gespeichert', 'Zu den Trips', 'Lade eine'];

describe('AC-5: GPX-Seite englisch (Formular, Vorschau-Tabelle, Schaltflaechen)', () => {
	test('Start: Formular englisch, Datumsplatzhalter YYYY-MM-DD bleibt', () => {
		const { de, en } = deDannEn(() => gpxRendern());
		hat(sichtbar(de), 'GPX hochladen');
		const text = sichtbar(en);
		for (const s of ['Upload GPX', 'Import GPX file', 'Upload a GPX file to create a stage and a trip from it.', 'GPX file', 'Date (optional)', 'Start time (hour)', 'Upload']) hat(text, s);
		hat(de, 'placeholder="YYYY-MM-DD"');
		hat(en, 'placeholder="YYYY-MM-DD"');
		for (const s of DEUTSCH) hatNicht(text, s);
	});
	test('Vorschau nach dem Hochladen: Tabelle und Speichern englisch, Wegpunkte und Name unveraendert', () => {
		const { en } = deDannEn(() => gpxRendern({ parsedStage: GPX_ETAPPE, tripName: GPX_ETAPPE.name }));
		const text = sichtbar(en);
		for (const s of ['Stage preview', 'Name Lat Lon Elevation Time window', 'Calenzana 42.50812 8.85543 275 m 08:00-10:00', 'Ortu di u Piobbu', 'Save as trip', 'Trip name', 'GR20 Etappe 1 · 2026-06-01']) hat(text, s);
		hat(en, 'placeholder="Enter trip name"');
		hat(en, 'value="GR20 Etappe 1"');
		assert.equal((text.match(/Save as trip/g) ?? []).length, 2, 'Ueberschrift und Schaltflaeche');
		for (const s of DEUTSCH) hatNicht(text, s);
	});
	test('gespeichert: Erfolgsmeldung und Link englisch', () => {
		const { en } = deDannEn(() => gpxRendern({ parsedStage: GPX_ETAPPE, tripName: GPX_ETAPPE.name, savedTripId: 'gr20-etappe-1' }));
		const text = sichtbar(en);
		hat(text, 'Trip saved successfully.');
		hat(text, 'Go to trips');
		hatNicht(text, 'Save as trip Trip name');
		for (const s of DEUTSCH) hatNicht(text, s);
	});
	test('eigener Fehlerhinweis folgt der Sprache, Servertext bleibt unveraendert', async () => {
		const zeigen = async (ersetzungen: [string, string][]) => {
			const url = `${pathToFileURL(GPX_SEITE).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`;
			const Seite = (await import(url)).default;
			const { render } = await import('svelte/server');
			(globalThis as Record<string, unknown>).__F8_GPX = { parsedStage: null, tripName: '', savedTripId: null };
			try {
				return deDannEn(() => sichtbar(render(Seite as never, { props: {} } as never).body));
			} finally {
				delete (globalThis as Record<string, unknown>).__F8_GPX;
			}
		};
		const basis: [string, string][] = [
			['let parsedStage: ParsedStage | null = $state(null);', 'let parsedStage: ParsedStage | null = $state(globalThis.__F8_GPX.parsedStage);'],
			["let tripName: string = $state('');", 'let tripName: string = $state(globalThis.__F8_GPX.tripName);'],
			['let savedTripId: string | null = $state(null);', 'let savedTripId: string | null = $state(globalThis.__F8_GPX.savedTripId);']
		];
		const eigen = await zeigen([...basis, ['let errorKey: MessageKey | null = $state(null);', "let errorKey: MessageKey | null = $state('layout.gpx.fehler_nur_gpx');"]]);
		hat(eigen.de, 'Nur .gpx Dateien erlaubt.');
		hat(eigen.en, 'Only .gpx files are allowed.');
		const server = await zeigen([...basis, ['let error: string | null = $state(null);', "let error: string | null = $state('GPX ungültig: kein <trk>');"]]);
		hat(server.en, 'GPX ungültig: kein');
	});
});

/**
 * Seitenfluss (Adversary F001): die ECHTEN Handler handleUpload/handleSave laufen beim
 * Erzeugen der Seite; ersetzt ist nur die Netzgrenze (gpxHochladen/api.post werfen
 * synchron das Fehlerobjekt des Servers), damit der Fehlerzweig vor dem SSR-Render greift.
 */
async function seitenfluss(zustand: Record<string, unknown>, ausloesen: 'upload' | 'save') {
	const ersetzungen: [string, string][] = [
		['let parsedStage: ParsedStage | null = $state(null);', 'let parsedStage: ParsedStage | null = $state(globalThis.__F8_GPX.parsedStage);'],
		["let tripName: string = $state('');", 'let tripName: string = $state(globalThis.__F8_GPX.tripName);'],
		['let savedTripId: string | null = $state(null);', 'let savedTripId: string | null = $state(globalThis.__F8_GPX.savedTripId);'],
		['let fileList: FileList | undefined = $state(undefined);', 'let fileList: FileList | undefined = $state(globalThis.__F8_GPX.fileList);'],
		['const data = await gpxHochladen(fileList[0], stageDate, startHour);', 'const data = globalThis.__F8_GPX.hochladen(fileList[0]);'],
		["const result = await api.post<{ id: string }>('/api/trips', trip);", 'const result = globalThis.__F8_GPX.speichern(trip);'],
		['</script>', 'globalThis.__F8_GPX.ausloesen({ handleUpload, handleSave });\n</script>']
	];
	const url = `${pathToFileURL(GPX_SEITE).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`;
	const Seite = (await import(url)).default;
	const { render } = await import('svelte/server');
	const g = globalThis as Record<string, unknown>;
	const gespeichert: unknown[] = [];
	g.__F8_GPX = {
		parsedStage: null,
		tripName: '',
		savedTripId: null,
		fileList: [{ name: 'etappe1.gpx', size: 100 }],
		hochladen: () => {
			throw zustand.serverFehler ?? {};
		},
		speichern: (trip: unknown) => {
			gespeichert.push(trip);
			throw zustand.serverFehler ?? {};
		},
		ausloesen: (h: { handleUpload: () => void; handleSave: () => void }) => void (ausloesen === 'upload' ? h.handleUpload() : h.handleSave()),
		...zustand
	};
	try {
		return { ...deDannEn(() => sichtbar(render(Seite as never, { props: {} } as never).body)), gespeichert };
	} finally {
		delete g.__F8_GPX;
	}
}

describe('AC-5: Fehlerzweige im Seitenfluss (Hochladen, Speichern), erst de, dann en', () => {
	test('Hochladen scheitert ohne detail/error: eigener Hinweis je Sprache', async () => {
		const r = await seitenfluss({}, 'upload');
		hat(r.de, 'Fehler beim Hochladen der GPX-Datei.');
		hat(r.en, 'Failed to upload the GPX file.');
		hatNicht(r.en, 'Fehler beim Hochladen');
	});
	test('Hochladen scheitert mit Servertext: Text unveraendert in beiden Sprachen, kein eigener Hinweis', async () => {
		const r = await seitenfluss({ serverFehler: { detail: 'GPX ungültig: kein Track' } }, 'upload');
		hat(r.de, 'GPX ungültig: kein Track');
		hat(r.en, 'GPX ungültig: kein Track');
		hatNicht(r.en, 'Failed to upload');
	});
	test('Dateipruefung im Seitenfluss: falsche Endung je Sprache', async () => {
		const r = await seitenfluss({ fileList: [{ name: 'route.kml', size: 10 }] }, 'upload');
		hat(r.de, 'Nur .gpx Dateien erlaubt.');
		hat(r.en, 'Only .gpx files are allowed.');
	});
	test('Speichern mit ungueltigem Namen „!!!": Hinweis je Sprache, nichts gesendet', async () => {
		const r = await seitenfluss({ parsedStage: GPX_ETAPPE, tripName: '!!!' }, 'save');
		hat(r.de, 'Trip-Name muss mindestens einen Buchstaben oder eine Zahl enthalten.');
		hat(r.en, 'Trip name must contain at least one letter or number.');
		hatNicht(r.en, 'Trip-Name muss');
		assert.equal(r.gespeichert.length, 0);
	});
	test('Speichern scheitert ohne detail/error: eigener Hinweis je Sprache, Name unveraendert gesendet', async () => {
		const r = await seitenfluss({ parsedStage: GPX_ETAPPE, tripName: '  Mein Trip — GR20 Süd  ' }, 'save');
		hat(r.de, 'Fehler beim Speichern des Trips.');
		hat(r.en, 'Failed to save the trip.');
		hatNicht(r.en, 'Fehler beim Speichern');
		assert.equal(r.gespeichert.length, 2);
		for (const t of r.gespeichert as { name: string }[]) assert.equal(t.name, '  Mein Trip — GR20 Süd  ');
		assert.deepEqual(r.gespeichert[0], r.gespeichert[1]);
	});
	test('Speichern scheitert mit Servertext: Text unveraendert', async () => {
		const r = await seitenfluss({ parsedStage: GPX_ETAPPE, tripName: 'GR20', serverFehler: { error: 'trip exists' } }, 'save');
		hat(r.de, 'trip exists');
		hat(r.en, 'trip exists');
		hatNicht(r.en, 'Failed to save');
	});
});

describe('AC-5: Hochladen und Speichern ueber die echten Helfer, Trip-Name unveraendert', () => {
	test('Dateipruefung: Fehlerschluessel je Fall, Texte in beiden Sprachen', async () => {
		const { gpxDateiFehler } = await gpxTrip();
		const faelle: [unknown, string | null, string | null, string | null][] = [
			[undefined, 'layout.gpx.fehler_keine_datei', 'Bitte eine GPX-Datei auswählen.', 'Please select a GPX file.'],
			[{ name: 'gross.gpx', size: 10 * 1024 * 1024 + 1 }, 'layout.gpx.fehler_zu_gross', 'Datei zu groß (max. 10 MB).', 'File too large (max. 10 MB).'],
			[{ name: 'route.kml', size: 10 }, 'layout.gpx.fehler_nur_gpx', 'Nur .gpx Dateien erlaubt.', 'Only .gpx files are allowed.'],
			[{ name: 'Route.GPX', size: 10 * 1024 * 1024 }, null, null, null]
		];
		for (const [datei, key, de, en] of faelle) {
			const k = gpxDateiFehler(datei);
			assert.equal(k, key);
			if (k) {
				assert.equal(trFor('de', k), de);
				assert.equal(trFor('en', k), en);
			}
		}
	});

	test('Hochladen → Vorschau → Speichern: gleiche Nutzlast in de und en, Name exakt wie eingegeben', async () => {
		const { gpxHochladen, baueGpxTrip } = await gpxTrip();
		const echt = globalThis.fetch;
		const anfragen: { url: string; felder: [string, string][] }[] = [];
		globalThis.fetch = (async (u: string, init?: { body?: FormData }) => {
			anfragen.push({ url: String(u), felder: [...(init?.body?.entries() ?? [])].map(([k, v]) => [k, typeof v === 'string' ? v : `datei:${(v as File).name}`]) });
			return new Response(JSON.stringify(GPX_ETAPPE), { status: 200 });
		}) as unknown as typeof fetch;
		try {
			const lauf = async (lang: 'de' | 'en') => {
				locale.set(lang);
				const etappe = await gpxHochladen(new File(['<gpx/>'], 'etappe1.gpx'), '2026-06-01', 7);
				return baueGpxTrip('  Mein Trip — GR20 Süd  ', etappe);
			};
			const de = await lauf('de');
			const en = await lauf('en');
			assert.deepEqual(en, de);
			// Name exakt wie eingegeben: Randleerzeichen und Umlaute bleiben (Adversary F002).
			assert.equal(en.name, '  Mein Trip — GR20 Süd  ');
			assert.equal(de.name, '  Mein Trip — GR20 Süd  ');
			assert.equal(en.id, 'mein-trip-gr20-sd');
			assert.equal(en.stages[0].id, 'mein-trip-gr20-sd-t1');
			assert.equal(en.stages[0].name, 'GR20 Etappe 1');
			assert.deepEqual(en.stages[0].waypoints, GPX_ETAPPE.waypoints);
			assert.equal(anfragen.length, 2);
			assert.deepEqual(anfragen[0], anfragen[1]);
			assert.deepEqual(anfragen[0], { url: '/api/gpx/parse', felder: [['file', 'datei:etappe1.gpx'], ['stage_date', '2026-06-01'], ['start_hour', '7']] });
		} finally {
			globalThis.fetch = echt;
		}
	});

	test('Hochladen scheitert: Server-Fehlerobjekt wird unveraendert weitergereicht', async () => {
		const { gpxHochladen } = await gpxTrip();
		const echt = globalThis.fetch;
		globalThis.fetch = (async () => new Response(JSON.stringify({ detail: 'kein <trk>' }), { status: 422 })) as unknown as typeof fetch;
		try {
			await assert.rejects(gpxHochladen(new File(['x'], 'a.gpx'), '', 8), (e: unknown) => (e as { detail: string }).detail === 'kein <trk>');
			globalThis.fetch = (async () => new Response('kaputt', { status: 500 })) as unknown as typeof fetch;
			await assert.rejects(gpxHochladen(new File(['x'], 'a.gpx'), '', 8), (e: unknown) => (e as { error: string }).error === 'HTTP 500');
		} finally {
			globalThis.fetch = echt;
		}
	});
});
