// Abnahme — Issue #2913, Fix „Metrik-Liste nach Mockup“ (Spec docs/specs/modules/fix_2913_metrikliste_mockup.md).
// AC-1 bis AC-10, AC-12, AC-13: Messwert-Zusicherungen gegen Staging und Ganzseitenaufnahmen Mockup ↔ Staging
// (1280/1024/390 px, Trip + Orte, DE + EN) für den Agenten `mockup-bildpruefer`.
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste:
//   cd frontend && npx playwright test --config playwright.2913-metrikliste.staging.config.ts
// Aufnahmen landen im Test-Ausgabeordner (oder unter $BILD_DIR).
//
// Ganzseitenaufnahme: Staging scrollt in `main.overflow-auto` innerhalb `.h-screen`; `fullPage` sähe nur den
// sichtbaren Ausschnitt. Der Helfer hebt Höhe/Overflow NUR im Testskript zur Aufnahmezeit auf (Spec Impl. 11).

import { test, expect, type Locator, type Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ganzseite } from './ganzseitenaufnahme';
import { HUB_KINDS, type HubKind } from './helpers';
import { DESKTOP, MOBIL, WT, aktiveDerVorlage, oeffneWetter, seedWetter, vorlagen } from './s3a2794-teil3.helpers';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const MOCKUP = 'file://' + path.resolve(HIER, '..', '..', 'docs', 'context', 'einstellungen_neu', 'seiten', 'mockup-hub-fassung3.html');
const KATALOG = path.resolve(HIER, '..', 'src', 'lib', 'i18n', 'messages');
const katalog = (s: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(path.join(KATALOG, s, 'wetter.json'), 'utf8'));

const BREITEN = [1024, 1100, 1280, 1440] as const;
const AUFNAHME_BREITEN = [1280, 1024, 390] as const;
/** Zeilen mit Ampel und mindestens eine reine Anzeige (display_only), damit AC-10 Vergleichszeilen hat. */
const ZUSATZ = ['temperature', 'wind', 'precipitation', 'thunder', 'rain_probability', 'visibility', 'wind_direction', 'pressure'];

test.describe.configure({ mode: 'serial' });

// ── Werkzeuge ────────────────────────────────────────────────────────────────

function bildOrdner(): string {
	const d = process.env.BILD_DIR ?? test.info().outputPath('bilder');
	mkdirSync(d, { recursive: true });
	return d;
}

/** Ganzseitenaufnahme (gemeinsamer Helfer, #2953) plus AC-12: die Aufnahme ist höher als der Viewport. */
async function ganzseiteHoch(page: Page, datei: string): Promise<number> {
	const { hoehe } = await ganzseite(page, datei);
	expect(hoehe, `AC-12: ${path.basename(datei)} nicht höher als der Viewport`).toBeGreaterThan(page.viewportSize()!.height);
	return hoehe;
}

type Zeile = {
	id: string;
	spalten: string[];
	gap: string;
	hoehe: number;
	mitteLinks: number;
	mitteBreite: number;
	aktRechts: number;
	nurAnzeige: boolean;
	/** Runde 2, Befund 2: Zeilen der Aktionsspalte („Alarm ab“, Segmente, Knopf); Mitten innerhalb 6 px = eine Zeile. */
	aktZeilen: number;
};
type Messung = {
	karte: { x: number; breite: number };
	/** Inhaltsbreite von <main>: clientWidth minus horizontales Padding (AC-3). */
	mainInhalt: number;
	zeilen: Zeile[];
	temp: { warum: { schrift: string; zeilen: number }; gruen: { farbe: string; gewicht: string }; untertitel: string } | null;
	gruenToken: string;
	segment: { hoehe: number; hintergrund: string; schrift: string } | null;
	paperToken: string;
	accentDeepToken: string;
	knopf: { breite: number; hoehe: number } | null;
	treffer: { id: string; ok: boolean; fehl: string[] }[];
	marken: { schrift: string; farbe: string; hoehe: string; ueberlappt: boolean; abstand: string; rahmen: string; fugen: number }[];
	ink3Token: string;
	stdSegmentHintergrund: string;
	inkToken: string;
	sichtweiteUntertitel: string | null;
};

