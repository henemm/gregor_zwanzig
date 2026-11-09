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
// Lieferung B (R2 native Felder → Bausteine, R3 ✓/⊘ → Dot + Text, R5 Tippflächen):
//   DS-1  Startdatum beim Trip-Anlegen über molecules/DatumFeld (bits-ui DatePicker): Kalender
//         öffnen, 19.11.2026 anklicken ⇒ Feld „19.11.2026" (en „19/11/2026", Tag zuerst wie im
//         übrigen UI), Kalender beginnt Montag, gespeichert `2026-11-19` (API), Anzeige im Hub
//         nach Neuladen; Handy: Kalender + Anzeige.
//   DS-2  Etappen-Reiter: Datum und Startzeit über DatumFeld/UhrzeitFeld (Segmente per Tastatur)
//         ⇒ API `2026-11-20`/`07:30`, nach Neuladen „20.11.2026"/„07:30" ohne AM/PM; 1280 und 390.
//   DS-3  Trip-/Vergleichsliste, beide Hubs (Übersicht, Etappen/Orte, Zustellung = Versand-
//         Abschnitt + Mail-Inhalt + Speicher-Chip) und beide Anlege-Abläufe (erster Schritt,
//         Punkte-Schritt, Zustellung), 1280/390, de/en: kein input[type=date|time|radio] im DOM,
//         kein sichtbares natives <select>, kein „✓"/„⊘" im innerText.
//   DS-4  Aktivität beim Trip-Anlegen = listbox (Maus, Enter/Pfeil/Enter, Fokus sichtbar) und
//         Mail-Format im Trip-Hub = radiogroup (Maus, Pfeil links) ⇒ Wert nach Neuladen gespeichert.
//   DS-6  390 × 844: Zurück-Link (Hub, Anlegen), „Mit Standardwerten speichern", jedes ⓘ,
//         jeder Schnellwahl-Chip der Zustellung ≥ 44 × 44 (boundingBox), kein waagerechtes Überlaufen.
//
// Pflicht-Mutationen (Spec Implementation Details 4, Lieferung A): (a) MTabBar-Rahmen-Reset
// entfernt ⇒ DS-8 rot; (b) `.mono`-Regel gelöscht ⇒ DS-7 rot; (c) „+ Neuer Trip" im Leerzustand
// zurück auf accent ⇒ DS-5 rot. Lieferung B: (d) BackLink-Höhe am Handy zurück auf 36 px ⇒ DS-6
// rot; (e) DatumFeld gibt `MM/DD/YYYY` nach außen ⇒ DS-1 rot (gespeicherter Wert/Anzeige nach
// Neuladen); (f) ein ✓ in SaveIndicator zurück ⇒ DS-3 rot (Speicher-Chip im Hub, innerText).
//
// Leerzustände (DS-5) brauchen ein Konto ohne Trips und Vergleiche: dafür der zustellbare
// Zweitnutzer je Worker (testMitZustellbaremZiel, keine zusätzliche Registrierung). Sein Seed-Trip
// `e2e-cockpit-test` wird für die Messung entfernt und im finally unverändert neu angelegt
// (seedeZweitnutzerTrip), damit nachfolgende Specs desselben Workers ihn wieder vorfinden.
// Kein fester Schlaf, kein networkidle: gewartet wird auf sichtbare Elemente.
// Sprachwechsel über PUT /api/auth/profile, im finally zurück auf de (Muster kontrast-trip-vergleich).

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
	registerForCleanup,
	seedHub,
	seedeZweitnutzerTrip,
	testMitZustellbaremZiel,
	tippeDatum,
	tippeUhrzeit,
	tripGpxHochladen,
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
			const profil = (await (await req.get('/api/auth/profile')).json()) as { onboarding_dismissed?: boolean };
			const warAusgeblendet = profil?.onboarding_dismissed === true;
			try {
				// Trip-Liste leer: Kopf-Knopf + Leerzustands-Knopf.
				await page.goto('/trips');
				await expect(page.getByText('Noch keine Trips').first()).toBeVisible({ timeout: 15_000 });
				pruefeInk(await messeAnlegeKnoepfe(page, `Trip-Liste leer ${breite.width}`, 2), `Trip-Liste leer ${breite.width}`, fehler);
				// Vergleichsliste leer: Kopf-Knopf.
				await page.goto('/compare');
				await expect(page.getByText('Noch keine Vergleiche angelegt.').first()).toBeAttached({ timeout: 15_000 });
				pruefeInk(await messeAnlegeKnoepfe(page, `Vergleichsliste leer ${breite.width}`, 1), `Vergleichsliste leer ${breite.width}`, fehler);
				// Startseite leer, BEIDE Zweige der EmptyKachel: Willkommen (neues Konto) und normaler
				// Leerzustand (Willkommen ausgeblendet) — je Kopfleiste (2) + Kachel (2) Anlege-Knöpfe.
				for (const ausblenden of [false, true]) {
					const r = await req.put('/api/auth/profile', { data: { onboarding_dismissed: ausblenden } });
					expect(r.ok(), `onboarding_dismissed=${ausblenden} setzen: ${r.status()}`).toBeTruthy();
					await page.goto('/');
					const willkommen = page.getByTestId('onboarding-willkommen');
					if (ausblenden) await expect(willkommen, 'Leerzustand ohne Willkommen erwartet').toHaveCount(0, { timeout: 15_000 });
					const seite = `Startseite leer (${ausblenden ? 'Leerzustand' : 'Willkommen'}) ${breite.width}`;
					pruefeInk(await messeAnlegeKnoepfe(page, seite, 4), seite, fehler);
				}
			} finally {
				await req.put('/api/auth/profile', { data: { onboarding_dismissed: warAusgeblendet } });
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
		// innerText folgt text-transform (Stat-Beschriftungen in Großbuchstaben) — Vergleich ohne Groß/Klein.
		const liste = (await page.locator('body').innerText()).toLowerCase();
		await openHub(page, 'route', hub.id, { tab: 'uebersicht' });
		const panel = page.locator(`[data-testid="${HUB_SEL.route.panel}-uebersicht"]:visible`).first();
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel).toContainText('Morgen-Briefing');
		const uebersicht = (await page.locator('body').innerText()).toLowerCase();
		for (const [seite, text] of [
			['Trip-Liste', liste],
			['Trip-Übersicht', uebersicht]
		] as const) {
			for (const tabu of ['Drafts', 'Alert-Trigger', 'Alerts justieren']) {
				expect(text.includes(tabu.toLowerCase()), `${seite} zeigt „${tabu}"`).toBe(false);
			}
		}
		expect(liste, 'Trip-Liste: Zähler „Entwürfe"').toContain('entwürfe');
		expect(liste, 'Trip-Liste: Einleitung „Alarme einstellen"').toContain('alarme einstellen');
		expect(uebersicht, 'Trip-Übersicht: Zeile „Alarm-Auslöser"').toContain('alarm-auslöser');
	} finally {
		await hub.aufraeumen();
	}
});

