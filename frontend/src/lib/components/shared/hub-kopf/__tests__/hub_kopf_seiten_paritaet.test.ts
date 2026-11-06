// TDD RED — Issue #2837 Scheibe S1 (Epic #2345): Hub-Kopf an der Stelle, wo er WIRKT —
// beide Detailseiten (`routes/trips/[id]/+page.svelte`, `routes/compare/[id]/+page.svelte`)
// echt serverseitig gerendert, über die bestehenden i18n-Prüfstände
// (trip-detail/__tests__/f9Pruefstand.ts, compare/__tests__/f10Pruefstand.ts: echte
// Seiten mit festen Daten und fester Uhr, ohne Netz).
// Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md — AC-1, AC-3, AC-4, AC-5, AC-6,
// AC-9, AC-11, AC-13 (SSR-Anteil; Farbe, Lage in Pixeln, Klicks: E2E
// frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts).
//
// Pflicht-Mutationen (Spec Test Plan), hier gefangen:
//   (a) Trip-Senden wieder `variant="accent"`        → „AC-1 … data-variant primary" rot
//   (c) Status wieder in eigener Zeile unter dem Kopf → „AC-6 … Titelzeile" rot
// (b) Reiter-Zähler accent: mobile/__tests__/mtabbar_zaehler_neutral.test.ts + E2E HT-8.
//
// Kein `f8variante`-Zustand (z. B. `let mobil = …`) in diesem Test: nur die Ruhe-
// Varianten der Prüfstände; mobil (Kebab-Symbol) bewacht hub_kopf_seiten_bindung.test.ts
// am AST und die E2E bei 390 px.
//
// RED HEUTE: Die Seiten haben keinen geteilten Hub-Kopf (keine `hub-kopf-leiste`),
// Trip-Senden ist `accent`, der Trip-Status steht in `.status-line` unter dem Kopf, der
// Vergleich zeigt „ORTS-VERGLEICHE / Hub" und titelt mit 30 px.
//
// Pfadregel #1409: Prüfstände relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { baum, alle, einzig, mitTestid, text, liegtIn, lage, vorfahren, klassen, type Knoten } from './htmlBaum.ts';

const T = await import('../../../trip-detail/__tests__/f9Pruefstand.ts');
const C = await import('../../../compare/__tests__/f10Pruefstand.ts');
const { locale, trFor } = T;

afterEach(() => locale.set('de'));

type Art = 'route' | 'vergleich';
const ARTEN: Art[] = ['route', 'vergleich'];

/** Ruhe-Render der Seite je Art (optional mit eigenem Datensatz). */
function seite(art: Art, daten?: Record<string, unknown>): Knoten {
	const html =
		art === 'route'
			? T.seiteRendern('ruhe', (daten ?? T.tripLaufend()) as ReturnType<typeof T.tripLaufend>)
			: C.seiteRendern('ruhe', daten ?? C.vergleichAktiv());
	return baum(html);
}

const ELTERN: Record<Art, { schluessel: string; href: string }> = {
	route: { schluessel: 'listen.trips.titel', href: '/trips' },
	vergleich: { schluessel: 'listen.vergleiche.titel', href: '/compare' }
};
/** Kind des Breadcrumbs: Trip = Kürzel ?? Name, Vergleich = Name. */
const KIND: Record<Art, string> = { route: 'GR20', vergleich: 'Skitouren Tirol' };

const ueberschrift = (w: Knoten): Knoten => {
	const t = alle(w, (n) => n.tag === 'h1');
	assert.equal(t.length, 1, `genau eine Überschrift auf der Seite erwartet, gefunden ${t.length}`);
	return t[0];
};
/** Das Status-Badge der Art: Trip = TripStatusBadge, Vergleich = CompareStatusPill (data-status). */
const statusBadge = (w: Knoten, art: Art): Knoten[] =>
	art === 'route' ? mitTestid(w, 'trip-detail-status-badge') : alle(w, (n) => n.tag === 'span' && n.attrs['data-status'] !== undefined);