/** Alle Messwerte der Metrik-Liste in einem Zug (getComputedStyle / getBoundingClientRect / elementFromPoint). */
async function messen(reiter: Locator): Promise<Messung> {
	return reiter.evaluate((wurzel) => {
		const cs = (el: Element) => getComputedStyle(el);
		const r = (el: Element) => el.getBoundingClientRect();
		const farbeVon = (wert: string) => {
			const p = document.createElement('span');
			p.style.color = wert;
			document.body.appendChild(p);
			const c = cs(p).color;
			p.remove();
			return c;
		};
		const karte = wurzel.querySelector('[data-abschnitt="metriken"]')!;
		const zeilen = Array.from(karte.querySelectorAll<HTMLElement>('.wt-zeile')).map((z) => {
			const mitte = z.querySelector('.wt-mitte')!;
			const akt = z.querySelector('.wt-act')!;
			return {
				id: (z.dataset.testid ?? '').replace('wetter-zeile-', ''),
				spalten: cs(z).gridTemplateColumns.split(' '),
				gap: cs(z).columnGap,
				hoehe: r(z).height,
				mitteLinks: r(mitte).left,
				mitteBreite: r(mitte).width,
				aktRechts: r(akt).right,
				nurAnzeige: !!z.querySelector('.wt-nur'),
				aktZeilen: Array.from(akt.children)
					.map((c) => r(c))
					.filter((b) => b.height > 0)
					.map((b) => b.top + b.height / 2)
					.sort((x, y) => x - y)
					.filter((m, i, a) => i === 0 || m - a[i - 1] > 6).length
			};
		});
		const tz = karte.querySelector('[data-testid="wetter-zeile-temperature"]');
		let temp = null;
		if (tz) {
			const why = tz.querySelector('.wt-why')!;
			const lh = parseFloat(cs(why).lineHeight) || parseFloat(cs(why).fontSize) * 1.45;
			const g = tz.querySelector('[data-testid="wetter-gruen-temperature"]')!;
			temp = {
				warum: { schrift: cs(why).fontSize, zeilen: Math.round(r(why).height / lh) },
				gruen: { farbe: cs(g).color, gewicht: cs(g).fontWeight },
				untertitel: (tz.querySelector('.wt-name small')?.textContent ?? '').trim()
			};
		}
		const seg = karte.querySelector('[data-slot="segmented"][data-variant="kompakt"] [data-slot="segmented-item"][data-active="true"]');
		const knopf = karte.querySelector('[data-testid^="wetter-grenzen-aendern-"]');
		// AC-8: 44×44-Fläche um den Mittelpunkt muss das Element (bzw. bei Segmenten ein Segment derselben Gruppe —
		// waagrecht teilen sich Nachbarsegmente die Fläche, WCAG 2.5.8 Abstandsregel) treffen.
		const ziele = Array.from(karte.querySelectorAll<HTMLElement>('[data-testid^="wetter-zeile-entfernen-"], [data-testid^="wetter-grenzen-aendern-"], [data-slot="segmented"][data-variant="kompakt"] [data-slot="segmented-item"]'));
		const treffer = ziele.slice(0, 40).map((el) => {
			el.scrollIntoView({ block: 'center' });
			const b = r(el);
			const cx = b.left + b.width / 2;
			const cy = b.top + b.height / 2;
			const fehl: string[] = [];
			const punkte: [string, number, number, boolean][] = [
				['oben', cx, cy - 21, true],
				['unten', cx, cy + 21, true],
				['links', cx - 21, cy, false],
				['rechts', cx + 21, cy, false]
			];
			for (const [name, x, y, streng] of punkte) {
				const t = document.elementFromPoint(x, y);
				const eigen = !!t && (t === el || el.contains(t));
				const gruppe = !!t && !streng && el.parentElement === t.closest('[data-slot="segmented"]') && !!t.closest('[data-slot="segmented-item"]');
				if (!eigen && !gruppe) fehl.push(name);
			}
			return { id: el.dataset.testid ?? '', ok: fehl.length === 0, fehl };
		});
		const marken = Array.from(karte.querySelectorAll<HTMLElement>('[data-testid^="wetter-ampel-leiste-"]')).map((l) => {
			const m = l.querySelector('.wt-marken')!;
			const zahlen = Array.from(m.querySelectorAll('i')).map((i) => r(i)).sort((a, b) => a.left - b.left);
			const band = l.querySelector('.wt-band')!;
			const fugen = Array.from(band.querySelectorAll('span')).filter((s) => parseFloat(cs(s).borderLeftWidth) > 0).length;
			return {
				schrift: cs(m).fontSize,
				farbe: cs(m).color,
				hoehe: cs(m).height,
				ueberlappt: zahlen.some((z, i) => i > 0 && z.left < zahlen[i - 1].right - 0.5),
				abstand: cs(l).rowGap,
				rahmen: cs(band).borderTopWidth,
				fugen
			};
		});
		const probe = document.createElement('div');
		probe.setAttribute('data-slot', 'segmented');
		probe.innerHTML = '<button data-slot="segmented-item" data-active="true">x</button>';
		document.body.appendChild(probe);
		const stdSegmentHintergrund = cs(probe.firstElementChild!).backgroundColor;
		probe.remove();
		const sicht = karte.querySelector('[data-testid="wetter-zeile-visibility"] .wt-name small');
		const main = document.querySelector('main')!;
		const mainInhalt = main.clientWidth - parseFloat(cs(main).paddingLeft) - parseFloat(cs(main).paddingRight);
		return {
			karte: { x: r(karte).left, breite: r(karte).width },
			mainInhalt,
			zeilen,
			temp,
			gruenToken: farbeVon('var(--g-ok-fg)'),
			segment: seg ? { hoehe: r(seg).height, hintergrund: cs(seg).backgroundColor, schrift: cs(seg).color } : null,
			paperToken: farbeVon('var(--g-paper)'),
			accentDeepToken: farbeVon('var(--g-accent-deep)'),
			knopf: knopf ? { breite: r(knopf).width, hoehe: r(knopf).height } : null,
			treffer,
			marken,
			ink3Token: farbeVon('var(--g-ink-3)'),
			stdSegmentHintergrund,
			inkToken: farbeVon('var(--g-ink)'),
			sichtweiteUntertitel: sicht ? (sicht.textContent ?? '').trim() : null
		};
	});
}

