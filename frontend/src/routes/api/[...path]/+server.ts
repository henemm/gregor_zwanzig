import type { RequestHandler } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


const handler: RequestHandler = async ({ request, params, cookies, url: reqUrl }) => {
	const url = `${API()}/api/${params.path}${reqUrl.search}`;
	const headers = new Headers(request.headers);

	const session = cookies.get('gz_session');
	if (session) {
		headers.set('Cookie', `gz_session=${session}`);
	}
	// Remove host header to avoid conflicts
	headers.delete('host');

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
