<script lang="ts">
	// Issue #322 — WIcon: Lucide-Wrapper fuer 8 Wetter-Icon-Varianten.
	//
	// Spec: docs/specs/modules/issue_322_wicon_komponente.md
	//
	// Loest AP-009 (Emoji-Verbot im Produkt-UI): Konsumenten verwenden
	// <WIcon kind={wmoToWIconKind(...)} /> statt Emoji-Strings.

	import Sun from '@lucide/svelte/icons/sun';
	import Cloud from '@lucide/svelte/icons/cloud';
	import CloudRain from '@lucide/svelte/icons/cloud-rain';
	import CloudLightning from '@lucide/svelte/icons/cloud-lightning';
	import CloudSnow from '@lucide/svelte/icons/cloud-snow';
	import Wind from '@lucide/svelte/icons/wind';
	import Moon from '@lucide/svelte/icons/moon';
	import Flashlight from '@lucide/svelte/icons/flashlight';
	import type { WIconKind } from '$lib/utils/weatherUtils.js';

	interface Props {
		// Issue #371: kind-Default 'cloud' (additiv, bestehende Aufrufer setzen kind explizit).
		kind?: WIconKind;
		size?: number;
		color?: string;
		class?: string;
	}

	let {
		kind = 'cloud',
		size = 20,
		color = 'currentColor',
		class: className = ''
	}: Props = $props();

	const iconMap = {
		sun: Sun,
		cloud: Cloud,
		rain: CloudRain,
		thunder: CloudLightning,
		snow: CloudSnow,
		wind: Wind,
		moon: Moon,
		headlamp: Flashlight
	} as const;

	const IconComp = $derived(iconMap[kind]);
</script>

<IconComp {size} {color} class={className} aria-hidden="true" />
