import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { API_PROXY_TARGET } from './e2e/apiProxyTarget.ts';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: API_PROXY_TARGET,
				changeOrigin: true
			}
		}
	}
});
