// TDD RED — Issue #2521 S1 (Spec begriff_erklaerung_infobox.md): die beiden neuen
// Bausteine `molecules/Infobox.svelte` und `molecules/BegriffErklaerung.svelte`
// sowie die Lookup-Map `shared/infoboxKeys.ts`.
//
//   AC-3   Texte je Reiter UND Kontext aus der Map (Vergleichs-Versand != Trip-Versand)
//   AC-7   Infobox: <aside>, KEIN Bedienelement, kein Zustand
//   AC-13  ⓘ ist ein <button type="button"> mit sprechendem Namen (aria-label aus dem Katalog)
//   AC-18  die neuen Dateien enthalten keine `context ===`-Verzweigung (die Ratsche
//          `context_herkunft_zweige_eingefroren` scannt nur shared/ — diese Luecke schliesst
//          der Waechter unten)
//
// Erwartete Schnittstelle (der Implementierer baut genau danach):
//   <Infobox reiter="versand" context="vergleich" />
//        -> <aside data-testid="infobox-versand-vergleich">…Text aus t(infoboxKey(context, reiter))…</aside>
//   <BegriffErklaerung begriff="cooldown" />
//        -> <button type="button" data-testid="begriff-erklaerung-cooldown…" aria-label={t('tip.aria.cooldown')}>ⓘ</button>
//           (Testid darf ein Suffix tragen: Desktop- und Mobil-Panel rendern gleichzeitig, Spec Entscheidung 9)
//   shared/infoboxKeys.ts: export function infoboxKey(context, reiter): MessageKey
//                          export const BEGRIFF_KEYS (Schluessel = die vier Begriffe)
//
// Das Popover-Portal (geoeffneter Inhalt) ist im SSR nicht pruefbar — das misst
// frontend/e2e/begriff-erklaerung.spec.ts im Browser.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/molecules/begriff_erklaerung_infobox_bausteine.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { de } from '../../i18n/messages/de/index.ts';
import {
	COMPONENTS,
	attribut,
	innen,
	lade,
	renderKomponente,
	sichtbarerText,
	tagsMitTestid
} from '../shared/__tests__/infoboxSsr.ts';
import { BEGRIFFE, INFO_TEXTE, REITER_MIT_INFOBOX, type Kontext } from '../shared/__tests__/infoboxTexte.ts';

const katalog = de as Record<string, string>;

const KOMBINATIONEN: [string, Kontext][] = (['route', 'vergleich'] as Kontext[]).flatMap((k) =>
	REITER_MIT_INFOBOX[k].map((r) => [r, k] as [string, Kontext])
);

describe('Infobox: <aside> mit dem Text der Lookup-Map, ohne Bedienelement', () => {
	for (const [reiter, kontext] of KOMBINATIONEN) {
		test(`${reiter} / ${kontext}: Text wortgleich, <aside>, kein button/input/a`, async () => {
			const Infobox = await lade('molecules/Infobox.svelte');
			const html = renderKomponente(Infobox, { reiter, context: kontext });
			const id = `infobox-${reiter}-${kontext}`;
			const tags = tagsMitTestid(html, id);
			assert.equal(tags.length, 1, `Testid ${id} fehlt: ${html.slice(0, 200)}`);
			assert.ok(tags[0].startsWith('<aside'), `kein <aside>: ${tags[0]}`);
			const roh = innen(html, id);
			assert.ok(!/<(button|input|a|dialog)\b|onclick|role="dialog"/.test(roh), 'Bedienelement/Zustand in der Infobox');
			assert.equal(sichtbarerText(roh), INFO_TEXTE[`info.${reiter}.${kontext}`]);
		});
	}

	test('AC-3: Versand — Vergleich nennt NUR 07:00, Trip nennt 07:00 und 18:00', async () => {
		const Infobox = await lade('molecules/Infobox.svelte');
		const vergleich = sichtbarerText(
			innen(renderKomponente(Infobox, { reiter: 'versand', context: 'vergleich' }), 'infobox-versand-vergleich')
		);
		const trip = sichtbarerText(
			innen(renderKomponente(Infobox, { reiter: 'versand', context: 'route' }), 'infobox-versand-route')
		);
		assert.match(vergleich, /07:00/);
		assert.doesNotMatch(vergleich, /18:00/);
		assert.match(vergleich, /kein Enddatum/);
		assert.match(trip, /07:00/);
		assert.match(trip, /18:00/);
		assert.notEqual(vergleich, trip, 'Vergleichs- und Trip-Versandtext sind identisch');
	});

	test('AC-3: Wetter-Metriken — Vergleich nennt Stundenverlauf/3-Tages-Ausblick, Trip nicht', async () => {
		const Infobox = await lade('molecules/Infobox.svelte');
		const v = sichtbarerText(
			innen(renderKomponente(Infobox, { reiter: 'wetter-metriken', context: 'vergleich' }), 'infobox-wetter-metriken-vergleich')
		);
		const r = sichtbarerText(
			innen(renderKomponente(Infobox, { reiter: 'wetter-metriken', context: 'route' }), 'infobox-wetter-metriken-route')
		);
		assert.match(v, /Stundenverlauf/);
		assert.match(v, /3-Tages-Ausblick/);
		assert.doesNotMatch(r, /Stundenverlauf/);
	});
});

