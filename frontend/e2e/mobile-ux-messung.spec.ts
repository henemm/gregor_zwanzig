// E2E — Mobile-UX-Audit Runde 2 (#2601): Messtests aus Nutzersicht.
//
// Spec: docs/specs/modules/mobile_ux_audit_2601.md (v1.1) — AC-7 bis AC-14.
// Gemessen wird im echten Browser (getBoundingClientRect, getComputedStyle, scrollWidth/
// clientWidth, elementFromPoint), nie am Quelltext.
//
// Profile (Schleife IM Fall, setViewportSize): 390×844, 402×874, Querformat 844×390. Das
// Haupt-Projekt `tests` hat keine Touch-Emulation; die Fixes greifen über
// `@media (max-width: 899px), (pointer: coarse)` — alle drei Profile sind ≤ 899 px breit.
// Sprache: Profilsprache des Test-Nutzers per PUT /api/auth/profile (Muster
// anlege-rahmen-paritaet.spec.ts); das <html lang> wird je Lauf geprüft, damit ein stiller
// Rückfall auf Deutsch nicht als EN-Messung durchgeht. afterEach setzt immer auf „de" zurück.
//
//   AC-7  Segmente Tag/Monat (stage-date-field) und Stunde/Minute (stage-start-time-field) im
//         Etappen-Tab sowie Tag/Monat im Trip-Anlegen (trip-new-date-input) ≥ 24×24 px, DE+EN.
//         Das Jahr ist laut Spec „unverändert" und wird hier nicht vermessen.
//   AC-8  dasselbe im Vergleichs-Editor (context="vergleich"): Zustellung → Laufzeit „Bis Datum"
//         (DatumFeld, testid compare-versand-enddate-input). Der Vergleichs-Editor hat heute KEIN
//         UhrzeitFeld (grep: UhrzeitFeld nur in edit/StageTimeField.svelte) — gemessen werden
//         daher Tag/Monat; die Größe stammt aus demselben Baustein DatumFeld.
//   AC-9  Desktop-Gegenprobe 1280×800 (Maus): Segmentmaße = feste Soll-Werte des Stands VOR
//         Runde 2 (gemessen auf 76ca6e4d9). REGRESSIONSSCHUTZ — dieser Fall ist im RED-Lauf
//         absichtlich GRÜN und muss es nach dem Fix bleiben.
//   AC-10 Brotkrumen im Hub-Kopf (Trip + Vergleich): scrollHeight ≤ clientHeight des Bereichs,
//         und elementFromPoint trifft den Link bei 25 %/50 %/75 % der vollen Trefferhöhe
//         (inkl. Padding der .g-link-tap) — eine abgeschnittene Trefferfläche fällt dort auf.
//   AC-11 (Messteil) Höhenprofil-Etappenrechtecke tragen data-tap-equivalent; die gleichwertige
//         Etappenwahl im Etappen-Tab (stage-cardm-row) ist ≥ 24×24 px. Hochformat-Profile.
//   AC-12 /compare: kein <main> scrollt waagerecht (scrollWidth − clientWidth ≤ 1), DE+EN.
//         /compare/new in EN: die Mobil-Reiterleiste (AnlegeReiter, testid cm-mobile-tabbar —
//         im Code belegt: shared/anlege-rahmen/AnlegeReiter.svelte, eingebunden in
//         compare-new/CompareNewEditor.svelte) läuft entweder nicht über, oder der letzte Reiter
//         ist nach scrollIntoViewIfNeeded vollständig in der Leiste sichtbar und antippbar.
//   AC-13 berechnete font-size ≥ 11 px: Tab-Badges (trip-detail-tab-badge-*, Badge im Reiter
//         compare-detail-tab-orte), ✉ in der Hub-Übersicht, Menülabel „AKTIONEN" des
//         Karten-Menüs (Aktions-Blatt auf /trips), DE+EN.
//   AC-14 Höhe ≥ 36 px: trip-list-new-mobile, compare-list-new-mobile, hub-orte-add, der Knopf
//         in briefings-laufzeit („Etappen öffnen →") und „Im Editor öffnen →" (kein testid —
//         per Rolle/Name gefunden, kein Produktivcode ergänzt).
//
// Kein fester Schlaf, kein networkidle (Positivlisten-Filter A). Aufräumen in afterEach.
// Ausführen (lokaler Stack, siehe Spec „Laufanleitung"; NIE ohne GZ_E2E_API_PROXY_TARGET):
//   cd frontend && npx playwright test e2e/mobile-ux-messung.spec.ts --workers=1

