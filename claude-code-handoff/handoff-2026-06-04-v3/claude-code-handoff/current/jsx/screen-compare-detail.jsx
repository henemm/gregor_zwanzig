/* Screen: Ortsvergleich-Hub (Desktop) — Klick-Ziel einer Vergleich-Kachel.
 * ─────────────────────────────────────────────────────────────────────
 * Issue #504. EINE Fläche pro Vergleich mit kanonischer Tab-Leiste — analog
 * zum Trip-Hub. Drei-Rollen-Modell:
 *   Ansehen     → Tab „Übersicht"  (Monitoring + Zusammenfassung, read-only)
 *   Bearbeiten  → Tabs „Orte" · „Idealwerte" · „Layout" · „Versand"
 *   Verifizieren→ Tab „Vorschau"   (CompareEmail profil-gemappt, Kanal-Umschalter)
 *   Lesen       → außerhalb der App, im Kanal
 *
 * Grundverständnis (CLAUDE.md): Web-App = Einrichtung + Monitoring, KEIN Reader.
 * Die Vorschau ist Verifikation, kein Konsum-Surface und kein Listen-Klick-Ziel.
 *
 * Atomic Design: Compare-Domain-Molecules (CompareStatusPill, CompareKebab,
 * CompareLocationRow, CompareIdealRow, CompareLayoutRow, CompareBriefingPreview,
 * CompareChannelSwitch, compareActions) + DetailRow/Card/Btn/Pill/Eyebrow/Dot.
 * Lokale Helfer tragen CHub_-Prefix (Babel-Scope-Disziplin).
 */

const CHUB_CHANNEL_LABEL = { email: "Email", telegram: "Telegram", sms: "SMS" };

/* Lebenszyklus-Aktionen für den Hub-Header (Charter §6). Bearbeiten passiert in
 * den Tabs, Vorschau/Senden sind eigene Affordanzen → Kebab = nur Lifecycle. */
function CHub_lifecycleActions(status) {
  if (status === "draft") return [{ key: "trash", label: "Entwurf löschen", danger: true }];
  const toggle = status === "active"
    ? { key: "pause", label: "Pausieren" }
    : { key: "resume", label: "Aktivieren" };
  return [toggle, { key: "archive", label: "Archivieren" }, { key: "trash", label: "Löschen", danger: true }];
}

