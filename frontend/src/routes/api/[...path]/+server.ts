import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

const handler: RequestHandler = async ({ request, params, cookies }) => {
	const url = `${API()}/api/${params.path}`;
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

	return new Response(res.body, {
		status: res.status,
		statusText: res.statusText,
		headers: {
			'Content-Type': res.headers.get('Content-Type') ?? 'application/json'
		}
	});
};

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
