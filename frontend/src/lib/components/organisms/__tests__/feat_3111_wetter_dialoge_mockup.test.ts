// TDD RED — Issue #3111 (Epic #2913): Wetter-Dialoge nach Mockup Fassung 4, Trip und Orte, DE und EN.
// Spec: docs/specs/modules/feat_3111_wetter_dialoge_mockup.md (AC-1 bis AC-8).
// Soll-Bild: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html Z. 356-357, 458-500.
//
// Server-Render der ECHTEN Dateien GrenzenEditor, VorlageKarte, SavePresetDialog (Muster
// wetter_tab_abschnitt_marker_2966.test.ts; offene Zustände über startzustandHook.mjs). Gelesen wird so wie der
// Elementlisten-Abgleich liest (frontend/e2e/elementliste-abgleich.staging.spec.ts:110-132, siehe
// docs/artifacts/feat-3111-wetter-dialoge-mockup/klaerung-textlesung.md): je Element die EIGENEN Textknoten,
// aneinandergehängt und im Leerraum vereinheitlicht. Folgen: `a<br>b` ergibt „ab“; Text in einem verschachtelten
// Kind-Element zählt als EIGENER Text, nicht zum Elternabsatz.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/organisms/__tests__/feat_3111_wetter_dialoge_mockup.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const SPD = path.resolve(HERE, '../../shared/weather-metrics-tab/SavePresetDialog.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { eigeneVorlagen, eigeneVorlageAus, ortAnzahlVon } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/wetter-tab/wetterTabLaden.ts')).href);
after(() => locale.set('de'));

const datei = (n: string) => path.join(WT, `${n}.svelte`);
async function lade(file: string, start: [string, string][] = []): Promise<any> {
	const abfrage = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(pathToFileURL(file).href + abfrage)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '').trim();
const noop = () => {};

const ENTITAETEN: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ' };
const entschluesseln = (s: string) => s.replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (m) => ENTITAETEN[m]);
const norm = (s: string) => s.replace(/\s+/g, ' ').trim();
const VOID = new Set(['br', 'input', 'img', 'hr', 'meta', 'link']);

/** Wie `sichtbareTexte()` des Abgleichs: je Element die eigenen Textknoten (br trennt NICHT), Eingaben als Platzhalter. */
function eigeneTexte(h: string): string[] {
	const aus: string[] = [];
	const stapel: { tag: string; text: string; versteckt: boolean }[] = [];
	const re = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>|([^<]+)/g;
	const schliesse = () => {
		const e = stapel.pop()!;
		if (!e.versteckt && norm(entschluesseln(e.text))) aus.push(norm(entschluesseln(e.text)));
	};
	for (let m = re.exec(h); m; m = re.exec(h)) {
		if (m[4] !== undefined) {
			if (stapel.length) stapel[stapel.length - 1].text += m[4];
			continue;
		}
		const [, zu, tag, attr] = m;
		if (zu) {
			while (stapel.length && stapel[stapel.length - 1].tag !== tag) schliesse();
			if (stapel.length) schliesse();
			continue;
		}
		const versteckt = /\saria-hidden="true"/.test(attr) || stapel.some((e) => e.versteckt);
		if (tag === 'input') {
			const p = attr.match(/\splaceholder="([^"]*)"/);
			if (p && !versteckt) aus.push(norm(entschluesseln(p[1])));
			continue;
		}
		if (VOID.has(tag) || /\/\s*$/.test(attr)) continue;
		stapel.push({ tag, text: '', versteckt });
	}
	while (stapel.length) schliesse();
	return aus;
}