function ScreenCompareDetail({ subId = "skitour-hochkoenig", tab = "overview", menuOpen = false }) {
  const sub = (window.MOCK_COMPARE_SUBS || []).find(s => s.id === subId)
            || (window.MOCK_COMPARE_SUBS || [])[0];
  const [active, setActive] = React.useState(tab);
  if (!sub) return null;

  const isActive = sub.status === "active";
  const isDraft = sub.status === "draft";
  const locs = sub.locationIds
    .map(id => (window.MOCK_LOCATIONS || []).find(l => l.id === id))
    .filter(Boolean);

  const tabs = [
    { id: "overview", label: "Übersicht" },
    { id: "locations", label: "Orte", badge: String(locs.length) },
    { id: "ideals", label: "Idealwerte" },
    { id: "layout", label: "Layout" },
    { id: "send", label: "Versand" },
    { id: "preview", label: "Vorschau" },
  ];

  const ctx = { sub, locs, isActive, isDraft, go: setActive };

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }} data-screen-label={`Ortsvergleich-Hub · ${sub.name} · ${active}`}>
      <Sidebar active="compare"/>
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.12}/>

        {/* ── Kontext-Header (über alle Tabs konstant) ───────────── */}
        <div style={{ position: "relative", padding: "22px 40px 0", borderBottom: "1px solid var(--g-rule)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <a href="#" style={{ fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--g-ink-3)", textDecoration: "none" }}>Orts-Vergleiche</a>
            <span style={{ color: "var(--g-ink-4)", fontSize: 11 }}>/</span>
            <span style={{ fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--g-ink-4)" }}>Hub</span>
          </div>

          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24 }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <h1 style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.1, margin: 0, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{sub.name}</h1>
                <span style={{ flexShrink: 0 }}><CompareStatusPill status={sub.status}/></span>
              </div>
              <div style={{ fontSize: 14, color: "var(--g-ink-3)", margin: "8px 0 18px" }}>
                {sub.region} · {sub.profileLabel} · {locs.length} Orte
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
              <Btn variant="primary" size="md" onClick={() => setActive(isDraft ? "send" : "preview")} icon={
                isDraft
                  ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></svg>
                  : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 3L3 10l7 3 3 7z"/><path d="M21 3l-11 11"/></svg>
              }>{isDraft ? "Setup abschließen" : "Test senden"}</Btn>
              <CompareKebab items={CHub_lifecycleActions(sub.status)} defaultOpen={menuOpen}/>
            </div>
          </div>

          {/* ── Tab-Leiste ─────────────────────────────────────── */}
          <div style={{ display: "flex", gap: 0 }}>
            {tabs.map(t => {
              const on = t.id === active;
              return (
                <button key={t.id} onClick={() => setActive(t.id)} style={{
                  padding: "12px 16px", cursor: "pointer", fontSize: 13, fontWeight: on ? 600 : 500,
                  background: "transparent", border: "none", fontFamily: "var(--g-font-sans)",
                  color: on ? "var(--g-ink)" : "var(--g-ink-3)",
                  borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
                  marginBottom: -1, display: "flex", alignItems: "center", gap: 7,
                }}>
                  {t.label}
                  {t.badge && (
                    <span className="mono" style={{ fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 3, background: "var(--g-paper-deep)", color: "var(--g-ink-3)" }}>{t.badge}</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Tab-Inhalt ─────────────────────────────────────────── */}
        <div style={{ position: "relative", padding: "28px 40px 80px", maxWidth: 1320 }}>
          {active === "overview"  && <CHub_OverviewTab ctx={ctx}/>}
          {active === "locations" && <CHub_LocationsTab ctx={ctx}/>}
          {active === "ideals"    && <CHub_IdealsTab ctx={ctx}/>}
          {active === "layout"    && <CHub_LayoutTab ctx={ctx}/>}
          {active === "send"      && <CHub_SendTab ctx={ctx}/>}
          {active === "preview"   && <CHub_PreviewTab ctx={ctx}/>}
        </div>
      </main>
    </div>
  );
}

/* ════════════════════ Tab 1 · Übersicht (Ansehen) ════════════════════ */
function CHub_OverviewTab({ ctx }) {
  const { sub, locs, isActive, isDraft, go } = ctx;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* Monitoring-Streifen */}
      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ padding: "18px 24px", display: "flex", alignItems: "center", gap: 40, flexWrap: "wrap" }}>
          <CHub_Stat label="Status">
            {isActive
              ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Dot tone="good" size={7}/> Läuft automatisch</span>
              : isDraft
                ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Dot tone="neutral" size={7}/> Entwurf · nicht aktiv</span>
                : <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Dot tone="neutral" size={7}/> Pausiert</span>}
          </CHub_Stat>
          <CHub_Stat label="Nächster Versand">{sub.nextSend}</CHub_Stat>
          <CHub_Stat label="Zuletzt raus">{sub.lastSent}</CHub_Stat>
          <CHub_Stat label="Kanäle">
            {sub.channels.length === 0
              ? "—"
              : <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>{sub.health === "ok" && <Dot tone="good" size={7}/>}{sub.channels.map(c => CHUB_CHANNEL_LABEL[c]).join(" · ")}</span>}
          </CHub_Stat>
        </div>
      </Card>

      {/* Zusammenfassung — je Sektion „Bearbeiten →" */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <CHub_SummaryCard eyebrow="Orte" title={`${locs.length} Kandidaten`} onEdit={() => go("locations")}>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6 }}>
            {locs.slice(0, 3).map(l => l.name).join(" · ")}{locs.length > 3 ? ` +${locs.length - 3} weitere` : ""}
          </div>
        </CHub_SummaryCard>

        <CHub_SummaryCard eyebrow="Idealwerte" title={sub.profileLabel} onEdit={() => go("ideals")}>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6 }}>
            {sub.ideals.length} Metriken bestimmen das Ranking — {sub.ideals.filter(i => i.weight === "hoch").length} hoch gewichtet.
          </div>
        </CHub_SummaryCard>

        <CHub_SummaryCard eyebrow="Layout pro Kanal" title={sub.channels.length ? sub.channels.map(c => CHUB_CHANNEL_LABEL[c]).join(" · ") : "Keine Kanäle"} onEdit={() => go("layout")}>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6 }}>
            Engere Kanäle zeigen automatisch weniger Spalten — Reihenfolge nach Priorität.
          </div>
        </CHub_SummaryCard>

        <CHub_SummaryCard eyebrow="Versand" title={isDraft ? "Noch nicht geplant" : sub.schedule} onEdit={() => go("send")}>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6 }}>
            {isDraft ? "Rhythmus & Aktivierung im Tab Versand festlegen." : <>Vorausschau {sub.horizon} · nächster Versand {sub.nextSend}.</>}
          </div>
        </CHub_SummaryCard>
      </div>

      {/* Verifikations-Hinweis (kein Reader) */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 18px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-3)" }}>
        <div style={{ fontSize: 13, color: "var(--g-ink-2)", flex: 1, lineHeight: 1.5 }}>
          Gelesen wird das Briefing unterwegs im Postfach — nicht hier. Der Tab <strong>Vorschau</strong> dient nur zum Prüfen der Konfiguration.
        </div>
        <Btn variant="ghost" size="sm" onClick={() => go("preview")}>Vorschau prüfen →</Btn>
      </div>
    </div>
  );
}

