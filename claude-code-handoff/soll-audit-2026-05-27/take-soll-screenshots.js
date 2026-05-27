// Phase 1: SOLL-Screenshots aus Design-Handoff
// Rendert alle Artboards der 3 Design-Dateien via Playwright

const { chromium } = require('/home/hem/gregor_zwanzig/frontend/node_modules/playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:18765';
const OUT_DIR = path.join(__dirname, 'soll-screenshots');

const FILES = [
  { name: 'desktop',     file: 'Gregor 20 - Desktop.html' },
  { name: 'mobile',      file: 'Gregor 20 - Mobile.html'  },
  { name: 'komponenten', file: 'Gregor 20 - Komponenten.html' },
];

async function run() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  for (const { name, file } of FILES) {
    const url = BASE_URL + '/' + encodeURIComponent(file);
    console.log(`\n=== ${name.toUpperCase()} ===`);

    const page = await browser.newPage();
    await page.setViewportSize({ width: 1920, height: 1080 });

    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    // Babel-Transpilation + React-Rendering abwarten
    await page.waitForTimeout(12000);

    // Full-page screenshot
    const fullPath = path.join(OUT_DIR, `${name}-full.png`);
    await page.screenshot({ path: fullPath, fullPage: true });
    const fullSize = fs.statSync(fullPath).size;
    console.log(`  Full-page: ${fullPath} (${Math.round(fullSize/1024)}KB)`);

    // Einzelne Artboards via [data-dc-slot]
    const slots = await page.$$('[data-dc-slot]');
    let count = 0;
    for (const slot of slots) {
      const id = await slot.getAttribute('data-dc-slot');
      if (!id) continue;

      // Das .dc-card Element screenshotten (nur Inhalt, ohne Header-Chrome)
      const card = await slot.$('.dc-card');
      const target = card || slot;
      const box = await target.boundingBox();
      if (!box || box.width < 100 || box.height < 100) continue;

      const artPath = path.join(OUT_DIR, `${name}-${id}.png`);
      await target.screenshot({ path: artPath });
      const size = fs.statSync(artPath).size;
      console.log(`  [${id}] ${Math.round(box.width)}x${Math.round(box.height)}px → ${path.basename(artPath)} (${Math.round(size/1024)}KB)`);
      count++;
    }
    console.log(`  → ${count} Artboards gespeichert`);
    await page.close();
  }

  await browser.close();
  console.log('\n✓ Alle SOLL-Screenshots fertig.');
}

run().catch(err => {
  console.error('Fehler:', err);
  process.exit(1);
});
