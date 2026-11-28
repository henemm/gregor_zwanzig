// TDD RED — Issue #3438 (Epic #2913), Punkt 2a: Region-Stift an der Oberzeile, keine eigene Regionszeile.
// Spec: docs/specs/modules/fix_3438_wetter_ganzseite.md — AC-3 (Kopf ohne Regionszeile, Stift an der
// Oberzeile), AC-5 (Stift am Titel bleibt), AC-7 (Vergleich ohne Region: Oberzeile „Orte“).
//
// Geprüft dort, wo es WIRKT: die echten Detailseiten /trips/[id] und /compare/[id], serverseitig
// gerendert über die Prüfstände f9Pruefstand.ts / f10Pruefstand.ts (feste Uhr, ohne Netz) — derselbe
// Weg wie hub_kopf_c2_mockup.test.ts. Kein Mock, kein Quelltext-Grep.
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
//   Oberzeile  = der Block, der den Eyebrow (testid hub-kopf-eyebrow, weiterhin reiner Text) trägt.
//                Der Region-Stift (`<prefix>-region-edit-toggle`, nur Icon mit aria-label) steht VOR der
//                Überschrift und teilt mit dem Eyebrow einen Vorfahren, der die Überschrift NICHT enthält.
//   Titel      = der Name-Stift (`<prefix>-name-edit-toggle`) bleibt direkt an der h1 (gleiches Elternteil).
//   Keine Regionszeile: im Titelblock steht nach der h1 kein Element mehr, dessen eigener Text die Region
//                (bzw. der Platzhalter „—“) ist; die Region steht im Kopf genau einmal (im Eyebrow).
//   Ohne Region (Vergleich): Eyebrow „Orte“ allein, der Region-Stift bleibt an der Oberzeile erreichbar.
// ─────────────────────────────────────────────────────────────────────────────────────
//
// Pfadregel #1409: Prüflinge relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_region_oberzeile_3438.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { baum, alle, einzig, text, liegtIn, vorfahren, klassen, type Knoten } from './htmlBaum.ts';

const T = await import('../../../trip-detail/__tests__/f9Pruefstand.ts');
const C = await import('../../../compare/__tests__/f10Pruefstand.ts');
const { locale } = T;

afterEach(() => locale.set('de'));

type Lang = 'de' | 'en';
type Art = 'route' | 'vergleich';
const SPRACHEN: Lang[] = ['de', 'en'];
const ARTEN: Art[] = ['route', 'vergleich'];
const PRAEFIX: Record<Art, string> = { route: 'trip', vergleich: 'compare-hub' };
const REGION: Record<Art, string> = { route: 'Mallorca', vergleich: 'Tirol' };

const tripMallorca = (extra: Record<string, unknown> = {}) =>
	T.tripLaufend({ id: 'gd-mallorca', name: 'GR221 Mallorca', shortcode: undefined, region: 'Mallorca', ...extra });

function seite(art: Art, lang: Lang = 'de', daten?: Record<string, unknown>): Knoten {
	locale.set(lang);
	try {
		return baum(
			art === 'route'
				? T.seiteRendern('ruhe', (daten ?? tripMallorca()) as never)
				: C.seiteRendern('ruhe', daten ?? C.vergleichAktiv())
		);
	} finally {
		locale.set('de');
	}
}

const h1 = (w: Knoten): Knoten => {
	const t = alle(w, (n) => n.tag === 'h1');
	assert.equal(t.length, 1, `genau eine Überschrift erwartet, gefunden ${t.length}`);
	return t[0];
};

const titelBlock = (w: Knoten): Knoten => {
	const t = alle(w, (n) => klassen(n).includes('hub-kopf-titel'));
	assert.equal(t.length, 1, `Messaufbau: genau ein Titelblock .hub-kopf-titel erwartet, gefunden ${t.length}`);
	return t[0];
};

/** Tiefster gemeinsamer Vorfahre zweier Knoten. */
function gemeinsamerVorfahre(a: Knoten, b: Knoten): Knoten {
	const kette = new Set([a, ...vorfahren(a)]);
	for (const n of [b, ...vorfahren(b)]) if (kette.has(n)) return n;
	throw new Error('kein gemeinsamer Vorfahre');
}

