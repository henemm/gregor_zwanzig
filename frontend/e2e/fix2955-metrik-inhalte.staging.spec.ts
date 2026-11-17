// Abnahme — Issue #2955 (gebündelt mit #3012): Reiter Wetter, Metrik-Inhalte nach Mockup Fassung 3.
// Spec: docs/specs/modules/wetter_metrik_inhalte.md — AC-1, AC-2, AC-3, AC-4, AC-5, AC-6.
// Derselbe Test-Code für Trip (route, Vorlage Alpen-Trekking) und Orts-Vergleich (vergleich, Vorlage Allgemein),
// je in DE und EN (Sprache am Konto, am Ende zurück auf `de`).
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste:
//   cd frontend && npx playwright test --config playwright.2955-metrik-inhalte.staging.config.ts
//
// Erwartete Texte kommen aus den Katalogen (wetter.json, alarme.json) bzw. aus /api/metrics, nie aus einer
// Frontend-Kopie. Die Zählerzahlen sind keine festen 9/13/3 (Mockup-Daten), sondern aus den sichtbaren Zeilen.

import { test, expect, type Locator } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { HUB_KINDS, type HubKind } from './helpers';
import { DESKTOP, WT, aktiveDerVorlage, metriken, oeffneWetter, seedWetter, vorlagen, type Json } from './s3a2794-teil3.helpers';

type Sprache = 'de' | 'en';
const KATALOG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'lib', 'i18n', 'messages');
const katalog = (s: Sprache, bereich: string): Record<string, string> =>
	JSON.parse(readFileSync(path.join(KATALOG, s, `${bereich}.json`), 'utf8'));
const fuelle = (vorlage: string, werte: Record<string, string | number>): string =>
	vorlage.replace(/\{([a-z0-9_]+)\}/g, (_, k) => String(werte[k] ?? `{${k}}`));
const flach = (s: string): string => s.replace(/\s+/g, ' ').trim();

/** Vorlage je Kontext (Spec, Staging-E2E). */
const VORLAGE: Record<HubKind, string> = { route: 'alpen-trekking', vergleich: 'allgemein' };
/** ADR-0010-Vorboten, die #2955 neu kennzeichnet, plus cloud_low (Gegenprobe), Gewitter/Regen% (Reihenfolge), Namen. */
const VORBOTEN_NEU = ['wind_chill', 'cloud_total', 'dewpoint', 'pressure'];
const ZUSATZ_GEMEINSAM = [...VORBOTEN_NEU, 'cloud_low', 'thunder', 'rain_probability', 'gust', 'humidity'];
/** Nacht-Größen sind trip-exklusiv (#1848 C). */
const ZUSATZ_TRIP = ['temperature_night', 'wind_chill_night'];
const NEUE_NAMEN_DE: Record<string, string> = {
	temperature_night: 'Tiefsttemperatur Nacht',
	wind_chill_night: 'Gefühlte Tiefsttemperatur Nacht',
	humidity: 'Luftfeuchte'
};
const RANG: Record<string, number> = { yellow: 1, orange: 2, red: 3 };

const zeilen = (reiter: Locator): Locator =>
	reiter.locator('[data-testid^="wetter-zeile-"]:not([data-testid^="wetter-zeile-entfernen-"])');

async function zeilenIds(reiter: Locator): Promise<string[]> {
	return zeilen(reiter).evaluateAll((els) => els.map((e) => (e.getAttribute('data-testid') ?? '').replace('wetter-zeile-', '')));
}