for (const art of ARTEN) {
	describe(`#2837 S1 Seite ${art} — Hub-Kopf über den geteilten Baustein`, () => {
		test(`AC-11 (${art}): genau eine Hub-Kopf-Leiste, genau ein Breadcrumb, genau eine Überschrift; Leiste vor dem Titel`, () => {
			const w = seite(art);
			const leiste = einzig(w, 'hub-kopf-leiste');
			einzig(w, 'hub-kopf-breadcrumb');
			assert.ok(leiste.nr < ueberschrift(w).nr, 'Leiste steht nicht über dem Titel');
		});

		test(`Entscheidung 1 (${art}): der Kopf trägt data-kind="${art}"`, () => {
			const leiste = einzig(seite(art), 'hub-kopf-leiste');
			const marke = [leiste, ...vorfahren(leiste)].find((n) => n.attrs['data-kind'] !== undefined);
			assert.equal(marke?.attrs['data-kind'], art);
		});

		test(`AC-1 (${art}): „Senden" ist genau einmal da, steht IN der Leiste und ist Btn primary (Ink) — Mutation (a)`, () => {
			const w = seite(art);
			const senden = einzig(w, 'subscription-hub-send');
			assert.equal(senden.attrs['data-variant'], 'primary', `„Senden" hat variant „${senden.attrs['data-variant']}" — erwartet primary (schwarz)`);
			assert.ok(!liegtIn(senden, ueberschrift(w).eltern!.eltern!), '„Senden" steht neben der Überschrift (im Titelblock)');
			assert.ok(liegtIn(senden, einzig(w, 'hub-kopf-leiste')), '„Senden" steht nicht in der Leiste ganz oben');
		});

		test(`AC-4 (${art}): Breadcrumb „${trFor('de', ELTERN[art].schluessel as never)} / ${KIND[art]}" — Elternteil Link auf ${ELTERN[art].href}, Kind kein Link`, () => {
			const krumen = einzig(seite(art), 'hub-kopf-breadcrumb');
			const links = alle(krumen, (n) => n.tag === 'a');
			assert.equal(links.length, 1, `genau ein Link im Breadcrumb erwartet, gefunden ${links.length}`);
			assert.equal(links[0].attrs.href, ELTERN[art].href);
			assert.equal(text(links[0]), trFor('de', ELTERN[art].schluessel as never), 'Elternteil-Text nicht aus dem Katalog (bzw. im Markup umgeschrieben)');
			assert.ok(text(krumen).includes(KIND[art]), `Kind „${KIND[art]}" fehlt: „${text(krumen)}"`);
			assert.ok(!text(links[0]).includes(KIND[art]), 'Kind ist Teil des Links');
		});

		test(`AC-4 (${art}): im Kopf steht nirgends das Wort „Hub"`, () => {
			const w = seite(art);
			const leiste = einzig(w, 'hub-kopf-leiste');
			const zeile = ueberschrift(w).eltern!;
			const block = (zeile.eltern ?? zeile);
			for (const k of [leiste, block]) {
				const t = text(k);
				assert.ok(!/(?<![A-Za-zÄÖÜäöü-])Hub(?![A-Za-zÄÖÜäöü])/.test(t), `„Hub" im Kopf: „${t.slice(0, 300)}"`);
			}
		});

		test(`AC-6 (${art}): Status genau einmal, als Badge in der TITELZEILE (gleiches Elternelement wie h1) — Mutation (c)`, () => {
			const w = seite(art);
			const badges = statusBadge(w, art);
			assert.equal(badges.length, 1, `Status-Badge ${badges.length}× auf der Seite (erwartet genau 1)`);
			const zeile = ueberschrift(w).eltern!;
			assert.ok(liegtIn(badges[0], zeile), 'das Status-Badge steht nicht in der Titelzeile (eigene Statuszeile unter dem Kopf?)');
			const huelle = einzig(w, 'hub-kopf-status');
			assert.equal(huelle.eltern, zeile, 'hub-kopf-status steht nicht in der Titelzeile');
			assert.ok(liegtIn(badges[0], huelle), 'das Status-Badge steht nicht in hub-kopf-status (Titelzeile)');
		});

		test(`AC-9 (${art}): Überschrift mit 38 px am Desktop (titleSize 38, beide Arten gleich)`, () => {
			const k = klassen(ueberschrift(seite(art)));
			assert.ok(k.includes('desktop:text-[38px]'), `h1-Klassen: ${k.join(' ')}`);
			assert.ok(!k.includes('desktop:text-[30px]'), 'h1 trägt noch die 30-px-Klasse');
		});

		test(`AC-2 (${art}): mobiler Zurück-Link steht in der Leiste und führt zur Liste`, () => {
			const w = seite(art);
			const zurueck = alle(einzig(w, 'hub-kopf-leiste'), (n) => n.attrs['data-testid'] === 'back-link');
			assert.equal(zurueck.length, 1, `Zurück-Links in der Leiste: ${zurueck.length}`);
			assert.equal(zurueck[0].attrs.href, ELTERN[art].href);
			assert.equal(mitTestid(w, 'back-link').length, 1, 'zweiter Zurück-Link außerhalb der Leiste');
		});

		test(`AC-7 (${art}): der Kebab steht in der Leiste, genau einmal, Symbol vertikal`, () => {
			const w = seite(art);
			const kebab = einzig(w, 'subscription-kebab');
			assert.ok(liegtIn(kebab, einzig(w, 'hub-kopf-leiste')), 'Kebab steht nicht in der Leiste');
			const icons = alle(kebab, (n) => n.tag === 'svg').map((n) => n.attrs.class ?? '');
			assert.ok(icons.some((c) => /\blucide-ellipsis-vertical\b/.test(c)), `Kebab-Symbol nicht vertikal: ${icons.join(' | ')}`);
		});
	});
}

