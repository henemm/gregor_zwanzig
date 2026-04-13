import { createHmac } from 'crypto';

export function signSession(userId: string, secret: string): string {
	const ts = Math.floor(Date.now() / 1000);
	const sig = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	return `${userId}.${ts}.${sig}`;
}

export function verifySession(
	cookie: string,
	secret: string,
	maxAge = 86400
): { userId: string } | null {
	const parts = cookie.split('.');
	if (parts.length !== 3) return null;

	const [userId, tsStr, sig] = parts;
	if (!userId || !tsStr || !sig) return null;

	const ts = parseInt(tsStr, 10);
	if (isNaN(ts)) return null;
	if (Date.now() / 1000 - ts > maxAge) return null;

	const expected = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	if (sig !== expected) return null;

	return { userId };
}
