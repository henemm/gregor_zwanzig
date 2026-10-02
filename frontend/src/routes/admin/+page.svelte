<script lang="ts">
	// Issue #2155 S4 — Minimal-UI Nutzerverwaltung (Liste, Tier, Sperren/Entsperren).
	// Nur atoms/molecules (Import-Guard #470). Mutationen im Client per fetch; die
	// Antwort (AdminUser) ersetzt die Zeile, keine optimistische Anzeige.
	import { Card, PageHeader, Btn } from '$lib/components/atoms';
	import ConfirmDialog from '$lib/components/molecules/ConfirmDialog.svelte';
	import {
		TIER_LABELS,
		applySendResult,
		sendAdminUpdate,
		askDisable,
		cancelDisable,
		confirmDisableAction,
		enableAction,
		disableBlocked,
		tierSelectValueAfter
	} from '$lib/admin';
	import type { AdminUser, UserTier } from '$lib/types';

	let { data } = $props();

	let users = $state<AdminUser[]>(data.users);
	let errors = $state<Record<string, string>>({});
	let busy = $state<Record<string, boolean>>({});
	let confirmId = $state<string | null>(null);

	const TIERS: UserTier[] = ['free', 'standard', 'premium'];
	const confirmUser = $derived(users.find((u) => u.id === confirmId) ?? null);

	function tierLabel(tier: string): string {
		return TIER_LABELS[tier as UserTier] ?? tier;
	}

	function formatTime(iso: string): string {
		const d = new Date(iso);
		return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('de-DE');
	}

	function lastRun(u: AdminUser): string {
		if (!u.last_trip_report_run) return 'kein Lauf';
		return `${formatTime(u.last_trip_report_run.time)} (${u.last_trip_report_run.status})`;
	}

	async function send(id: string, path: 'tier' | 'disabled', body: unknown): Promise<boolean> {
		busy[id] = true;
		delete errors[id];
		const result = await sendAdminUpdate(fetch, id, path, body);
		busy[id] = false;
		const next = applySendResult(users, errors, id, result);
		users = next.users;
		errors = next.errors;
		return result.ok;
	}

	function makeTierHandler(u: AdminUser) {
		return async (e: Event) => {
			const select = e.currentTarget as HTMLSelectElement;
			const ok = await send(u.id, 'tier', { tier: select.value });
			select.value = tierSelectValueAfter(ok, select.value, u.tier); // Zeile bleibt unveraendert
		};
	}
	function makeAskDisable(u: AdminUser) {
		return () => {
			confirmId = askDisable(u.id);
		};
	}
	function makeEnable(u: AdminUser) {
		return () => {
			const a = enableAction(u.id);
			void send(a.id, a.path, a.body);
		};
	}
	function onCancelDisable() {
		confirmId = cancelDisable();
	}
	async function confirmDisable() {
		const action = confirmDisableAction(confirmId);
		confirmId = cancelDisable();
		if (action) await send(action.id, action.path, action.body);
	}
</script>

<div class="mx-auto max-w-5xl space-y-4" data-testid="admin-page">
	<PageHeader eyebrow="Verwaltung" title="Admin" sub="Nutzer, Tier und Kontosperre" />

	{#each users as u (u.id)}
		<Card data-testid="admin-user-row" data-user-id={u.id}>
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div class="min-w-0 space-y-1">
					<div class="font-semibold">
						{u.display_name || u.id}
						{#if u.is_test_user}<span class="mono text-xs">· Testnutzer</span>{/if}
						{#if u.disabled}
							<span data-testid="admin-disabled-badge" class="mono text-xs font-semibold" style="color: var(--g-danger);">· gesperrt</span>
						{/if}
					</div>
					<div class="mono text-xs" style="color: var(--g-ink-2);">{u.id} · {u.email}</div>
					<div class="text-sm">Tier: <strong>{tierLabel(u.tier)}</strong></div>
					{#if u.requested_tier}
						<div
							data-testid="admin-open-request"
							class="inline-block rounded-md px-2 py-1 text-sm font-semibold"
							style="background: rgba(196,90,42,0.12); color: var(--g-accent-deep);"
						>
							Offener Antrag: {tierLabel(u.requested_tier)}
							{#if u.requested_at}(seit {formatTime(u.requested_at)}){/if}
						</div>
					{/if}
					<div class="text-sm" style="color: var(--g-ink-2);">Letzter Trip-Report: {lastRun(u)}</div>
					<div class="text-sm" style="color: var(--g-ink-2);">Verbrauch heute (Open-Meteo): <strong data-testid="admin-user-verbrauch">{u.open_meteo_calls_today ?? 0}</strong></div>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<select
						data-testid="admin-tier-select"
						aria-label="Tier von {u.display_name || u.id}"
						value={u.tier}
						disabled={busy[u.id]}
						onchange={makeTierHandler(u)}
						class="h-9 rounded-md border border-input bg-background px-3 text-sm"
					>
						{#each TIERS as t}
							<option value={t}>{tierLabel(t)}</option>
						{/each}
					</select>
					{#if u.disabled}
						<Btn variant="outline" data-testid="admin-enable-btn" disabled={busy[u.id]} onclick={makeEnable(u)}>
							Entsperren
						</Btn>
					{:else}
						<Btn
							variant="outline"
							data-testid="admin-disable-btn"
							disabled={disableBlocked(u.id, data.selfId, busy[u.id])}
							onclick={makeAskDisable(u)}
						>
							Sperren
						</Btn>
					{/if}
				</div>
			</div>
			{#if errors[u.id]}
				<p data-testid="admin-row-error" role="alert" class="mt-2 text-sm font-semibold" style="color: var(--g-danger);">{errors[u.id]}</p>
			{/if}
		</Card>
	{/each}
</div>

<ConfirmDialog
	open={confirmId !== null}
	title="Konto sperren?"
	description="{confirmUser?.display_name || confirmUser?.id || ''} wird gesperrt; alle Sitzungen dieses Kontos enden sofort."
	confirmLabel="Sperren"
	confirmVariant="destructive"
	data-testid="admin-confirm-dialog"
	confirmTestid="admin-confirm-disable"
	cancelTestid="admin-cancel-disable"
	onConfirm={confirmDisable}
	onCancel={onCancelDisable}
	onOpenChange={(o) => {
		if (!o) onCancelDisable();
	}}
/>