// ═══ Lieferung B (R2 native Felder, R3 Symbole, R5 Tippflächen) ════════════════

/** Vertrag der neuen Bausteine molecules/DatumFeld und molecules/UhrzeitFeld (data-slot). */
const DATUM = {
	eingabe: '[data-slot="datum-feld-eingabe"]',
	knopf: '[data-slot="datum-feld-kalender-knopf"]',
	kalender: '[data-slot="datum-feld-kalender"]',
	wochentag: '[data-slot="datum-feld-wochentag"]',
	zurueck: '[data-slot="datum-feld-zurueck"]',
	weiter: '[data-slot="datum-feld-weiter"]'
} as const;
const UHRZEIT_EINGABE = '[data-slot="uhrzeit-feld-eingabe"]';

/** Startdatum der Trip-Anlege-Seite (Computer/Handy). */
const tripDatumFeld = (page: Page, mobil: boolean): Locator =>
	page.getByTestId(mobil ? 'trip-new-date-input' : 'trip-new-date-input-desktop');

async function setzeSprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const r = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(r.ok(), `Sprache ${lang} setzen: ${r.status()}`).toBeTruthy();
}

/** Kalender des Datumsfelds öffnen, zum Monat blättern, Tag anklicken; liefert die Wochentags-Köpfe. */
async function waehleImKalender(page: Page, feld: Locator, iso: string): Promise<string[]> {
	await feld.locator(DATUM.knopf).click({ timeout: 10_000 });
	const kalender = page.locator(`${DATUM.kalender}:visible`);
	await expect(kalender, 'Kalender-Popover öffnet nicht').toBeVisible();
	const koepfe = (await kalender.locator(DATUM.wochentag).allInnerTexts()).map((s) => s.trim());
	const ziel = kalender.locator(`[data-value="${iso}"]:not([data-outside-month])`);
	const ersterTag = kalender.locator('[data-value]:not([data-outside-month])').first();
	for (let i = 0; i < 36 && (await ziel.count()) === 0; i++) {
		const erster = (await ersterTag.getAttribute('data-value')) ?? '';
		await kalender.locator(erster > iso ? DATUM.zurueck : DATUM.weiter).click();
		await expect(ersterTag).not.toHaveAttribute('data-value', erster);
	}
	await ziel.getByRole('button').click();
	await expect(kalender, 'Kalender schließt nach der Wahl nicht').toBeHidden();
	return koepfe;
}

