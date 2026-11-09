// TDD RED — Issue #2837 Scheibe S2 (Epic #2345, ADR-0110): geteilter Anlege-Rahmen
// `AnlegeRahmen` für /trips/new (`context="route"`) und /compare/new (`context="vergleich"`).
// Spec: docs/specs/modules/rework_2837_s2_anlege_rahmen.md
//   Entscheidungen 1 (Breadcrumb Elternteil Link, Kind kein Link), 3 (Eyebrow „Neuer Trip" /
//   „Neuer Vergleich"), 4 (Abbrechen `Btn ghost` unten links im Fuß), 5 (Hauptaktion
//   `Btn primary` unten rechts, gesperrt ohne Abschluss), 6 (Standardwerte im Fuß), 7 (Weiter
//   `Btn accent`, gesperrt allein über `disabled`).
//   AC-1, AC-4, AC-5, AC-8, AC-9, AC-10, AC-11 (Struktur-Anteil), AC-14, AC-15 (Baustein-Anteil).
//
// Echte Komponente, serverseitig gerendert (svelte/server, Hooks über infoboxSsr.ts) — kein
// Mock, kein Datei-Grep. Lage-Zusicherungen über den Element-Baum des SSR-Outputs
// (htmlBaum.ts aus S1). Farbe, Pixel-Lage, Klickwirkung und Sticky-Verhalten prüft die E2E
// frontend/e2e/anlege-rahmen-paritaet.spec.ts im echten Browser.
//
// Vertrag (Spec „Implementation Details" Schritt 2; mit * markierte Namen von RED festgelegt):
//   context ('route' | 'vergleich'), name*, onCancel? (Trip), cancelHref, abschlussLabel,
//   abschlussTestid* (Trip `trip-new-save-btn`, Vergleich `compare-editor-activate`, AC-16),
//   canFinish, onFinish, testidPrefix ('tn' | 'cm' ⇒ Fuß `${testidPrefix}-desktop-footer`,
//   AC-16: `tn-desktop-footer` bleibt, `cm-desktop-footer` neu), navClearance;
//   Snippets hinweis, standardwerte, children.
//   #2837 S2b (Spec rework_2837_s2b_anlege_fortschritt.md, Entscheidung 4, AC-10): der Snippet-
//   Slot `fortschritt` entfällt; der Rahmen nimmt `steps` (readonly string[]), `done` (number,
//   Ergebnis von `progressCount`) und `aktiv?` entgegen und rendert `AnlegeFortschritt
//   variante="desktop"` selbst im Kopf — Testid je Art `trip-new-progress` /
//   `compare-editor-progress`, Segmente `${…}-segment` mit data-done. Ein trotzdem übergebenes
//   `fortschritt`-Snippet wird NICHT gerendert.
//   Texte (Katalog): Elternteil `listen.trips.titel` / `listen.vergleiche.titel`,
//   Eyebrow = Kind des Breadcrumbs „Neuer Trip" / „Neuer Vergleich" (en „New trip" /
//   „New comparison"), Abbrechen `aktionen.abbrechen`, h1 Name oder `trip.anlegen.kein_name`.
//   Der mobile Kopf ist hier NICHT festgelegt (Editor-Tests + E2E AC-3 prüfen ihn); alle
//   Desktop-Zusicherungen schließen deshalb `[data-slot="page-header"]` aus.
//
// RED HEUTE: `shared/anlege-rahmen/AnlegeRahmen.svelte` existiert nicht (Import erst in
// `lade()`, damit jeder Test einzeln mit eigener Meldung scheitert); die Weiter-Knöpfe der
// Editoren sind heute roher <button> bzw. `quiet` mit Inline-Deckkraft (AC-11).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { lade as ladeRel, renderKomponente, renderTrip, renderVergleichNeu, FRONTEND } from '../../__tests__/infoboxSsr.ts';
import { baum, alle, einzig, mitTestid, text, liegtIn, vorfahren, type Knoten } from '../../hub-kopf/__tests__/htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PRUEFLING = path.join(HERE, '..', 'AnlegeRahmen.svelte');

const { createRawSnippet } = await import('svelte');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

async function lade(): Promise<unknown> {
	return (await import(pathToFileURL(PRUEFLING).href)).default;
}

