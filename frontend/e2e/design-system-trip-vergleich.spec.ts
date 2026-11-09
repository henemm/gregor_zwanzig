// E2E — Issue #2881 Lieferung A (ADR-0111): Design-System auf Trip- und Vergleichsseiten.
//
// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md — DS-Nummer = AC.
//   DS-5  Anlege-Aktion „Neuer Trip"/„Neuer Vergleich" auf Trip-Liste, Vergleichsliste (gefüllt
//         und leer) und Startseite (leer), Computer und Handy: überall `Btn primary`, Ink-Fläche
//         rgb(26, 26, 24), helle Schrift (R4, ADR-0110 „Hauptaktion = Ink").
//   DS-7  `.mono` (Fortschrittszähler beim Anlegen) trägt die Mono-Schrift aus --g-font-mono und
//         font-feature-settings mit "tnum"; `.tnum` schaltet tabellarische Ziffern (R6, TOKENS §12).
//   DS-8  Hub-Reiterleiste am Computer nach ADR-0111 Punkt 1: kein Kasten (oben/links/rechts kein
//         Rahmen, kein Radius, keine Trennstriche), eine 1-px-Grundlinie --g-rule, Reiter 13 px/500
//         --g-ink, aktiv 600 mit 2-px-Unterstrich --g-accent, Zähler Mono 10 px neutral, Radius 3 px;
//         Trip und Vergleich gleich.
//   DS-9  Fortschritts-Segmente beim Anlegen (ADR-0111 Punkt 4): erledigt gefüllt --g-accent, offen
//         ohne Füllung mit 1-px-Kontur --g-ink-3, beide ≥ 3:1 gegen den Seitengrund; Zähler als Text.
//   DS-10 Tabu-Begriffe: „Drafts", „Alert-Trigger", „Alerts justieren" erscheinen auf Trip-Liste und
//         Trip-Übersicht (de) nicht; dort stehen „Entwürfe", „Alarm-Auslöser", „Alarme einstellen".
//   (AC-11 ist der Kern-Test tests/test_adr_index_drift.py.)
//
// Pflicht-Mutationen (Spec Implementation Details 4, Lieferung A): (a) MTabBar-Rahmen-Reset
// entfernt ⇒ DS-8 rot; (b) `.mono`-Regel gelöscht ⇒ DS-7 rot; (c) „+ Neuer Trip" im Leerzustand
// zurück auf accent ⇒ DS-5 rot.
//
// Leerzustände (DS-5) brauchen ein Konto ohne Trips und Vergleiche: dafür der zustellbare
// Zweitnutzer je Worker (testMitZustellbaremZiel, keine zusätzliche Registrierung). Sein Seed-Trip
// `e2e-cockpit-test` wird für die Messung entfernt und im finally unverändert neu angelegt
// (seedeZweitnutzerTrip), damit nachfolgende Specs desselben Workers ihn wieder vorfinden.
// Kein fester Schlaf, kein networkidle: gewartet wird auf sichtbare Elemente.

import { test, expect, type Locator, type Page } from '@playwright/test';
import {
	ANLEGE_SEL,
	HUB_KINDS,
	HUB_SEL,
	TOKEN_RGB,
	anlegenPflicht,
	cleanupTracked,
	kontrastVerhaeltnis,
	openHub,
	seedHub,
	seedeZweitnutzerTrip,
	testMitZustellbaremZiel,
	type HubKind
} from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };
const BREITEN = [DESKTOP, MOBIL] as const;

/** Festwerte aus ADR-0111 / TOKENS.md (getComputedStyle-Form). */
const RULE = 'rgb(216, 211, 194)';
const PAPER = 'rgb(246, 244, 238)';
const TRANSPARENT = 'rgba(0, 0, 0, 0)';

/** Sichtbare Anlege-Knöpfe (Btn-Baustein) mit „Neuer Trip"/„Neuer Vergleich" (optional „+ "). */
const anlegeKnoepfe = (page: Page): Locator =>
	page.locator('[data-slot="btn"]:visible').filter({ hasText: /^\s*(\+\s*)?Neuer (Trip|Vergleich)\s*$/ });