async function postId(page: Page, pfad: string, ausloesen: () => Promise<void>): Promise<string> {
	const antwort = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === pfad, {
		timeout: 30_000
	});
	await ausloesen();
	const res = await antwort;
	expect(res.ok(), `POST ${pfad}: ${res.status()}`).toBeTruthy();
	const id = ((await res.json()) as { id: string }).id;
	registerForCleanup(pfad === '/api/trips' ? 'trip' : 'preset', id);
	return id;
}

async function tripStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET /api/trips/${id}: ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

// ─── DS-1 (AC-1) ────────────────────────────────────────────────────────────

for (const [lang, anzeige, montag] of [
	['de', '19.11.2026', /^Mo/],
	['en', '19/11/2026', /^Mon/]
] as const) {
	test(`DS-1 (${lang}): Startdatum per Kalender 19.11.2026, Wochenbeginn Montag, gespeichert als 2026-11-19, Anzeige nach Neuladen`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		await setzeSprache(page, lang);
		try {
			await page.goto(ANLEGE_SEL.route.url);
			const feld = tripDatumFeld(page, false);
			await expect(feld).toBeVisible({ timeout: 15_000 });
			await ANLEGE_SEL.route.name(page).fill(`E2E-GZ-DS1-${lang}-${Date.now()}`);
			const koepfe = await waehleImKalender(page, feld, '2026-11-19');
			expect(koepfe[0], `Kalender beginnt nicht mit Montag: ${koepfe.join(' ')}`).toMatch(montag);
			await expect(feld.locator(DATUM.eingabe), 'Anzeige im Feld').toHaveText(anzeige);
			await page.getByTestId('trip-new-tab-etappen').click();
			await tripGpxHochladen(page);
			const knopf = ANLEGE_SEL.route.standardwerte(page);
			await expect(knopf).toBeEnabled({ timeout: 15_000 });
			const id = await postId(page, '/api/trips', () => knopf.click());
			const stages = (await tripStand(page, id)).stages as { date: string }[];
			expect(stages[0]?.date, 'gespeichertes Startdatum').toBe('2026-11-19');
			// Neuladen: das Etappen-Datum im Hub zeigt dasselbe Datum im Format der Sprache.
			await openHub(page, 'route', id, { tab: 'etappen' });
			const etappe = page.locator('[data-testid="stage-date-field"]:visible').first();
			await expect(etappe.locator(DATUM.eingabe), 'Anzeige nach Neuladen').toHaveText(anzeige, { timeout: 15_000 });
		} finally {
			await setzeSprache(page, 'de');
			await cleanupTracked(page.request);
		}
	});
}

