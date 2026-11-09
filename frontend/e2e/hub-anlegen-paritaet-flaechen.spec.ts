// E2E — Issue #2880 (Epic #2345, ADR-0097/ADR-0110): Parität Trip/Vergleich bei der Reiterfläche
// im Hub (P1) und bei Feld-Bausteinen und Schritt-Reitern beim Anlegen (P3).
//
// Spec: docs/specs/modules/rework_2880_paritaet_reiterflaeche_anlegefelder.md — AC-1 … AC-6
// (PF-1 … PF-6, Nummer = AC). Gemessen im echten Browser (boundingBox, getComputedStyle),
// Trip gegen Vergleich, Computer 1440 × 900 und Handy 390 × 844; AC-4/AC-5 auf de und en.
//
//   PF-1/PF-2 erstes sichtbares Kind jedes Hub-Reiters: gleicher linker Rand und gleicher Abstand
//             zur Unterkante der Reiterleiste (±1 px); Handy ohne waagerechten Überlauf.
//   PF-3      Reiterfläche (Übersicht, Etappen/Orte): Innenrand 28/40/60 bzw. 20/16/48 px, und sie
//             beginnt direkt an der Leiste und am linken Panelrand (kein Zusatzrand drumherum).
//   PF-4/PF-5 Feldbeschriftung „Name"/„Region" beim Anlegen: gleiche Optik, Pflicht-Sternchen
//             (aria-hidden) an Name, Hinweis „optional · max …" rechts in der Beschriftungszeile
//             (gleicher Abstand zur Feldkante), Name-Eingabe aria-required.
//   PF-6      Schritt-Reiter beim Anlegen: gleiche Höhe/Schrift/Farbe je Zustand (aktiv, gesperrt),
//             gesperrt aria-disabled und gleicher Marker, Optional-Pille an optionalen Schritten
//             (auch gesperrt), Handy jeder Reiter ≥ 44 px.
//
// Pflicht-Mutationen (Spec Implementation Details 6): `.tab-panel { padding: 1.5rem 0 }` zurück ⇒
// PF-1/PF-2 rot; Trip-Reiterfläche 32 px oben ⇒ PF-3 rot; Trip-Feld mit handgeschriebener
// Beschriftung ⇒ PF-4 rot; Optional-Pille fehlt ⇒ PF-6 rot.
//
// Kind-Zweige NUR für Whitelist-Werte (Beschriftungstexte, optionale Schritte). Kein fester
// Schlaf, kein networkidle; Messwerte werden gepollt, bis sie stabil sind.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { ANLEGE_SEL, HUB_KINDS, HUB_SEL, openHub, seedHub, testMitZustellbaremZiel, type HubKind } from './helpers';

const DESKTOP = { width: 1440, height: 900 };
const MOBIL = { width: 390, height: 844 };
const TOL = 1;

/** Reiterpaare Trip ↔ Vergleich (gleiche Stelle in der Leiste). */
const REITER: { name: string; id: Record<HubKind, string> }[] = [
	{ name: 'Übersicht', id: { route: 'uebersicht', vergleich: 'uebersicht' } },
	{ name: 'Etappen ↔ Orte', id: { route: 'etappen', vergleich: 'orte' } },
	{ name: 'Wetter-Metriken', id: { route: 'wetter-metriken', vergleich: 'wetter-metriken' } },
	{ name: 'Wertebereiche', id: { route: 'wertebereiche', vergleich: 'wertebereiche' } },
	{ name: 'Alarme', id: { route: 'alarme', vergleich: 'alarme' } }
];

/** Whitelist: Beschriftungstexte je Art und Sprache (Katalog), optionale Anlege-Schritte. */
const NAME_LABEL: Record<HubKind, Record<'de' | 'en', string>> = {
	route: { de: 'Trip-Name', en: 'Trip name' },
	vergleich: { de: 'Name des Vergleichs', en: 'Comparison name' }
};
const REGION_LABEL: Record<'de' | 'en', string> = { de: 'Region', en: 'Region' };
const OPTIONALE_SCHRITTE: Record<HubKind, string[]> = { route: ['wegpunkte'], vergleich: [] };
const ALLE_SCHRITTE: Record<HubKind, string[]> = {
	route: ['route', 'etappen', 'wegpunkte', 'wetter-metriken', 'wertebereiche', 'alarme'],
	vergleich: ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme']
};

