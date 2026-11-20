<script lang="ts">
	// Karte „Als eigene Vorlage speichern" — POST /api/metric-presets.
	// Epic #138 Issue #177 (Ursprung), Issue #587 (Fixed-Overlay, abgelöst durch #3190).
	// Issue #2794 S3a, Teil-PR 3 (W5b, AC-42): auf die Ampel umgestellt. Gespeichert werden die
	// aufgeloeste Abo-Ampel und die Art (`kind`: route im Trip, vergleich im Orts-Briefing),
	// Body ueber `eigeneVorlagePayload` (ampelSchreiben.ts); keine Zeithorizonte, keine
	// Zusammenfassung. Name ist Pflicht, die Duplikatpruefung laeuft serverseitig (409
	// `name_exists`) und wird im Dialog angezeigt. Keine nativen Controls (ADR-0111, AC-40).
	// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md §5
	//
	// Issue #3190 (Epic #2913): Inline-Karte nach Mockup Fassung 4 (Z.485-505) statt modalem Overlay —
	// kein Scrim, kein ×, role="group" mit Titel; Reihenfolge Titel, Name, Fehler, Beschreibung
	// (einzeilig), Ankreuzfeld, Hinweis, Speichern vor Abbrechen. Steht in SEITEN_SCOPE (ADR-0112,
	// Regel (a)): nur Bausteine, kein <style>; die Karten-Optik (Klassen spd-*) steht in app.css.
	// Fokus beim Öffnen im Namensfeld; Escape schließt nur bei Fokus in der Karte. Die Fokus-Rückgabe
	// auf den Auslöser macht der Aufrufer (onClose bzw. onSaved).
	// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md

	import { api } from '$lib/api.js';
	import type { Ampel, MetricPreset } from '$lib/types';
	import { t, tr } from '$lib/i18n';
	import { Btn, Haken, Input } from '$lib/components/atoms';
	import { eigeneVorlagePayload, vorlagenNameFehler } from '../wetter-tab/ampelSchreiben.ts';
	import { beiKartenWechsel, karteSchliesstPerTaste } from '$lib/utils/vorlageSpeichernKarte.js';

	interface Props {
		open: boolean;
		kind: 'route' | 'vergleich';
		/** Aufgeloeste Abo-Ampel (Vorlage + Abweichungen, `enabled` = Auswahl). */
		ampel: Ampel;
		onClose: () => void;
		onSaved: (preset: MetricPreset) => void;
		/** Client-seitige Eindeutigkeitspruefung (case-insensitive, getrimmt), Issue #690. */
		existingNames?: string[];
		/** #3189: Trip bzw. Orts-Vergleich, aus dem gespeichert wird (fehlt im Anlege-Modus). */
		herkunft?: { id: string; name: string };
		/** #3190: id der Karte (Ziel von aria-controls am Auslöser); ohne Angabe eine eigene (per bind:id lesbar). */
		id?: string;
	}

	const eigeneId = $props.id();
	let { open = $bindable(false), kind, ampel, onClose, onSaved, existingNames = [], herkunft, id = $bindable(eigeneId) }: Props = $props();

	let name = $state('');
	let description = $state('');
	let isDefault = $state(false);
	let saving = $state(false);
	let error: string | null = $state(null);
	let nameFeld: HTMLInputElement | null = $state(null);

	const STANDARD_TEXT = { route: 'wetter.dialog.standard_route', vergleich: 'wetter.dialog.standard_vergleich' } as const;
	const standardText = $derived($t(STANDARD_TEXT[kind]));

	function reset() {
		name = '';
		description = '';
		isDefault = false;
		saving = false;
		error = null;
	}

	// #3190: Fokus beim Öffnen ins Namensfeld (Pflichtfeld); geschlossen von außen (Umschalter) ⇒ zurücksetzen.
	$effect(() => {
		if (beiKartenWechsel(open, nameFeld) === 'zuruecksetzen') reset();
	});

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
			const body = eigeneVorlagePayload({ name, beschreibung: description, alsStandard: isDefault, kind, ampel, herkunft });
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

	/**
	 * #3190: Escape nur bei Fokus in der Karte; das Ereignis endet hier (Picker-Escape bleibt unabhängig).
	 * Während des Speicherns ist Abbrechen gesperrt — dann schließt auch Escape nicht.
	 */
	function taste(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		e.stopPropagation();
		if (karteSchliesstPerTaste(e.key, saving)) close();
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		{id}
		class="wt-karte spd-karte"
		role="group"
		aria-labelledby="{id}-titel"
		data-testid="save-preset-dialog"
		data-abschnitt="vorlage-speichern"
		onkeydown={taste}
	>
		<b id="{id}-titel">{$t('wetter.dialog.titel')}</b>

		<div class="spd-feld">
			<label for="{id}-name">{$t('wetter.dialog.name')}</label>
			<Input
				id="{id}-name"
				data-testid="save-preset-name"
				type="text"
				bind:value={name}
				bind:ref={nameFeld}
				maxlength={40}
				placeholder={$t('wetter.dialog.name_platzhalter')}
				error={!!error}
				aria-describedby={error ? `${id}-fehler` : undefined}
			/>
			{#if error}
				<p id="{id}-fehler" class="spd-fehler" role="alert" data-testid="save-preset-error" data-abschnitt="vorlage-speichern-fehler">{error}</p>
			{/if}
		</div>

		<div class="spd-feld">
			<label for="{id}-beschreibung">{$t('wetter.dialog.beschreibung')}</label>
			<Input
				id="{id}-beschreibung"
				data-testid="save-preset-description"
				type="text"
				bind:value={description}
				maxlength={120}
				placeholder={$t('wetter.dialog.beschreibung_platzhalter')}
			/>
		</div>

		<Haken
			zustand={isDefault ? 'an' : 'aus'}
			name={standardText}
			beschriftung={standardText}
			bedienbar={!saving}
			testid="save-preset-is-default"
			onAenderung={(an) => (isDefault = an)}
		/>

		<p class="spd-hinweis" data-testid="save-preset-hinweis">{$t('wetter.dialog.hinweis')}</p>

		<div class="spd-knoepfe">
			<!-- #3111 AC-7 (Mockup Fassung 4): Speichern vor Abbrechen. -->
			<Btn variant="accent" size="tap" data-testid="save-preset-submit" disabled={saving} onclick={submit}>{$t('aktionen.speichern')}</Btn>
			<Btn variant="ghost" size="tap" data-testid="save-preset-cancel" disabled={saving} onclick={close}>{$t('aktionen.abbrechen')}</Btn>
		</div>
	</div>
{/if}