afterEach(() => locale.set('de'));

type Ctx = 'route' | 'vergleich';
type Lang = 'de' | 'en';
const roh = (html: string) => createRawSnippet(() => ({ render: () => html }));

/** Whitelist-Werte je Art (Spec „Whitelist" Nr. 2 und 5) — feste Soll-Texte, nicht aus dem Produkt. */
const ART: Record<Ctx, { liste: string; elternKey: string; neu: Record<Lang, string>; prefix: string; abschlussTestid: string; abschlussKey: string }> = {
	route: {
		liste: '/trips',
		elternKey: 'listen.trips.titel',
		neu: { de: 'Neuer Trip', en: 'New trip' },
		prefix: 'tn',
		abschlussTestid: 'trip-new-save-btn',
		abschlussKey: 'trip.anlegen.speichern'
	},
	vergleich: {
		liste: '/compare',
		elternKey: 'listen.vergleiche.titel',
		neu: { de: 'Neuer Vergleich', en: 'New comparison' },
		prefix: 'cm',
		abschlussTestid: 'compare-editor-activate',
		abschlussKey: 'vergleich.neu.aktivieren'
	}
};

const FUSS = (c: Ctx) => `${ART[c].prefix}-desktop-footer`;
/** #2837 S2b: Testid des Desktop-Fortschritts je Art (Spec Implementation Details 4) — fester Wert. */
const FORTSCHRITT: Record<Ctx, string> = { route: 'trip-new-progress', vergleich: 'compare-editor-progress' };
/** Fünf Pflicht-Schritte je Art (Spec AN-2) — feste Werte, nicht aus dem Produkt. */
const SCHRITTE: Record<Ctx, readonly string[]> = {
	route: ['route', 'etappen', 'wetter-metriken', 'wertebereiche', 'alarme'],
	vergleich: ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme']
};

function props(context: Ctx, extra: Record<string, unknown> = {}, lang: Lang = 'de'): Record<string, unknown> {
	const a = ART[context];
	return {
		context,
		name: '',
		...(context === 'route' ? { onCancel: () => {} } : {}),
		cancelHref: a.liste,
		abschlussLabel: trFor(lang, a.abschlussKey),
		abschlussTestid: a.abschlussTestid,
		canFinish: false,
		onFinish: () => {},
		testidPrefix: a.prefix,
		navClearance: false,
		steps: SCHRITTE[context],
		done: 0,
		aktiv: SCHRITTE[context][0],
		hinweis: roh('<span data-testid="probe-hinweis">Hinweis</span>'),
		standardwerte: roh('<button type="button" data-testid="probe-standardwerte">Std</button>'),
		// #2837 S2b: der Slot entfällt — die Probe bleibt übergeben und darf NICHT erscheinen.
		fortschritt: roh('<div data-testid="probe-fortschritt">0/5</div>'),
		children: roh('<div data-testid="probe-inhalt">Inhalt</div>'),
		...extra
	};
}

async function render_(p: Record<string, unknown>): Promise<{ html: string; wurzel: Knoten }> {
	const Komponente = await lade();
	const html = renderKomponente(Komponente, p);
	return { html, wurzel: baum(html) };
}

const imMobilKopf = (n: Knoten) => [n, ...vorfahren(n)].some((v) => v.attrs['data-slot'] === 'page-header');
const desktop = (w: Knoten, pred: (n: Knoten) => boolean) => alle(w, (n) => pred(n) && !imMobilKopf(n));

function h1(w: Knoten): Knoten {
	const t = desktop(w, (n) => n.tag === 'h1');
	assert.equal(t.length, 1, `genau eine Desktop-Überschrift erwartet, gefunden ${t.length}`);
	return t[0];
}

/** Elternteil-Link des Desktop-Breadcrumbs: <a href=Liste> mit Katalogtext, außerhalb von Fuß und Mobil-Kopf. */
function elternLink(w: Knoten, context: Ctx, lang: Lang = 'de'): Knoten {
	const fuss = einzig(w, FUSS(context));
	const label = trFor(lang, ART[context].elternKey);
	const links = desktop(w, (n) => n.tag === 'a' && n.attrs.href === ART[context].liste && !liegtIn(n, fuss));
	assert.equal(links.length, 1, `genau ein Breadcrumb-Link auf ${ART[context].liste} erwartet, gefunden ${links.length}`);
	assert.equal(text(links[0]), label, `Elternteil-Text muss der Katalogtext „${label}" sein`);
	return links[0];
}

