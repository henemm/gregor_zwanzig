// E2E (Staging) — Issue #1719 Scheibe 3, Block A: die Live-Vorschau "So
// kommt es an" wird ersatzlos entfernt (PO-Entscheid).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-1, AC-2.
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md Abschnitt 5 + 10.5
//   ("Die Vorschau-Löschung ist ein Umbau, keine Löschung" — LayoutTab.svelte
//   verliert die rechte Zwei-Spalten-Hälfte, WeatherMetricsTab.svelte den
//   Mobile-FAB + Sheet-Wrapper).
//
// SCHREIBT NUR — wird in dieser RED-Phase NICHT ausgeführt (Staging läuft
// noch auf dem alten Stand mit Vorschau). Der Lauf gehört in die
// GREEN-/Verifikationsphase (Testauflage PO, "Das ist KRITISCH!!!!!").
//
// Vorbilder: metrik-grundauswahl-schneidet-kanal.staging.spec.ts (S2,
// Dreier-Struktur spec+setup+config), layout-tab-route.spec.ts (Testaufbau,
// dragDndZoneItem-Helper, wm2-* Test-IDs), weather-metrics-tab-autosave.spec.ts
// (report_config-Normalisierung gegen den Mount-Effekt-Autosave).
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14): die Metrik-Oberflaeche ist aus dem Reiter
// Zustellung entfernt; Kanaele und Reihenfolge bedient die Karte „Was steht wo“ im Reiter Wetter.
//   AC-1 (keine Vorschau-Spalte, kein Mobile-Knopf): laeuft an beiden Reitern (Wetter mit Karte, Zustellung).
//   AC-2 (Kanal-Waehler + Ziehen ohne Vorschau bedienbar, kein horizontaler Scroll): gestrichen — Ersatz
//     was-steht-wo-karte.spec.ts WS-2 (Ziehen per Tastatur und Maus) und WS-8 (390 px: keine seitliche Seite).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config):
//   npx playwright test --project=tests e2e/wetter-metriken-vorschau-entfernt.staging.spec.ts
// Ausführen (gegen Staging, aus frontend/, NACH GREEN):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.wetter-metriken-vorschau-entfernt.staging.config.ts

import { test, expect } from '@playwright/test';
import { ZT, oeffneZustellung } from './s3b2795-zustellung.helpers';
import { oeffneKarte, seedAbo } from './was-steht-wo.helpers';

test.describe('Issue #1719 S3 Block A: Live-Vorschau ist ersatzlos weg', () => {
	test('AC-1: weder Vorschau-Spalte noch Mobile-Knopf existieren — Desktop UND Mobil, Reiter Wetter und Zustellung', async ({ page }) => {
		const abo = await seedAbo(page.request, 'route');
		try {
			for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
				await page.setViewportSize(vp);
				await oeffneKarte(page, 'route', abo.id);
				await expect(page.getByTestId('wm2-mail-preview'), `AC-1 FAIL (${vp.width}px, Wetter): "So kommt es an"`).toHaveCount(0);
				await expect(page.getByTestId('mobile-mail-fab'), `AC-1 FAIL (${vp.width}px, Wetter): Mobile-FAB`).toHaveCount(0);
				const z = await oeffneZustellung(page, 'route', abo.id);
				// #3458: Beispiel-Alarm entfernt — der Reiter ist geladen, wenn Stille Stunden steht.
				await expect(z.locator('[data-abschnitt="stille-stunden"]')).toBeVisible();
				await expect(z.getByTestId(ZT.beispielAlarm)).toHaveCount(0);
				await expect(page.getByTestId('wm2-mail-preview'), `AC-1 FAIL (${vp.width}px, Zustellung): "So kommt es an"`).toHaveCount(0);
				await expect(page.getByTestId('mobile-mail-fab'), `AC-1 FAIL (${vp.width}px, Zustellung): Mobile-FAB`).toHaveCount(0);
			}
		} finally {
			await abo.aufraeumen();
		}
	});
});