describe('#2837 S1 Parität — beide Seiten bauen die Leiste gleich', () => {
	const leistenGeruest = (w: Knoten): string[] => {
		const leiste = einzig(w, 'hub-kopf-leiste');
		return alle(leiste, () => true).map((n) => `${lage(n, leiste)}|${n.attrs['data-testid'] ?? ''}|${n.attrs['data-slot'] ?? ''}|${n.attrs['data-variant'] ?? ''}`);
	};
	test('AC-1/AC-2: Senden sitzt bei beiden an derselben Stelle der Leiste', () => {
		const a = seite('route');
		const b = seite('vergleich');
		assert.equal(
			lage(einzig(b, 'subscription-hub-send'), einzig(b, 'hub-kopf-leiste')),
			lage(einzig(a, 'subscription-hub-send'), einzig(a, 'hub-kopf-leiste'))
		);
	});
	test('AC-15 (SSR-Anteil): das Leisten-Gerüst ist bei Trip und Vergleich identisch', () => {
		assert.deepEqual(leistenGeruest(seite('vergleich')), leistenGeruest(seite('route')));
	});
});

describe('#2837 S1 AC-10 — Reiter-Zähler: Trip und Vergleich rendern dasselbe Badge (Mutation b, Seiten-Anteil)', () => {
	// Die Farbe selbst kommt aus den MTabBar-Regeln (mobile/__tests__/mtabbar_zaehler_neutral.test.ts);
	// hier wird gesichert, dass keine Seite sie am Badge vorbei umfärbt (Inline-Stil, eigene
	// Varianten-Attribute/Klassen) und die Leisten sich nur in der Größe `sm` unterscheiden.
	const badge = (w: Knoten): Knoten => {
		const b = alle(w, (n) => n.attrs['data-slot'] === 'segmented-badge');
		assert.ok(b.length >= 1, 'kein Reiter-Zähler gerendert');
		return b[0];
	};
	const ohneTestid = (k: Knoten) => Object.entries(k.attrs).filter(([a]) => a !== 'data-testid').sort();
	test('gleiche Badge-Attribute (ohne testid), kein Inline-Stil', () => {
		const a = badge(seite('route'));
		const b = badge(seite('vergleich'));
		assert.deepEqual(ohneTestid(b), ohneTestid(a));
		assert.ok(!('style' in a.attrs) && !('style' in b.attrs), 'Zähler mit Inline-Stil (umgeht die neutrale Variante)');
	});
	test('die Reiterleisten unterscheiden sich höchstens in der Größe `sm`', () => {
		const leiste = (w: Knoten) => {
			const l = alle(w, (n) => n.attrs.class?.split(/\s+/).includes('mtabbar') ?? false);
			assert.equal(l.length, 1, `Reiterleisten: ${l.length}`);
			return klassen(l[0]).filter((c) => c !== 'sm').sort();
		};
		assert.deepEqual(leiste(seite('vergleich')), leiste(seite('route')));
	});
});

