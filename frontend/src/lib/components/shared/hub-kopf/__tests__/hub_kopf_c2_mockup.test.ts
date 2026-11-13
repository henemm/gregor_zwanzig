// TDD RED — Issue #2913 Scheibe c2 (Seitenkopf des Editor-Hubs nach Mockup), Epic #2791.
// Spec: docs/specs/modules/feat_2913_c2_seitenkopf.md — AC-1 bis AC-6, AC-8 bis AC-10 (SSR-Anteil).
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html Z. 228–245 (Leiste),
// 310–326 (CTX/PILL), 358–365 (renderHead/Reiter), 454–465 (Picker), 508–512 (Vorlage-Karte).
//
// Geprüft wird dort, wo es WIRKT: die echten Detailseiten /trips/[id] und /compare/[id]
// (serverseitig gerendert über die Prüfstände f9Pruefstand.ts / f10Pruefstand.ts, feste Uhr,
// ohne Netz) und die echte VorlageKarte. Kein Mock, kein Quelltext-Grep. Der Katalog-Teil
// liest die Katalogdateien als Daten (Parität DE/EN).
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
// testids (gelten für Trip UND Vergleich, beide Seiten über den geteilten HubKopf):
//   hub-kopf-eyebrow  — genau 1×, im Titelblock VOR der h1, reiner Text (keine Kind-Elemente):
//                       Trip „Trip · <Region>“, Vergleich „Orte · <Region>“ (EN „Locations · <Region>“).
//   hub-kopf-meta     — genau 1×, im Titelblock NACH der h1, reiner Text, Teile mit „ · “:
//                       Trip  „<Datumsbereich> · <N Etappen> · <km> km · ↑<m> m“
//                             (Datumsbereich = formatDateRange(trip); N aus listen.anzahl.etappen;
//                              km 1 Nachkommastelle locale-formatiert DE „31,5“, EN „31.5“;
//                              m gerundet mit Tausendertrennung DE „1.737“, EN „1,737“).
//                       Orte  „<N Orte> · Vergleichstabelle · Morgen-Briefing HH:MM“
//                             (N aus listen.anzahl.orte = location_ids.length; Briefing: morning_enabled
//                              ⇒ Morgen-Briefing morning_time, sonst evening_enabled ⇒ Abend-Briefing
//                              evening_time, sonst Teil entfällt).
//   hub-kopf-aktivieren — Btn im hub-kopf-status (Titelzeile), NUR im Zustand Entwurf (draft),
//                       Text aktionen.kopf.aktivieren; beide Kontexte. HubKopf-Prop: `onAktivieren?: () => void`
//                       (Seite übergibt es nur im Entwurf; Klickziel wählt die Seite).
//   HubKopf neue Props: `eyebrowText?: string`, `metaTeile?: string[]` (rendert die beiden testids oben),
//                       `onAktivieren?: () => void`. Snippets eyebrow/meta dürfen bleiben, die Seiten
//                       nutzen aber die neuen Props (genau ein Eyebrow, genau eine Meta-Zeile).
//   Knopf `subscription-hub-send` (bleibt) — Beschriftung aktionen.kopf.test_schicken (nicht Entwurf).
//   Brotkrumen: Trip-Elternteil listen.trips.titel → /trips, Vergleich-Elternteil
//                       aktionen.kopf.eltern_orte → /compare; Kind kein Link.
//   Status-Pill (StatusSchild, testid trip-detail-status-badge, data-status): fünf Zustände in BEIDEN
//                       Kontexten. Vergleich: archived_at ⇒ archived; Enddatum vor heute (nicht archiviert)
//                       ⇒ finished (Regel wie compareFilterStatus); sonst draft/active/paused wie bisher.
//   Reiterleiste (MTabBar): aktiver Reiter aria-current="page", alle anderen ohne aria-current
//                       oder aria-current="false"; Zähler-Badge Etappen = stages.length, Orte = location_ids.length.
//   VorlageKarte: Rücksetz-Text mit doppelten Anführungszeichen (Mockup): DE „Auf „X“ zurücksetzen“,
//                       EN „Reset to “X”“.
// Neue/geänderte Katalog-Schlüssel (DE und EN, Bereich aktionen.json bzw. wetter.json):
//   aktionen.kopf.test_schicken   „Test schicken ▾“        / „Send test ▾“
//   aktionen.kopf.eltern_orte     „Orte“                   / „Locations“
//   aktionen.kopf.eyebrow_trip    „Trip · {region}“        / „Trip · {region}“
//   aktionen.kopf.eyebrow_orte    „Orte · {region}“        / „Locations · {region}“
//   aktionen.kopf.vergleichstabelle „Vergleichstabelle“    / „Comparison table“
//   aktionen.kopf.morgen_briefing „Morgen-Briefing {zeit}“ / „Morning briefing {zeit}“
//   aktionen.kopf.abend_briefing  „Abend-Briefing {zeit}“  / „Evening briefing {zeit}“
//   aktionen.kopf.aktivieren      „Aktivieren“             / „Activate“
//   wetter.vorlage.zuruecksetzen  „Auf „{vorlage}“ zurücksetzen“ / „Reset to “{vorlage}”“   (GEÄNDERT)
//   (Zählwörter wiederverwendet: listen.anzahl.etappen.*, listen.anzahl.orte.*; Kebab: aktionen.weitere)
// ─────────────────────────────────────────────────────────────────────────────────────
//
// Pfadregel #1409: Prüflinge relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { baum, alle, einzig, mitTestid, text, liegtIn, type Knoten } from './htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> hub-kopf -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
const KOMP = path.resolve(HERE, '../../..');

