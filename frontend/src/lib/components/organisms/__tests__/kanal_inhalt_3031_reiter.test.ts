// #3031 Fix-Loop 1 (Adversary F002, F003 a/b/d, LOW): Verdrahtung Karte → Reiter → Speicherer.
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md (AC-2, AC-3, AC-7, AC-8, AC-9).
//
// WetterTabInhalt laedt erst in onMount; ein Server-Render erreicht die Karte nicht (Muster
// fix2944_nicht_im_briefing_verdrahtung.test.ts). Deshalb liegt die Reiter-Logik der Karte als
// reine Funktionen in organisms/wetter-tab/kanalInhaltReiter.ts und wird hier VERHALTENSGEPRUEFT,
// bis zum echten Speicherer (Nutzlast). Dass WetterTabInhalt genau diese Funktionen nutzt, sichert
// der Quelltext-Teil am Ende (// doc-compliance-test).
//
//   Erwartete Schnittstelle (kanalInhaltReiter.ts):
//     signaturVon(s, vorlagen): string                       // was gespeichert wird, inkl. s.kanaele
//     zuMelden(gemeldet, neu, vorlagen): string | null       // neue Signatur, wenn gemeldet werden muss
//     standMitKanaelen(kontext, s, abo, formatFuer): WetterStand   // Hydration (nur bei eigenen Listen)
//     kanalListenFuerAnzeige(kontext, s, abo, formatFuer): KanalListen // normalisiert gegen s.auswahl
//     karteSichtbar(createMode, listen): boolean             // beim Anlegen keine Karte
//     kanalFormatAusKatalog(katalog): (id) => Format         // Format neuer Zeilen = Katalog-Default
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/kanal_inhalt_3031_reiter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import { fixture, live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { formatAusKatalog, kanalInhalt, katalogNachId } from '../../shared/wetter-tab/__tests__/kanalInhaltPruefstand.ts';
import { vorlagenAusTemplates } from '../../shared/wetter-tab/ampelModell.ts';
import { mitMetrik, ohneMetrik, standAusAbo, type AboSicht, type WetterStand } from '../../shared/wetter-tab/wetterZustand.ts';
import { tripNutzlast } from '../../shared/wetter-tab/wetterTabSpeicherung.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WT = path.resolve(HERE, '..', 'wetter-tab');
const vorlagen = vorlagenAusTemplates(live().templates);
const fmt = (id: string) => formatAusKatalog(id);
type Dc = Record<string, unknown>;

async function reiter(): Promise<any> {
	const p = path.join(WT, 'kanalInhaltReiter.ts');
	if (!existsSync(p)) assert.fail('TDD RED: organisms/wetter-tab/kanalInhaltReiter.ts fehlt');
	return import(pathToFileURL(p).href);
}

function tripAbo(): AboSicht {
	const g = fixture('einstellung_auslieferung/golden_b.json');
	return { id: 'trip-3031-reiter', profil: 'wandern', report_config: g.report_config, display_config: g.display_config };
}

describe('F002: eine Karten-Aenderung wird gemeldet und erreicht den Speicherer', () => {
	test('Umsortieren in E-Mail ⇒ zuMelden liefert eine neue Signatur, die Nutzlast traegt die neue Reihenfolge', async () => {
		const r = await reiter();
		const m = await kanalInhalt();
		const abo = tripAbo();
		const start: WetterStand = r.standMitKanaelen('route', standAusAbo('route', abo, vorlagen), abo, fmt);
		const gemeldet: string = r.signaturVon(start, vorlagen);
		const listen = r.kanalListenFuerAnzeige('route', start, abo, fmt);
		const ids = listen.email.map((z: { id: string }) => z.id);
		const neu = { ...start, kanaele: m.mitReihenfolge(listen, 'email', [...ids].reverse()) } as WetterStand;
		const sig = r.zuMelden(gemeldet, neu, vorlagen);
		assert.ok(sig && sig !== gemeldet, 'Karten-Aenderung wird nicht gemeldet (Signatur ohne Kanallisten)');
		assert.equal(sig, r.signaturVon(neu, vorlagen));
		assert.equal(r.zuMelden(sig, neu, vorlagen), null, 'unveraenderter Stand darf nicht erneut melden');
		const cl = (tripNutzlast({ client: null as never, stand: () => neu, vorlagen: () => vorlagen, abo: () => abo, kanalFormatFuer: fmt }).weatherConfig as Dc).channel_layouts as Record<string, { metric_id: string }[]>;
		assert.deepEqual(cl.email.map((e) => e.metric_id), [...ids].reverse());
	});

	test('Schalter in SMS ⇒ neue Signatur (nicht nur Reihenfolge)', async () => {
		const r = await reiter();
		const m = await kanalInhalt();
		const abo = tripAbo();
		const start: WetterStand = r.standMitKanaelen('route', standAusAbo('route', abo, vorlagen), abo, fmt);
		const listen = r.kanalListenFuerAnzeige('route', start, abo, fmt);
		const id = listen.sms.find((z: { enabled: boolean }) => z.enabled).id;
		const neu = { ...start, kanaele: m.mitSchalter(listen, 'sms', id, false) } as WetterStand;
		assert.notEqual(r.zuMelden(r.signaturVon(start, vorlagen), neu, vorlagen), null);
	});
});

describe('F003a: Hydration — eigene Kanallisten des Abos landen im Stand, sonst nicht', () => {
	test('Abo mit channel_layouts ⇒ stand.kanaele = gespeicherte Listen (Trip und Vergleich)', async () => {
		const r = await reiter();
		const m = await kanalInhalt();
		for (const kontext of ['route', 'vergleich'] as const) {
			const abo = tripAbo();
			const s = standAusAbo(kontext, abo, vorlagen);
			const h: WetterStand = r.standMitKanaelen(kontext, s, abo, fmt);
			assert.deepEqual(h.kanaele, m.listenAusAbo(kontext, abo, s.auswahl, fmt), `${kontext}: gespeicherte Listen nicht hydriert`);
		}
	});
	test('Abo ohne eigene Listen ⇒ kein stand.kanaele (kein ungefragtes Schreiben von channel_layouts)', async () => {
		const r = await reiter();
		const abo = { ...tripAbo(), display_config: { metrics: tripAbo().display_config!.metrics } } as AboSicht;
		assert.equal(r.standMitKanaelen('route', standAusAbo('route', abo, vorlagen), abo, fmt).kanaele, undefined);
	});
});

describe('F003b: beim Anlegen keine Karte (Anlege-Seiten uebernehmen keine Kanallisten)', () => {
	test('karteSichtbar', async () => {
		const r = await reiter();
		const l = { email: [], telegram: [], sms: [] };
		assert.equal(r.karteSichtbar(true, l), false);
		assert.equal(r.karteSichtbar(false, l), true);
		assert.equal(r.karteSichtbar(false, null), false);
	});
});

describe('F003d / LOW: Anzeige normalisiert gegen die aktuelle Wetter-Auswahl, neue Zeile im Katalog-Format', () => {
	test('neu gewaehlte Metrik eingeschaltet am Ende jeder Liste, abgewaehlte fehlt', async () => {
		const r = await reiter();
		const abo = tripAbo();
		const s0: WetterStand = r.standMitKanaelen('route', standAusAbo('route', abo, vorlagen), abo, fmt);
		const s = ohneMetrik(mitMetrik(s0, 'pressure'), 'gust');
		const l = r.kanalListenFuerAnzeige('route', s, abo, fmt);
		for (const k of ['email', 'telegram', 'sms'] as const) {
			assert.deepEqual(l[k].at(-1), { id: 'pressure', enabled: true, format: 'roh' }, `${k}: neue Metrik nicht am Ende`);
			assert.ok(!l[k].some((z: { id: string }) => z.id === 'gust'), `${k}: abgewaehlte Metrik noch in der Liste`);
		}
	});
	test('kanalFormatAusKatalog: Format neuer Zeilen = default_format_mode des Katalogs (nicht fest Roh)', async () => {
		const r = await reiter();
		const f = r.kanalFormatAusKatalog(katalogNachId());
		assert.equal(f('thunder'), 'einfach', 'Gewitter ist im Katalog symbol ⇒ Einfach');
		assert.equal(f('cloud_total'), 'einfach');
		assert.equal(f('temperature'), 'roh');
		assert.equal(f('unbekannt'), 'roh');
	});
});

describe('WetterTabInhalt nutzt genau diese Funktionen (doc-compliance-test)', () => {
	const q = readFileSync(path.join(WT, 'WetterTabInhalt.svelte'), 'utf8');
	const ast: any = parse(q, { modern: true });
	const skript = q.slice(ast.instance.content.start, ast.instance.content.end).replace(/\/\/[^\n]*/g, ' ').replace(/\s+/g, ' ');
	const markup = q.slice(ast.fragment.start, ast.fragment.end).replace(/<!--[\s\S]*?-->/g, ' ').replace(/\s+/g, ' ');
	test('Signatur, Melde-Entscheidung, Hydration (Laden UND Neuladen nach 412), Anzeige, Format, Sichtbarkeit', () => {
		assert.match(skript, /const signatur = \(s: Z\.WetterStand\) => signaturVon\(s, daten!\.vorlagen\)/);
		assert.match(skript, /zuMelden\(gemeldet, neu, daten!\.vorlagen\)/);
		assert.equal(skript.match(/standMitKanaelen\(context, Z\.standAusAbo\(/g)?.length, 2, 'Hydration fehlt in laden() oder neuGeladen()');
		assert.match(skript, /const kanaele = \$derived\(anzeige && daten \? kanalListenFuerAnzeige\(context, anzeige, abo\(\), kanalFormatFuer\) : null\);/);
		assert.match(skript, /kanalFormatAusKatalog\(/);
		assert.match(markup, /\{#if karteSichtbar\(createMode, kanaele\)\}/);
	});
	test('F101: Karten-Aenderung laeuft ueber aendern() (sonst nur Anzeige, nie gespeichert)', () => {
		const karten = [...markup.matchAll(/<KanalInhaltKarte\b[\s\S]*?\/>/g)].map((m) => m[0]);
		assert.equal(karten.length, 1, 'genau eine KanalInhaltKarte erwartet');
		assert.match(karten[0], /onAendern=\{\(neu\) => aendern\(\{ \.\.\.stand!, kanaele: neu \}\)\}/, `onAendern nicht ueber aendern(): ${karten[0]}`);
	});
});