describe('BegriffErklaerung: ⓘ als echter <button> mit sprechendem Namen', () => {
	for (const begriff of BEGRIFFE) {
		test(`${begriff}: button type="button", aria-label aus tip.aria.${begriff}, sichtbares Zeichen ⓘ`, async () => {
			const BegriffErklaerung = await lade('molecules/BegriffErklaerung.svelte');
			const html = renderKomponente(BegriffErklaerung, { begriff });
			const tags = tagsMitTestid(html, `begriff-erklaerung-${begriff}`);
			assert.equal(tags.length, 1, `ⓘ ${begriff} fehlt: ${html.slice(0, 300)}`);
			assert.ok(tags[0].startsWith('<button'), `ⓘ ist kein <button>: ${tags[0]}`);
			assert.equal(attribut(tags[0], 'type'), 'button');
			assert.equal(attribut(tags[0], 'aria-label'), katalog[`tip.aria.${begriff}`]);
			assert.ok((attribut(tags[0], 'aria-label') ?? '').length > 0);
			assert.equal(sichtbarerText(innen(html, tags[0].match(/data-testid="([^"]*)"/)![1])), 'ⓘ');
		});
	}
});

describe('shared/infoboxKeys.ts: die Lookup-Map waehlt den Katalogschluessel (keine Kontext-Verzweigung)', () => {
	test('infoboxKey(kontext, reiter) liefert info.<reiter>.<kontext> fuer jede freigegebene Kombination', async () => {
		const modul = await import(new URL('shared/infoboxKeys.ts', `file://${COMPONENTS}/`).href);
		for (const [reiter, kontext] of KOMBINATIONEN) {
			assert.equal(modul.infoboxKey(kontext, reiter), `info.${reiter}.${kontext}`);
			assert.ok(katalog[modul.infoboxKey(kontext, reiter)], 'Schluessel nicht im Katalog');
		}
		assert.notEqual(modul.infoboxKey('route', 'versand'), modul.infoboxKey('vergleich', 'versand'));
	});

	test('BEGRIFF_KEYS kennt genau die vier Begriffe', async () => {
		const modul = await import(new URL('shared/infoboxKeys.ts', `file://${COMPONENTS}/`).href);
		assert.deepEqual(Object.keys(modul.BEGRIFF_KEYS).sort(), [...BEGRIFFE].sort());
	});
});

// doc-compliance-test
describe('AC-18: die neuen Dateien enthalten keine Kontext-Vergleichs-Verzweigung (Ratsche scannt nur shared/)', () => {
	test('molecules/Infobox, molecules/BegriffErklaerung, shared/infoboxKeys, ui/popover/*', () => {
		const dateien = [
			join(COMPONENTS, 'molecules/Infobox.svelte'),
			join(COMPONENTS, 'molecules/BegriffErklaerung.svelte'),
			join(COMPONENTS, 'shared/infoboxKeys.ts')
		];
		const popoverDir = join(COMPONENTS, 'ui/popover');
		assert.ok(existsSync(popoverDir), 'ui/popover/ existiert nicht');
		for (const f of readdirSync(popoverDir)) dateien.push(join(popoverDir, f));
		assert.ok(dateien.length >= 5, 'Popover-Wrapper unvollstaendig');
		for (const d of dateien) {
			assert.ok(existsSync(d), `${d} existiert nicht`);
			const code = readFileSync(d, 'utf-8');
			assert.doesNotMatch(code, /context\s*[!=]==?\s*['"](route|vergleich)['"]/, `${d}: Kontext-Verzweigung statt Lookup-Map`);
			assert.doesNotMatch(code, /['"](route|vergleich)['"]\s*[!=]==?\s*context/, `${d}: Kontext-Verzweigung statt Lookup-Map`);
		}
		// Waechter-Teil im selben (roten) Fall: die bestehende Ratsche context_herkunft_zweige_eingefroren
		// bleibt unveraendert vorhanden und laeuft weiter (AC-18: „bleibt unveraendert gruen“).
		assert.ok(
			existsSync(join(COMPONENTS, 'shared/__tests__/context_herkunft_zweige_eingefroren.test.ts')),
			'Ratsche fehlt (darf nicht angefasst/entfernt werden)'
		);
	});
});