// Prüfstände registrieren alle SSR-Hooks (inkl. f8VarianteHook) und liefern echte Seiten.
const T = await import('../../../trip-detail/__tests__/f9Pruefstand.ts');
const C = await import('../../../compare/__tests__/f10Pruefstand.ts');
const { locale, trFor, trnFor } = T;
const { render } = await import('svelte/server');
const { computeTripStats } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/utils/tripStats.ts')).href);
const { formatDateRange } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/utils/tripHero.ts')).href);

afterEach(() => locale.set('de'));

type Lang = 'de' | 'en';
type Art = 'route' | 'vergleich';
const SPRACHEN: Lang[] = ['de', 'en'];
const ARTEN: Art[] = ['route', 'vergleich'];

function mitSprache<R>(lang: Lang, f: () => R): R {
	locale.set(lang);
	try {
		return f();
	} finally {
		locale.set('de');
	}
}

// ── Fixtures ────────────────────────────────────────────────────────────────────────
// Trip „Mallorca“, vier datierte Etappen (Uhr der Prüfstände: 2026-07-02 ⇒ läuft).
const wp = (id: string, lat: number, ele: number) => ({ id, name: id, lat, lon: 2.7 + lat / 100, elevation_m: ele });
const VIER_ETAPPEN = [
	{ id: 'm1', name: 'Sant Elm – Estellencs', date: '2026-07-01', waypoints: [wp('a', 39.58, 20), wp('b', 39.65, 420)] },
	{ id: 'm2', name: 'Estellencs – Esporles', date: '2026-07-02', waypoints: [wp('c', 39.66, 380), wp('d', 39.67, 1100)] },
	{ id: 'm3', name: 'Esporles – Valldemossa', date: '2026-07-03', waypoints: [wp('e', 39.7, 900), wp('f', 39.71, 1350)] },
	{ id: 'm4', name: 'Valldemossa – Deià', date: '2026-07-04', waypoints: [wp('g', 39.74, 400), wp('h', 39.75, 900)] }
];
const tripMallorca = (extra: Record<string, unknown> = {}) =>
	T.tripLaufend({ id: 'gd-mallorca', name: 'GR221 Mallorca', shortcode: undefined, region: 'Mallorca', stages: VIER_ETAPPEN, ...extra });

