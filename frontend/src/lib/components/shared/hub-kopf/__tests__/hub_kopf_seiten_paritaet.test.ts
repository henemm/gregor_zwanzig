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
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { compile } from 'svelte/compiler';
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
	// #2913 c2 (Mockup): Elternteil „Orte" statt „Orts-Vergleiche".
	vergleich: { schluessel: 'aktionen.kopf.eltern_orte', href: '/compare' }
};
/** Kind des Breadcrumbs: Trip = Kürzel ?? Name, Vergleich = Name. */
const KIND: Record<Art, string> = { route: 'GR20', vergleich: 'Skitouren Tirol' };
/** Text des Kind-Krümels: das einzige Kind-Element des Breadcrumbs, das weder Link noch Trenner „/" ist. */
const kindKruemel = (krumen: Knoten): string => {
	const k = krumen.kinder.filter((n) => n.tag !== 'a' && text(n) !== '/');
	assert.equal(k.length, 1, `Breadcrumb: genau ein Kind-Krümel erwartet, gefunden ${k.length}`);
	return text(k[0]);
};

const ueberschrift = (w: Knoten): Knoten => {
	const t = alle(w, (n) => n.tag === 'h1');
	assert.equal(t.length, 1, `genau eine Überschrift auf der Seite erwartet, gefunden ${t.length}`);
	return t[0];
};
/** Die Titelzeile: #2878 legt Überschrift und Stift in eine innere Gruppe (der Stift springt beim
 *  Umbruch nie allein weg) — die Titelzeile ist daher das Elternelement dieser Gruppe, nicht mehr
 *  das der Überschrift. Status und „Tag x von y" stehen weiterhin in dieser Zeile. */
const titelzeile = (w: Knoten): Knoten => ueberschrift(w).eltern!.eltern!;
/** Das Status-Schild: umgehängt durch #2837 S1b (AC-8) — EIN Baustein `StatusSchild`, bei beiden
 *  Arten mit Testid `trip-detail-status-badge` (vormals Vergleich = CompareStatusPill über data-status). */
