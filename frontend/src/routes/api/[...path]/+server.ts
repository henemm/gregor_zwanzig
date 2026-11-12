import type { RequestHandler } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { proxyAnfrageKopfzeilen, proxyZielPfad } from '$lib/server/apiPfad.js';

// Issue #2961 (FE3): der Durchreicher bildet den Zielpfad Segment fuer Segment
// neu (ungueltige Segmente => 400, ohne Aufruf der Go-API) und reicht nur eine
// feste Positivliste von Kopfzeilen weiter, als Cookie nur die Sitzung.
const handler: RequestHandler = async ({ request, cookies, url: reqUrl }) => {
	const zielPfad = proxyZielPfad(reqUrl.pathname);
	if (zielPfad === null) {
		return new Response(JSON.stringify({ error: 'invalid path' }), {
			status: 400,
			headers: { 'content-type': 'application/json' }
		});
	}
	const url = `${API()}${zielPfad}${reqUrl.search}`;
	const headers = proxyAnfrageKopfzeilen(request.headers, cookies.get('gz_session'));

	const res = await fetch(url, {
		method: request.method,
		headers,
		body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
		// @ts-expect-error duplex needed for streaming body
		duplex: request.method !== 'GET' && request.method !== 'HEAD' ? 'half' : undefined
	});

	const responseHeaders = new Headers();
	res.headers.forEach((value, key) => {
		if (key.toLowerCase() !== 'transfer-encoding') {
			responseHeaders.set(key, value);
		}
	});

	return new Response(res.body, {
		status: res.status,
		statusText: res.statusText,
		headers: responseHeaders
	});
};

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