interface KnopfBefund {
	text: string;
	variante: string | null;
	grund: string;
	schrift: string;
}

async function messeAnlegeKnoepfe(page: Page, seite: string, mindestens: number): Promise<KnopfBefund[]> {
	const knoepfe = anlegeKnoepfe(page);
	await expect
		.poll(() => knoepfe.count(), { message: `${seite}: zu wenige sichtbare Anlege-Knöpfe`, timeout: 15_000 })
		.toBeGreaterThanOrEqual(mindestens);
	// Hover-Farbe ausschließen: Maus in eine leere Ecke.
	await page.mouse.move(1, 1);
	const befunde: KnopfBefund[] = [];
	for (let i = 0; i < (await knoepfe.count()); i++) {
		const k = knoepfe.nth(i);
		befunde.push({
			text: ((await k.textContent()) ?? '').trim(),
			variante: await k.getAttribute('data-variant'),
			...(await k.evaluate((el) => {
				const s = getComputedStyle(el);
				return { grund: s.backgroundColor, schrift: s.color };
			}))
		});
	}
	return befunde;
}

function pruefeInk(befunde: KnopfBefund[], seite: string, fehler: string[]): void {
	for (const b of befunde) {
		if (b.variante !== 'primary') fehler.push(`${seite} „${b.text}": data-variant=${b.variante}, erwartet primary`);
		if (b.grund !== TOKEN_RGB.ink) fehler.push(`${seite} „${b.text}": Fläche ${b.grund}, erwartet Ink ${TOKEN_RGB.ink}`);
		if (b.schrift !== PAPER) fehler.push(`${seite} „${b.text}": Schrift ${b.schrift}, erwartet hell ${PAPER}`);
	}
}

// ─── DS-5 (AC-5) ────────────────────────────────────────────────────────────

test.describe('DS-5: Anlege-Aktion überall Btn primary (Ink)', () => {
	for (const breite of BREITEN) {
		test(`DS-5 gefüllt (${breite.width} px): Trip-Liste und Vergleichsliste`, async ({ page }) => {
			await page.setViewportSize(breite);
			const hubs = [await seedHub(page.request, 'route'), await seedHub(page.request, 'vergleich')];
			const fehler: string[] = [];
			try {
				for (const kind of HUB_KINDS) {
					await page.goto(HUB_SEL[kind].liste.url);
					await expect(page.getByTestId(HUB_SEL[kind].liste.zeile(hubs[kind === 'route' ? 0 : 1].id)).first()).toBeAttached({
						timeout: 15_000
					});
					pruefeInk(await messeAnlegeKnoepfe(page, `${kind}-Liste gefüllt ${breite.width}`, 1), `${kind}-Liste gefüllt ${breite.width}`, fehler);
				}
			} finally {
				for (const h of hubs) await h.aufraeumen();
			}
			expect(fehler, fehler.join('\n')).toEqual([]);
		});
	}
});

testMitZustellbaremZiel.describe('DS-5: Leerzustände (Konto ohne Trips und Vergleiche)', () => {
	for (const breite of BREITEN) {
		testMitZustellbaremZiel(`DS-5 leer (${breite.width} px): Trip-Liste, Vergleichsliste, Startseite`, async ({ page }) => {
			await page.setViewportSize(breite);
			const req = page.request;
			// Vorbedingung Leerzustand: Seed-Trip des Zweitnutzers und etwaige Reste entfernen.
			const trips = ((await (await req.get('/api/trips')).json()) as { id: string }[]) ?? [];
			for (const t of trips) await req.delete(`/api/trips/${t.id}`);
			const presets = ((await (await req.get('/api/compare/presets')).json()) as { id: string }[]) ?? [];
			for (const p of presets) await req.delete(`/api/compare/presets/${p.id}`);
			const fehler: string[] = [];
			try {
				// Trip-Liste leer: Kopf-Knopf + Leerzustands-Knopf.
				await page.goto('/trips');
				await expect(page.getByText('Noch keine Trips').first()).toBeVisible({ timeout: 15_000 });
				pruefeInk(await messeAnlegeKnoepfe(page, `Trip-Liste leer ${breite.width}`, 2), `Trip-Liste leer ${breite.width}`, fehler);
				// Vergleichsliste leer: Kopf-Knopf.
				await page.goto('/compare');
				await expect(page.getByText('Noch keine Vergleiche angelegt.').first()).toBeAttached({ timeout: 15_000 });
				pruefeInk(await messeAnlegeKnoepfe(page, `Vergleichsliste leer ${breite.width}`, 1), `Vergleichsliste leer ${breite.width}`, fehler);
				// Startseite leer: „+ Neuer Trip" und „+ Neuer Vergleich".
				await page.goto('/');
				pruefeInk(await messeAnlegeKnoepfe(page, `Startseite leer ${breite.width}`, 2), `Startseite leer ${breite.width}`, fehler);
			} finally {
				const neu = await seedeZweitnutzerTrip(req);
				expect(neu.ok(), `Seed-Trip des Zweitnutzers wiederherstellen: ${neu.status()}`).toBeTruthy();
			}
			expect(fehler, fehler.join('\n')).toEqual([]);
		});
	}
});