/** Region-Stift sitzt in der Oberzeile: vor der h1, gemeinsamer Block mit dem Eyebrow ohne die h1. */
function pruefeStiftInOberzeile(w: Knoten, art: Art): void {
	const stift = einzig(w, `${PRAEFIX[art]}-region-edit-toggle`);
	const eb = einzig(w, 'hub-kopf-eyebrow');
	const titel = h1(w);
	assert.ok(stift.nr < titel.nr, `Region-Stift steht unter dem Titel (Stift nr ${stift.nr}, h1 nr ${titel.nr}) statt an der Oberzeile`);
	const block = gemeinsamerVorfahre(stift, eb);
	assert.ok(!liegtIn(titel, block), `Region-Stift teilt mit dem Eyebrow erst einen Block, der auch den Titel enthält (<${block.tag} class="${block.attrs.class ?? ''}">) — er steht nicht in der Oberzeile`);
	assert.ok((stift.attrs['aria-label'] ?? '').trim().length > 0, 'Region-Stift ohne aria-label');
	assert.equal(text(stift), '', `Region-Stift zeigt sichtbaren Text „${text(stift)}“`);
}

for (const art of ARTEN) {
	for (const lang of SPRACHEN) {
		describe(`#3438 Kopf ${art} ${lang}`, () => {
			test(`AC-3: Region-Stift sitzt in der Oberzeile (Eyebrow), nicht unter dem Titel`, () => {
				pruefeStiftInOberzeile(seite(art, lang), art);
			});

			test(`AC-3: keine eigene Regionszeile unter dem Titel — Region „${REGION[art]}“ steht nur im Eyebrow`, () => {
				const w = seite(art, lang);
				const titel = h1(w);
				const nachTitel = alle(titelBlock(w), (n) => n.nr > titel.nr && n.texte.join('').trim() !== '');
				const zeile = nachTitel.filter((n) => [REGION[art], '—'].includes(n.texte.join('').trim()));
				assert.deepEqual(
					zeile.map((n) => `<${n.tag}> „${n.texte.join('').trim()}“`),
					[],
					'unter dem Titel steht noch eine eigene Regionszeile'
				);
				const eigeneTexte = alle(w, (n) => n.texte.join('').includes(REGION[art]) && n.tag !== 'h1' && n.tag !== 'title');
				const imKopf = eigeneTexte.filter((n) => liegtIn(n, titelBlock(w)) || n === titelBlock(w));
				assert.equal(imKopf.length, 1, `Region steht ${imKopf.length}× im Titelblock (erwartet nur im Eyebrow): ${imKopf.map((n) => `<${n.tag}>`).join(', ')}`);
				assert.equal(imKopf[0].attrs['data-testid'], 'hub-kopf-eyebrow', 'die Region steht im Titelblock nicht im Eyebrow');
			});

			test('AC-5: Stift am Titel bleibt (Name-Stift neben der Überschrift)', () => {
				const w = seite(art, lang);
				const titel = h1(w);
				const stift = einzig(w, `${PRAEFIX[art]}-name-edit-toggle`);
				assert.equal(stift.eltern, titel.eltern, 'Name-Stift steht nicht mehr neben der Überschrift');
				assert.ok(stift.nr > titel.nr, 'Name-Stift steht vor der Überschrift');
				assert.ok((stift.attrs['aria-label'] ?? '').trim().length > 0, 'Name-Stift ohne aria-label');
			});
		});
	}
}

describe('#3438 AC-7: Orts-Vergleich ohne Region', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: Oberzeile „${lang === 'de' ? 'Orte' : 'Locations'}“ allein, Region-Stift trotzdem an der Oberzeile`, () => {
			const ohne = C.vergleichAktiv({ display_config: { region: '' } });
			const w = seite('vergleich', lang, ohne);
			assert.equal(text(einzig(w, 'hub-kopf-eyebrow')), lang === 'de' ? 'Orte' : 'Locations');
			pruefeStiftInOberzeile(w, 'vergleich');
		});
	}
});