/** Element (samt Inhalt) ab dem öffnenden Tag mit passendem data-testid. */
function elementMit(h: string, testid: string): string {
	const m = h.match(new RegExp(`<([a-z0-9]+)\\b[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m && m.index !== undefined, `Element mit data-testid="${testid}" fehlt`);
	const zaehler = new RegExp(`<${m![1]}\\b[^>]*>|</${m![1]}>`, 'g');
	zaehler.lastIndex = m!.index! + m![0].length;
	let tiefe = 1;
	for (let x = zaehler.exec(h); x; x = zaehler.exec(h)) {
		tiefe += x[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return h.slice(m!.index!, x.index + x[0].length);
	}
	throw new Error(`Element ${testid} nicht geschlossen`);
}

// ---------------------------------------------------------------------------------------------------------------
// AC-1 / AC-2: Grenzen-Editor
// ---------------------------------------------------------------------------------------------------------------
const GRENZEN = {
	id: 'wind', erlaubt: 'both', eintrag: undefined, gewitter: null, vorlageLabel: 'Alpen-Trekking', fehler: [],
	onWert: noop, onGewitter: noop,
};
const GRENZEN_TEXT = {
	de: { unten: 'untenzu wenig', oben: 'obenzu viel', satz: 'Grün ist alles zwischen „gelb unten“ und „gelb oben“. Ein leeres Feld heißt: auf dieser Seite keine Grenze. Abweichend von der Vorlage „Alpen-Trekking“.', ohne: 'Grün ist alles zwischen „gelb unten“ und „gelb oben“. Ein leeres Feld heißt: auf dieser Seite keine Grenze.' },
	en: { unten: 'lowertoo little', oben: 'uppertoo much' },
} as const;

describe('#3111 AC-1: Grenzen-Gruppentitel zweizeilig (zwei Textknoten mit <br>)', () => {
	for (const sprache of ['de', 'en'] as const) {
		test(`Titel „unten/oben“ steht als zwei Zeilen mit <br> (${sprache})`, async () => {
			locale.set(sprache);
			const h = html(await lade(datei('GrenzenEditor')), { ...GRENZEN, abweichend: false });
			const titel = [...h.matchAll(/<span class="wt-grp-name[^"]*"[^>]*>(.*?)<\/span>/g)].map((m) => m[1]);
			assert.equal(titel.length, 2, 'zwei Gruppentitel (unten, oben)');
			for (const t of titel) assert.match(t, /^[^<]+<br\s*\/?>[^<]+$/, `Titel muss „Zeile1<br>Zeile2“ sein, war: ${t}`);
			// Svelte-SSR schreibt leere Elemente als `<br/>`; geprüft wird der Schrägstrich im TEXT, nicht im Tag.
			assert.doesNotMatch(titel.join(' ').replace(/<br\s*\/?>/g, ''), /\//, 'kein Schrägstrich mehr im Titel');
			if (sprache === 'de') {
				assert.deepEqual(eigeneTexte(h).filter((t) => t === 'untenzu wenig' || t === 'obenzu viel'), ['untenzu wenig', 'obenzu viel']);
			} else {
				assert.ok(eigeneTexte(h).includes('lowertoo little') && eigeneTexte(h).includes('uppertoo much'), 'EN: zwei Zeilen lower / too little, upper / too much');
			}
		});
	}
});

describe('#3111 AC-2: Hinweis und Abweichend-Satz im selben Absatz, „…“-Anführungszeichen', () => {
	test('DE: ein einziger eigener Text des Hinweis-Elements enthält Hinweis UND Abweichend-Satz (so liest der Abgleich)', async () => {
		locale.set('de');
		const h = html(await lade(datei('GrenzenEditor')), { ...GRENZEN, abweichend: true });
		const absatz = elementMit(h, 'wetter-grenzen-hinweis-wind');
		assert.ok(eigeneTexte(absatz).includes(GRENZEN_TEXT.de.satz), `eigener Text des Absatzes ist nicht „${GRENZEN_TEXT.de.satz}“, sondern: ${JSON.stringify(eigeneTexte(absatz))}`);
	});
	test('DE: ohne Abweichung fehlt der Abweichend-Satz, der Hinweis bleibt mit „…“', async () => {
		locale.set('de');
		const h = html(await lade(datei('GrenzenEditor')), { ...GRENZEN, abweichend: false });
		assert.ok(eigeneTexte(h).includes(GRENZEN_TEXT.de.ohne));
		assert.doesNotMatch(h, /Abweichend von der Vorlage/);
		assert.doesNotMatch(h, /data-testid="wetter-grenzen-abweichend-wind"/);
	});
	test('EN: Abweichend-Satz im selben Absatz wie der Hinweis, englisch', async () => {
		locale.set('en');
		const h = html(await lade(datei('GrenzenEditor')), { ...GRENZEN, abweichend: true });
		const absatz = elementMit(h, 'wetter-grenzen-hinweis-wind');
		const eigen = eigeneTexte(absatz);
		assert.equal(eigen.length, 1, `Hinweis und Abweichend-Satz müssen ein Text sein, waren: ${JSON.stringify(eigen)}`);
		assert.match(eigen[0], /Alpen-Trekking/);
		assert.match(eigen[0], /empty field/i);
	});
	test('Gewitter: „keins“ ist immer grün mit „…“ und Abweichend-Satz im selben Absatz (Mockup Z. 458)', async () => {
		locale.set('de');
		const h = html(await lade(datei('GrenzenEditor')), { ...GRENZEN, id: 'thunder', gewitter: { mittel: 'yellow', hoch: 'orange' }, abweichend: true });
		assert.ok(eigeneTexte(h).includes('„keins“ ist immer grün. Abweichend von der Vorlage „Alpen-Trekking“.'), JSON.stringify(eigeneTexte(h)));
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-3 bis AC-6: Vorlagen-Menü und Bestätigung
// ---------------------------------------------------------------------------------------------------------------
const PICKER = 'let pickerOffen = $state(false);';
const WAHL = 'let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(null);';
const offen = [[PICKER, PICKER.replace('(false)', '(true)')]] as [string, string][];
const mitWahl = (w: string): [string, string][] => [...offen, [WAHL, WAHL.replace('(null)', `(${w})`)]];

const LISTE = [
	{ id: 'alpen-trekking', label: 'Alpen-Trekking', anzahl: 14, stichworte: ['thunder', 'gust', 'freezing_level'] },
	{ id: 'wandern', label: 'Wandern', anzahl: 10, stichworte: ['wind'] },
	{ id: 'neu-unbekannt', label: 'Neu', anzahl: 3, stichworte: ['wind', 'gust'] },
];
const EIGENE_ANTWORT = {
	presets: [
		{ id: 'e1', name: 'Mallorca Frühling', kind: 'route', description: 'für den Frühling', metrics: [] },
		{ id: 'e2', name: 'Ohne Text', kind: 'route', metrics: [] },
	],
};
const vorlageProps = (context: string, aktiv = 'alpen-trekking', abweichungen = 0) => ({
	context, vorlageId: aktiv, liste: LISTE, eigene: eigeneVorlagen(EIGENE_ANTWORT, 'route', { allgemein: { metrics: {} } }), abweichungen,
	metrikName: (id: string) => `<${id}>`, aboAmpel: {}, onUebernehmen: noop, onEigene: noop, onZuruecksetzen: noop, onGespeichert: noop,
});
const menue = async (sprache: 'de' | 'en', props: Record<string, unknown>, start = offen) => {
	locale.set(sprache);
	return html(await lade(datei('VorlageKarte'), start), props);
};

describe('#3111 AC-3: „· aktiv“ als Text an der aktiven Vorlage', () => {
	for (const [sprache, text] of [['de', 'Alpen-Trekking · aktiv'], ['en', 'Alpine trekking · active']] as const) {
		test(`${sprache}: aktive Vorlage „${text}“, keine andere trägt den Zusatz`, async () => {
			const h = await menue(sprache, vorlageProps('route'));
			assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-option-alpen-trekking')).includes(text), JSON.stringify(eigeneTexte(elementMit(h, 'wetter-vorlage-option-alpen-trekking'))));
			assert.doesNotMatch(elementMit(h, 'wetter-vorlage-option-wandern'), /aktiv|active/);
			assert.doesNotMatch(elementMit(h, 'wetter-vorlage-option-neu-unbekannt'), /aktiv|active/);
		});
	}
	test('Zusatz wandert mit der aktiven Vorlage (Wandern aktiv)', async () => {
		const h = await menue('de', vorlageProps('route', 'wandern'));
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-option-wandern')).includes('Wandern · aktiv'));
		assert.doesNotMatch(elementMit(h, 'wetter-vorlage-option-alpen-trekking'), /aktiv/);
	});
});

describe('#3111 AC-4: Kurzbeschreibung = Zahl aus Daten + kuratierte Stichworte; unbekannte ID: Ableitung', () => {
	for (const context of ['route', 'vergleich']) {
		test(`DE, ${context}: bekannte Systemvorlagen mit Katalog-Stichworten, unbekannte ID mit Ableitung`, async () => {
			const h = await menue('de', vorlageProps(context));
			assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-beschreibung-alpen-trekking')).includes('14 Metriken · Gewitter, Böen, Nullgradgrenze'), JSON.stringify(eigeneTexte(elementMit(h, 'wetter-vorlage-beschreibung-alpen-trekking'))));
			assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-beschreibung-wandern')).includes('10 Metriken · Regen, Sonne, UV'));
			assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-beschreibung-neu-unbekannt')).includes('3 Metriken · <wind> · <gust>'), 'Fallback: Ableitung aus den aktiven Metriken');
		});
	}
	test('EN: Zahl aus Daten, Stichworte englisch aus dem Katalog', async () => {
		const h = await menue('en', vorlageProps('route'));
		const t = eigeneTexte(elementMit(h, 'wetter-vorlage-beschreibung-alpen-trekking'))[0];
		assert.match(t, /^14 metrics · /i);
		assert.doesNotMatch(t, /Gewitter|Böen|Nullgradgrenze/, 'Stichworte nicht übersetzt');
		assert.doesNotMatch(t, /<thunder>/, 'bekannte Vorlage nutzt die kuratierten Stichworte, nicht die Ableitung');
	});
});

describe('#3111 AC-5: Unterzeile eigener Vorlagen „eigene“ (+ Beschreibung)', () => {
	test('DE: „eigene · für den Frühling“ bzw. nur „eigene“', async () => {
		const h = await menue('de', vorlageProps('route'));
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-e1')).includes('eigene · für den Frühling'), JSON.stringify(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-e1'))));
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-e2')).includes('eigene'), JSON.stringify(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-e2'))));
	});
	test('EN: „own · …“ bzw. „own“', async () => {
		const h = await menue('en', vorlageProps('route'));
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-e1')).includes('own · für den Frühling'));
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-e2')).includes('own'));
	});
});

describe('#3111 AC-6: Bestätigung zweiteilig, Übernehmen vor Abbrechen', () => {
	const WAHL_ALPIN = "({ id: 'wandern', name: 'Wandern', eigen: false })";
	test('DE Trip, mit Abweichungen: fetter Titel + EIN Rumpf-Text in Mockup-Reihenfolge', async () => {
		const h = await menue('de', vorlageProps('route', 'alpen-trekking', 2), mitWahl(WAHL_ALPIN));
		const dialog = elementMit(h, 'wetter-vorlage-wechsel-dialog');
		assert.match(dialog, /<b>„Wandern“ übernehmen\?<\/b>/, 'fetter Titel „„Wandern“ übernehmen?“ fehlt');
		const texte = eigeneTexte(dialog);
		assert.ok(texte.includes('„Wandern“ übernehmen?'), JSON.stringify(texte));
		assert.ok(
			texte.includes('Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips. Deine 2 Abweichungen von „Alpine trekking“ gehen verloren. Zustellung, Etappen und Orte bleiben unverändert.') ||
				texte.includes('Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips. Deine 2 Abweichungen von „Alpen-Trekking“ gehen verloren. Zustellung, Etappen und Orte bleiben unverändert.'),
			`Rumpf nicht als ein Text im Mockup-Wortlaut: ${JSON.stringify(texte)}`
		);
	});
	test('DE Trip ohne Abweichung: Rumpf ohne Verlust-Satz', async () => {
		const h = await menue('de', vorlageProps('route', 'alpen-trekking', 0), mitWahl(WAHL_ALPIN));
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-wechsel-dialog')).includes('Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips. Zustellung, Etappen und Orte bleiben unverändert.'));
	});
	test('DE Orte: Rumpf nennt „für diesen Ort“ bzw. „für diese Orte“, nicht „Orts-Briefings“', async () => {
		const h = await menue('de', vorlageProps('vergleich', 'alpen-trekking', 0), mitWahl(WAHL_ALPIN));
		const dialog = elementMit(h, 'wetter-vorlage-wechsel-dialog');
		assert.match(dialog, /<b>„Wandern“ übernehmen\?<\/b>/);
		assert.match(eigeneTexte(dialog).join(' | '), /Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen für dies(en Ort|e Orte)\. Zustellung, Etappen und Orte bleiben unverändert\./);
		assert.doesNotMatch(dialog, /Orts-Briefing/);
	});
	test('EN Trip: Titel und Rumpf getrennt, englisch', async () => {
		const h = await menue('en', vorlageProps('route', 'alpen-trekking', 1), mitWahl(WAHL_ALPIN));
		const dialog = elementMit(h, 'wetter-vorlage-wechsel-dialog');
		assert.match(dialog, /<b>[^<]*Hiking[^<]*<\/b>/, 'fetter Titel mit englischem Vorlagennamen');
		assert.ok(eigeneTexte(dialog).length >= 3, `Titel, Rumpf und Knopftexte erwartet: ${JSON.stringify(eigeneTexte(dialog))}`);
		assert.doesNotMatch(dialog, /Ersetzt|übernehmen|Zustellung/);
	});
	test('Übernehmen steht vor Abbrechen', async () => {
		const h = await menue('de', vorlageProps('route', 'alpen-trekking', 0), mitWahl(WAHL_ALPIN));
		const dialog = elementMit(h, 'wetter-vorlage-wechsel-dialog');
		assert.ok(dialog.indexOf('wetter-vorlage-wechsel-uebernehmen') < dialog.indexOf('wetter-vorlage-wechsel-abbrechen'));
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-6 (Fix-Loop 1, F001/F002): Orte-Rumpf Einzahl/Mehrzahl — an der Karte UND über den Hub (WetterTabInhalt)
// ---------------------------------------------------------------------------------------------------------------
const RUMPF_ORTE = {
	de: {
		ein: 'Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen für diesen Ort. Zustellung, Etappen und Orte bleiben unverändert.',
		mehr: 'Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen für diese Orte. Zustellung, Etappen und Orte bleiben unverändert.',
	},
	en: {
		ein: 'Replaces the metric selection, traffic-light limits and alert levels for this location. Delivery, stages and locations stay unchanged.',
		mehr: 'Replaces the metric selection, traffic-light limits and alert levels for these locations. Delivery, stages and locations stay unchanged.',
	},
} as const;
const WAHL_WANDERN = "({ id: 'wandern', name: 'Wandern', eigen: false })";

describe('#3111 AC-6 (F001): Orte-Rumpf an der Karte — ein Ort Einzahl, mehrere Orte Mehrzahl', () => {
	for (const sprache of ['de', 'en'] as const) {
		for (const [anzahl, form] of [[1, 'ein'], [3, 'mehr']] as const) {
			test(`${sprache}, ortAnzahl=${anzahl}: Rumpf „${RUMPF_ORTE[sprache][form]}“`, async () => {
				const h = await menue(sprache, { ...vorlageProps('vergleich', 'alpen-trekking', 0), ortAnzahl: anzahl }, mitWahl(WAHL_WANDERN));
				const texte = eigeneTexte(elementMit(h, 'wetter-vorlage-wechsel-dialog'));
				assert.ok(texte.includes(RUMPF_ORTE[sprache][form]), JSON.stringify(texte));
				assert.ok(!texte.includes(RUMPF_ORTE[sprache][form === 'ein' ? 'mehr' : 'ein']), 'falsche Form zusätzlich');
			});
		}
	}
});

describe('#3111 AC-6 (F002): Hub-Verdrahtung — Ortezahl aus location_ids erreicht die Bestätigung', () => {
	// Hub im Zustand „bereit“ mit offenem Menü und gewählter Vorlage: WetterTabInhalt (Startwerte über den Hook),
	// die Karte über denselben Hook am Import. Alles andere ist Produktcode.
	const KARTE_START = JSON.stringify(mitWahl(WAHL_WANDERN));
	const HUB_START: [string, string][] = [
		["$state<'laedt' | 'fehler' | 'bereit'>('laedt')", "$state<'laedt' | 'fehler' | 'bereit'>('bereit')"],
		[
			'let daten = $state<WetterDaten | null>(null);',
			"let daten = $state<WetterDaten | null>({ eig: {}, vorlagen: { 'alpen-trekking': { metrics: {} }, wandern: { metrics: {} } }, liste: [{ id: 'alpen-trekking', label: 'Alpen-Trekking', anzahl: 0, stichworte: [] }, { id: 'wandern', label: 'Wandern', anzahl: 0, stichworte: [] }], eigene: [] });",
		],
		[
			'let stand = $state<Z.WetterStand | null>(null);',
			"let stand = $state<Z.WetterStand | null>({ vorlageId: 'alpen-trekking', ampel: { template: 'alpen-trekking', metrics: {} }, auswahl: [], warnungenAn: false, radarAn: false, tagesfenster: { start: 6, end: 20 } });",
		],
		// Absolute file-URL: der relative Auflöser des SSR-Hooks würde an eine Abfrage „.ts“ anhängen.
		["import VorlageKarte from './VorlageKarte.svelte';", `import VorlageKarte from '${pathToFileURL(datei('VorlageKarte')).href}?start=${encodeURIComponent(KARTE_START).replace(/'/g, '%27')}';`],
	];
	for (const sprache of ['de', 'en'] as const) {
		for (const [ids, form] of [[['o1'], 'ein'], [['o1', 'o2', 'o3'], 'mehr']] as const) {
			test(`${sprache}, Orte-Briefing mit ${ids.length} Ort(en): Rumpf in der ${form === 'ein' ? 'Einzahl' : 'Mehrzahl'}`, async () => {
				locale.set(sprache);
				const h = html(await lade(datei('WetterTabInhalt'), HUB_START), { context: 'vergleich', preset: { id: 'p1', name: 'Orte', location_ids: [...ids] } });
				const texte = eigeneTexte(elementMit(h, 'wetter-vorlage-wechsel-dialog'));
				assert.ok(texte.includes(RUMPF_ORTE[sprache][form]), JSON.stringify(texte));
			});
		}
	}
	test('ortAnzahlVon: Länge von location_ids, ohne Liste undefined', () => {
		assert.equal(ortAnzahlVon({ location_ids: ['a'] }), 1);
		assert.equal(ortAnzahlVon({ location_ids: ['a', 'b', 'c'] }), 3);
		assert.equal(ortAnzahlVon({}), undefined);
		assert.equal(ortAnzahlVon(undefined), undefined);
	});
});