import { test, expect, type Locator, type Page } from '@playwright/test';
import { openHub, seedHub, createTestComparePreset, cleanupTracked, type HubKind, type SeededHub } from './helpers';

type Lang = 'de' | 'en';
const SPRACHEN: readonly Lang[] = ['de', 'en'];
const PROFILE = [
	{ name: '390×844', width: 390, height: 844 },
	{ name: '402×874', width: 402, height: 874 },
	{ name: '844×390 quer', width: 844, height: 390 }
] as const;
const HOCHFORMAT = PROFILE.filter((p) => p.height > p.width);
const DESKTOP = { width: 1280, height: 800 };

const MIN_SEGMENT = 24;
const MIN_TEXT = 11;
const MIN_KNOPF = 36;

const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 9.0, elevation_m });
// Mehrere datierte Etappen mit Startzeit; Etappe 2 lang, 1 und 3 kurz ⇒ schmale Profil-Rechtecke.
const ETAPPEN = [
	{ id: 's1', name: 'Tag 1', date: '2027-08-01', start_time: '07:30', waypoints: [wp('a', 42.0, 800), wp('b', 42.04, 1200)] },
	{ id: 's2', name: 'Tag 2', date: '2027-08-02', start_time: '08:00', waypoints: [wp('c', 42.1, 900), wp('d', 42.3, 1500)] },
	{ id: 's3', name: 'Tag 3', date: '2027-08-03', start_time: '08:15', waypoints: [wp('e', 42.31, 900), wp('f', 42.32, 1000)] }
];

let seeded: SeededHub[] = [];

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

async function seedTrip(page: Page): Promise<string> {
	const hub = await seedHub(page.request, 'route', { extra: { stages: ETAPPEN } });
	seeded.push(hub);
	return hub.id;
}

async function seedVergleich(page: Page): Promise<string> {
	const hub = await seedHub(page.request, 'vergleich');
	seeded.push(hub);
	return hub.id;
}

test.afterEach(async ({ page }) => {
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
	for (const hub of seeded) await hub.aufraeumen();
	seeded = [];
	await cleanupTracked(page.request);
});

async function spracheAktiv(page: Page, lang: Lang, wo: string): Promise<void> {
	await expect(page.locator('html'), `${wo}: Oberfläche in ${lang}`).toHaveAttribute('lang', lang);
}

type Mass = { was: string; w: number; h: number };

/** Sichtbare Segmente (Tag/Monat/Stunde/Minute) unterhalb von `scope` mit berechneter Größe. */
async function segmentMasse(scope: Locator): Promise<Mass[]> {
	return scope.evaluateAll((roots) => {
		const out: { was: string; w: number; h: number }[] = [];
		for (const root of roots) {
			for (const el of Array.from(root.querySelectorAll('[data-segment="day"], [data-segment="month"], [data-segment="hour"], [data-segment="minute"]'))) {
				const r = el.getBoundingClientRect();
				if (r.width === 0 || r.height === 0) continue; // ausgeblendete Doppel-Variante
				out.push({ was: el.getAttribute('data-segment') ?? '?', w: Math.round(r.width * 100) / 100, h: Math.round(r.height * 100) / 100 });
			}
		}
		return out;
	});
}

