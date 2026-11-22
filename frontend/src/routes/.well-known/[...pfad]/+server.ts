import type { RequestHandler } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { OAUTH_METADATEN_PFADE } from '$lib/server/oauthMetadaten.js';

// Issue #3281 (MCP-Konnektor „Gregor Wetter“, ADR-0128): nginx leitet die
// Wurzelpfade `/.well-known/*` an SvelteKit. Die OAuth-Metadaten liegen in Go;
// diese Route reicht genau diese drei Pfade unveraendert (ohne Cookie, ohne
// Anmeldung) an Go durch. Alles andere unter `/.well-known/` gibt es nicht.
export const GET: RequestHandler = async ({ url }) => {
	if (!OAUTH_METADATEN_PFADE.has(url.pathname)) {
		return new Response('Not found', { status: 404, headers: { 'content-type': 'text/plain' } });
	}
	const res = await fetch(`${API()}${url.pathname}`, { headers: { accept: 'application/json' } });
	const kopf = new Headers();
	for (const name of ['content-type', 'access-control-allow-origin', 'cache-control']) {
		const wert = res.headers.get(name);
		if (wert !== null) kopf.set(name, wert);
	}
	return new Response(res.body, { status: res.status, headers: kopf });
};