const TRIP_ZUSTAENDE: Record<string, () => Record<string, unknown>> = {
	draft: () => tripMallorca({ stages: [{ id: 'd1', name: 'E1', waypoints: [] }] }),
	active: () => tripMallorca(),
	paused: () => tripMallorca({ paused_at: '2026-06-20T08:00:00Z' }),
	archived: () => tripMallorca({ archived_at: '2026-07-01T00:00:00Z' }),
	finished: () => tripMallorca({ stages: VIER_ETAPPEN.map((s, i) => ({ ...s, date: `2026-05-0${i + 1}` })) })
};
// Vergleich: Uhr der Prüfstände 2026-10-29; Region Tirol, drei Orte, Morgen-Briefing 07:00.
const VERGLEICH_ZUSTAENDE: Record<string, () => Record<string, unknown>> = {
	draft: () => C.vergleichEntwurf(),
	active: () => C.vergleichAktiv(),
	paused: () => C.vergleichAktiv({ schedule: 'manual', previous_schedule: 'daily', paused_at: '2026-10-20T08:00:00Z' }),
	archived: () => C.vergleichAktiv({ archived_at: '2026-10-25T00:00:00Z' }),
	finished: () => C.vergleichAktiv({ end_date: '2026-10-01' })
};
const ZUSTAENDE = ['draft', 'active', 'paused', 'archived', 'finished'] as const;

function seite(art: Art, lang: Lang = 'de', daten?: Record<string, unknown>): Knoten {
	return mitSprache(lang, () =>
		baum(
			art === 'route'
				? T.seiteRendern('ruhe', (daten ?? tripMallorca()) as never)
				: C.seiteRendern('ruhe', daten ?? C.vergleichAktiv())
		)
	);
}

const h1 = (w: Knoten): Knoten => {
	const t = alle(w, (n) => n.tag === 'h1');
	assert.equal(t.length, 1, `genau eine Überschrift erwartet, gefunden ${t.length}`);
	return t[0];
};
/** Reiner Text eines Elements ohne Kind-Elemente (Vertrag: Eyebrow und Meta sind reiner Text). */
function reinerText(k: Knoten, was: string): string {
	assert.equal(k.kinder.length, 0, `${was}: erwartet reinen Text ohne Kind-Elemente, gefunden <${k.kinder.map((n) => n.tag).join('>, <')}>`);
	return text(k);
}

