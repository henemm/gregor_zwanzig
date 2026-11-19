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
const { eigeneVorlagen } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/wetter-tab/wetterTabLaden.ts')).href);
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
			assert.doesNotMatch(titel.join(' '), /\//, 'kein Schrägstrich mehr im Titel');
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
// AC-7: Speichern-Dialog
// ---------------------------------------------------------------------------------------------------------------
const dialogProps = (kind: string) => ({ open: true, kind, ampel: {}, onClose: noop, onSaved: noop });

describe('#3111 AC-7: Dialog „Als eigene Vorlage speichern“', () => {
	for (const kind of ['route', 'vergleich']) {
		test(`DE (${kind}): Label „Beschreibung (optional)“, beide Platzhalter, Speichern vor Abbrechen`, async () => {
			locale.set('de');
			const h = html(await lade(SPD), dialogProps(kind));
			const texte = eigeneTexte(h);
			assert.ok(texte.includes('Beschreibung (optional)'), JSON.stringify(texte));
			assert.match(h, /placeholder="z\.B\. Mallorca Frühling"/);
			assert.match(h, /placeholder="wofür die Vorlage gedacht ist"/);
			const submit = h.indexOf('data-testid="save-preset-submit"');
			const abbrechen = h.indexOf('>Abbrechen<');
			assert.ok(submit > 0 && abbrechen > 0, 'Knöpfe fehlen');
			assert.ok(submit < abbrechen, 'Speichern muss vor Abbrechen stehen');
		});
		test(`EN (${kind}): Label mit „optional“, englische Platzhalter, Speichern vor Abbrechen`, async () => {
			locale.set('en');
			const h = html(await lade(SPD), dialogProps(kind));
			assert.ok(eigeneTexte(h).some((t) => /^Description \(optional\)$/i.test(t)), JSON.stringify(eigeneTexte(h)));
			const ph = [...h.matchAll(/placeholder="([^"]*)"/g)].map((m) => m[1]);
			assert.equal(ph.length, 2, `zwei Platzhalter erwartet: ${JSON.stringify(ph)}`);
			assert.ok(ph.every((p) => p !== 'z.B. Mallorca Frühling' && p !== 'wofür die Vorlage gedacht ist'), 'EN-Platzhalter nicht übersetzt');
			assert.ok(h.indexOf('data-testid="save-preset-submit"') < h.indexOf('>Cancel<'), 'Save vor Cancel');
		});
	}
});