for (const kind of HUB_KINDS) {
	for (const sprache of ['de', 'en'] as const) {
		test(`#2955 (${kind}, ${sprache}): Vorboten, Gewitter-Satz, Reihenfolge, Namen, Kopfzähler, Stufenwort`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const w = katalog(sprache, 'wetter');
			const a = katalog(sprache, 'alarme');
			const vorlageId = VORLAGE[kind];
			const v = (await vorlagen(page.request))[vorlageId];
			const zusatz = kind === 'route' ? [...ZUSATZ_GEMEINSAM, ...ZUSATZ_TRIP] : ZUSATZ_GEMEINSAM;
			const auswahl = [...new Set([...aktiveDerVorlage(v), ...zusatz])];
			const hub = await seedWetter(page.request, kind, { vorlageId, auswahl });
			try {
				const res = await page.request.put('/api/auth/profile', { data: { language: sprache } });
				expect(res.ok(), `Sprache ${sprache} setzen: HTTP ${res.status()}`).toBeTruthy();
				const kat: Record<string, Json> = await metriken(page.request);
				const reiter = await oeffneWetter(page, kind, hub.id);

				// ── AC-1: Vorboten zeigen die drei Texte, cloud_low ist kein Vorbote ──
				for (const id of VORBOTEN_NEU) {
					const zeile = reiter.getByTestId(WT.zeile(id));
					await expect(zeile, `AC-1: Zeile ${id} fehlt`).toBeVisible();
					await expect(zeile, `AC-1 ${id}: Untertitel`).toContainText(w['wetter.untertitel.vorbote']);
					await expect(zeile.getByTestId(WT.erklaersatz(id)), `AC-1 ${id}: Erklärung`).toHaveText(w['wetter.erklaer.vorbote']);
					await expect(zeile.getByTestId(WT.alarmAb(id)), `AC-1 ${id}: rechts`).toHaveText(w['wetter.alarm_ab.vorbote']);
				}
				const wolken = reiter.getByTestId(WT.zeile('cloud_low'));
				await expect(wolken.getByTestId(WT.alarmAb('cloud_low')), 'AC-1: cloud_low zeigt „kein Alarm“').toHaveText(w['wetter.alarm_ab.kein_alarm']);
				await expect(wolken, 'AC-1: cloud_low ist kein Vorbote').not.toContainText(w['wetter.untertitel.vorbote']);

				// ── AC-3: Gewitter vor Regenwahrscheinlichkeit, Folge aus `rang` von /api/metrics ──
				const ids = await zeilenIds(reiter);
				expect(ids.indexOf('thunder'), `AC-3: Gewitter fehlt (${ids.join(',')})`).toBeGreaterThanOrEqual(0);
				expect(ids.indexOf('thunder'), `AC-3: Gewitter nach Regenwahrscheinlichkeit (${ids.join(',')})`).toBeLessThan(ids.indexOf('rain_probability'));
				for (const gruppe of new Set(ids.map((id) => kat[id].group))) {
					const inGruppe = ids.filter((id) => kat[id].group === gruppe);
					const nachRang = [...inGruppe].sort((x, y) => kat[x].rang - kat[y].rang);
					expect(inGruppe, `AC-3: Gruppe ${gruppe} nicht nach rang aus /api/metrics`).toEqual(nachRang);
				}

				// ── AC-4: Namen (DE neu, EN unverändert = label_en) ──
				for (const [id, de] of Object.entries(NEUE_NAMEN_DE)) {
					if (!auswahl.includes(id) || (kind !== 'route' && ZUSATZ_TRIP.includes(id))) continue;
					const soll = sprache === 'de' ? de : kat[id].label_en;
					await expect(reiter.getByTestId(WT.zeile(id)).locator('.wt-name b'), `AC-4: Name ${id}`).toHaveText(soll);
				}

				// ── AC-2 + AC-6: Gewitter-Satz bei „Alarm ab Orange“, Stufenwort groß ──
				const gewitter = reiter.getByTestId(WT.zeile('thunder'));
				const orange = gewitter.getByTestId(WT.alarmAbStufe('thunder', 'orange'));
				if ((await orange.getAttribute('aria-checked')) !== 'true') await orange.click();
				await expect(orange).toHaveAttribute('aria-checked', 'true');
				const th: Json = v.ampel.thunder ?? {};
				const mittelGreift = !!th.mittel && RANG[th.mittel] >= RANG.orange;
				const hochGreift = !!th.hoch && RANG[th.hoch] >= RANG.orange;
				const satz = gewitter.getByTestId(WT.erklaersatz('thunder'));
				if (mittelGreift || hochGreift) {
					const stufeWort = w[mittelGreift ? 'wetter.gewitter.mittel_ab' : 'wetter.gewitter.hoch'];
					await expect(satz, 'AC-2/AC-6: Gewitter-Erklärsatz').toHaveText(
						flach(fuelle(w['wetter.erklaer.gewitter'], { gewitter_stufe: stufeWort, stufe: a['alarme.alarm_ab.stufe.orange'] }))
					);
				}

				// AC-6: jede alarmfähige Zeile mit Stufe ≠ nie nennt das große Stufenwort in Klammern.
				for (const id of ids) {
					if (!kat[id].alertable || id === 'thunder') continue;
					for (const stufe of ['yellow', 'orange', 'red'] as const) {
						const knopf = reiter.getByTestId(WT.alarmAbStufe(id, stufe));
						if ((await knopf.count()) === 0 || (await knopf.getAttribute('aria-checked')) !== 'true') continue;
						const text = flach(await reiter.getByTestId(WT.erklaersatz(id)).innerText());
						if (text === flach(w['wetter.erklaer.nie'] ?? '')) continue;
						expect(text, `AC-6 ${id}: großes Stufenwort fehlt`).toContain(`(${a[`alarme.alarm_ab.stufe.${stufe}`]})`);
						expect(text, `AC-6 ${id}: kleines Farbwort statt Stufenwort`).not.toContain(`(${w[`wetter.farbe.${stufe}`]})`);
					}
				}

				// ── AC-5: Kopfzähler „n von m … k können keinen auslösen“, m = alle sichtbaren Zeilen ──
				const m = ids.length;
				const k = ids.filter((id) => kat[id].alertable !== true).length;
				let n = 0;
				for (const id of ids) {
					if (kat[id].alertable !== true) continue;
					const nie = reiter.getByTestId(WT.alarmAbStufe(id, 'never'));
					if ((await nie.getAttribute('aria-checked')) !== 'true') n++;
				}
				const zaehler = reiter.getByTestId(WT.zaehler);
				await expect(zaehler, 'AC-5: Kopfzähler').toContainText(
					flach(fuelle(w['wetter.alarm_ab.zaehler'], { ausloesend: n, ausgewaehlt: m, ohne: k }))
				);
				await expect(reiter.getByTestId(WT.alarmAlle), 'AC-5: kein Abgleich-Tag „A5“').not.toContainText(/\bA5\b/);
			} finally {
				await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
				await hub.aufraeumen();
			}
		});
	}
}