// ── Zahlformat (locale) ──────────────────────────────────────────────────────────────
const LOC: Record<Lang, string> = { de: 'de-DE', en: 'en-GB' };
function tripMetaSoll(lang: Lang, trip: Record<string, unknown>): string {
	const stats = computeTripStats(trip);
	const km = new Intl.NumberFormat(LOC[lang], { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(stats.kmTotal);
	const m = new Intl.NumberFormat(LOC[lang], { maximumFractionDigits: 0 }).format(Math.round(stats.ascentM));
	const datum = mitSprache(lang, () => formatDateRange(trip));
	const n = trnFor(lang, 'listen.anzahl.etappen', (trip.stages as unknown[]).length);
	return `${datum} · ${n} · ${km} km · ↑${m} m`;
}

// ═══ Kopf: Eyebrow und Meta (AC-3, AC-4, AC-10) ══════════════════════════════════════

const EYEBROW_SOLL: Record<Art, Record<Lang, string>> = {
	route: { de: 'Trip · Mallorca', en: 'Trip · Mallorca' },
	vergleich: { de: 'Orte · Tirol', en: 'Locations · Tirol' }
};

for (const art of ARTEN) {
	for (const lang of SPRACHEN) {
		describe(`c2 Kopf ${art} ${lang}`, () => {
			test(`AC-3/AC-4: Eyebrow „${EYEBROW_SOLL[art][lang]}“ genau einmal, vor der Überschrift`, () => {
				const w = seite(art, lang);
				const eb = einzig(w, 'hub-kopf-eyebrow');
				assert.equal(reinerText(eb, 'Eyebrow'), EYEBROW_SOLL[art][lang]);
				assert.ok(eb.nr < h1(w).nr, 'Eyebrow steht nicht über dem Titel');
			});

			test('AC-3/AC-4: Meta-Zeile nach Mockup, genau einmal, nach der Überschrift', () => {
				const w = seite(art, lang);
				const meta = einzig(w, 'hub-kopf-meta');
				const soll =
					art === 'route'
						? tripMetaSoll(lang, tripMallorca())
						: lang === 'de'
							? '3 Orte · Vergleichstabelle · Morgen-Briefing 07:00'
							: '3 locations · Comparison table · Morning briefing 07:00';
				assert.equal(reinerText(meta, 'Meta'), soll);
				assert.ok(meta.nr > h1(w).nr, 'Meta-Zeile steht nicht unter dem Titel');
			});
		});
	}
}

describe('c2 Meta Zahlformat und Briefing-Wahl', () => {
	test('AC-3: Trip-Meta DE mit Dezimalkomma und Tausenderpunkt, EN mit Punkt und Komma', () => {
		const de = reinerText(einzig(seite('route', 'de'), 'hub-kopf-meta'), 'Meta');
		const en = reinerText(einzig(seite('route', 'en'), 'hub-kopf-meta'), 'Meta');
		assert.match(de, / · 4 Etappen · \d+,\d km · ↑[\d.]+ m$/);
		assert.match(en, / · 4 stages · \d+\.\d km · ↑[\d,]+ m$/);
	});
	test('AC-4: nur Abend-Briefing konfiguriert ⇒ „Abend-Briefing 18:00“', () => {
		const w = seite('vergleich', 'de', C.vergleichAktiv({ morning_enabled: false }));
		assert.equal(reinerText(einzig(w, 'hub-kopf-meta'), 'Meta'), '3 Orte · Vergleichstabelle · Abend-Briefing 18:00');
	});
	test('AC-4: Orte-Zähler folgt location_ids (2 Orte)', () => {
		const w = seite('vergleich', 'de', C.vergleichAktiv({ location_ids: ['l-hx', 'l-ka'] }));
		assert.match(reinerText(einzig(w, 'hub-kopf-meta'), 'Meta'), /^2 Orte · Vergleichstabelle · /);
	});
	test('AC-3: Etappen-Zähler in der Meta folgt den Daten (5 Etappen)', () => {
		const fuenf = tripMallorca({ stages: [...VIER_ETAPPEN, { ...VIER_ETAPPEN[3], id: 'm5', date: '2026-07-05' }] });
		assert.match(reinerText(einzig(seite('route', 'de', fuenf), 'hub-kopf-meta'), 'Meta'), / · 5 Etappen · /);
	});
});

// ═══ Leiste: Brotkrumen, Kebab, Knopf (AC-1, AC-2, AC-10) ════════════════════════════

const ELTERN: Record<Art, { href: string; text: Record<Lang, string> }> = {
	route: { href: '/trips', text: { de: 'Trips', en: 'Trips' } },
	vergleich: { href: '/compare', text: { de: 'Orte', en: 'Locations' } }
};

for (const art of ARTEN) {
	for (const lang of SPRACHEN) {
		describe(`c2 Leiste ${art} ${lang}`, () => {
			test(`AC-1/AC-2: Brotkrumen „${ELTERN[art].text[lang]} / <Name>“ — Elternteil Link auf ${ELTERN[art].href}, Name kein Link`, () => {
				const krumen = einzig(seite(art, lang), 'hub-kopf-breadcrumb');
				const links = alle(krumen, (n) => n.tag === 'a');
				assert.equal(links.length, 1, `genau ein Link erwartet, gefunden ${links.length}`);
				assert.equal(links[0].attrs.href, ELTERN[art].href);
				assert.equal(text(links[0]), ELTERN[art].text[lang]);
				const name = art === 'route' ? 'GR221 Mallorca' : 'Skitouren Tirol';
				assert.ok(text(krumen).endsWith(name), `Brotkrumen enden nicht auf dem Namen: „${text(krumen)}“`);
				assert.ok(!text(links[0]).includes(name), 'Name ist Teil des Links');
			});

			test(`AC-1/AC-2: Knopf „${lang === 'de' ? 'Test schicken ▾' : 'Send test ▾'}“ (testid subscription-hub-send) in der Leiste`, () => {
				const w = seite(art, lang);
				const knopf = einzig(w, 'subscription-hub-send');
				assert.equal(text(knopf), lang === 'de' ? 'Test schicken ▾' : 'Send test ▾');
				assert.ok(liegtIn(knopf, einzig(w, 'hub-kopf-leiste')), 'Knopf steht nicht in der Leiste');
			});

			test(`AC-1/AC-2: Kebab „${lang === 'de' ? 'Weitere Aktionen' : 'More actions'}“ in der Leiste`, () => {
				const w = seite(art, lang);
				const kebab = einzig(w, 'subscription-kebab');
				assert.ok(liegtIn(kebab, einzig(w, 'hub-kopf-leiste')));
				const beschriftet = [kebab, ...alle(kebab, () => true)].some((n) => n.attrs['aria-label'] === (lang === 'de' ? 'Weitere Aktionen' : 'More actions'));
				assert.ok(beschriftet, 'Kebab ohne aria-label „Weitere Aktionen“');
			});
		});
	}
}

// ═══ Status-Pill über fünf Zustände, Aktivieren im Entwurf (AC-5, AC-10) ═════════════

for (const art of ARTEN) {
	for (const lang of SPRACHEN) {
		for (const zustand of ZUSTAENDE) {
			test(`AC-5 (${art}, ${lang}): Zustand ${zustand} ⇒ Pill „${trFor(lang, `trip.status.${zustand}` as never)}“${zustand === 'draft' ? ' + Aktivieren' : ', kein Aktivieren'}`, () => {
				const daten = (art === 'route' ? TRIP_ZUSTAENDE : VERGLEICH_ZUSTAENDE)[zustand]();
				const w = seite(art, lang, daten);
				const pills = mitTestid(w, 'trip-detail-status-badge');
				assert.equal(pills.length, 1, `Status-Pill ${pills.length}×`);
				assert.equal(pills[0].attrs['data-status'], zustand, `data-status „${pills[0].attrs['data-status']}“ statt „${zustand}“`);
				assert.equal(text(pills[0]).toLowerCase(), trFor(lang, `trip.status.${zustand}` as never).toLowerCase());
				const akt = mitTestid(w, 'hub-kopf-aktivieren');
				if (zustand === 'draft') {
					assert.equal(akt.length, 1, `„Aktivieren“ ${akt.length}× im Entwurf (erwartet 1)`);
					assert.equal(text(akt[0]), lang === 'de' ? 'Aktivieren' : 'Activate');
					assert.ok(liegtIn(akt[0], einzig(w, 'hub-kopf-status')), '„Aktivieren“ steht nicht neben der Pill (Titelzeile)');
				} else {
					assert.equal(akt.length, 0, `„Aktivieren“ im Zustand ${zustand}`);
				}
			});
		}
	}
}

// ═══ Stift im Ruhezustand (AC-9) ═════════════════════════════════════════════════════

for (const art of ARTEN) {
	test(`AC-9 (${art}): Stift für Name und Region nur als Icon mit aria-label, ohne sichtbaren Text`, () => {
		const w = seite(art);
		const p = art === 'route' ? 'trip' : 'compare-hub';
		for (const feld of ['name', 'region']) {
			const stift = einzig(w, `${p}-${feld}-edit-toggle`);
			assert.ok((stift.attrs['aria-label'] ?? '').trim().length > 0, `${feld}: kein aria-label`);
			assert.equal(text(stift), '', `${feld}: sichtbarer Text „${text(stift)}“`);
			assert.ok(alle(stift, (n) => n.tag === 'svg').length === 1, `${feld}: kein Icon`);
		}
	});
}

// ═══ Reiterleiste: Badge und aria-current (AC-6) ════════════════════════════════════

const REITER: Record<Art, { prefix: string; punkte: string; zahl: string }> = {
	route: { prefix: 'trip-detail-tab', punkte: 'etappen', zahl: '4' },
	vergleich: { prefix: 'compare-detail-tab', punkte: 'orte', zahl: '3' }
};
for (const art of ARTEN) {
	describe(`c2 Reiterleiste ${art}`, () => {
		const reiter = (w: Knoten) => alle(w, (n) => n.attrs['role'] === 'tab' && n.attrs['data-slot'] === 'segmented-item');
		test(`AC-6: Reiter „${REITER[art].punkte}“ trägt Badge ${REITER[art].zahl}`, () => {
			const w = seite(art);
			const r = einzig(w, `${REITER[art].prefix}-${REITER[art].punkte}`);
			const b = alle(r, (n) => n.attrs['data-slot'] === 'segmented-badge');
			assert.equal(b.length, 1, 'kein Zähler-Badge');
			assert.equal(text(b[0]), REITER[art].zahl);
		});
		test('AC-6: aktiver Reiter aria-current="page", alle anderen nicht', () => {
			const tabs = reiter(seite(art));
			assert.ok(tabs.length >= 4, `Reiter: ${tabs.length}`);
			const aktiv = tabs.filter((t) => t.attrs['data-state'] === 'active');
			assert.equal(aktiv.length, 1);
			assert.equal(aktiv[0].attrs['aria-current'], 'page', `aktiver Reiter aria-current=${aktiv[0].attrs['aria-current']}`);
			for (const t of tabs.filter((x) => x !== aktiv[0])) {
				assert.ok(t.attrs['aria-current'] === undefined || t.attrs['aria-current'] === 'false', `inaktiver Reiter ${t.attrs['data-value']} mit aria-current=${t.attrs['aria-current']}`);
			}
		});
	});
}
test('AC-6/AC-7: Etappen-Badge folgt den Daten (5 statt 4)', () => {
	const fuenf = tripMallorca({ stages: [...VIER_ETAPPEN, { ...VIER_ETAPPEN[3], id: 'm5', date: '2026-07-05' }] });
	const r = einzig(seite('route', 'de', fuenf), 'trip-detail-tab-etappen');
	assert.equal(text(alle(r, (n) => n.attrs['data-slot'] === 'segmented-badge')[0]), '5');
});

// ═══ Vorlage-Karte (AC-8, AC-10) ═════════════════════════════════════════════════════

const VK = path.join(KOMP, 'organisms', 'wetter-tab', 'VorlageKarte.svelte');
const vkVariante = async (offen: boolean) =>
	(await import(`${pathToFileURL(VK).href}${offen ? `?f8variante=${Buffer.from(JSON.stringify([['let pickerOffen = $state(false);', 'let pickerOffen = $state(true);']])).toString('base64url')}` : ''}`)).default;
const VK_OFFEN = await vkVariante(true);
const VK_ZU = await vkVariante(false);
const LISTE = [
	{ id: 'alpen-trekking', label: 'Alpen-Trekking', anzahl: 14, stichworte: ['thunder', 'gust'] },
	{ id: 'wandern', label: 'Wandern', anzahl: 10, stichworte: ['precipitation'] }
];
const EIGENE = [{ id: 'mf', name: 'Mallorca Frühling', ampel: { metrics: {} } }];
function karte(context: Art, lang: Lang, abweichungen: number, offen = true): Knoten {
	return mitSprache(lang, () =>
		baum(
			render((offen ? VK_OFFEN : VK_ZU) as never, {
				props: {
					context, vorlageId: 'alpen-trekking', liste: LISTE, eigene: EIGENE, abweichungen,
					metrikName: (id: string) => id, aboAmpel: { metrics: {} },
					onUebernehmen: () => {}, onEigene: () => {}, onZuruecksetzen: () => {}, onGespeichert: () => {}
				}
			} as never).body
		)
	);
}
const VK_SOLL: Record<Lang, { titel: string; gruppen: [string, string]; speichern: string; reset: string; unveraendert: string; zwei: string }> = {
	de: { titel: 'Vorlage', gruppen: ['Vorlagen', 'Eigene'], speichern: 'Als eigene Vorlage speichern', reset: 'Auf „Alpen-Trekking“ zurücksetzen', unveraendert: 'unverändert', zwei: '2 Abweichungen' },
	en: { titel: 'Template', gruppen: ['Templates', 'Your own'], speichern: 'Save as your own template', reset: 'Reset to “Alpen-Trekking”', unveraendert: 'unchanged', zwei: '2 deviations' }
};
for (const art of ARTEN) {
	for (const lang of SPRACHEN) {
		describe(`c2 Vorlage-Karte ${art} ${lang}`, () => {
			test('AC-8: Überschrift, Gruppen Vorlagen/Eigene, Aktionen, kein Mail-Kopf-Satz', () => {
				const k = karte(art, lang, 2);
				const s = VK_SOLL[lang];
				const ganz = text(k);
				assert.ok(ganz.startsWith(s.titel), `Karte beginnt nicht mit „${s.titel}“: „${ganz.slice(0, 60)}“`);
				const gruppen = alle(k, (n) => (n.attrs.class ?? '').split(/\s+/).includes('wt-gruppe')).map(text);
				assert.deepEqual(gruppen, s.gruppen);
				assert.equal(text(einzig(k, 'wetter-vorlage-als-eigene')), s.speichern);
				assert.ok(!/ersetzt das Profil|replaces the profile|Kopf der Mail|mail header/i.test(ganz), 'Mail-Kopf-Satz steht in der Karte');
			});
			test(`AC-8: Rücksetzen heißt ${VK_SOLL[lang].reset} (Mockup-Anführungszeichen)`, () => {
				assert.equal(text(einzig(karte(art, lang, 2, false), 'wetter-vorlage-zuruecksetzen')), VK_SOLL[lang].reset);
			});
			test('AC-8: Zustand „unverändert“ bzw. „2 Abweichungen“; ohne Abweichung kein Rücksetzen', () => {
				const ohne = karte(art, lang, 0, false);
				assert.equal(text(einzig(ohne, 'wetter-vorlage-status')), VK_SOLL[lang].unveraendert);
				assert.equal(mitTestid(ohne, 'wetter-vorlage-zuruecksetzen').length, 0);
				if (lang === 'de') assert.equal(text(einzig(karte(art, lang, 2, false), 'wetter-vorlage-status')), VK_SOLL[lang].zwei);
			});
		});
	}
}

// ═══ Katalog-Parität der neuen Schlüssel (AC-10, ADR-0104) ═══════════════════════════

const MESSAGES = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
const katalog = (lang: Lang, bereich: string): Record<string, string> => JSON.parse(readFileSync(path.join(MESSAGES, lang, `${bereich}.json`), 'utf8'));
const NEUE: Array<[string, string, string, string]> = [
	['aktionen', 'aktionen.kopf.test_schicken', 'Test schicken ▾', 'Send test ▾'],
	['aktionen', 'aktionen.kopf.eltern_orte', 'Orte', 'Locations'],
	['aktionen', 'aktionen.kopf.eyebrow_trip', 'Trip · {region}', 'Trip · {region}'],
	['aktionen', 'aktionen.kopf.eyebrow_orte', 'Orte · {region}', 'Locations · {region}'],
	['aktionen', 'aktionen.kopf.vergleichstabelle', 'Vergleichstabelle', 'Comparison table'],
	['aktionen', 'aktionen.kopf.morgen_briefing', 'Morgen-Briefing {zeit}', 'Morning briefing {zeit}'],
	['aktionen', 'aktionen.kopf.abend_briefing', 'Abend-Briefing {zeit}', 'Evening briefing {zeit}'],
	['aktionen', 'aktionen.kopf.aktivieren', 'Aktivieren', 'Activate'],
	['wetter', 'wetter.vorlage.zuruecksetzen', 'Auf „{vorlage}“ zurücksetzen', 'Reset to “{vorlage}”']
];
describe('c2 Katalog: neue Schlüssel DE und EN vollständig', () => {
	for (const [bereich, schluessel, de, en] of NEUE) {
		test(`AC-10: ${schluessel}`, () => {
			assert.equal(katalog('de', bereich)[schluessel], de, `DE ${schluessel}`);
			assert.equal(katalog('en', bereich)[schluessel], en, `EN ${schluessel}`);
		});
	}
});
