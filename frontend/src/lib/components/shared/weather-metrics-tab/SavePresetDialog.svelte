<script lang="ts">
	// Dialog „Als eigene Vorlage speichern" — POST /api/metric-presets.
	// Epic #138 Issue #177 (Ursprung), Issue #587 (Fixed-Overlay).
	// Issue #2794 S3a, Teil-PR 3 (W5b, AC-42): auf die Ampel umgestellt. Gespeichert werden die
	// aufgeloeste Abo-Ampel und die Art (`kind`: route im Trip, vergleich im Orts-Briefing),
	// Body ueber `eigeneVorlagePayload` (ampelSchreiben.ts); keine Zeithorizonte, keine
	// Zusammenfassung. Name ist Pflicht, die Duplikatpruefung laeuft serverseitig (409
	// `name_exists`) und wird im Dialog angezeigt. Keine nativen Controls (ADR-0111, AC-40).
	// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md §5

	import { api } from '$lib/api.js';
	import type { Ampel, MetricPreset } from '$lib/types';
	import { t, tr } from '$lib/i18n';
	import { eigeneVorlagePayload, vorlagenNameFehler } from '../wetter-tab/ampelSchreiben.ts';

	interface Props {
		open: boolean;
		kind: 'route' | 'vergleich';
		/** Aufgeloeste Abo-Ampel (Vorlage + Abweichungen, `enabled` = Auswahl). */
		ampel: Ampel;
		onClose: () => void;
		onSaved: (preset: MetricPreset) => void;
		/** Client-seitige Eindeutigkeitspruefung (case-insensitive, getrimmt), Issue #690. */
		existingNames?: string[];
	}

	let { open = $bindable(false), kind, ampel, onClose, onSaved, existingNames = [] }: Props = $props();

	let name = $state('');
	let description = $state('');
	let isDefault = $state(false);
	let saving = $state(false);
	let error: string | null = $state(null);

	const STANDARD_TEXT = { route: 'wetter.dialog.standard_route', vergleich: 'wetter.dialog.standard_vergleich' } as const;

	function reset() {
		name = '';
		description = '';
		isDefault = false;
		saving = false;
		error = null;
	}

	function close() {
		open = false;
		reset();
		onClose();
	}

	function vergeben(n: string): boolean {
		const x = n.trim().toLowerCase();
		return existingNames.some((e) => e.trim().toLowerCase() === x);
	}

	async function submit() {
		if (saving) return;
		const pflicht = vorlagenNameFehler(name);
		if (pflicht) return void (error = tr(pflicht as 'wetter.dialog.name_pflicht'));
		if (vergeben(name)) return void (error = tr('wetter.dialog.name_vergeben', { name: name.trim() }));
		saving = true;
		error = null;
		try {
			const body = eigeneVorlagePayload({ name, beschreibung: description, alsStandard: isDefault, kind, ampel });
			const preset = await api.post<MetricPreset>('/api/metric-presets', body);
			onSaved(preset);
			open = false;
			reset();
		} catch (e: unknown) {
			const errToken = (e as { error?: string })?.error;
			error = errToken === 'name_exists' ? tr('wetter.dialog.name_vergeben', { name: name.trim() }) : (errToken ?? tr('aktionen.speichern_fehlgeschlagen'));
		} finally {
			saving = false;
		}
	}

	function taste(e: KeyboardEvent) {
		if (open && e.key === 'Escape') close();
	}
</script>

<svelte:window onkeydown={taste} />