// ─── DS-7 (AC-7) ────────────────────────────────────────────────────────────

test('DS-7: .mono = Mono-Schrift aus --g-font-mono mit "tnum"; .tnum = tabellarische Ziffern', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(ANLEGE_SEL.route.url);
	const fortschritt = ANLEGE_SEL.route.fortschritt(page);
	await expect(fortschritt).toBeVisible({ timeout: 15_000 });
	const zaehler = fortschritt.locator('.mono');
	await expect(zaehler).toHaveCount(1);
	const mass = await zaehler.evaluate((el) => {
		const s = getComputedStyle(el);
		// Wert von --g-font-mono an derselben Stelle aufgelöst (Variablen-Kette font-mono → font-data).
		const probe = document.createElement('span');
		probe.style.fontFamily = 'var(--g-font-mono)';
		el.parentElement!.appendChild(probe);
		const soll = getComputedStyle(probe).fontFamily;
		probe.remove();
		// .tnum am echten Dokument (app.css), ohne Schriftwechsel.
		const tnum = document.createElement('span');
		tnum.className = 'tnum';
		tnum.textContent = '0123';
		el.parentElement!.appendChild(tnum);
		const tnumStil = getComputedStyle(tnum);
		const tnumWerte = { numeric: tnumStil.fontVariantNumeric, familie: tnumStil.fontFamily };
		const elternFamilie = getComputedStyle(el.parentElement!).fontFamily;
		tnum.remove();
		return { familie: s.fontFamily, features: s.fontFeatureSettings, soll, tnumWerte, elternFamilie };
	});
	expect(mass.soll, '--g-font-mono ist nicht die Mono-Schrift').toContain('JetBrains Mono');
	expect(mass.familie, 'Schrift des .mono-Zählers').toBe(mass.soll);
	expect(mass.features, 'font-feature-settings des .mono-Zählers').toContain('"tnum"');
	expect(mass.features).toContain('"zero"');
	expect(mass.tnumWerte.numeric, '.tnum ohne tabellarische Ziffern').toContain('tabular-nums');
	expect(mass.tnumWerte.familie, '.tnum wechselt die Schrift').toBe(mass.elternFamilie);
});

// ─── DS-8 (AC-8) ────────────────────────────────────────────────────────────

interface ReiterMass {
	leiste: Record<string, string>;
	inaktiv: Record<string, string>[];
	aktiv: Record<string, string>;
	zaehler: Record<string, string>;
}