const statusBadge = (w: Knoten, _art: Art): Knoten[] => mitTestid(w, 'trip-detail-status-badge');

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
			assert.ok(!liegtIn(senden, titelzeile(w).eltern!), '„Senden" steht neben der Überschrift (im Titelblock)');
			assert.ok(liegtIn(senden, einzig(w, 'hub-kopf-leiste')), '„Senden" steht nicht in der Leiste ganz oben');
		});

		test(`AC-4 (${art}): Breadcrumb „${trFor('de', ELTERN[art].schluessel as never)} / ${KIND[art]}" — Elternteil Link auf ${ELTERN[art].href}, Kind kein Link`, () => {
			const krumen = einzig(seite(art), 'hub-kopf-breadcrumb');
			const links = alle(krumen, (n) => n.tag === 'a');
			assert.equal(links.length, 1, `genau ein Link im Breadcrumb erwartet, gefunden ${links.length}`);
			assert.equal(links[0].attrs.href, ELTERN[art].href);
			assert.equal(text(links[0]), trFor('de', ELTERN[art].schluessel as never), 'Elternteil-Text nicht aus dem Katalog (bzw. im Markup umgeschrieben)');
			// Adversary F003: Kind EXAKT (nicht includes — „GR20 Nord 2026" enthielte „GR20").
			assert.equal(kindKruemel(krumen), KIND[art]);
			assert.ok(!text(links[0]).includes(KIND[art]), 'Kind ist Teil des Links');
		});

		test(`AC-4 (${art}): im Kopf steht nirgends das Wort „Hub"`, () => {
			const w = seite(art);
			const leiste = einzig(w, 'hub-kopf-leiste');
			const zeile = titelzeile(w);
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
			const zeile = titelzeile(w);
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
	// Varianten-Attribute/Klassen) und beide Leisten dieselbe Optik ohne Variante tragen (#2845).
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
	test('die Reiterleisten tragen bei Trip und Vergleich dieselben Klassen (#2845)', () => {
		const leiste = (w: Knoten) => {
			const l = alle(w, (n) => n.attrs.class?.split(/\s+/).includes('mtabbar') ?? false);
			assert.equal(l.length, 1, `Reiterleisten: ${l.length}`);
			return klassen(l[0]).sort();
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
		assert.equal(kindKruemel(krumen), 'GR20 Nord 2026', `Kind des Breadcrumbs ist nicht exakt der Name: „${text(krumen)}"`);
		const links = alle(krumen, (n) => n.tag === 'a');
		assert.equal(links.length, 1);
		assert.ok(!text(links[0]).includes('GR20 Nord 2026'));
	});
});

describe('#2837 S1 AC-6 — Trip: Status steht in der Titelzeile, die Region darunter (vormals .status-line)', () => {
	// #2913 c2 (Mockup Z. 358–365): neben der Pill steht kein Zusatz „Tag x von y" mehr —
	// der Zeitraum steht in der Meta-Zeile (hub_kopf_c2_mockup.test.ts).
	test('Status-Pill in der Titelzeile, kein Zusatz trip-detail-status-supplement; keine eigene Statuszeile', () => {
		const w = seite('route');
		const zeile = titelzeile(w);
		assert.ok(liegtIn(einzig(w, 'trip-detail-status-badge'), zeile), 'die Status-Pill steht nicht in der Titelzeile');
		assert.equal(mitTestid(w, 'trip-detail-status-supplement').length, 0, 'Zusatz „Tag x von y" steht noch neben der Pill');
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

// Adversary F001 (#2837 S1): Abstand und Unterkante (Linie --g-rule) gehören allein dem HubKopf.
// Rot, sobald eine Seite (oder die Trip-Hülle) wieder einen eigenen Rahmen, Abstand oder eine Linie
// um den HubKopf legt — als Klasse/Inline-Stil im gerenderten Markup ODER als Regel im echten
// Stylesheet (svelte/compiler) einer der Dateien, die diese umgebenden Elemente bauen.
describe('#2837 S1 Parität — die Unterkante des Kopfs trägt nur der HubKopf (kein Seiten-Wrapper)', () => {
	const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
	const UMGEBUNG: Record<Art, string[]> = {
		route: ['routes/trips/[id]/+page.svelte', 'lib/components/trip-detail/TripHeader.svelte'],
		vergleich: ['routes/compare/[id]/+page.svelte']
	};
	const RAHMEN = /^(border|padding|margin)/;
	const RAHMEN_KLASSE = /(^|:)(border|p[trblxy]?-|m[trblxy]?-|\[border|\[padding|\[margin)|g-rule/;
	const kopfWurzel = (w: Knoten, art: Art): Knoten => {
		const leiste = einzig(w, 'hub-kopf-leiste');
		const wurzel = vorfahren(leiste).find((n) => n.attrs['data-kind'] === art);
		assert.ok(wurzel, 'HubKopf-Wurzel (data-kind) nicht gefunden');
		return wurzel;
	};
	for (const art of ARTEN) {
		test(`${art}: kein Vorfahre der HubKopf-Wurzel trägt Rahmen/Abstand/Linie (Markup)`, () => {
			const verstoesse = vorfahren(kopfWurzel(seite(art), art)).flatMap((n) => [
				...klassen(n).filter((k) => RAHMEN_KLASSE.test(k)).map((k) => `<${n.tag} class=…${k}>`),
				...(n.attrs.style ?? '').split(';').filter((d) => RAHMEN.test(d.trim()) || /g-rule/.test(d)).map((d) => `<${n.tag} style=…${d.trim()}>`)
			]);
			assert.deepEqual(verstoesse, []);
		});
		test(`${art}: kein Stylesheet der Seite/Hülle gibt den Vorfahren des HubKopf Rahmen/Abstand/Linie`, () => {
			const vorfahrenKlassen = new Set(vorfahren(kopfWurzel(seite(art), art)).flatMap((n) => klassen(n)).filter((k) => !/^svelte-/.test(k)));
			const verstoesse: string[] = [];
			for (const rel of UMGEBUNG[art]) {
				const datei = path.join(SRC, rel);
				const css = compile(readFileSync(datei, 'utf-8'), { generate: 'client', filename: datei }).css?.code.replace(/\/\*[\s\S]*?\*\//g, '') ?? '';
				for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
					const sel = m[1].trim();
					const treffer = [...vorfahrenKlassen].filter((k) => new RegExp(`\\.${k.replace(/[^a-zA-Z0-9_-]/g, '\\$&')}(?![a-zA-Z0-9_-])`).test(sel));
					if (treffer.length && m[2].split(';').some((d) => RAHMEN.test(d.trim()) || /g-rule/.test(d))) verstoesse.push(`${rel}: ${sel} { ${m[2].trim()} }`);
				}
			}
			assert.deepEqual(verstoesse, []);
		});
	}
});

// ── #2837 Nachbesserung S1b (Spec docs/specs/modules/rework_2837_s1b_status_profil.md) ─────────
// EIN Status-Schild (shared/status-schild/StatusSchild.svelte) und das Profil in der Titel-
// Unterzeile bei beiden Arten. Beide Seiten echt gerendert (Prüfstände f9/f10).
// Pflicht-Mutationen, hier gefangen:
//   Vergleich wieder eigenes/gefülltes Schild   → „AC-1/AC-8 … gleiche Attribute" rot
//   profileLabel im Trip weglassen              → „AC-6 … Trekking" rot
// RED HEUTE: Der Vergleich rendert CompareStatusPill (keine Testid, kein data-slot=pill, Text
// „pausiert"/„draft" aus listen.status.*), der Trip trägt kein data-status und kein Profil.
// Wächter (heute schon grün, bewusst): AC-7 (kein Zusatz ohne Aktivität), AC-10 (Laufzeit-Hinweis).

describe('#2837 S1b — Trip und Vergleich zeigen im selben Zustand dasselbe Status-Schild', () => {
	const PAARE = [
		{ zustand: 'active', trip: () => T.tripLaufend(), vergleich: () => C.vergleichAktiv() },
		// #2913 c2: ein pausierter Vergleich mit vergangenem Enddatum zeigt „fertig" (Regel wie
		// compareFilterStatus) — für „pausiert" daher ein Vergleich ohne abgelaufene Laufzeit.
		{ zustand: 'paused', trip: () => T.tripPausiert(), vergleich: () => C.vergleichAktiv({ schedule: 'manual', previous_schedule: 'daily', paused_at: '2026-10-20T08:00:00Z' }) },
		{ zustand: 'draft', trip: () => T.tripEntwurf(), vergleich: () => C.vergleichEntwurf() }
	] as const;
	const schild = (w: Knoten, art: Art): Knoten => {
		const s = statusBadge(w, art);
		assert.equal(s.length, 1, `${art}: [data-testid=trip-detail-status-badge] ${s.length}× statt genau 1× (AC-8)`);
		return s[0];
	};
	for (const lang of ['de', 'en'] as const) {
		for (const p of PAARE) {
			test(`AC-1/AC-8/AC-11 (${lang}, ${p.zustand}): gleicher Text, gleiche Attribute (Pill, Tone, umrandet, data-status), kein Inline-Stil`, () => {
				locale.set(lang);
				const a = schild(seite('route', p.trip()), 'route');
				const b = schild(seite('vergleich', p.vergleich()), 'vergleich');
				assert.equal(a.attrs['data-status'], p.zustand, `Trip: data-status „${a.attrs['data-status']}" (AC-8)`);
				assert.equal(b.attrs['data-status'], p.zustand, `Vergleich: data-status „${b.attrs['data-status']}"`);
				assert.equal(b.attrs['data-slot'], 'pill', 'Vergleich: Schild ist nicht das Pill-Atom (eigener Baustein?)');
				assert.ok('data-outlined' in b.attrs, 'Vergleich: Schild nicht umrandet (gefüllt?) — AC-5');
				assert.equal(text(a), trFor(lang, `trip.status.${p.zustand}`), `Trip-Text nicht aus trip.status.${p.zustand}`);
				assert.equal(text(b), text(a), `Vergleich zeigt „${text(b)}", Trip „${text(a)}"`);
				assert.deepEqual(Object.entries(b.attrs).sort(), Object.entries(a.attrs).sort(), 'Schild-Markup verschieden');
				assert.ok(!('style' in b.attrs), 'Vergleich: Inline-Stil am Schild');
			});
		}
	}
	test('AC-3: Vergleich im Entwurf (de) — Schild „Entwurf", im Kopf nirgends „draft"', () => {
		locale.set('de');
		const w = seite('vergleich', C.vergleichEntwurf());
		assert.equal(text(schild(w, 'vergleich')), trFor('de', 'trip.status.draft'));
		const kopf = vorfahren(einzig(w, 'hub-kopf-leiste')).find((n) => n.attrs['data-kind'] === 'vergleich')!;
		assert.ok(!/\bdraft\b/i.test(text(kopf)), `„draft" im Kopf: ${text(kopf).slice(0, 300)}`);
	});
	test('AC-10 (Wächter): Laufzeit-Hinweis steht weiterhin neben dem Schild in hub-kopf-status', () => {
		const w = seite('vergleich', C.vergleichPausiert()); // paused_at + end_date 2026-10-25 (vergangen)
		const huelle = einzig(w, 'hub-kopf-status');
		const hinweis = mitTestid(w, 'runtime-exceeded-hint');
		assert.equal(hinweis.length, 1, 'Laufzeit-Hinweis fehlt (Messaufbau: pausiert, end_date vergangen)');
		assert.ok(liegtIn(hinweis[0], huelle), 'Laufzeit-Hinweis steht nicht in hub-kopf-status');
	});
});

describe('#2837 S1b — Profil in der Zeile unter dem Titel bei beiden Arten (AC-6, AC-7)', () => {
	const PRAEFIX: Record<Art, string> = { route: 'trip', vergleich: 'compare-hub' };
	/** Das Element direkt hinter dem Region-Stift in der Region-Zeile (Profil-Zusatz oder meta). */
	const hinterStift = (w: Knoten, art: Art): Knoten | undefined => {
		const stift = einzig(w, `${PRAEFIX[art]}-region-edit-toggle`);
		const zeile = stift.eltern!;
		return zeile.kinder[zeile.kinder.indexOf(stift) + 1];
	};
	test('AC-6: Trip mit Aktivität trekking zeigt „· Trekking" direkt hinter dem Region-Stift (wie der Vergleich sein Profil)', () => {
		locale.set('de');
		const trip = hinterStift(seite('route'), 'route');
		const vergleich = hinterStift(seite('vergleich'), 'vergleich');
		assert.equal(vergleich && text(vergleich), `· ${C.helfer.presetProfileLabel('wintersport')}`, 'Messaufbau: Vergleich ohne Profil-Zusatz');
		assert.ok(trip, 'Trip: hinter dem Region-Stift steht nichts — profileLabel fehlt');
		assert.equal(text(trip), `· ${trFor('de', 'trip.aktivitaet.trekking')}`, 'Trip: Profil-Zusatz falsch oder fehlt');
		assert.equal(trip.tag, vergleich!.tag, 'Profil-Zusatz bei Trip und Vergleich verschieden gebaut');
	});
	test('AC-6/AC-11: Profil-Zusatz des Trips folgt der Nutzersprache (en)', () => {
		locale.set('en');
		const trip = hinterStift(seite('route'), 'route');
		assert.equal(trip && text(trip), `· ${trFor('en', 'trip.aktivitaet.trekking')}`);
	});
	test('AC-7 (Wächter): Trip ohne Aktivität und Vergleich ohne Profil — kein Profil-Zusatz hinter dem Stift', () => {
		const trip = hinterStift(seite('route', T.tripLaufend({ activity: undefined })), 'route');
		assert.ok(!trip || !text(trip).startsWith('·'), `Trip ohne Aktivität: Zusatz „${trip && text(trip)}"`);
		const v = hinterStift(seite('vergleich', C.vergleichAktiv({ profil: undefined })), 'vergleich');
		// Der Vergleich hängt danach die Orte-Anzahl (meta, Whitelist) an; ein Profil darf dort nicht stehen.
		assert.ok(!v || !text(v).startsWith(`· ${C.helfer.presetProfileLabel('wintersport')}`), `Vergleich ohne Profil: Zusatz „${v && text(v)}"`);
	});
});