/* ════════════════════ Tab 2 · Orte (Bearbeiten) ════════════════════ */
function CHub_LocationsTab({ ctx }) {
  const { locs } = ctx;
  return (
    <CHub_EditSection title="Verglichene Orte" hint="Reihenfolge = Ranking-Tiebreak · ziehen zum Sortieren">
      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ borderBottom: locs.length ? "1px solid var(--g-rule-soft)" : "none" }}>
          {locs.map((l, i) => (
            <div key={l.id} style={{ display: "flex", alignItems: "center", background: i % 2 === 1 ? "var(--g-paper-deep)" : "transparent" }}>
              <span style={{ paddingLeft: 16, color: "var(--g-ink-4)", display: "flex", cursor: "grab" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>
              </span>
              <div style={{ flex: 1, minWidth: 0 }}><CompareLocationRow loc={l} index={i}/></div>
              <button title="Entfernen" style={{ marginRight: 14, width: 32, height: 32, flexShrink: 0, border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", background: "transparent", color: "var(--g-ink-3)", cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
              </button>
            </div>
          ))}
        </div>
        <div style={{ padding: 14 }}>
          <Btn variant="ghost" size="sm" icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>}>Ort hinzufügen</Btn>
        </div>
      </Card>
    </CHub_EditSection>
  );
}

/* ════════════════════ Tab 3 · Idealwerte (Bearbeiten) ════════════════════ */
function CHub_IdealsTab({ ctx }) {
  const { sub } = ctx;
  return (
    <CHub_EditSection title={`Was „gut" bedeutet`} hint="je höher gewichtet, desto stärker zählt die Metrik">
      <Card padding={20}>
        <div>
          {sub.ideals.map((it, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ flex: 1 }}><CompareIdealRow item={it} last={i === sub.ideals.length - 1}/></div>
              <button title="Bearbeiten" style={{ width: 32, height: 32, flexShrink: 0, border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", background: "transparent", color: "var(--g-ink-3)", cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4l6 6L9 21H3v-6z"/></svg>
              </button>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, paddingTop: 14, borderTop: "1px solid var(--g-rule-soft)" }}>
          <Btn variant="ghost" size="sm" icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>}>Metrik hinzufügen</Btn>
        </div>
      </Card>
    </CHub_EditSection>
  );
}

/* ════════════════════ Tab 4 · Layout (Bearbeiten) ════════════════════ */
function CHub_LayoutTab({ ctx }) {
  const { sub } = ctx;
  const limits = [["Email", "alle Spalten"], ["Telegram", "max 8"], ["SMS", "flach · 0"]];
  return (
    <CHub_EditSection title="Spalten pro Kanal" hint="eine Konfiguration — der Renderer kappt je Kanal">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 18 }}>
        {limits.map(([k, v]) => (
          <span key={k} className="mono" style={{ fontSize: 11, padding: "5px 10px", borderRadius: "var(--g-r-pill)", border: "1px solid var(--g-rule)", background: "var(--g-card-alt)", color: "var(--g-ink-2)" }}>
            {k} · {v}
          </span>
        ))}
      </div>
      <Card padding={20}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {(sub.channels.length ? sub.channels : ["email"]).map(ch => (
            <CompareLayoutRow key={ch} channel={ch} cols={sub.layout[ch] || []}/>
          ))}
        </div>
      </Card>
    </CHub_EditSection>
  );
}