async function seed(page: Page, kind: HubKind) {
	const v = (await vorlagen(page.request))['alpen-trekking'];
	const auswahl = [...new Set([...aktiveDerVorlage(v), ...ZUSATZ])];
	return seedWetter(page.request, kind, { auswahl });
}

const px = (s: string) => parseFloat(s);

// ── AC-1 bis AC-10: Messwerte je Breite, Trip und Orte identisch ─────────────

test('AC-1/2/3/4/6/7/8/9/10/11: Messwerte bei 1024/1100/1280/1440 und 390 px, Trip = Orte', async ({ page }) => {
	const je: Record<string, Record<HubKind, Messung>> = {};
	for (const kind of HUB_KINDS) {
		const hub = await seed(page, kind);
		try {
			for (const breite of [...BREITEN, 900, MOBIL.width]) {
				await page.setViewportSize(breite === MOBIL.width ? MOBIL : { width: breite, height: DESKTOP.height });
				const reiter = await oeffneWetter(page, kind, hub.id);
				(je[breite] ??= {} as Record<HubKind, Messung>)[kind] = await messen(reiter);
			}
		} finally {
			await hub.aufraeumen();
		}
	}
	await test.info().attach('messwerte.json', { body: JSON.stringify(je, null, 2), contentType: 'application/json' });

	for (const kind of HUB_KINDS) {
		for (const breite of BREITEN) {
			const m = je[breite][kind];
			const tag = `${kind} @${breite}`;
			const desktop = m.karte.breite > 700;
			const t = m.zeilen.find((z) => z.id === 'temperature');
			expect(t, `${tag}: Zeile Temperatur fehlt`).toBeTruthy();
			// AC-2: Layout hängt an der Kartenbreite (Schwelle 700 px).
			expect(t!.spalten.length, `AC-2 ${tag}: Karte ${m.karte.breite} px`).toBe(desktop ? 4 : 2);
			if (desktop) {
				// AC-1: Raster 32 / 130–190 / ≥160 / auto, Abstand 18 px.
				expect(px(t!.spalten[0]), `AC-1 ${tag}`).toBeCloseTo(32, 0);
				expect(px(t!.spalten[1]), `AC-1 ${tag}`).toBeGreaterThanOrEqual(130);
				expect(px(t!.spalten[1]), `AC-1 ${tag}`).toBeLessThanOrEqual(190);
				expect(px(t!.spalten[2]), `AC-1 ${tag}: Mittelspalte`).toBeGreaterThanOrEqual(160);
				expect(t!.gap, `AC-1 ${tag}`).toBe('18px');
				// Runde 2, Befund 2: Mitte ≥ 160 px allein war grün, obwohl die Aktionsspalte dreizeilig umbrach.
				// Die Wirkung entsteht in der Aktionsspalte: „Alarm ab“, Segmente und Knopf in EINER Zeile,
				// Erklärung „Temperatur“ höchstens 4 Zeilen (vorher 6–7 bei 1024).
				for (const z of m.zeilen) expect(z.aktZeilen, `Befund 2 ${tag}: Aktionsspalte ${z.id} umgebrochen`).toBe(1);
				expect(m.temp!.warum.zeilen, `Befund 2 ${tag}: Erklärung Temperatur`).toBeLessThanOrEqual(4);
			}
			// AC-6: „grün“ im grünen Text-Token --g-ok-fg, 600.
			expect(m.temp!.gruen.farbe, `AC-6 ${tag}`).toBe(m.gruenToken);
			expect(m.temp!.gruen.gewicht, `AC-6 ${tag}`).toBe('600');
			// AC-7: aktives Segment hell, Text accent-deep, 23 ± 2 px; Standard-Segmented bleibt dunkel gefüllt.
			expect(m.segment, `AC-7 ${tag}: kompaktes Segment fehlt`).toBeTruthy();
			expect(Math.abs(m.segment!.hoehe - 23), `AC-7 ${tag}: Segmenthöhe ${m.segment!.hoehe}`).toBeLessThanOrEqual(2);
			expect(m.segment!.hintergrund, `AC-7 ${tag}`).toBe(m.paperToken);
			expect(m.segment!.schrift, `AC-7 ${tag}`).toBe(m.accentDeepToken);
			expect(m.stdSegmentHintergrund, `AC-7 ${tag}: Standard-Segmented verändert`).toBe(m.inkToken);
			// AC-8: Knopf sichtbar ca. 29 px, Trefferfläche 44×44 für alle Bedienelemente.
			expect(m.knopf!.hoehe, `AC-8 ${tag}: Knopfhöhe`).toBeLessThanOrEqual(30);
			expect(m.knopf!.hoehe, `AC-8 ${tag}: Knopfhöhe`).toBeGreaterThanOrEqual(26);
			const zuKlein = m.treffer.filter((x) => !x.ok).map((x) => `${x.id} (${x.fehl.join('/')})`);
			expect(zuKlein, `AC-8 ${tag}: Trefferfläche < 44 px`).toEqual([]);
			// AC-9: Grenzzahlen und Leiste.
			for (const mk of m.marken) {
				expect(mk.schrift, `AC-9 ${tag}`).toBe('10.5px');
				expect(mk.farbe, `AC-9 ${tag}`).toBe(m.ink3Token);
				expect(mk.hoehe, `AC-9 ${tag}`).toBe('14px');
				expect(mk.abstand, `AC-9 ${tag}`).toBe('3px');
				expect(mk.rahmen, `AC-9 ${tag}: Rahmen`).toBe('0px');
				expect(mk.fugen, `AC-9 ${tag}: Fugen`).toBe(0);
				if (breite === 1024 || breite === 1280) expect(mk.ueberlappt, `AC-9 ${tag}: Grenzzahlen überlappen`).toBe(false);
			}
			// AC-10: Mittelspalte beginnt überall am selben linken Rand, Aktionsspalte endet am selben rechten Rand.
			const nur = m.zeilen.filter((z) => z.nurAnzeige);
			expect(nur.length, `AC-10 ${tag}: keine display_only-Zeile`).toBeGreaterThan(0);
			for (const z of m.zeilen) {
				expect(Math.abs(z.mitteLinks - t!.mitteLinks), `AC-10 ${tag}: ${z.id} links`).toBeLessThanOrEqual(1);
				expect(Math.abs(z.aktRechts - t!.aktRechts), `AC-10 ${tag}: ${z.id} rechts`).toBeLessThanOrEqual(1);
			}
		}
		// AC-3: Karte bei 1280 = Inhaltsbreite von <main> (≤ 2 px) und ≥ 1000 px; bei 390 px beginnt sie bei x = 16.
		const k1280 = je[1280][kind];
		expect(Math.abs(k1280.karte.breite - k1280.mainInhalt), `AC-3 ${kind} @1280: Karte ${k1280.karte.breite} vs. main ${k1280.mainInhalt}`).toBeLessThanOrEqual(2);
		expect(k1280.karte.breite, `AC-3 ${kind} @1280`).toBeGreaterThanOrEqual(1000);
		expect(Math.round(je[MOBIL.width][kind].karte.x), `AC-3 ${kind} @390`).toBe(16);
		// AC-4: Zeile Temperatur bei 1280 ≤ 124 px, Erklärung ≤ 4 Zeilen bei 12 px.
		const t1280 = je[1280][kind];
		expect(t1280.zeilen.find((z) => z.id === 'temperature')!.hoehe, `AC-4 ${kind}`).toBeLessThanOrEqual(124);
		expect(t1280.temp!.warum.schrift, `AC-4 ${kind}`).toBe('12px');
		expect(t1280.temp!.warum.zeilen, `AC-4 ${kind}`).toBeLessThanOrEqual(4);
		// AC-2: bei 900 px (mit Seitenleiste, Karte ≤ 700) bereits Handy-Layout, bei 390 px zweispaltig 40px 1fr.
		const t900 = je[900][kind];
		if (t900.karte.breite <= 700) expect(t900.zeilen[0].spalten.length, `AC-2 ${kind} @900`).toBe(2);
		const t390 = je[MOBIL.width][kind].zeilen.find((z) => z.id === 'temperature')!;
		expect(t390.spalten.length, `AC-2 ${kind} @390`).toBe(2);
		expect(px(t390.spalten[0]), `AC-2 ${kind} @390`).toBeCloseTo(40, 0);
	}
	// AC-1/AC-11: Trip und Orte liefern dieselben Werte.
	for (const breite of BREITEN) {
		const a = je[breite].route.zeilen.find((z) => z.id === 'temperature')!;
		const b = je[breite].vergleich.zeilen.find((z) => z.id === 'temperature')!;
		expect(b.spalten, `AC-1 @${breite}: Trip ≠ Orte`).toEqual(a.spalten);
	}
});