async function messeReiterleiste(page: Page, kind: HubKind): Promise<ReiterMass> {
	const leiste = page.getByTestId(HUB_SEL[kind].reiterListe).locator('.mtabbar');
	await expect(leiste.getByRole('tab')).toHaveCount(5);
	await expect(leiste.locator('[data-slot="segmented-badge"]').first()).toBeVisible();
	await page.mouse.move(1, 1);
	return leiste.evaluate((el) => {
		const cs = (e: Element) => getComputedStyle(e);
		const rahmen = (e: Element) => {
			const s = cs(e);
			return {
				borderTopWidth: s.borderTopWidth,
				borderLeftWidth: s.borderLeftWidth,
				borderRightWidth: s.borderRightWidth,
				borderBottomWidth: s.borderBottomWidth,
				borderBottomColor: s.borderBottomColor
			};
		};
		const s = cs(el);
		const reiter = (e: Element) => ({
			...rahmen(e),
			fontSize: cs(e).fontSize,
			fontWeight: cs(e).fontWeight,
			color: cs(e).color,
			backgroundColor: cs(e).backgroundColor
		});
		const badge = el.querySelector('[data-slot="segmented-badge"]')!;
		return {
			leiste: {
				...rahmen(el),
				borderRadius: `${s.borderTopLeftRadius} ${s.borderTopRightRadius} ${s.borderBottomRightRadius} ${s.borderBottomLeftRadius}`
			},
			inaktiv: Array.from(el.querySelectorAll('[data-slot="segmented-item"][data-state="inactive"]')).map(reiter),
			aktiv: reiter(el.querySelector('[data-slot="segmented-item"][data-state="active"]')!),
			zaehler: {
				fontFamily: cs(badge).fontFamily,
				fontSize: cs(badge).fontSize,
				backgroundColor: cs(badge).backgroundColor,
				color: cs(badge).color,
				borderRadius: cs(badge).borderTopLeftRadius
			}
		};
	});
}

test('DS-8: Hub-Reiterleiste am Computer ohne Kasten, Grundlinie --g-rule, 13 px/500, aktiv 600 — Trip = Vergleich', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	const mass = {} as Record<HubKind, ReiterMass>;
	for (const kind of HUB_KINDS) {
		const hub = await seedHub(page.request, kind);
		try {
			await openHub(page, kind, hub.id, { tab: 'uebersicht' });
			mass[kind] = await messeReiterleiste(page, kind);
		} finally {
			await hub.aufraeumen();
		}
	}
	for (const kind of HUB_KINDS) {
		const m = mass[kind];
		// Kein Kasten: oben/links/rechts kein Rahmen, kein Radius; unten eine 1-px-Linie --g-rule.
		expect(m.leiste, `${kind}: Leiste trägt einen Kasten`).toEqual({
			borderTopWidth: '0px',
			borderLeftWidth: '0px',
			borderRightWidth: '0px',
			borderBottomWidth: '1px',
			borderBottomColor: RULE,
			borderRadius: '0px 0px 0px 0px'
		});
		expect(m.inaktiv.length, `${kind}: inaktive Reiter`).toBe(4);
		for (const r of m.inaktiv) {
			expect(r, `${kind}: inaktiver Reiter`).toMatchObject({
				fontSize: '13px',
				fontWeight: '500',
				color: TOKEN_RGB.ink,
				borderTopWidth: '0px',
				borderLeftWidth: '0px',
				borderRightWidth: '0px'
			});
			expect(r.borderBottomColor, `${kind}: inaktiver Reiter trägt Accent`).not.toBe(TOKEN_RGB.accent);
		}
		expect(m.aktiv, `${kind}: aktiver Reiter`).toMatchObject({
			fontSize: '13px',
			fontWeight: '600',
			color: TOKEN_RGB.ink,
			backgroundColor: TRANSPARENT,
			borderBottomWidth: '2px',
			borderBottomColor: TOKEN_RGB.accent,
			borderTopWidth: '0px',
			borderLeftWidth: '0px',
			borderRightWidth: '0px'
		});
		expect(m.zaehler.fontFamily, `${kind}: Zähler nicht Mono`).toContain('JetBrains Mono');
		expect(m.zaehler, `${kind}: Zähler`).toMatchObject({
			fontSize: '10px',
			backgroundColor: TOKEN_RGB.paperDeep,
			color: TOKEN_RGB.ink3,
			borderRadius: '3px'
		});
	}
	expect(mass.vergleich, 'Reiterleiste Trip ≠ Vergleich').toEqual(mass.route);
});