type Box = { x: number; y: number; width: number; height: number };

/** Liest so lange, bis zwei Messungen in Folge gleich und nicht null sind. */
async function stabil<T>(lies: () => Promise<T | null>, was: string): Promise<T> {
	let vorher = '';
	let wert: T | null = null;
	await expect
		.poll(
			async () => {
				wert = await lies();
				const s = JSON.stringify(wert);
				const ok = wert !== null && s === vorher;
				vorher = s;
				return ok;
			},
			{ message: `${was}: keine stabile Messung`, timeout: 20_000, intervals: [300] }
		)
		.toBe(true);
	return wert as T;
}

function nah(ist: number, soll: number, was: string): void {
	expect(Math.abs(ist - soll), `${was}: ist ${ist}, soll ${soll} (±${TOL})`).toBeLessThanOrEqual(TOL);
}

// ─────────────────────────────────────────────────────────────────────────────
// Hub: Reiterfläche
// ─────────────────────────────────────────────────────────────────────────────

interface HubMessung {
	leisteUnten: number;
	panel: Box;
	kind: Box & { tag: string };
	flaeche: (Box & { pad: [number, number, number, number] }) | null;
	ueberlauf: number;
}

/** Misst Reiterleiste, Panel, erstes sichtbares Kind des Panels und (falls da) die Reiterfläche. */
async function messeHub(page: Page, kind: HubKind, reiter: string): Promise<HubMessung> {
	const panelSel = `[data-testid="${HUB_SEL[kind].panel}-${reiter}"]`;
	const leisteSel = `[data-testid="${HUB_SEL[kind].reiterListe}"] [role="tablist"]`;
	return stabil(
		() =>
			page.evaluate(
				({ panelSel, leisteSel }) => {
					const sichtbar = (e: Element) => {
						const r = e.getBoundingClientRect();
						return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
					};
					const box = (e: Element) => {
						const r = e.getBoundingClientRect();
						return { x: Math.round(r.x * 10) / 10, y: Math.round(r.y * 10) / 10, width: Math.round(r.width), height: Math.round(r.height) };
					};
					const panel = [...document.querySelectorAll(panelSel)].find(sichtbar);
					const leiste = [...document.querySelectorAll(leisteSel)].find(sichtbar);
					if (!panel || !leiste) return null;
					const kind = [...panel.children].find(sichtbar);
					if (!kind) return null;
					const fl = [...panel.querySelectorAll('[data-testid$="-reiterflaeche"]')].find(sichtbar);
					const px = (v: string) => Math.round(parseFloat(v) * 10) / 10;
					const s = fl ? getComputedStyle(fl) : null;
					return {
						leisteUnten: Math.round(leiste.getBoundingClientRect().bottom * 10) / 10,
						panel: box(panel),
						kind: { ...box(kind), tag: `${kind.tagName}.${String(kind.className).split(' ')[0]}` },
						flaeche:
							fl && s
								? { ...box(fl), pad: [px(s.paddingTop), px(s.paddingRight), px(s.paddingBottom), px(s.paddingLeft)] as [number, number, number, number] }
								: null,
						ueberlauf: document.documentElement.scrollWidth - window.innerWidth
					};
				},
				{ panelSel, leisteSel }
			),
		`${kind}/${reiter}`
	);
}

async function mitBeidenHubs(page: Page, fn: (id: Record<HubKind, string>) => Promise<void>): Promise<void> {
	const seeds = await Promise.all(HUB_KINDS.map((k) => seedHub(page.request, k)));
	try {
		await fn({ route: seeds[0].id, vergleich: seeds[1].id });
	} finally {
		for (const s of seeds) await s.aufraeumen().catch(() => {});
	}
}