// ── AC-5: Untertitel DE/EN im DOM ────────────────────────────────────────────

test('AC-5: Untertitel `Einheit · Hinweis` in DE und EN', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	for (const sprache of ['de', 'en'] as const) {
		const k = katalog(sprache);
		const res = await page.request.put('/api/auth/profile', { data: { language: sprache } });
		expect(res.ok(), `Sprache ${sprache}: HTTP ${res.status()}`).toBeTruthy();
		for (const kind of HUB_KINDS) {
			const hub = await seed(page, kind);
			try {
				const reiter = await oeffneWetter(page, kind, hub.id);
				const unter = (id: string) => reiter.getByTestId(WT.zeile(id)).locator('.wt-name small');
				await expect(unter('temperature')).toHaveText(`°C · ${k['wetter.hinweis.temperature']}`);
				await expect(unter('wind')).toHaveText(`km/h · ${k['wetter.hinweis.wind']}`);
				await expect(unter('precipitation')).toHaveText(`mm · ${k['wetter.hinweis.precipitation']}`);
				await expect(unter('rain_probability')).toHaveText(`% · ${k['wetter.untertitel.vorbote']}`);
				await expect(unter('wind_direction')).toHaveText(`° · ${k['wetter.untertitel.nur_anzeige']}`);
				// Runde 2, Befund 1: Gewitter-Leiste beschriftet alle drei Zonen (Mockup „keins · mittel · hoch“).
				await expect(reiter.getByTestId('wetter-ampel-leiste-thunder').locator('.wt-marken--stufen span')).toHaveText([k['wetter.gewitter.keins'], k['wetter.gewitter.mittel'], k['wetter.gewitter.hoch']]);
			} finally {
				await hub.aufraeumen();
			}
		}
	}
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
});

