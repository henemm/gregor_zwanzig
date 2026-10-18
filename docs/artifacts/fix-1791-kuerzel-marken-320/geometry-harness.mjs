// Statisches Mess-Geruest: <style>-Block der Komponente (Datei als Argument), Chromium misst Zeilengeometrie.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire('/home/hem/gregor_zwanzig/.claude/worktrees/logical-bouncing-newt/frontend/package.json');
const { chromium } = require('@playwright/test');
const src = fs.readFileSync(process.argv[2], 'utf8');
const css = src.match(/<style>([\s\S]*)<\/style>/)[1];
const row = '<div class="row"><div class="pos mono">1</div><span class="drag-handle" style="display:flex"><svg width="14" height="14"></svg></span><div class="label-cell"><span class="metric-label">Gewitter</span><span class="metric-unit mono">%</span><span class="col-badge"><span class="badge-key">Mail</span> <span class="badge-val mono">Thunder</span></span><span class="kurzform-badge"><span class="badge-key">Kurzform</span> <span class="badge-val mono">TH TH+ TH++</span></span></div><div class="controls"><div style="width:90px;height:24px;border:1px solid">Roh|Einfach</div><button class="btn-aus">Aus</button></div></div>';
const aus = '<div class="row aus-row"><div class="label-cell"><span class="metric-label">Wind</span><span class="col-badge"><span class="badge-key">Mail</span> <span class="badge-val mono">Wind</span></span></div><div class="controls"><button class="btn-ein">Ein</button></div></div>';
const html = '<style>:root{--g-card:#fff}body{margin:0;font:13px sans-serif}' + css + '</style><div>' + row + aus + '</div>';
const b = await chromium.launch();
for (const w of [320, 375, 899, 900, 901, 1024]) {
  const p = await b.newPage({ viewport: { width: w, height: 568 } });
  await p.setContent(html);
  const r = await p.evaluate(() => {
    const q = (s, e = document) => e.querySelector(s);
    const bb = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
    const row = q('.row');
    const bad = Array.from(row.querySelectorAll('.col-badge,.kurzform-badge')).map((e) => [e.clientWidth, e.scrollWidth]);
    const ar = q('.aus-row');
    const o = {};
    o.pos = bb(q('.pos'));
    o.griff = bb(q('.drag-handle'));
    o.label = bb(q('.label-cell'));
    o.ctl = bb(q('.row .controls'));
    o.badges = bad;
    o.ausLabel = bb(q('.label-cell', ar));
    o.ausCtl = bb(q('.controls', ar));
    o.docW = document.documentElement.scrollWidth;
    return o;
  });
  console.log(w, JSON.stringify(r));
}
await b.close();