describe('#3111 AC-5 (F002): frisch gespeicherte eigene Vorlage behält ihre Beschreibung', () => {
	// Laden UND „gespeichert“ im Hub (WetterTabInhalt.vorlageGespeichert) bilden die Karte über eigeneVorlageAus.
	test('mit Beschreibung: beschreibung gesetzt, Unterzeile „eigene · …“ in der Karte', async () => {
		const e = eigeneVorlageAus({ id: 'n1', name: 'Neu', kind: 'route', description: 'für Mallorca', metrics: [] }, { allgemein: { metrics: {} } });
		assert.equal(e.beschreibung, 'für Mallorca');
		const h = await menue('de', { ...vorlageProps('route'), eigene: [e] });
		assert.ok(eigeneTexte(elementMit(h, 'wetter-vorlage-eigene-n1')).includes('eigene · für Mallorca'));
	});
	test('ohne Beschreibung: kein beschreibung-Feld', () => {
		const e = eigeneVorlageAus({ id: 'n2', name: 'Neu', kind: 'route', metrics: [] }, { allgemein: { metrics: {} } });
		assert.equal('beschreibung' in e, false);
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-7: Speichern-Dialog
// ---------------------------------------------------------------------------------------------------------------
/** Wert des Attributs `placeholder` (mit Attribut-Grenze) am öffnenden Tag des Felds mit `data-testid`. */
function platzhalterVon(h: string, testid: string): string | null {
	const tag = h.match(new RegExp(`<(?:input|textarea)\\b[^>]*\\sdata-testid="${testid}"[^>]*>`));
	assert.ok(tag, `Feld ${testid} fehlt`);
	const m = tag![0].match(/\splaceholder="([^"]*)"/);
	return m ? entschluesseln(m[1]) : null;
}
const dialogProps = (kind: string) => ({ open: true, kind, ampel: {}, onClose: noop, onSaved: noop });

describe('#3111 AC-7: Dialog „Als eigene Vorlage speichern“', () => {
	for (const kind of ['route', 'vergleich']) {
		test(`DE (${kind}): Label „Beschreibung (optional)“, beide Platzhalter, Speichern vor Abbrechen`, async () => {
			locale.set('de');
			const h = html(await lade(SPD), dialogProps(kind));
			const texte = eigeneTexte(h);
			assert.ok(texte.includes('Beschreibung (optional)'), JSON.stringify(texte));
			// Attribut-Grenze (F003): das Attribut `placeholder` am richtigen Feld, nicht irgendein `…placeholder=`.
			assert.equal(platzhalterVon(h, 'save-preset-name'), 'z.B. Mallorca Frühling');
			assert.equal(platzhalterVon(h, 'save-preset-description'), 'wofür die Vorlage gedacht ist');
			const submit = h.indexOf('data-testid="save-preset-submit"');
			const abbrechen = h.indexOf('>Abbrechen<');
			assert.ok(submit > 0 && abbrechen > 0, 'Knöpfe fehlen');
			assert.ok(submit < abbrechen, 'Speichern muss vor Abbrechen stehen');
		});
		test(`EN (${kind}): Label mit „optional“, englische Platzhalter, Speichern vor Abbrechen`, async () => {
			locale.set('en');
			const h = html(await lade(SPD), dialogProps(kind));
			assert.ok(eigeneTexte(h).some((t) => /^Description \(optional\)$/i.test(t)), JSON.stringify(eigeneTexte(h)));
			assert.equal(platzhalterVon(h, 'save-preset-name'), 'e.g. Mallorca spring');
			assert.equal(platzhalterVon(h, 'save-preset-description'), 'what the template is meant for');
			assert.ok(h.indexOf('data-testid="save-preset-submit"') < h.indexOf('>Cancel<'), 'Save vor Cancel');
		});
	}
});