// ── AC-13: km bleibt, Dark Mode lesbar, nichts ragt über die Karte ───────────

test('AC-13: Sichtweite bleibt km, Dark Mode lesbar und nicht abgeschnitten', async ({ page }) => {
	await page.addInitScript(() => localStorage.setItem('gz-dark', '1'));
	for (const vp of [DESKTOP, MOBIL]) {
		await page.setViewportSize(vp);
		for (const kind of HUB_KINDS) {
			const hub = await seed(page, kind);
			try {
				const reiter = await oeffneWetter(page, kind, hub.id);
				expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe('dark');
				const m = await messen(reiter);
				expect(m.sichtweiteUntertitel ?? '', 'AC-13: Sichtweite-Einheit (#2946 Nicht-Ziel)').toMatch(/^km\b/);
				const befund = await reiter.locator('[data-abschnitt="metriken"]').evaluate((karte) => {
					const kr = karte.getBoundingClientRect();
					const hg = getComputedStyle(karte).backgroundColor;
					const aus: string[] = [];
					for (const el of Array.from(karte.querySelectorAll<HTMLElement>('.wt-zeile *'))) {
						const b = el.getBoundingClientRect();
						if (b.width === 0 || b.height === 0) continue;
						if (b.right > kr.right + 1 || b.left < kr.left - 1) aus.push(`ragt: ${el.className || el.tagName}`);
						if (el.childElementCount === 0 && (el.textContent ?? '').trim() && getComputedStyle(el).color === hg) aus.push(`unlesbar: ${el.textContent}`);
					}
					// WCAG-Kontrast (Fix-Runde 1, F002): „grün: …“ und Erklärtext gegen den effektiven Hintergrund ≥ 4,5:1.
					const rgb = (c: string): number[] => (c.match(/[\d.]+/g) ?? []).map(Number);
					const deckend = (c: string) => {
						const w = rgb(c);
						return w.length >= 3 && (w.length < 4 || w[3] > 0);
					};
					const hintergrund = (el: Element): string => {
						for (let e: Element | null = el; e; e = e.parentElement) {
							const c = getComputedStyle(e).backgroundColor;
							if (deckend(c)) return c;
						}
						return getComputedStyle(document.body).backgroundColor;
					};
					const lum = (c: string) => {
						const [r, g, b] = rgb(c).map((v) => {
							const s = v / 255;
							return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
						});
						return 0.2126 * r + 0.7152 * g + 0.0722 * b;
					};
					const kontrast = (a: string, b: string) => {
						const [h, d] = [lum(a), lum(b)].sort((x, y) => y - x);
						return (h + 0.05) / (d + 0.05);
					};
					const texte = Array.from(karte.querySelectorAll<HTMLElement>('.wt-gruen, [data-testid^="wetter-erklaersatz-"]'));
					if (texte.length === 0) aus.push('kontrast: keine grün-/Erklärtexte gefunden');
					for (const el of texte) {
						const k = kontrast(getComputedStyle(el).color, hintergrund(el));
						if (k < 4.5) aus.push(`kontrast ${k.toFixed(2)}:1 < 4,5:1: ${el.dataset.testid ?? el.className}`);
					}
					return aus;
				});
				expect(befund, `AC-13 ${kind} @${vp.width}`).toEqual([]);
			} finally {
				await hub.aufraeumen();
			}
		}
	}
});