describe('#2837 S1 AC-3 — Entwurf: Trip-Senden gesperrt, Vergleich „Setup abschließen" auf dem Senden-Platz', () => {
	test('Trip-Entwurf: Senden steht in der Leiste und ist disabled', () => {
		const w = seite('route', T.tripEntwurf());
		assert.equal(text(einzig(w, 'trip-detail-status-badge')), trFor('de', 'trip.status.draft'), 'Vorbedingung: Trip ist Entwurf');
		const senden = einzig(w, 'subscription-hub-send');
		assert.ok(liegtIn(senden, einzig(w, 'hub-kopf-leiste')));
		assert.ok('disabled' in senden.attrs, 'Senden ist beim Trip-Entwurf nicht gesperrt');
	});
	test('Vergleich-Entwurf: kein Senden, „Setup abschließen" (Btn primary) an der Stelle, an der Trip-Senden sitzt', () => {
		const label = trFor('de', 'vergleich.hub.setup_abschliessen');
		const v = seite('vergleich', C.vergleichEntwurf());
		assert.equal(mitTestid(v, 'subscription-hub-send').length, 0, 'im Vergleich-Entwurf steht ein Senden-Knopf');
		const leiste = einzig(v, 'hub-kopf-leiste');
		const setup = alle(leiste, (n) => n.attrs['data-slot'] === 'btn' && text(n) === label);
		assert.equal(setup.length, 1, `„${label}" nicht genau einmal in der Leiste`);
		assert.equal(setup[0].attrs['data-variant'], 'primary');
		assert.equal(alle(v, (n) => n.attrs['data-slot'] === 'btn' && text(n) === label).length, 1, '„Setup abschließen" zusätzlich außerhalb der Leiste');
		const t = seite('route', T.tripEntwurf());
		assert.equal(lage(setup[0], leiste), lage(einzig(t, 'subscription-hub-send'), einzig(t, 'hub-kopf-leiste')), 'nicht auf dem Senden-Platz');
	});
});

describe('#2837 S1 AC-5 — Trip ohne Kürzel: Breadcrumb zeigt den Namen', () => {
	test('shortcode fehlt ⇒ Kind = Trip-Name, kein Link', () => {
		const w = seite('route', T.tripLaufend({ shortcode: undefined }));
		const krumen = einzig(w, 'hub-kopf-breadcrumb');
		assert.ok(text(krumen).includes('GR20 Nord 2026'), `Name fehlt im Breadcrumb: „${text(krumen)}"`);
		const links = alle(krumen, (n) => n.tag === 'a');
		assert.equal(links.length, 1);
		assert.ok(!text(links[0]).includes('GR20 Nord 2026'));
	});
});

describe('#2837 S1 AC-6 — Trip: „Tag x von y" steht in der Titelzeile, die Region darunter (vormals .status-line)', () => {
	test('Zusatz trip-detail-status-supplement genau einmal, in der Titelzeile; keine eigene Statuszeile', () => {
		const w = seite('route');
		const zeile = ueberschrift(w).eltern!;
		const zusatz = einzig(w, 'trip-detail-status-supplement');
		assert.ok(liegtIn(zusatz, zeile), 'der Zusatz „Tag x von y" steht nicht in der Titelzeile');
		assert.equal(alle(w, (n) => klassen(n).includes('status-line')).length, 0, 'es gibt noch eine eigene Statuszeile (.status-line)');
	});
	test('Reihenfolge: Überschrift → Status (Titelzeile) → Region-Zeile', () => {
		const w = seite('route');
		const titel = ueberschrift(w);
		const badge = einzig(w, 'trip-detail-status-badge');
		const region = einzig(w, 'trip-region-edit-toggle');
		assert.ok(titel.nr < badge.nr && badge.nr < region.nr, `Reihenfolge h1=${titel.nr}, Status=${badge.nr}, Region=${region.nr}`);
	});
});

describe('#2837 S1 AC-13 — Breadcrumb und Kopftexte folgen der Nutzersprache (de/en, ohne Neuladen)', () => {
	for (const art of ARTEN) {
		test(`${art}: Elternteil de → en aus dem Katalog; kein „Hub"-Text, keine Mobil-Eyebrow`, () => {
			locale.set('de');
			const de = seite(art);
			locale.set('en');
			const en = seite(art);
			for (const [lang, w] of [['de', de], ['en', en]] as const) {
				const link = alle(einzig(w, 'hub-kopf-breadcrumb'), (n) => n.tag === 'a')[0];
				assert.ok(link, `${lang}: kein Eltern-Link`);
				assert.equal(text(link), trFor(lang, ELTERN[art].schluessel as never), `${lang}: Elternteil`);
				const zurueck = alle(einzig(w, 'hub-kopf-leiste'), (n) => n.attrs['data-testid'] === 'back-link')[0];
				assert.equal(zurueck?.attrs['aria-label'], trFor(lang, 'aktionen.zurueck_uebersicht'), `${lang}: Zurück-Aria`);
				assert.equal(einzig(w, 'subscription-hub-send').attrs['data-variant'], 'primary', `${lang}: Senden-Variante`);
			}
			const enText = text(en);
			for (const alt of ['Location comparison · Hub', 'LOCATION COMPARISONS', 'Orts-Vergleich · Hub', 'ORTS-VERGLEICHE'])
				assert.ok(!enText.includes(alt) && !text(de).includes(alt), `alter Kopftext „${alt}" steht noch auf der Seite`);
		});
	}
});