/** Verstöße je Ort und Segmentart zusammengefasst (gleiche Maße ⇒ eine Zeile mit Anzahl). */
function zuKlein(masse: Mass[], wo: string, min = MIN_SEGMENT): string[] {
	const n = new Map<string, number>();
	for (const m of masse.filter((x) => x.w < min || x.h < min)) {
		const k = `${wo}: Segment ${m.was} ${m.w}×${m.h} px (< ${min}×${min})`;
		n.set(k, (n.get(k) ?? 0) + 1);
	}
	return [...n].map(([k, c]) => (c > 1 ? `${k} ×${c}` : k));
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-7 — Segmentfelder im Trip (Etappen-Tab + Trip-Anlegen)
// ─────────────────────────────────────────────────────────────────────────────
test('AC-7: Datums-/Uhrzeitsegmente im Etappen-Tab und im Trip-Anlegen ≥ 24×24 px (3 Profile, de+en)', async ({ page }) => {
	test.setTimeout(240_000);
	const tripId = await seedTrip(page);
	const verstoesse: string[] = [];
	for (const lang of SPRACHEN) {
		await sprache(page, lang);
		for (const p of PROFILE) {
			await page.setViewportSize({ width: p.width, height: p.height });
			const wo = `${p.name}/${lang}`;

			await openHub(page, 'route', tripId, { tab: 'etappen' });
			await spracheAktiv(page, lang, `${wo} Etappen-Tab`);
			const datum = page.getByTestId('stage-date-field');
			const zeit = page.getByTestId('stage-start-time-field');
			await datum.locator('[data-segment="day"]').first().waitFor({ state: 'visible', timeout: 15_000 });
			const dm = await segmentMasse(datum);
			const zm = await segmentMasse(zeit);
			// Nicht leer messen: 3 Etappen × (Tag+Monat) bzw. × (Stunde+Minute).
			expect(dm.length, `${wo}: sichtbare Datumssegmente im Etappen-Tab`).toBeGreaterThanOrEqual(6);
			expect(zm.length, `${wo}: sichtbare Uhrzeitsegmente im Etappen-Tab`).toBeGreaterThanOrEqual(6);
			verstoesse.push(...zuKlein(dm, `${wo} Etappen-Tab stage-date-field`), ...zuKlein(zm, `${wo} Etappen-Tab stage-start-time-field`));

			await page.goto('/trips/new');
			await spracheAktiv(page, lang, `${wo} Trip-Anlegen`);
			const neu = page.getByTestId('trip-new-date-input');
			await neu.locator('[data-segment="day"]').first().waitFor({ state: 'visible', timeout: 15_000 });
			const nm = await segmentMasse(neu);
			expect(nm.length, `${wo}: sichtbare Datumssegmente im Trip-Anlegen`).toBe(2);
			verstoesse.push(...zuKlein(nm, `${wo} /trips/new trip-new-date-input`));
		}
	}
	expect(verstoesse, `Segmente unter ${MIN_SEGMENT}×${MIN_SEGMENT} px:\n${verstoesse.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-8 — Segmentfelder im Vergleichs-Editor (geteilter Baustein DatumFeld)
// ─────────────────────────────────────────────────────────────────────────────
test('AC-8: Datumssegmente im Vergleichs-Editor (Zustellung → Laufzeit „Bis Datum") ≥ 24×24 px (3 Profile, de+en)', async ({ page }) => {
	test.setTimeout(180_000);
	const id = await seedVergleich(page);
	const verstoesse: string[] = [];
	for (const lang of SPRACHEN) {
		await sprache(page, lang);
		for (const p of PROFILE) {
			await page.setViewportSize({ width: p.width, height: p.height });
			const wo = `${p.name}/${lang}`;
			await openHub(page, 'vergleich', id, { tab: 'zustellung' });
			await spracheAktiv(page, lang, `${wo} Vergleich Zustellung`);
			await page.locator('[data-testid="compare-versand-enddate-date"]:visible').first().click();
			const feld = page.getByTestId('compare-versand-enddate-input');
			await feld.locator('[data-segment="day"]').first().waitFor({ state: 'visible', timeout: 15_000 });
			const m = await segmentMasse(feld);
			expect(m.length, `${wo}: sichtbare Datumssegmente im Vergleichs-Editor`).toBe(2);
			verstoesse.push(...zuKlein(m, `${wo} Vergleich compare-versand-enddate-input`));
		}
	}
	expect(verstoesse, `Segmente unter ${MIN_SEGMENT}×${MIN_SEGMENT} px:\n${verstoesse.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-9 — Desktop-Gegenprobe (Regressionsschutz, im RED-Lauf absichtlich grün)
// ─────────────────────────────────────────────────────────────────────────────
// Soll-Werte des Stands vor Runde 2 (gemessen 2026-11-10 auf 76ca6e4d9, Chromium, 1280×800):
const SOLL_DESKTOP = {
	etappenDatum: { day: [18, 21.5], month: [18, 21.5], year: [34, 21.5] },
	etappenZeit: { hour: [18, 21.5], minute: [18, 21.5] },
	tripNeu: { day: [18, 23], month: [18, 23], year: [34, 23] }
} as const;
const TOLERANZ = 0.5;

test('AC-9: Desktop 1280×800 — Segmentmaße in Etappen-Tab und Trip-Anlegen unverändert (Regressionsschutz)', async ({ page }) => {
	test.setTimeout(90_000);
	const tripId = await seedTrip(page);
	await page.setViewportSize(DESKTOP);
	const abweichungen: string[] = [];
	const pruefe = async (scope: Locator, soll: Record<string, readonly number[]>, wo: string) => {
		const ist = await scope.evaluateAll((roots) => {
			const out: { was: string; w: number; h: number }[] = [];
			for (const root of roots)
				for (const el of Array.from(root.querySelectorAll('[data-segment]'))) {
					const r = el.getBoundingClientRect();
					if (r.width === 0 || r.height === 0) continue;
					out.push({ was: el.getAttribute('data-segment') ?? '?', w: r.width, h: r.height });
				}
			return out;
		});
		const gemessen = new Set<string>();
		for (const m of ist) {
			const s = soll[m.was];
			if (!s) continue;
			gemessen.add(m.was);
			if (Math.abs(m.w - s[0]) > TOLERANZ || Math.abs(m.h - s[1]) > TOLERANZ)
				abweichungen.push(`${wo}: ${m.was} ist ${m.w}×${m.h}, Soll ${s[0]}×${s[1]}`);
		}
		for (const k of Object.keys(soll)) if (!gemessen.has(k)) abweichungen.push(`${wo}: Segment ${k} nicht sichtbar`);
	};

	await openHub(page, 'route', tripId, { tab: 'etappen' });
	await page.getByTestId('stage-date-field').locator('[data-segment="day"]').first().waitFor({ state: 'visible', timeout: 15_000 });
	await pruefe(page.getByTestId('stage-date-field'), SOLL_DESKTOP.etappenDatum, 'Etappen-Tab Datum');
	await pruefe(page.getByTestId('stage-start-time-field'), SOLL_DESKTOP.etappenZeit, 'Etappen-Tab Startzeit');

	await page.goto('/trips/new');
	const neu = page.getByTestId('trip-new-date-input-desktop');
	await neu.locator('[data-segment="day"]').first().waitFor({ state: 'visible', timeout: 15_000 });
	await pruefe(neu, SOLL_DESKTOP.tripNeu, 'Trip-Anlegen (Desktop-Feld)');

	expect(abweichungen, `Desktop-Segmentmaße verändert:\n${abweichungen.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-10 — Brotkrumen im Hub-Kopf nicht abgeschnitten, Link voll antippbar
// ─────────────────────────────────────────────────────────────────────────────
test('AC-10: Brotkrumen-Link im Hub-Kopf (Trip + Vergleich) nicht beschnitten und auf voller Trefferhöhe antippbar (3 Profile)', async ({ page }) => {
	test.setTimeout(120_000);
	const ids: Record<HubKind, string> = { route: await seedTrip(page), vergleich: await seedVergleich(page) };
	const befunde: string[] = [];
	for (const kind of ['route', 'vergleich'] as const) {
		for (const p of PROFILE) {
			await page.setViewportSize({ width: p.width, height: p.height });
			const wo = `${kind} ${p.name}`;
			await openHub(page, kind, ids[kind]);
			const crumb = page.locator('[data-testid="hub-kopf-breadcrumb"]:visible').first();
			await crumb.waitFor({ state: 'visible', timeout: 15_000 });
			const r = await crumb.evaluate((el) => {
				const link = el.querySelector('a') as HTMLElement | null;
				if (!link) return { fehlt: true as const };
				const lr = link.getBoundingClientRect();
				const cx = lr.x + lr.width / 2;
				const treffer = [0.25, 0.5, 0.75].map((f) => {
					const y = lr.y + lr.height * f;
					const hit = document.elementFromPoint(cx, y);
					return { f, y: Math.round(y), ok: !!hit && (hit === link || link.contains(hit)), hit: hit ? `${hit.tagName.toLowerCase()}.${(hit.getAttribute('class') ?? '').split(/\s+/)[0]}` : 'null' };
				});
				return { fehlt: false as const, sh: el.scrollHeight, ch: el.clientHeight, lh: Math.round(lr.height * 10) / 10, treffer };
			});
			if (r.fehlt) {
				befunde.push(`${wo}: kein Link im Brotkrumen-Bereich`);
				continue;
			}
			if (r.sh > r.ch) befunde.push(`${wo}: hub-kopf-breadcrumb scrollHeight ${r.sh} > clientHeight ${r.ch} (Link-Trefferhöhe ${r.lh} px beschnitten)`);
			for (const t of r.treffer)
				if (!t.ok) befunde.push(`${wo}: elementFromPoint bei ${t.f * 100} % der Link-Trefferhöhe (y=${t.y}) trifft ${t.hit}, nicht den Link`);
		}
	}
	expect(befunde, `Brotkrumen beschnitten:\n${befunde.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-11 — Höhenprofil als dokumentierte Ausnahme + gleichwertige Etappenwahl
// ─────────────────────────────────────────────────────────────────────────────
test('AC-11: Höhenprofil-Etappenrechtecke tragen data-tap-equivalent, Etappenwahl im Etappen-Tab ≥ 24×24 px (Hochformat)', async ({ page }) => {
	test.setTimeout(120_000);
	const tripId = await seedTrip(page);
	const befunde: string[] = [];
	for (const p of HOCHFORMAT) {
		await page.setViewportSize({ width: p.width, height: p.height });
		await openHub(page, 'route', tripId);
		const rects = page.locator('[data-testid^="trip-full-profile-stage-"]');
		await expect(rects, `${p.name}: ein Profil-Rechteck je Etappe`).toHaveCount(ETAPPEN.length, { timeout: 15_000 });
		const attr = await rects.evaluateAll((els) =>
			els.map((e) => ({ id: e.getAttribute('data-testid'), w: Math.round(e.getBoundingClientRect().width * 10) / 10, eq: e.hasAttribute('data-tap-equivalent') }))
		);
		for (const a of attr) if (!a.eq) befunde.push(`${p.name}: ${a.id} (${a.w} px breit) ohne data-tap-equivalent`);

		await openHub(page, 'route', tripId, { tab: 'etappen' });
		const rows = page.locator('[data-testid="stage-cardm-row"]:visible');
		await expect(rows, `${p.name}: Etappenwahl je Etappe im Etappen-Tab`).toHaveCount(ETAPPEN.length, { timeout: 15_000 });
		const masse = await rows.evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; }));
		masse.forEach((m, i) => {
			if (m.w < MIN_SEGMENT || m.h < MIN_SEGMENT) befunde.push(`${p.name}: Etappenwahl ${i + 1} im Etappen-Tab ${m.w}×${m.h} px (< 24)`);
		});
	}
	expect(befunde, `Höhenprofil-Ausnahme/Etappenwahl:\n${befunde.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-12 — /compare-Hauptbereich und EN-Reiterleiste von /compare/new
// ─────────────────────────────────────────────────────────────────────────────
test('AC-12a: /compare — kein <main> scrollt waagerecht (Überlauf ≤ 1 px, 3 Profile, de+en)', async ({ page }) => {
	test.setTimeout(120_000);
	const preset = await createTestComparePreset(page.request, { locationIds: ['e2e-loc-innsbruck', 'e2e-loc-stubai'] });
	const befunde: string[] = [];
	for (const lang of SPRACHEN) {
		await sprache(page, lang);
		for (const p of PROFILE) {
			await page.setViewportSize({ width: p.width, height: p.height });
			const wo = `${p.name}/${lang}`;
			await page.goto('/compare');
			await spracheAktiv(page, lang, `${wo} /compare`);
			await page.getByTestId('compare-list-new-mobile').waitFor({ state: 'visible', timeout: 15_000 });
			await page.getByText(preset.name).filter({ visible: true }).first().waitFor({ state: 'visible', timeout: 15_000 });
			const mains = await page.locator('main').evaluateAll((els) =>
				els
					.filter((e) => e.getBoundingClientRect().width > 0)
					.map((e) => ({ cls: (e.getAttribute('class') ?? '').split(/\s+/)[0] || '(ohne Klasse)', sw: e.scrollWidth, cw: e.clientWidth }))
			);
			expect(mains.length, `${wo}: sichtbare <main>`).toBeGreaterThan(0);
			for (const m of mains) if (m.sw - m.cw > 1) befunde.push(`${wo}: <main ${m.cls}> scrollWidth ${m.sw} / clientWidth ${m.cw} (+${m.sw - m.cw} px)`);
		}
	}
	expect(befunde, `waagerechter Überlauf im Hauptbereich von /compare:\n${befunde.join('\n')}`).toEqual([]);
});

test('AC-12b: /compare/new in EN — Mobil-Reiterleiste ohne Überlauf oder letzter Reiter erreichbar und antippbar (3 Profile)', async ({ page }) => {
	test.setTimeout(120_000);
	await sprache(page, 'en');
	const befunde: string[] = [];
	for (const p of PROFILE) {
		await page.setViewportSize({ width: p.width, height: p.height });
		const wo = `${p.name}/en`;
		await page.goto('/compare/new');
		await spracheAktiv(page, 'en', `${wo} /compare/new`);
		const leiste = page.getByTestId('cm-mobile-tabbar');
		await leiste.waitFor({ state: 'visible', timeout: 15_000 });
		const reiter = leiste.locator('button');
		const n = await reiter.count();
		expect(n, `${wo}: Reiter in der Leiste`).toBeGreaterThan(1);
		const letzter = reiter.nth(n - 1);
		const ueberlauf = await leiste.evaluate((el) => ({ sw: el.scrollWidth, cw: el.clientWidth }));
		test.info().annotations.push({ type: 'messung', description: `${wo}: cm-mobile-tabbar scrollWidth ${ueberlauf.sw} / clientWidth ${ueberlauf.cw}` });
		if (ueberlauf.sw - ueberlauf.cw <= 1) continue; // kein Überlauf ⇒ erfüllt
		// Überlauf ⇒ die Leiste muss bewusst scrollbar und als solche erkennbar sein
		// (waagerecht scrollbar + Rand-Ausblendung per mask-image als Hinweis auf weitere Reiter).
		const art = await leiste.evaluate((el) => {
			const cs = getComputedStyle(el);
			return { ox: cs.overflowX, maske: cs.maskImage || cs.getPropertyValue('-webkit-mask-image') || 'none' };
		});
		if (art.ox !== 'auto' && art.ox !== 'scroll') befunde.push(`${wo}: Leiste läuft über (${ueberlauf.sw}/${ueberlauf.cw}), ist aber nicht scrollbar (overflow-x ${art.ox})`);
		if (art.maske === 'none') befunde.push(`${wo}: Leiste läuft über (${ueberlauf.sw}/${ueberlauf.cw}) ohne erkennbaren Scroll-Hinweis (mask-image none)`);
		await letzter.scrollIntoViewIfNeeded();
		const r = await letzter.evaluate((btn) => {
			const bar = btn.closest('[data-testid="cm-mobile-tabbar"]') as HTMLElement;
			const b = btn.getBoundingClientRect();
			const l = bar.getBoundingClientRect();
			const hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
			return {
				drin: b.left >= l.left - 1 && b.right <= l.right + 1,
				b: `${Math.round(b.left)}–${Math.round(b.right)}`,
				l: `${Math.round(l.left)}–${Math.round(l.right)}`,
				trifft: !!hit && (hit === btn || btn.contains(hit)),
				text: (btn.textContent ?? '').trim()
			};
		});
		if (!r.drin) befunde.push(`${wo}: letzter Reiter „${r.text}" (${r.b}) nach Scrollen nicht ganz in der Leiste (${r.l}), Überlauf ${ueberlauf.sw}/${ueberlauf.cw}`);
		if (!r.trifft) befunde.push(`${wo}: letzter Reiter „${r.text}" nach Scrollen nicht antippbar (elementFromPoint trifft ihn nicht)`);
	}
	expect(befunde, `EN-Reiterleiste /compare/new:\n${befunde.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-13 — Kleintext ≥ 11 px an den Fundstellen
// ─────────────────────────────────────────────────────────────────────────────
async function schrift(loc: Locator): Promise<{ text: string; fs: number }[]> {
	return loc.evaluateAll((els) =>
		els
			.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
			.map((e) => ({ text: (e.textContent ?? '').trim().slice(0, 20), fs: parseFloat(getComputedStyle(e).fontSize) }))
	);
}

test('AC-13: Tab-Badges, ✉ in der Übersicht und Menülabel „AKTIONEN" mit berechneter Schrift ≥ 11 px (3 Profile, de+en)', async ({ page }) => {
	test.setTimeout(240_000);
	const tripId = await seedTrip(page);
	const cmpId = await seedVergleich(page);
	const befunde: string[] = [];
	const pruefe = (masse: { text: string; fs: number }[], wo: string, min = 1) => {
		expect(masse.length, `${wo}: Element sichtbar`).toBeGreaterThanOrEqual(min);
		for (const m of masse) if (m.fs < MIN_TEXT) befunde.push(`${wo}: „${m.text}" font-size ${m.fs} px (< ${MIN_TEXT})`);
	};
	for (const lang of SPRACHEN) {
		await sprache(page, lang);
		for (const p of PROFILE) {
			await page.setViewportSize({ width: p.width, height: p.height });
			const wo = `${p.name}/${lang}`;

			// Trip-Hub: Badge am Etappen-Reiter + ✉ in der Übersicht.
			await openHub(page, 'route', tripId);
			await spracheAktiv(page, lang, `${wo} Trip-Hub`);
			await page.getByTestId('hub-overview').waitFor({ state: 'visible', timeout: 15_000 });
			pruefe(await schrift(page.locator('[data-testid^="trip-detail-tab-badge-"]')), `${wo} trip-detail-tab-badge`);
			const brief = page.getByTestId('hub-overview').getByText('✉', { exact: true });
			await brief.first().waitFor({ state: 'visible', timeout: 15_000 });
			pruefe(await schrift(brief), `${wo} ✉ hub-overview`);

			// Vergleichs-Hub: Badge (Anzahl Orte) im Reiter „Orte".
			await openHub(page, 'vergleich', cmpId);
			pruefe(await schrift(page.locator('[data-testid="compare-detail-tab-orte"] [data-slot="segmented-badge"]')), `${wo} compare-detail-tab-orte Badge`);

			// /trips: Karten-Menü öffnen ⇒ Aktions-Blatt mit Menülabel.
			await page.goto('/trips');
			const menue = page.locator('[data-testid^="subscription-card-menu-"]:visible').first();
			await menue.waitFor({ state: 'visible', timeout: 15_000 });
			await menue.click();
			const label = page.getByText(/^(AKTIONEN|ACTIONS)$/i).filter({ visible: true });
			await label.first().waitFor({ state: 'visible', timeout: 10_000 });
			pruefe(await schrift(label), `${wo} Karten-Menü Label`);
			await page.keyboard.press('Escape');
		}
	}
	expect(befunde, `Text unter ${MIN_TEXT} px:\n${befunde.join('\n')}`).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-14 — 28-px-Knöpfe erreichen den 36-px-Boden
// ─────────────────────────────────────────────────────────────────────────────
async function hoehe(loc: Locator, wo: string): Promise<number> {
	await loc.waitFor({ state: 'visible', timeout: 15_000 });
	const h = await loc.evaluate((e) => e.getBoundingClientRect().height);
	expect(h, `${wo}: Knopf sichtbar`).toBeGreaterThan(0);
	return Math.round(h * 100) / 100;
}

test('AC-14: „+ Neuer Trip", „+ Neuer Vergleich", „Im Editor öffnen →", „Ort hinzufügen", Laufzeit-Knopf ≥ 36 px hoch (3 Profile)', async ({ page }) => {
	test.setTimeout(180_000);
	const tripId = await seedTrip(page);
	const cmpId = await seedVergleich(page);
	const befunde: string[] = [];
	const merke = (h: number, wo: string) => { if (h < MIN_KNOPF) befunde.push(`${wo}: Höhe ${h} px (< ${MIN_KNOPF})`); };
	for (const p of PROFILE) {
		await page.setViewportSize({ width: p.width, height: p.height });
		const wo = p.name;

		await page.goto('/trips');
		merke(await hoehe(page.getByTestId('trip-list-new-mobile'), `${wo} trip-list-new-mobile`), `${wo} trip-list-new-mobile`);

		await page.goto('/compare');
		merke(await hoehe(page.getByTestId('compare-list-new-mobile'), `${wo} compare-list-new-mobile`), `${wo} compare-list-new-mobile`);

		await openHub(page, 'route', tripId);
		const editor = page.getByTestId('hub-overview').getByRole('button', { name: 'Im Editor öffnen →' });
		merke(await hoehe(editor, `${wo} Im Editor öffnen`), `${wo} „Im Editor öffnen →"`);

		await openHub(page, 'route', tripId, { tab: 'zustellung' });
		const laufzeit = page.locator('[data-testid="briefings-laufzeit"]:visible').first().getByRole('button');
		merke(await hoehe(laufzeit, `${wo} briefings-laufzeit`), `${wo} briefings-laufzeit-Knopf`);

		await openHub(page, 'vergleich', cmpId, { tab: 'orte' });
		merke(await hoehe(page.locator('[data-testid="hub-orte-add"]:visible').first(), `${wo} hub-orte-add`), `${wo} hub-orte-add`);
	}
	expect(befunde, `Knöpfe unter dem ${MIN_KNOPF}-px-Boden:\n${befunde.join('\n')}`).toEqual([]);
});