{#if open}
	<div class="spd-scrim" onclick={close} role="presentation">
		<div
			data-testid="save-preset-dialog"
			class="spd-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby="spd-titel"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<div class="spd-kopf">
				<div id="spd-titel" class="spd-titel">{$t('wetter.dialog.titel')}</div>
				<button type="button" class="spd-x" onclick={close} aria-label={$t('aktionen.schliessen')}>×</button>
			</div>

			<div class="spd-body">
				<label class="spd-feld">
					<span>{$t('wetter.dialog.name')}</span>
					<input data-testid="save-preset-name" type="text" bind:value={name} maxlength="40" />
				</label>
				<label class="spd-feld">
					<span>{$t('wetter.dialog.beschreibung')}</span>
					<textarea data-testid="save-preset-description" bind:value={description} maxlength="120" rows="2"></textarea>
				</label>
				<button type="button" class="spd-standard" role="switch" aria-checked={isDefault} data-testid="save-preset-is-default" onclick={() => (isDefault = !isDefault)}>
					<span class="spd-track" class:an={isDefault}><span class="spd-knopf"></span></span>
					<span>{$t(STANDARD_TEXT[kind])}</span>
				</button>
				<p class="spd-hinweis" data-testid="save-preset-hinweis">{$t('wetter.dialog.hinweis')}</p>
				{#if error}
					<p class="spd-fehler" role="alert" data-testid="save-preset-error">{error}</p>
				{/if}
			</div>

			<div class="spd-fuss">
				<button type="button" class="spd-btn" onclick={close} disabled={saving}>{$t('aktionen.abbrechen')}</button>
				<button type="button" class="spd-btn spd-btn--primaer" data-testid="save-preset-submit" disabled={saving} onclick={submit}>{$t('aktionen.speichern')}</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.spd-scrim {
		position: fixed;
		inset: 0;
		background: rgba(26, 26, 24, 0.45);
		backdrop-filter: blur(2px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}
	.spd-dialog {
		width: min(520px, calc(100vw - 32px));
		background: var(--g-paper);
		color: var(--g-ink);
		border: 1px solid var(--g-rule);
		border-radius: 6px;
		box-shadow: var(--g-shadow-3);
		overflow: hidden;
	}
	.spd-kopf {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 16px 12px 24px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.spd-titel {
		font-size: 18px;
		font-weight: 600;
	}
	.spd-x {
		min-width: 44px;
		min-height: 44px;
		border: none;
		background: none;
		font-size: 20px;
		color: var(--g-ink-2);
		cursor: pointer;
	}
	.spd-body {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 18px 24px;
	}
	.spd-feld {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 13px;
		color: var(--g-ink-2);
	}
	.spd-feld input,
	.spd-feld textarea {
		box-sizing: border-box;
		width: 100%;
		min-height: 44px;
		padding: 10px 12px;
		font: inherit;
		font-size: 15px;
		color: var(--g-ink);
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: 4px;
	}
	.spd-feld textarea {
		resize: vertical;
	}
	.spd-standard {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		min-height: 44px;
		padding: 0;
		border: none;
		background: transparent;
		color: var(--g-ink);
		font: inherit;
		font-size: 14px;
		text-align: left;
		cursor: pointer;
	}
	.spd-track {
		position: relative;
		display: block;
		flex-shrink: 0;
		width: 44px;
		height: 26px;
		border-radius: 13px;
		background: var(--g-ink-3);
	}
	.spd-track.an {
		background: var(--g-success);
	}
	.spd-knopf {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--g-paper);
	}
	.spd-track.an .spd-knopf {
		left: 20px;
	}
	.spd-hinweis {
		margin: 0;
		font-size: 12.5px;
		color: var(--g-ink-2);
	}
	.spd-fehler {
		margin: 0;
		font-size: 13px;
		color: var(--g-danger);
	}
	.spd-fuss {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		padding: 12px 24px;
		border-top: 1px solid var(--g-rule-soft);
		background: var(--g-card-alt);
	}
	.spd-btn {
		min-height: 44px;
		min-width: 44px;
		padding: 0 16px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
		font-size: 14px;
		cursor: pointer;
	}
	.spd-btn--primaer {
		background: var(--g-accent-deep);
		border-color: var(--g-accent-deep);
		color: var(--g-on-accent);
	}
	@media (max-width: 767px) {
		.spd-feld input,
		.spd-feld textarea {
			font-size: 16px;
		}
	}
</style>
