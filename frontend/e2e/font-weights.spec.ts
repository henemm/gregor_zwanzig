import { test, expect } from '@playwright/test';

// Issue #211 — Zusicherung unveraendert: alle benoetigten Schriftschnitte sind
// verfuegbar und die Schrift flackert beim Laden nicht (`swap`).
//
// Der MESSPUNKT ist mit Issue #2128 gewandert: die Schnitte kamen frueher ueber
// einen <link> von fonts.googleapis.com, jetzt kommen sie per @font-face aus
// dem eigenen /fonts-Verzeichnis. Gemessen wird darum nicht mehr die URL des
// Fremd-Verweises, sondern was der Browser tatsaechlich als Schriftschnitt
// fuehrt (`document.fonts`) und ob die woff2-Dateien wirklich ausgeliefert
// werden.

type Schnitt = { family: string; weight: string; display: string };

async function geladeneSchnitte(page: import('@playwright/test').Page): Promise<Schnitt[]> {
  await page.goto('/');
  return page.evaluate(() => {
    const out: { family: string; weight: string; display: string }[] = [];
    document.fonts.forEach((f) =>
      out.push({ family: f.family.replace(/["']/g, ''), weight: f.weight, display: f.display })
    );
    return out;
  });
}

test.describe('Issue #211 — Schrift-Weights vollständig geladen', () => {
  test('AC-1: Inter Tight ist in 400/500/600/700 als Schnitt verfügbar', async ({ page }) => {
    const schnitte = await geladeneSchnitte(page);
    const gewichte = schnitte.filter((s) => s.family === 'Inter Tight').map((s) => s.weight);
    for (const w of ['400', '500', '600', '700']) {
      expect(gewichte, `Inter Tight ${w} fehlt (gefunden: ${gewichte.join(', ')})`).toContain(w);
    }
  });

  test('AC-2: JetBrains Mono ist in 400/500/600 als Schnitt verfügbar', async ({ page }) => {
    const schnitte = await geladeneSchnitte(page);
    const gewichte = schnitte.filter((s) => s.family === 'JetBrains Mono').map((s) => s.weight);
    for (const w of ['400', '500', '600']) {
      expect(gewichte, `JetBrains Mono ${w} fehlt (gefunden: ${gewichte.join(', ')})`).toContain(w);
    }
  });

  test('AC-3: jeder Schnitt lädt mit display=swap und die woff2 werden ausgeliefert', async ({
    page
  }) => {
    const schnitte = await geladeneSchnitte(page);
    const eigene = schnitte.filter(
      (s) => s.family === 'Inter Tight' || s.family === 'JetBrains Mono'
    );
    expect(eigene.length, 'keine eigenen @font-face-Schnitte gefunden').toBeGreaterThan(0);
    const ohneSwap = eigene.filter((s) => s.display !== 'swap');
    expect(
      ohneSwap.map((s) => `${s.family} ${s.weight}: ${s.display}`),
      'ohne swap bliebe der Text beim Laden unsichtbar (Flackern/FOIT)'
    ).toEqual([]);

    for (const datei of ['/fonts/inter-tight-latin.woff2', '/fonts/jetbrains-mono-latin.woff2']) {
      const res = await page.request.get(datei);
      expect(res.status(), `${datei} wird nicht ausgeliefert`).toBe(200);
      expect(Number(res.headers()['content-length'] ?? '1')).toBeGreaterThan(0);
    }
  });
});