// ── AC-12: Ganzseitenaufnahmen Mockup ↔ Staging ──────────────────────────────

test('AC-12: Ganzseitenaufnahmen Mockup und Staging (1280/1024/390, Trip + Orte, DE + EN)', async ({ page, browser }) => {
	test.setTimeout(600_000);
	const ordner = bildOrdner();
	for (const breite of AUFNAHME_BREITEN) {
		const vp = breite === MOBIL.width ? MOBIL : { width: breite, height: DESKTOP.height };
		// Mockup (nur Deutsch vorhanden): Kontext per data-ctx umschalten.
		const m = await browser.newPage({ viewport: vp });
		try {
			await m.goto(MOCKUP);
			for (const ctx of ['trip', 'orte'] as const) {
				await m.evaluate((c) => document.querySelector<HTMLElement>(`[data-ctx="${c}"]`)?.click(), ctx);
				await ganzseiteHoch(m, path.join(ordner, `mockup-${ctx}-de-${breite}.png`));
			}
		} finally {
			await m.close();
		}
		// Staging
		await page.setViewportSize(vp);
		for (const sprache of ['de', 'en'] as const) {
			await page.request.put('/api/auth/profile', { data: { language: sprache } });
			for (const kind of HUB_KINDS) {
				const hub = await seed(page, kind);
				try {
					await oeffneWetter(page, kind, hub.id);
					await ganzseiteHoch(page, path.join(ordner, `staging-${kind === 'route' ? 'trip' : 'orte'}-${sprache}-${breite}.png`));
				} finally {
					await hub.aufraeumen();
				}
			}
		}
	}
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
});
