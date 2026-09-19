<script lang="ts">
	// Mobile-Shell S2 — Konto-Sheet: ersetzt den mobilen Drawer (Hamburger).
	// Oeffnet sich von unten ueber den Konto-Kreis der Tabbar. Inhalt (PO
	// 2026-09-19): Kanaele & Empfaenger · Einstellungen · System-Status ·
	// Dunkles Design · Datenexport · Abmelden. KEINE Benachrichtigungen-Zeile,
	// bis ein echter Posteingang existiert (#1701).
	// Soll: Design-Canvas „Gregor Mobile Shell", Artboard „Konto-Sheet".
	// Konzept: docs/design-requests/mobile_shell_ohne_topbar.md §3, §8.
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import { Switch } from '$lib/components/atoms';
	import MessageSquare from '@lucide/svelte/icons/message-square';
	import SettingsIcon from '@lucide/svelte/icons/settings';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import LogOut from '@lucide/svelte/icons/log-out';
	import XIcon from '@lucide/svelte/icons/x';

	interface Props {
		open: boolean;
		onClose: () => void;
		initials: string;
		displayName?: string | null;
		userId?: string | null;
		darkMode: boolean;
		ontoggleDark: () => void;
	}

	let { open, onClose, initials, displayName, userId, darkMode, ontoggleDark }: Props = $props();

	// Anzeigename hat Vorrang (#642); die Login-Kennung steht darunter, wenn sie
	// etwas anderes sagt.
	const name = $derived((displayName && displayName.trim()) || userId || '');
	const sub = $derived(userId && userId !== name ? userId : null);

	const links = [
		{ href: '/account#kanaele', label: 'Kanäle & Empfänger', icon: MessageSquare, testid: 'konto-sheet-kanaele' },
		{ href: '/account', label: 'Einstellungen', icon: SettingsIcon, testid: 'konto-sheet-einstellungen' },
		{ href: '/account#system-status', label: 'System-Status', icon: MonitorIcon, testid: 'konto-sheet-status' },
	];
</script>

<Sheet {open} {onClose} snap="auto">
	<div data-testid="konto-sheet" role="dialog" aria-label="Konto" class="konto">
		<div class="konto__kopf">
			<span class="konto__avatar mono" aria-hidden="true">{initials}</span>
			<div class="konto__name">
				<div data-testid="konto-sheet-name">{name}</div>
				{#if sub}<div class="mono konto__sub">{sub}</div>{/if}
			</div>
			<button type="button" class="konto__close" aria-label="Schließen" onclick={onClose}>
				<XIcon class="size-[18px]" />
			</button>
		</div>

		<div class="konto__liste">
			{#each links as l (l.href)}
				<a href={l.href} data-testid={l.testid} class="konto__zeile" onclick={onClose}>
					<svelte:component this={l.icon} class="size-[22px] shrink-0" />
					<span class="konto__label">{l.label}</span>
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
				</a>
			{/each}
			<div class="konto__zeile" data-testid="konto-sheet-dark">
				<MoonIcon class="size-[22px] shrink-0" />
				<span class="konto__label">Dunkles Design</span>
				<Switch checked={darkMode} size="lg" tone="accent" aria-label="Dunkles Design" onchange={ontoggleDark} />
			</div>
			<a href="/account#datenexport" data-testid="konto-sheet-export" class="konto__zeile" onclick={onClose}>
				<DownloadIcon class="size-[22px] shrink-0" />
				<span class="konto__label">Datenexport</span>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
			</a>
		</div>

		<div class="konto__fuss">
			<span class="mono konto__version">V0.20 · Wetter-Briefing</span>
			<form method="POST" action="/logout">
				<button type="submit" data-testid="konto-sheet-logout" class="konto__logout">
					<LogOut class="size-[18px]" />
					Abmelden
				</button>
			</form>
		</div>
	</div>
</Sheet>

<style>
	.konto {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding-bottom: env(safe-area-inset-bottom);
		color: var(--g-ink);
	}
	.konto__kopf {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 4px 6px;
	}
	.konto__avatar {
		width: 44px;
		height: 44px;
		border-radius: 22px;
		background: var(--g-accent);
		color: #ffffff;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 15px;
		font-weight: 600;
		letter-spacing: 0.02em;
		flex-shrink: 0;
	}
	.konto__name {
		flex: 1;
		min-width: 0;
		font-size: 16px;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.konto__sub {
		font-size: 12px;
		font-weight: 400;
		color: var(--g-ink-3);
		margin-top: 2px;
	}
	.konto__close {
		width: 44px;
		height: 44px;
		border-radius: 22px;
		border: none;
		background: var(--g-paper);
		color: var(--g-ink);
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		flex-shrink: 0;
	}
	.konto__liste {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-r-3);
		overflow: hidden;
	}
	.konto__zeile {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 56px;
		padding: 0 16px;
		text-decoration: none;
		color: var(--g-ink);
		font-size: 15px;
		background: var(--g-card);
	}
	.konto__zeile + .konto__zeile {
		border-top: 1px solid var(--g-rule-soft);
	}
	.konto__label {
		flex: 1;
	}
	.konto__fuss {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 2px 4px 0;
	}
	.konto__version {
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--g-ink-3);
	}
	.konto__logout {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 44px;
		padding: 0 14px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
		color: var(--g-danger);
		font-size: 15px;
		font-weight: 500;
		cursor: pointer;
	}
</style>