function abbrechen(w: Knoten, context: Ctx, lang: Lang = 'de'): Knoten {
	const fuss = einzig(w, FUSS(context));
	const soll = trFor(lang, 'aktionen.abbrechen');
	const t = alle(w, (n) => n.attrs['data-slot'] === 'btn' && text(n) === soll);
	assert.equal(t.length, 1, `genau ein Btn „${soll}" erwartet, gefunden ${t.length}`);
	assert.ok(liegtIn(t[0], fuss), `„${soll}" steht nicht im Fuß ${FUSS(context)}`);
	return t[0];
}

for (const context of ['route', 'vergleich'] as const) {
	const a = ART[context];

	describe(`#2837 S2 AnlegeRahmen (${context}) — Kopf, Eyebrow, Titel`, () => {
		test(`Entscheidung 1/AC-14 (${context}): data-kind="${context}" über Fuß UND Überschrift`, async () => {
			const { wurzel } = await render_(props(context));
			for (const k of [einzig(wurzel, FUSS(context)), h1(wurzel)]) {
				const marke = [k, ...vorfahren(k)].find((n) => n.attrs['data-kind'] !== undefined);
				assert.ok(marke, `kein data-kind über <${k.tag}>`);
				assert.equal(marke.attrs['data-kind'], context);
			}
		});

		test(`AC-1 (${context}): Breadcrumb — Elternteil „${trFor('de', a.elternKey)}" ist Link auf ${a.liste}, Kind „${a.neu.de}" kein Link, steht vor der Überschrift`, async () => {
			const { wurzel } = await render_(props(context));
			const link = elternLink(wurzel, context);
			const krumen = link.eltern!;
			assert.ok(text(krumen).includes(a.neu.de), `Kind „${a.neu.de}" fehlt im Breadcrumb: „${text(krumen)}"`);
			assert.ok(!text(link).includes(a.neu.de), 'das Kind darf nicht Teil des Links sein');
			assert.equal(alle(krumen, (n) => n.tag === 'a').length, 1, 'im Breadcrumb darf nur der Elternteil verlinkt sein');
			assert.ok(link.nr < h1(wurzel).nr, 'Breadcrumb muss oben stehen (vor dem Titel)');
		});

		test(`AC-4 (${context}): genau ein Desktop-Eyebrow „${a.neu.de}" zwischen Breadcrumb und Überschrift, nie „Neue Trip"`, async () => {
			const { html, wurzel } = await render_(props(context));
			const eb = desktop(wurzel, (n) => n.attrs['data-slot'] === 'eyebrow');
			assert.equal(eb.length, 1, `genau ein Desktop-Eyebrow erwartet, gefunden ${eb.length}`);
			assert.equal(text(eb[0]), a.neu.de);
			assert.ok(elternLink(wurzel, context).nr < eb[0].nr && eb[0].nr < h1(wurzel).nr, 'Eyebrow steht nicht zwischen Breadcrumb und Titel');
			assert.ok(!/Neue Trip(?!s)/.test(html.replace(/Neuer Trip/g, '')), '„Neue Trip" steht im Rahmen');
		});

		test(`Titel (${context}): h1 = Name, ohne Namen der Katalogtext „kein Name"`, async () => {
			const ohne = await render_(props(context));
			assert.equal(text(h1(ohne.wurzel)), trFor('de', 'trip.anlegen.kein_name'));
			const mit = await render_(props(context, { name: 'Dolomiten Süd' }));
			assert.equal(text(h1(mit.wurzel)), 'Dolomiten Süd');
		});

		test(`Aufbau (${context}): Überschrift → Fortschritt (${FORTSCHRITT[context]}, vom Rahmen selbst) → Inhalt → Fuß`, async () => {
			const { wurzel } = await render_(props(context));
			const f = einzig(wurzel, FORTSCHRITT[context]);
			const i = einzig(wurzel, 'probe-inhalt');
			const fuss = einzig(wurzel, FUSS(context));
			assert.ok(h1(wurzel).nr < f.nr && f.nr < i.nr && i.nr < fuss.nr, 'Reihenfolge Titel/Fortschritt/Inhalt/Fuß falsch');
			assert.ok(!liegtIn(i, fuss) && !liegtIn(f, fuss), 'Inhalt/Fortschritt stehen im Fuß');
		});

		test(`S2b AC-10 (${context}): kein Snippet-Slot fortschritt mehr — übergebene Probe erscheint nicht`, async () => {
			const { wurzel } = await render_(props(context));
			assert.equal(mitTestid(wurzel, 'probe-fortschritt').length, 0, 'Rahmen rendert noch das Snippet `fortschritt`');
		});

		for (const done of [0, 2]) {
			test(`S2b AC-1/AC-10 (${context}, done=${done}): Rahmen zeichnet ${FORTSCHRITT[context]} mit 5 Segmenten, die ersten ${done} erledigt, Zähler aus dem Katalog`, async () => {
				const { wurzel } = await render_(props(context, { done, aktiv: SCHRITTE[context][Math.min(done, 4)] }));
				const f = einzig(wurzel, FORTSCHRITT[context]);
				assert.ok(!imMobilKopf(f), 'Fortschritt steht im mobilen Kopf statt im Desktop-Kopf');
				const seg = mitTestid(wurzel, `${FORTSCHRITT[context]}-segment`);
				assert.equal(seg.length, 5, `${FORTSCHRITT[context]}-segment: ${seg.length}× (erwartet 5)`);
				for (const s of seg) assert.ok(liegtIn(s, f), 'Segment außerhalb des Fortschritts-Containers');
				assert.deepEqual(seg.map((s) => s.attrs['data-done']), [0, 1, 2, 3, 4].map((i) => String(i < done)));
				const zaehler = f.kinder[f.kinder.length - 1];
				assert.equal(zaehler?.tag, 'span', 'Zähler ist nicht das letzte Kind (<span class="mono">)');
				const soll = done === 0 ? trFor('de', 'trip.anlegen.nichts_eingerichtet') : trFor('de', 'trip.anlegen.abschnitte', { n: done, gesamt: 5 });
				assert.equal(text(zaehler), soll);
			});
		}
	});

	describe(`#2837 S2 AnlegeRahmen (${context}) — Fuß`, () => {
		test(`AC-16 (${context}): Fuß ${FUSS(context)} ist der geteilte EditorStickyFooter (data-context, ohne Tabbar-Abstand)`, async () => {
			const { wurzel } = await render_(props(context));
			const fuss = einzig(wurzel, FUSS(context));
			assert.equal(fuss.attrs['data-context'], context);
			assert.ok((fuss.attrs.class ?? '').split(/\s+/).includes('editor-sticky-footer'), 'Fuß ist kein EditorStickyFooter');
			assert.ok(!(fuss.attrs.class ?? '').split(/\s+/).includes('has-nav'), 'navClearance=false wird nicht durchgereicht');
		});

		test(`AC-5 (${context}): „Abbrechen" ist Btn ghost im Fuß, VOR allen Aktionen rechts (Standardwerte, Hinweis, Hauptaktion)`, async () => {
			const { wurzel } = await render_(props(context));
			const ab = abbrechen(wurzel, context);
			assert.equal(ab.attrs['data-variant'], 'ghost', `Abbrechen hat variant „${ab.attrs['data-variant']}" (erwartet ghost)`);
			for (const id of ['probe-standardwerte', 'probe-hinweis', a.abschlussTestid]) {
				assert.ok(ab.nr < einzig(wurzel, id).nr, `Abbrechen steht nicht links von ${id}`);
			}
		});

		test(`Entscheidung 4 (${context}): Abbrechen ${context === 'route' ? 'ist ein Knopf (onCancel, kein href-Sprung am Autosave vorbei)' : `führt auf ${a.liste}`}`, async () => {
			const { wurzel } = await render_(props(context));
			const ab = abbrechen(wurzel, context);
			if (context === 'route') assert.equal(ab.tag, 'button', 'Trip-Abbrechen muss onCancel auslösen (Button), sonst greift das Autosave');
			else assert.equal(ab.attrs.href, a.liste);
		});

		test(`AC-10 (${context}): Standardwerte und Hinweis stehen im Fuß, nicht im Kopf`, async () => {
			const { wurzel } = await render_(props(context));
			const fuss = einzig(wurzel, FUSS(context));
			for (const id of ['probe-standardwerte', 'probe-hinweis']) {
				assert.ok(liegtIn(einzig(wurzel, id), fuss), `${id} steht nicht im Fuß`);
				assert.ok(einzig(wurzel, id).nr > h1(wurzel).nr, `${id} steht über dem Titel`);
			}
		});

		test(`AC-8 (${context}): Hauptaktion ${a.abschlussTestid} ist Btn primary im Fuß, nach Standardwerten und Hinweis, Text = abschlussLabel`, async () => {
			const { wurzel } = await render_(props(context, { canFinish: true }));
			const fuss = einzig(wurzel, FUSS(context));
			const h = einzig(wurzel, a.abschlussTestid);
			assert.ok(liegtIn(h, fuss), 'Hauptaktion steht nicht im Fuß');
			assert.equal(h.tag, 'button');
			assert.equal(h.attrs['data-slot'], 'btn', 'Hauptaktion ist kein Btn');
			assert.equal(h.attrs['data-variant'], 'primary', `Hauptaktion hat variant „${h.attrs['data-variant']}" (erwartet primary = Ink)`);
			assert.equal(text(h), trFor('de', a.abschlussKey));
			assert.ok(einzig(wurzel, 'probe-standardwerte').nr < h.nr && einzig(wurzel, 'probe-hinweis').nr < h.nr, 'Hauptaktion steht nicht ganz rechts');
			assert.equal(mitTestid(wurzel, a.abschlussTestid).length, 1);
		});

		test(`AC-9 (${context}): ohne canFinish gesperrt (disabled), Variante bleibt primary, Platz bleibt gleich`, async () => {
			const frei = await render_(props(context, { canFinish: true }));
			const zu = await render_(props(context, { canFinish: false }));
			const hf = einzig(frei.wurzel, a.abschlussTestid);
			const hz = einzig(zu.wurzel, a.abschlussTestid);
			assert.ok(!('disabled' in hf.attrs), 'Hauptaktion trotz canFinish gesperrt');
			assert.ok('disabled' in hz.attrs, 'Hauptaktion ohne canFinish nicht disabled');
			assert.equal(hz.attrs['data-variant'], 'primary', 'gesperrte Hauptaktion wechselt die Variante (Abblenden nur über disabled)');
			assert.ok(!/opacity/.test(hz.attrs.style ?? ''), `Inline-Deckkraft an der gesperrten Hauptaktion: ${hz.attrs.style}`);
		});
	});
}