// ─── DS-9 (AC-9) ────────────────────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`DS-9 (${kind}): Fortschritt — erledigt gefüllt --g-accent, offen nur 1-px-Kontur --g-ink-3, beide ≥ 3:1`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		try {
			await anlegenPflicht(page, kind, { name: `E2E-GZ-DS9-${kind}-${Date.now()}` });
			const segmente = ANLEGE_SEL[kind].fortschrittSegment(page);
			await expect(segmente).toHaveCount(ANLEGE_SEL[kind].fortschrittSegmente);
			const fortschritt = ANLEGE_SEL[kind].fortschritt(page);
			await expect(fortschritt).toContainText('2 / 5 Abschnitte eingerichtet', { timeout: 10_000 });
			await expect(segmente.and(page.locator('[data-done="true"]'))).toHaveCount(2);
			// Farbwechsel laufen mit `transition: 350ms` — erst messen, wenn keine Animation mehr läuft.
			await page.evaluate(() =>
				Promise.all(
					document
						.getAnimations()
						.filter((a) => a instanceof CSSTransition)
						.map((a) => a.finished.catch(() => undefined))
				)
			);
			const werte = await segmente.evaluateAll((els) =>
				els.map((el) => {
					const s = getComputedStyle(el);
					return {
						erledigt: el.getAttribute('data-done') === 'true',
						grund: s.backgroundColor,
						rahmen: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth],
						rahmenFarbe: [s.borderTopColor, s.borderRightColor, s.borderBottomColor, s.borderLeftColor],
						rahmenStil: s.borderTopStyle
					};
				})
			);
			const seitenGrund = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
			for (const [i, w] of werte.entries()) {
				if (w.erledigt) {
					expect(w.grund, `Segment ${i} erledigt: Füllung`).toBe(TOKEN_RGB.accent);
					expect(kontrastVerhaeltnis(w.grund, seitenGrund), `Segment ${i} erledigt: Kontrast`).toBeGreaterThanOrEqual(3);
				} else {
					expect(w.grund, `Segment ${i} offen: Füllung`).toBe(TRANSPARENT);
					expect(w.rahmen, `Segment ${i} offen: Kontur`).toEqual(['1px', '1px', '1px', '1px']);
					expect(w.rahmenStil, `Segment ${i} offen: Konturstil`).toBe('solid');
					expect(w.rahmenFarbe, `Segment ${i} offen: Konturfarbe`).toEqual(Array(4).fill(TOKEN_RGB.ink3));
					expect(kontrastVerhaeltnis(TOKEN_RGB.ink3, seitenGrund), `Segment ${i} offen: Kontrast`).toBeGreaterThanOrEqual(3);
				}
			}
		} finally {
			await cleanupTracked(page.request);
		}
	});
}

// ─── DS-10 (AC-10) ──────────────────────────────────────────────────────────

test('DS-10: Trip-Liste und Trip-Übersicht (de) ohne „Drafts", „Alert-Trigger", „Alerts justieren"', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const sprache = await page.request.put('/api/auth/profile', { data: { language: 'de' } });
	expect(sprache.ok(), `Sprache de setzen: ${sprache.status()}`).toBeTruthy();
	const hub = await seedHub(page.request, 'route');
	try {
		await page.goto('/trips');
		await expect(page.getByTestId(HUB_SEL.route.liste.zeile(hub.id)).first()).toBeAttached({ timeout: 15_000 });
		const liste = await page.locator('body').innerText();
		await openHub(page, 'route', hub.id, { tab: 'uebersicht' });
		const panel = page.locator(`[data-testid="${HUB_SEL.route.panel}-uebersicht"]:visible`).first();
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel).toContainText('Morgen-Briefing');
		const uebersicht = await page.locator('body').innerText();
		for (const [seite, text] of [
			['Trip-Liste', liste],
			['Trip-Übersicht', uebersicht]
		] as const) {
			for (const tabu of ['Drafts', 'Alert-Trigger', 'Alerts justieren']) {
				expect(text.includes(tabu), `${seite} zeigt „${tabu}"`).toBe(false);
			}
		}
		expect(liste, 'Trip-Liste: Zähler „Entwürfe"').toContain('Entwürfe');
		expect(liste, 'Trip-Liste: Einleitung „Alarme einstellen"').toContain('Alarme einstellen');
		expect(uebersicht, 'Trip-Übersicht: Zeile „Alarm-Auslöser"').toContain('Alarm-Auslöser');
	} finally {
		await hub.aufraeumen();
	}
});
