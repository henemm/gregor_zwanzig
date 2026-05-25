<script lang="ts">
	// BrandUserBadge — Sidebar-Footer / Profile-Pill. Avatar (Initialen) + Name + Sekundaerzeile.
	// 1:1 portiert aus brand-kit.jsx. `sub` darf null sein → nur eine Zeile.
	interface Props {
		name?: string;
		sub?: string | null;
		initials?: string;
		accent?: boolean;
	}

	let { name = 'Gregor Henemm', sub = 'henemm.com', initials, accent = false }: Props = $props();

	const ini = $derived(
		initials ||
			name
				.split(' ')
				.map((p) => p[0])
				.slice(0, 2)
				.join('')
				.toUpperCase()
	);
	const avatarBg = $derived(accent ? 'var(--g-accent)' : 'var(--g-ink)');
</script>

<div style="display:flex;align-items:center;gap:10px">
	<div
		style="width:28px;height:28px;border-radius:50%;background:{avatarBg};color:var(--g-paper);font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center;font-family:var(--g-font-sans);flex-shrink:0"
	>{ini}</div>
	<div style="flex:1;min-width:0">
		<div
			style="font-family:var(--g-font-sans);font-size:13px;font-weight:500;line-height:1.2;color:var(--g-ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
		>{name}</div>
		{#if sub}
			<div
				style="font-family:var(--g-font-mono);font-size:11px;line-height:1.2;color:var(--g-ink-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
			>{sub}</div>
		{/if}
	</div>
</div>