describe('#2837 S2 AC-14 — ein Markup, context wählt nur Texte, Elternteil-Link, data-kind und Testids', () => {
	/** Gerüst: Tag + Klassen + style + data-slot/-variant + ob testid/href vorhanden; Texte und Werte von href/testid weg. */
	const geruest = (w: Knoten): string[] =>
		alle(w, () => true).map(
			(n) =>
				`${n.tag}|${n.attrs.class ?? ''}|${n.attrs.style ?? ''}|${n.attrs['data-slot'] ?? ''}|${n.attrs['data-variant'] ?? ''}|${'data-testid' in n.attrs}|${'href' in n.attrs}|${'disabled' in n.attrs}`
		);
	/** Gleiche Nicht-context-Props für beide Arten: der EINZIGE Unterschied ist context. */
	const gleich = (context: Ctx, extra: Record<string, unknown> = {}) =>
		props('route', { context, cancelHref: '/x', testidPrefix: 'tn', abschlussLabel: 'Fertig', ...extra });

	for (const canFinish of [false, true]) {
		test(`route und vergleich rendern dasselbe Gerüst (canFinish=${canFinish})`, async () => {
			const r = await render_(gleich('route', { canFinish }));
			const v = await render_(gleich('vergleich', { canFinish }));
			assert.deepEqual(geruest(v.wurzel), geruest(r.wurzel));
		});
	}

	test('kompiliertes CSS des Rahmens: kein Selektor nach data-kind oder nach Art benannten Klassen', async () => {
		const { compile } = await import('svelte/compiler');
		await lade(); // Existenz zuerst, sonst wäre der Fehler unten ein ENOENT ohne Bezug
		const css = (compile(readFileSync(PRUEFLING, 'utf-8'), { generate: 'client', filename: PRUEFLING }).css?.code ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
		const selektoren = [...css.matchAll(/([^{}@]+)\{/g)].map((m) => m[1].trim());
		const nachArt = selektoren.filter((s) => /data-kind|\[kind\b|\.(route|vergleich|trip|compare)(?![a-zA-Z0-9_-])|\.kind-|\.context-/.test(s));
		assert.deepEqual(nachArt, [], 'Stylesheet unterscheidet nach Art');
	});
});

describe('#2837 S2 AC-4/AC-15 — Texte des Rahmens aus dem Katalog (de und en)', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: Elternteil, Kind/Eyebrow und Abbrechen folgen der Nutzersprache`, async () => {
			const a = ART[context];
			for (const lang of ['de', 'en'] as const) {
				locale.set(lang);
				const { wurzel } = await render_(props(context, {}, lang));
				const link = elternLink(wurzel, context, lang);
				assert.ok(text(link.eltern!).includes(a.neu[lang]), `${lang}: Kind „${a.neu[lang]}" fehlt im Breadcrumb: „${text(link.eltern!)}"`);
				const eb = desktop(wurzel, (n) => n.attrs['data-slot'] === 'eyebrow');
				assert.equal(eb.length, 1, `${lang}: genau ein Desktop-Eyebrow`);
				assert.equal(text(eb[0]), a.neu[lang], `${lang}: Eyebrow`);
				abbrechen(wurzel, context, lang);
			}
		});
	}
});

// ── AC-11 an den Editoren: „Weiter" ist `Btn accent`, gesperrt NUR über `disabled` ──────────────
// Gerendert wird der echte Editor im gesperrten Zustand (SSR, Startwerte über stateOverride);
// gelesen wird das gerenderte Element, nicht der Quelltext. Strukturwächter-Anteil (Spec AC-11
// „keine Inline-opacity oder Inline-Farbe"): das style-Attribut des gerenderten Knopfs. Den
// Verhaltensnachweis (Hintergrund --g-accent, Abblenden) führt die E2E.
describe('#2837 S2 AC-11 — Weiter-Knöpfe beider Editoren (gesperrter Zustand)', () => {
	const tagVon = (html: string, testid: string): Knoten => einzig(baum(html), testid);
	const faelle: Array<[string, () => Promise<string>, string]> = [
		['Trip, Route ohne Namen', () => renderTrip({ activeTab: 'route', isMobileViewport: false }), 'trip-new-continue-etappen'],
		['Vergleich, Eckdaten ohne Namen', () => renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false, name: '' }), 'compare-editor-continue-orte'],
		['Vergleich, Orte mit 1 Ort', () => renderVergleichNeu({ activeTab: 'orte', isMobileViewport: false, pickedIds: ['loc-a'] }), 'compare-editor-continue-wetter'] // #2794 S3a
	];
	for (const [fall, renderer, testid] of faelle) {
		test(`${fall}: ${testid} ist Btn accent, disabled, ohne Inline-Deckkraft/-Farbe`, async () => {
			const k = tagVon(await renderer(), testid);
			assert.equal(k.tag, 'button');
			assert.equal(k.attrs['data-slot'], 'btn', `${testid} ist kein Btn (roher <button>)`);
			assert.equal(k.attrs['data-variant'], 'accent', `${testid} hat variant „${k.attrs['data-variant']}" (erwartet accent auch gesperrt)`);
			assert.ok('disabled' in k.attrs, `${testid} ist im gesperrten Zustand nicht disabled`);
			assert.ok(!/opacity|background/.test(k.attrs.style ?? ''), `${testid}: Inline-Stil am Weiter: „${k.attrs.style}"`);
		});
	}
});

// Messaufbau-Gegenprobe: der Lader findet die Editoren (sonst wären AC-11-Fälle vakuum).
test('Messaufbau: TripNewEditor und CompareNewEditor laden', async () => {
	assert.ok(await ladeRel('trip-new/TripNewEditor.svelte'));
	assert.ok(await ladeRel('compare-new/CompareNewEditor.svelte'));
});