for (const [ac, vp] of [
	['PF-1', DESKTOP],
	['PF-2', MOBIL]
] as const) {
	for (const r of REITER) {
		test(`${ac} (${vp.width} px): Reiter ${r.name} — erstes Inhaltselement bei Trip und Vergleich an derselben Stelle${vp === MOBIL ? ', kein Überlauf' : ''}`, async ({ page }) => {
			test.setTimeout(90_000);
			await page.setViewportSize(vp);
			await mitBeidenHubs(page, async (ids) => {
				const m = {} as Record<HubKind, HubMessung>;
				for (const kind of HUB_KINDS) {
					await openHub(page, kind, ids[kind], { tab: r.id[kind] });
					m[kind] = await messeHub(page, kind, r.id[kind]);
				}
				const [t, v] = [m.route, m.vergleich];
				nah(v.kind.x, t.kind.x, `linker Rand des ersten Kindes (Trip ${t.kind.tag}, Vergleich ${v.kind.tag})`);
				nah(v.kind.y - v.leisteUnten, t.kind.y - t.leisteUnten, `Abstand zur Leiste (Trip ${t.kind.tag}, Vergleich ${v.kind.tag})`);
				if (vp === MOBIL) {
					for (const kind of HUB_KINDS) expect(m[kind].ueberlauf, `${kind}: waagerechter Überlauf`).toBeLessThanOrEqual(0);
				}
			});
		});
	}
}