test('DS-1 (390 px): Startdatum am Handy per Kalender, Anzeige 19.11.2026, Wochenbeginn Montag', async ({ page }) => {
	await page.setViewportSize(MOBIL);
	await setzeSprache(page, 'de');
	await page.goto(ANLEGE_SEL.route.url);
	const feld = tripDatumFeld(page, true);
	await expect(feld).toBeVisible({ timeout: 15_000 });
	await ANLEGE_SEL.route.name(page, true).fill(`E2E-GZ-DS1-mobil-${Date.now()}`);
	const koepfe = await waehleImKalender(page, feld, '2026-11-19');
	expect(koepfe[0], `Kalender beginnt nicht mit Montag: ${koepfe.join(' ')}`).toMatch(/^Mo/);
	await expect(feld.locator(DATUM.eingabe)).toHaveText('19.11.2026');
	// Name + Datum erfüllt ⇒ der Weiter-Knopf des ersten Schritts ist frei.
	await expect(page.getByTestId('tn-mobile-route-cta').getByRole('button')).toBeEnabled();
});

// ─── DS-2 (AC-2) ────────────────────────────────────────────────────────────

for (const breite of BREITEN) {
	test(`DS-2 (${breite.width} px): Etappe — Datum 20.11.2026 und Startzeit 07:30 über die neuen Felder, nach Neuladen gespeichert (24 h)`, async ({
		page
	}) => {
		await page.setViewportSize(breite);
		await setzeSprache(page, 'de');
		const hub = await seedHub(page.request, 'route');
		try {
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const datum = page.locator('[data-testid="stage-date-field"]:visible').first();
			const zeit = page.locator('[data-testid="stage-start-time-field"]:visible').first();
			await tippeDatum(page, datum, '2026-11-20');
			await tippeUhrzeit(page, zeit, '07:30');
			await expect
				.poll(
					async () => {
						const s = ((await tripStand(page, hub.id)).stages as { date: string; start_time?: string }[])[0];
						return `${s?.date} ${s?.start_time}`;
					},
					{ message: 'Datum/Startzeit nicht gespeichert', timeout: 15_000 }
				)
				.toBe('2026-11-20 07:30');
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const datumNeu = page.locator('[data-testid="stage-date-field"]:visible').first();
			const zeitNeu = page.locator('[data-testid="stage-start-time-field"]:visible').first();
			await expect(datumNeu.locator(DATUM.eingabe)).toHaveText('20.11.2026', { timeout: 15_000 });
			await expect(zeitNeu.locator(UHRZEIT_EINGABE)).toHaveText('07:30');
			await expect(zeitNeu.locator('[data-segment="dayPeriod"]'), '24 h: kein AM/PM-Segment').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── DS-3 (AC-3) ────────────────────────────────────────────────────────────

/** Zustellung im Hub/Anlegen: Versand-Abschnitt, Mail-Inhalt-Karte, Speicher-Chip. */
const ZUSTELLUNG =
	'[data-testid="versand-abschnitt"], [data-testid="report-mail-content"], [data-testid="save-indicator"]';

/** Native Datums-/Uhrzeit-/Radio-Felder (im DOM), sichtbare native <select>, ✓/⊘ im sichtbaren Text. */
async function pruefeSeite(page: Page, seite: string, fehler: string[], bereich: string | null = null): Promise<void> {
	const r = await page.evaluate((bereich) => {
		const wurzeln = bereich ? Array.from(document.querySelectorAll<HTMLElement>(bereich)) : [document.body];
		const sichtbar = (el: Element) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
		const nativ: string[] = [];
		const symbole: string[] = [];
		for (const w of wurzeln) {
			for (const el of w.querySelectorAll('input[type="date"], input[type="time"], input[type="radio"]')) {
				nativ.push(`input[type=${el.getAttribute('type')}] ${el.getAttribute('data-testid') ?? el.getAttribute('name') ?? ''}`);
			}
			for (const el of w.querySelectorAll('select')) if (sichtbar(el)) nativ.push(`select ${el.getAttribute('data-testid') ?? ''}`);
			const text = w.innerText;
			for (const z of ['✓', '⊘']) {
				for (let i = text.indexOf(z); i >= 0; i = text.indexOf(z, i + 1)) {
					symbole.push(`${z} in „${text.slice(Math.max(0, i - 25), i + 25).replace(/\s+/g, ' ')}"`);
				}
			}
		}
		return { anzahl: wurzeln.length, nativ, symbole };
	}, bereich);
	if (r.anzahl === 0) fehler.push(`${seite}: Prüfbereich ${bereich} fehlt`);
	for (const n of r.nativ) fehler.push(`${seite}: natives Feld ${n}`);
	for (const s of r.symbole) fehler.push(`${seite}: Symbol ${s}`);
}

const ANLEGE_REITER = (kind: HubKind, id: string, mobil: boolean): string =>
	kind === 'route' ? `${mobil ? 'tn-mobile-tab' : 'trip-new-tab'}-${id}` : `${mobil ? 'cm-mobile-tab' : 'compare-editor-tab'}-${id}`;

for (const breite of BREITEN) {
	for (const lang of ['de', 'en'] as const) {
		test(`DS-3 (${breite.width} px, ${lang}): Listen, Hubs (Übersicht, Etappen/Orte, Zustellung) und Anlegen ohne native Datum/Uhrzeit/Radio/Select, ohne ✓/⊘`, async ({
			page
		}) => {
			test.setTimeout(180_000);
			const mobil = breite === MOBIL;
			await page.setViewportSize(breite);
			await setzeSprache(page, lang);
			const hubs = { route: await seedHub(page.request, 'route'), vergleich: await seedHub(page.request, 'vergleich') };
			const fehler: string[] = [];
			try {
				for (const kind of HUB_KINDS) {
					await page.goto(HUB_SEL[kind].liste.url);
					await expect(page.getByTestId(HUB_SEL[kind].liste.zeile(hubs[kind].id)).first()).toBeAttached({ timeout: 15_000 });
					await pruefeSeite(page, `${kind}-Liste`, fehler);
				}
				for (const kind of HUB_KINDS) {
					for (const tab of ['uebersicht', HUB_SEL[kind].punkteReiter]) {
						await openHub(page, kind, hubs[kind].id, { tab });
						await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-${tab}"]:visible`).first()).toBeVisible({
							timeout: 15_000
						});
						await expect(page.getByTestId('save-indicator')).toBeVisible();
						await pruefeSeite(page, `${kind}-Hub ${tab}`, fehler);
					}
					await openHub(page, kind, hubs[kind].id, { tab: 'wetter-metriken' });
					await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeVisible({ timeout: 15_000 });
					await pruefeSeite(page, `${kind}-Hub Zustellung`, fehler, ZUSTELLUNG);
				}
				for (const kind of HUB_KINDS) {
					await page.goto(ANLEGE_SEL[kind].url);
					await expect(page.getByTestId(ANLEGE_REITER(kind, ANLEGE_SEL[kind].ersterSchritt, mobil))).toBeVisible({
						timeout: 15_000
					});
					await pruefeSeite(page, `${kind}-Anlegen erster Schritt`, fehler);
					// Der Pflichtangaben-Helfer klickt am Handy deutsche Beschriftungen ⇒ Folge-Schritte am Handy nur de.
					if (mobil && lang === 'en') continue;
					await anlegenPflicht(page, kind, { name: `E2E-GZ-DS3-${kind}-${Date.now()}`, mobil });
					await pruefeSeite(page, `${kind}-Anlegen ${ANLEGE_SEL[kind].punkteSchritt}`, fehler);
					await page.getByTestId(ANLEGE_REITER(kind, 'wetter-metriken', mobil)).click();
					await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeVisible({ timeout: 15_000 });
					await pruefeSeite(page, `${kind}-Anlegen Zustellung`, fehler, ZUSTELLUNG);
				}
			} finally {
				await setzeSprache(page, 'de');
				for (const h of Object.values(hubs)) await h.aufraeumen();
				await cleanupTracked(page.request);
			}
			expect(fehler, fehler.join('\n')).toEqual([]);
		});
	}
}

// ─── DS-4 (AC-4) ────────────────────────────────────────────────────────────

test('DS-4 Aktivität: Auswahl beim Trip-Anlegen ist eine listbox, per Maus und Tastatur bedienbar, Fokus sichtbar, gespeichert', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	try {
		await anlegenPflicht(page, 'route', { name: `E2E-GZ-DS4-${Date.now()}` });
		await page.getByTestId('trip-new-tab-route').click();
		const ausloeser = page.getByTestId('activity-dropdown');
		await expect(ausloeser).toBeVisible({ timeout: 10_000 });
		const liste = page.getByRole('listbox');
		// Maus
		await ausloeser.click();
		await expect(liste, 'Auswahl öffnet keine listbox').toBeVisible({ timeout: 5_000 });
		await liste.getByRole('option', { name: 'Hochtour' }).click();
		await expect(liste).toBeHidden();
		await expect(ausloeser).toContainText('Hochtour');
		// Tastatur: Enter öffnet, Pfeil runter, Enter wählt
		await ausloeser.focus();
		await page.keyboard.press('Enter');
		await expect(liste).toBeVisible();
		await page.keyboard.press('ArrowDown');
		await page.keyboard.press('Enter');
		await expect(liste).toBeHidden();
		await expect(ausloeser).toContainText('Klettersteig');
		await expect(ausloeser).toBeFocused();
		const fokus = await ausloeser.evaluate((el) => {
			const s = getComputedStyle(el);
			return { sichtbar: el.matches(':focus-visible'), stil: s.outlineStyle, breite: s.outlineWidth };
		});
		expect(fokus.sichtbar && fokus.stil !== 'none' && fokus.breite !== '0px', `Fokus nicht sichtbar: ${JSON.stringify(fokus)}`).toBe(true);
		const knopf = ANLEGE_SEL.route.standardwerte(page);
		await expect(knopf).toBeEnabled({ timeout: 15_000 });
		const id = await postId(page, '/api/trips', () => knopf.click());
		expect((await tripStand(page, id)).activity, 'gespeicherte Aktivität').toBe('klettersteig');
	} finally {
		await cleanupTracked(page.request);
	}
});

test('DS-4 Mail-Format: Zustellung im Trip-Hub ist eine radiogroup, per Maus und Pfeiltaste bedienbar, Fokus sichtbar, gespeichert', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	const format = async () =>
		((await tripStand(page, hub.id)).report_config as { email_format?: string } | undefined)?.email_format ?? 'full';
	const gruppe = page.getByTestId('report-email-format-switcher');
	const voll = gruppe.getByRole('radio', { name: /Ausführlich/ });
	const kompakt = gruppe.getByRole('radio', { name: /Kompakt/ });
	try {
		await openHub(page, 'route', hub.id, { tab: 'wetter-metriken' });
		await expect(gruppe).toBeVisible({ timeout: 15_000 });
		await expect(gruppe, 'Mail-Format ist keine radiogroup').toHaveAttribute('role', 'radiogroup');
		await expect(voll).toBeChecked();
		// Maus
		await kompakt.click();
		await expect(kompakt).toBeChecked();
		await expect.poll(format, { message: 'Kompakt nicht gespeichert', timeout: 15_000 }).toBe('compact');
		await openHub(page, 'route', hub.id, { tab: 'wetter-metriken' });
		await expect(kompakt).toBeChecked({ timeout: 15_000 });
		// Tastatur: Pfeil links wählt das vorherige Format
		await kompakt.focus();
		await page.keyboard.press('ArrowLeft');
		await expect(voll).toBeFocused();
		await expect(voll).toBeChecked();
		const fokus = await voll.evaluate((el) => {
			const s = getComputedStyle(el);
			return { sichtbar: el.matches(':focus-visible'), stil: s.outlineStyle, breite: s.outlineWidth };
		});
		expect(fokus.sichtbar && fokus.stil !== 'none' && fokus.breite !== '0px', `Fokus nicht sichtbar: ${JSON.stringify(fokus)}`).toBe(true);
		await expect.poll(format, { message: 'Ausführlich nicht gespeichert', timeout: 15_000 }).toBe('full');
		await openHub(page, 'route', hub.id, { tab: 'wetter-metriken' });
		await expect(voll).toBeChecked({ timeout: 15_000 });
	} finally {
		await hub.aufraeumen();
	}
});

