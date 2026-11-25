// Probe-Löschung ohne Kopie (#3020 S1): macht die Dateien aus GZ_3020_TOT (JSON, absolute
// Pfade) für einen Node-Prozess unsichtbar — beim Modulladen und beim Lesen per `fs`.
// Der Arbeitsbaum bleibt unberührt. Wird per `--import` als ERSTER Hook geladen; dieselbe
// Datei läuft auch im Hook-Thread und sperrt dort das Lesen (`.svelte` über
// test-svelte-ssr-hooks.mjs liest mit `fs`, nicht über nextLoad).
import fs from 'node:fs';
import { register, syncBuiltinESMExports } from 'node:module';
import { resolve as absolut } from 'node:path';
import { fileURLToPath } from 'node:url';
import { isMainThread } from 'node:worker_threads';

const TOT = new Set(JSON.parse(process.env.GZ_3020_TOT ?? '[]'));

function pfad(p) {
	if (p instanceof URL) return fileURLToPath(p);
	if (typeof p !== 'string') return null;
	return p.startsWith('file:') ? fileURLToPath(p.split('?')[0]) : absolut(p);
}
const tot = (p) => TOT.has(pfad(p));
const fehlt = (p) => Object.assign(new Error(`PROBE-LOESCHUNG #3020: ${pfad(p)}`), { code: 'ENOENT' });

const { existsSync, readFileSync, statSync } = fs;
fs.existsSync = (p) => !tot(p) && existsSync(p);
fs.readFileSync = (p, ...rest) => {
	if (tot(p)) throw fehlt(p);
	return readFileSync(p, ...rest);
};
fs.statSync = (p, ...rest) => {
	if (tot(p)) throw fehlt(p);
	return statSync(p, ...rest);
};
syncBuiltinESMExports();

export async function load(url, context, nextLoad) {
	if (url.startsWith('file:') && tot(url)) throw fehlt(url);
	return nextLoad(url, context);
}

if (isMainThread && !globalThis.__gz3020Registriert) {
	globalThis.__gz3020Registriert = true;
	register(import.meta.url);
}