for (const [vp, pad] of [
	[DESKTOP, [28, 40, 60, 40]],
	[MOBIL, [20, 16, 48, 16]]
] as const) {
	for (const r of REITER.slice(0, 2)) {
		test(`PF-3 (${vp.width} px): Reiter ${r.name} — Reiterfläche mit Innenrand ${pad[0]}/${pad[1]}/${pad[2]} px, direkt an Leiste und Panelrand`, async ({ page }) => {
			test.setTimeout(90_000);
			await page.setViewportSize(vp);
			await mitBeidenHubs(page, async (ids) => {
				for (const kind of HUB_KINDS) {
					await openHub(page, kind, ids[kind], { tab: r.id[kind] });
					const m = await messeHub(page, kind, r.id[kind]);
					expect(m.flaeche, `${kind}/${r.id[kind]}: keine Reiterfläche [data-testid$="-reiterflaeche"]`).not.toBeNull();
					const f = m.flaeche!;
					expect(f.pad, `${kind}/${r.id[kind]}: Innenrand oben/rechts/unten/links`).toEqual([...pad]);
					// Etappen: die Reiterfläche steht unter dem Etappen-Band (Desktop) — dort zählt
					// nur der Innenrand; sonst beginnt sie direkt an Leiste und Panelrand.
					if (!(kind === 'route' && r.id.route === 'etappen' && vp === DESKTOP)) {
						nah(f.y, m.leisteUnten, `${kind}/${r.id[kind]}: Oberkante der Reiterfläche an der Leiste`);
					}
					nah(f.x, m.panel.x, `${kind}/${r.id[kind]}: linke Kante der Reiterfläche am Panelrand`);
				}
			});
		});
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Anlegen: Feld-Bausteine
// ─────────────────────────────────────────────────────────────────────────────

interface FeldMessung {
	stil: Record<string, string>;
	label: Box;
	feld: Box;
	stern: { farbe: string; ariaHidden: string | null } | null;
	hinweis: Box | null;
}

/** Feld zur sichtbaren Beschriftung `label`: Optik, Feldkante, Sternchen, Hinweis „optional · max …". */
async function messeFeld(page: Page, label: string): Promise<FeldMessung> {
	return stabil(
		() =>
			page.evaluate((label) => {
				const sichtbar = (e: Element) => {
					const r = e.getBoundingClientRect();
					return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
				};
				const eigen = (e: Element) =>
					[...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
				const box = (e: Element) => {
					const r = e.getBoundingClientRect();
					return { x: Math.round(r.x * 10) / 10, y: Math.round(r.y * 10) / 10, width: Math.round(r.width), height: Math.round(r.height) };
				};
				const el = [...document.body.querySelectorAll('*')].find((e) => sichtbar(e) && eigen(e) === label);
				if (!el) return null;
				// Beschriftungszeile = höchster Vorfahr ohne Eingabe; Feld = ihr nächstes sichtbares Geschwister.
				let zeile: Element = el;
				while (zeile.parentElement && !zeile.parentElement.querySelector('input, select')) zeile = zeile.parentElement;
				const wurzel = zeile.parentElement;
				let feld = zeile.nextElementSibling;
				while (feld && !sichtbar(feld)) feld = feld.nextElementSibling;
				if (!wurzel || !feld) return null;
				const s = getComputedStyle(el);
				const stern = [zeile, ...zeile.querySelectorAll('*')].find((e) => eigen(e) === '*' && sichtbar(e));
				const hinweis = [...wurzel.querySelectorAll('*')].find((e) => sichtbar(e) && /^optional · max \d+/.test(eigen(e)));
				return {
					stil: {
						fontFamily: s.fontFamily,
						fontSize: s.fontSize,
						fontWeight: s.fontWeight,
						textTransform: s.textTransform,
						letterSpacing: s.letterSpacing,
						color: s.color
					},
					label: box(el),
					feld: box(feld),
					stern: stern ? { farbe: getComputedStyle(stern).color, ariaHidden: stern.getAttribute('aria-hidden') } : null,
					hinweis: hinweis ? box(hinweis) : null
				};
			}, label),
		`Feld „${label}"`
	);
}

async function sprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

for (const [ac, vp] of [
	['PF-4', DESKTOP],
	['PF-5', MOBIL]
] as const) {
	for (const lang of ['de', 'en'] as const) {
		testMitZustellbaremZiel(`${ac} (${vp.width} px, ${lang}): Feldbeschriftungen Name und Region beim Anlegen gleich, Name mit Sternchen und aria-required, Hinweis rechts in der Beschriftungszeile`, async ({ page }) => {
			test.setTimeout(90_000);
			await page.setViewportSize(vp);
			const mobil = vp === MOBIL;
			const m = {} as Record<HubKind, { name: FeldMessung; region: FeldMessung; required: string | null }>;
			try {
				await sprache(page, lang);
				for (const kind of HUB_KINDS) {
					await page.goto(ANLEGE_SEL[kind].url);
					const eingabe = ANLEGE_SEL[kind].name(page, mobil);
					await expect(eingabe).toBeVisible({ timeout: 15_000 });
					m[kind] = {
						name: await messeFeld(page, NAME_LABEL[kind][lang]),
						region: await messeFeld(page, REGION_LABEL[lang]),
						required: await eingabe.getAttribute('aria-required')
					};
				}
			} finally {
				// Zweitnutzer gilt für den ganzen Worker — Sprache für Folgedateien zurück auf de.
				await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			}
			const [t, v] = [m.route, m.vergleich];
			expect(v.name.stil, 'Beschriftung Name: Schrift/Größe/Stärke/Versalien/Laufweite/Farbe').toEqual(t.name.stil);
			expect(v.region.stil, 'Beschriftung Region: Schrift/Größe/Stärke/Versalien/Laufweite/Farbe').toEqual(t.region.stil);
			expect(t.name.stil, 'Name und Region tragen dieselbe Beschriftungsoptik').toEqual(t.region.stil);
			for (const kind of HUB_KINDS) {
				const f = m[kind];
				expect(f.required, `${kind}: Name-Eingabe aria-required`).toBe('true');
				expect(f.name.stern, `${kind}: Pflicht-Sternchen an Name`).not.toBeNull();
				expect(f.name.stern!.ariaHidden, `${kind}: Sternchen aria-hidden`).toBe('true');
				expect(f.region.stern, `${kind}: Region ohne Sternchen`).toBeNull();
				expect(f.region.hinweis, `${kind}: Hinweis „optional · max …" an Region`).not.toBeNull();
				const h = f.region.hinweis!;
				expect(h.y + h.height, `${kind}: Hinweis in der Beschriftungszeile (über dem Feld)`).toBeLessThanOrEqual(f.region.feld.y + TOL);
				expect(h.x, `${kind}: Hinweis rechts neben der Beschriftung`).toBeGreaterThan(f.region.label.x + f.region.label.width);
			}
			expect(v.name.stern!.farbe, 'Sternchen-Farbe').toBe(t.name.stern!.farbe);
			const rechts = (f: FeldMessung) => f.feld.x + f.feld.width - (f.hinweis!.x + f.hinweis!.width);
			const oben = (f: FeldMessung) => f.feld.y - (f.hinweis!.y + f.hinweis!.height);
			nah(rechts(v.region), rechts(t.region), 'Hinweis: Abstand zur rechten Feldkante');
			nah(oben(v.region), oben(t.region), 'Hinweis: Abstand zur oberen Feldkante');
			nah(v.region.feld.y - (v.region.label.y + v.region.label.height), t.region.feld.y - (t.region.label.y + t.region.label.height), 'Beschriftung: Abstand zum Feld');
		});
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Anlegen: Schritt-Reiter
// ─────────────────────────────────────────────────────────────────────────────

async function reiterStil(loc: Locator) {
	return loc.evaluate((el) => {
		const s = getComputedStyle(el);
		const r = el.getBoundingClientRect();
		return {
			hoehe: Math.round(r.height),
			fontFamily: s.fontFamily,
			fontSize: s.fontSize,
			fontWeight: s.fontWeight,
			color: s.color,
			opacity: s.opacity,
			unterstrich: `${s.borderBottomWidth} ${s.borderBottomStyle} ${s.borderBottomColor}`
		};
	});
}

/** Text des Reiters ohne Buchstaben, Leerraum und „&" = Zustandsmarker (z. B. ⊘). */
async function marker(loc: Locator): Promise<string> {
	return ((await loc.textContent()) ?? '').replace(/[\p{L}\s&-]/gu, '');
}

const pille = (reiter: Locator) => reiter.locator('span').filter({ hasText: /^\s*opt(ional)?\s*$/i });

for (const vp of [DESKTOP, MOBIL]) {
	test(`PF-6 (${vp.width} px): Schritt-Reiter beim Anlegen — gleiche Optik je Zustand, gesperrt aria-disabled mit gleichem Marker, Optional-Pille${vp === MOBIL ? ', ≥ 44 px' : ''}`, async ({ page }) => {
		test.setTimeout(90_000);
		await page.setViewportSize(vp);
		const mobil = vp === MOBIL;
		const m = {} as Record<HubKind, { aktiv: Awaited<ReturnType<typeof reiterStil>>; gesperrt: Awaited<ReturnType<typeof reiterStil>>; marker: string; ariaDisabled: string | null }>;
		for (const kind of HUB_KINDS) {
			const sel = ANLEGE_SEL[kind];
			await page.goto(sel.url);
			await expect(sel.name(page, mobil)).toBeVisible({ timeout: 15_000 });
			const aktiv = sel.reiter(page, sel.ersterSchritt, mobil);
			const gesperrt = sel.reiter(page, sel.punkteSchritt, mobil);
			await expect(aktiv).toHaveCount(1);
			await expect(gesperrt).toHaveCount(1);
			m[kind] = {
				aktiv: await reiterStil(aktiv),
				gesperrt: await reiterStil(gesperrt),
				marker: await marker(gesperrt),
				ariaDisabled: await gesperrt.getAttribute('aria-disabled')
			};
			expect(await aktiv.getAttribute('aria-disabled'), `${kind}: aktiver Reiter nicht aria-disabled`).not.toBe('true');
			for (const id of ALLE_SCHRITTE[kind]) {
				const r = sel.reiter(page, id, mobil);
				await expect(r, `${kind}/${id}: Reiter vorhanden`).toHaveCount(1);
				await expect(pille(r), `${kind}/${id}: Optional-Pille`).toHaveCount(OPTIONALE_SCHRITTE[kind].includes(id) ? 1 : 0);
				if (mobil) {
					const b = await r.boundingBox();
					expect(b?.height ?? 0, `${kind}/${id}: Reiter am Handy ≥ 44 px`).toBeGreaterThanOrEqual(44);
				}
			}
		}
		const [t, v] = [m.route, m.vergleich];
		expect(v.aktiv, 'aktiver Reiter: Höhe, Schrift, Farbe, Unterstrich').toEqual(t.aktiv);
		expect(v.gesperrt, 'gesperrter Reiter: Höhe, Schrift, Farbe, Unterstrich').toEqual(t.gesperrt);
		for (const kind of HUB_KINDS) expect(m[kind].ariaDisabled, `${kind}: gesperrter Reiter aria-disabled`).toBe('true');
		expect(v.marker, 'Zustandsmarker gesperrt').toBe(t.marker);
		expect(t.marker, 'gesperrt trägt einen Marker').not.toBe('');
	});
}