// ─── DS-6 (AC-6) ────────────────────────────────────────────────────────────

async function messeTippflaechen(ziel: Locator, seite: string, mindestens: number, fehler: string[]): Promise<void> {
	const n = await ziel.count();
	if (n < mindestens) fehler.push(`${seite}: ${n} statt mindestens ${mindestens} Tippflächen gefunden`);
	for (let i = 0; i < n; i++) {
		const el = ziel.nth(i);
		const bb = await el.boundingBox();
		const name = (await el.getAttribute('data-testid')) ?? `#${i}`;
		if (!bb || bb.width + 0.01 < 44 || bb.height + 0.01 < 44) {
			fehler.push(`${seite} ${name}: ${bb ? `${bb.width.toFixed(1)} × ${bb.height.toFixed(1)}` : 'keine Box'} px (< 44 × 44)`);
		}
	}
}

async function pruefeUeberlauf(page: Page, seite: string, fehler: string[]): Promise<void> {
	const zuviel = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
	if (zuviel > 0) fehler.push(`${seite}: läuft waagerecht ${zuviel} px über`);
}

test('DS-6: Tippflächen am Handy (390 × 844) mindestens 44 × 44 — Zurück, Standardwerte, ⓘ, Schnellwahl — kein waagerechtes Überlaufen', async ({
	page
}) => {
	test.setTimeout(120_000);
	await page.setViewportSize(MOBIL);
	await setzeSprache(page, 'de');
	const fehler: string[] = [];
	const hubs = { route: await seedHub(page.request, 'route'), vergleich: await seedHub(page.request, 'vergleich') };
	try {
		for (const kind of HUB_KINDS) {
			const id = hubs[kind].id;
			await openHub(page, kind, id, { tab: 'uebersicht' });
			const zurueck = page.locator('[data-testid="back-link"]:visible');
			await expect(zurueck.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(zurueck, `${kind}-Hub Zurück`, 1, fehler);
			await pruefeUeberlauf(page, `${kind}-Hub Übersicht`, fehler);

			await openHub(page, kind, id, { tab: 'wetter-metriken' });
			const chips = page.locator(
				'[data-testid^="report-morning-quickpick-"]:visible, [data-testid^="report-evening-quickpick-"]:visible'
			);
			await expect(chips.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(chips, `${kind}-Hub Schnellwahl`, 4, fehler);
			await pruefeUeberlauf(page, `${kind}-Hub Zustellung`, fehler);

			await openHub(page, kind, id, { tab: 'wertebereiche' });
			const ii = page.locator('[data-testid^="begriff-erklaerung-"]:visible');
			await expect(ii.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(ii, `${kind}-Hub ⓘ`, 1, fehler);
			await pruefeUeberlauf(page, `${kind}-Hub Wertebereiche`, fehler);
		}
		for (const kind of HUB_KINDS) {
			await page.goto(ANLEGE_SEL[kind].url);
			const zurueck = page.locator('[data-testid="back-link"]:visible');
			await expect(zurueck.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(zurueck, `${kind}-Anlegen Zurück`, 1, fehler);
			const standard = page.locator(
				`[data-testid="${kind === 'route' ? 'tn-mobile-standardwerte' : 'cm-mobile-standardwerte'}"]:visible`
			);
			await messeTippflaechen(standard, `${kind}-Anlegen Standardwerte`, 1, fehler);
			await pruefeUeberlauf(page, `${kind}-Anlegen`, fehler);
		}
	} finally {
		for (const h of Object.values(hubs)) await h.aufraeumen();
	}
	expect(fehler, fehler.join('\n')).toEqual([]);
});