/* ════════════════════ Tab 5 · Versand (Bearbeiten) ════════════════════ */
function CHub_SendTab({ ctx }) {
  const { sub, isActive, isDraft } = ctx;
  const allCh = ["email", "telegram", "sms"];

  const banner = isDraft
    ? { tone: "accent", bg: "var(--g-accent-tint)", border: "var(--g-accent)", text: "Noch nicht aktiv. Sobald Orte, Idealwerte und mindestens ein Kanal stehen, kannst du den Vergleich aktivieren.", cta: "Aktivieren" }
    : isActive
      ? { tone: "good", bg: "rgba(61,107,58,0.10)", border: "var(--g-good)", text: "Läuft automatisch. Das Briefing geht im konfigurierten Rhythmus in die Kanäle.", cta: "Pausieren" }
      : { tone: "neutral", bg: "var(--g-paper-deep)", border: "var(--g-rule)", text: "Pausiert. Es geht aktuell kein Briefing raus.", cta: "Aktivieren" };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24, alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <CHub_EditSection title="Rhythmus & Vorausschau">
          <Card padding={20}>
            <DetailRow label="Rhythmus" value={isDraft ? "—" : sub.schedule} right={<CHub_EditIcon/>}/>
            <DetailRow label="Vorausschau-Horizont" value={isDraft ? "—" : sub.horizon} right={<CHub_EditIcon/>}/>
            <DetailRow label="Nächster Versand" value={sub.nextSend} divider="none"/>
          </Card>
        </CHub_EditSection>

        <CHub_EditSection title="Kanäle" hint="verifiziert / fehlt">
          <Card padding={0} style={{ overflow: "hidden" }}>
            {allCh.map((ch, i) => {
              const on = sub.channels.includes(ch);
              return (
                <div key={ch} style={{ display: "flex", alignItems: "center", gap: 12, padding: "13px 18px", borderTop: i === 0 ? "none" : "1px solid var(--g-rule-soft)" }}>
                  <Dot tone={on ? (sub.health === "ok" ? "good" : "neutral") : "neutral"} size={7}/>
                  <span style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>{CHUB_CHANNEL_LABEL[ch]}</span>
                  <span className="mono" style={{ fontSize: 11, color: on ? "var(--g-ink-3)" : "var(--g-ink-4)", letterSpacing: "0.04em" }}>
                    {on ? "verifiziert" : "nicht verbunden"}
                  </span>
                  <span style={{
                    width: 38, height: 22, borderRadius: 11, flexShrink: 0, position: "relative",
                    background: on ? "var(--g-good)" : "var(--g-rule)", transition: "background 120ms",
                  }}>
                    <span style={{ position: "absolute", top: 2, left: on ? 18 : 2, width: 18, height: 18, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 2px rgba(0,0,0,0.2)", transition: "left 120ms" }}/>
                  </span>
                </div>
              );
            })}
          </Card>
        </CHub_EditSection>
      </div>

      <CHub_EditSection title="Aktivierung">
        <Card padding={20} style={{ borderLeft: `3px solid ${banner.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 10 }}>
            <Dot tone={isActive ? "good" : "neutral"} size={8}/>
            <span style={{ fontSize: 15, fontWeight: 600 }}>{isDraft ? "Entwurf" : isActive ? "Aktiv" : "Pausiert"}</span>
          </div>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55, marginBottom: 16 }}>{banner.text}</div>
          <Btn variant={isActive ? "ghost" : "primary"} size="md" style={{ width: "100%", justifyContent: "center" }}>{banner.cta}</Btn>
          <div style={{ marginTop: 10 }}>
            <Btn variant="quiet" size="sm" style={{ width: "100%", justifyContent: "center" }} icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 3L3 10l7 3 3 7z"/><path d="M21 3l-11 11"/></svg>}>Test-Briefing jetzt senden</Btn>
          </div>
        </Card>
      </CHub_EditSection>
    </div>
  );
}

/* ════════════════════ Tab 6 · Vorschau (Verifizieren) ════════════════════ */
function CHub_PreviewTab({ ctx }) {
  const { sub } = ctx;
  const profileId = (window.ceProfileFor ? window.ceProfileFor(sub.profileId) : sub.profileId);
  const defaultCh = sub.channels[0] || "email";
  const [channel, setChannel] = React.useState(defaultCh);
  const [emailView, setEmailView] = React.useState("desktop");

  return (
    <div>
      {/* Verifikations-Hinweis */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "13px 18px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-3)", marginBottom: 20 }}>
        <Eyebrow style={{ flexShrink: 0 }}>Vorschau · Prüfung</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--g-ink-2)", flex: 1, lineHeight: 1.5 }}>
          So sieht dein Briefing aus — gelesen wird es unterwegs im Postfach, nicht hier.
        </div>
        <Btn variant="ghost" size="sm" icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 3L3 10l7 3 3 7z"/><path d="M21 3l-11 11"/></svg>}>Test-Briefing senden</Btn>
      </div>

      {/* Kanal-Umschalter */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <CompareChannelSwitch value={channel} onChange={setChannel} channels={sub.channels}/>
        {channel === "email" && (
          <div style={{ display: "inline-flex", background: "var(--g-paper-deep)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", padding: 3, gap: 2 }}>
            {[["desktop", "Desktop-Inbox"], ["iphone", "iPhone-Mail"]].map(([v, l]) => (
              <button key={v} onClick={() => setEmailView(v)} style={{
                padding: "7px 13px", border: "none", cursor: "pointer", borderRadius: 4, fontSize: 12.5,
                fontFamily: "var(--g-font-sans)", fontWeight: emailView === v ? 600 : 500,
                background: emailView === v ? "var(--g-card)" : "transparent",
                boxShadow: emailView === v ? "var(--g-shadow-1)" : "none",
                color: emailView === v ? "var(--g-ink)" : "var(--g-ink-3)",
              }}>{l}</button>
            ))}
          </div>
        )}
        {!sub.channels.includes(channel) && (
          <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
            Kanal nicht konfiguriert · Beispiel-Render
          </span>
        )}
      </div>

      {/* Render-Fläche */}
      <div style={{ display: "flex", justifyContent: channel === "email" ? "flex-start" : "flex-start" }}>
        <div style={{
          padding: channel === "email" && emailView === "desktop" ? 24 : 0,
          background: channel === "email" && emailView === "desktop" ? "var(--g-paper-deep)" : "transparent",
          borderRadius: "var(--g-r-3)",
          maxWidth: channel === "email" ? "none" : 380, width: channel === "email" ? "auto" : "100%",
        }}>
          <CompareBriefingPreview
            profileId={profileId}
            channel={channel}
            subscriptionName={sub.name}
            schedule={sub.schedule}
            emailView={emailView}
          />
        </div>
      </div>
    </div>
  );
}

/* ════════════════════ Lokale Helfer (CHub_) ════════════════════ */
function CHub_Stat({ label, children }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 5 }}>{label}</div>
      <div style={{ fontSize: 14, color: "var(--g-ink)", fontWeight: 500 }}>{children}</div>
    </div>
  );
}

function CHub_SummaryCard({ eyebrow, title, children, onEdit }) {
  return (
    <Card padding={20} style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 4 }}>
        <Eyebrow>{eyebrow}</Eyebrow>
        <button onClick={onEdit} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, fontSize: 12, fontWeight: 600, color: "var(--g-accent-deep)", fontFamily: "var(--g-font-sans)" }}>Bearbeiten →</button>
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8, letterSpacing: "-0.01em" }}>{title}</div>
      {children}
    </Card>
  );
}

function CHub_EditSection({ title, hint, children }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", margin: 0 }}>{title}</h2>
        {hint && <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.03em" }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function CHub_EditIcon() {
  return (
    <button title="Bearbeiten" style={{ width: 30, height: 30, border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", background: "transparent", color: "var(--g-ink-3)", cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4l6 6L9 21H3v-6z"/></svg>
    </button>
  );
}

window.ScreenCompareDetail = ScreenCompareDetail;
