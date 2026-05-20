/* Mobile · Übergreifende Patterns
 * App-Shell, Drawer offen, Modal/Bottom-Sheet, Toasts, Loading/Empty/Error.
 * Jede Variante als eigener Artboard, damit Devs alle Zustände als Referenz haben.
 */

/* ─────────────────── App-Shell · Drawer offen ─────────────────── */
function PatternAppShellDrawer() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar title="Trips" eyebrow="Workspace" leftIcon="menu" right={<IconBtn kind="plus"/>}/>
        <div style={{ flex: 1, padding: 16, opacity: 0.4 }}>
          <Card padding={14} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>KHW 403</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>2026-05-04 → 2026-05-17</div>
          </Card>
          <Card padding={14}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>GR221 Mallorca</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>2026-02-23 → 2026-02-26</div>
          </Card>
        </div>
        <BottomNav active="trips"/>
      </div>
      {/* Drawer */}
      <div style={{ position: "absolute", inset: 6, borderRadius: 32, overflow: "hidden", pointerEvents: "none" }}>
        <div style={{ position: "absolute", inset: 0, background: "rgba(26,26,24,0.45)" }}/>
        <aside style={{
          position: "absolute", top: 0, left: 0, bottom: 0, width: 296,
          background: "var(--g-paper-deep)",
          display: "flex", flexDirection: "column",
        }}>
          <div style={{ height: 44, flexShrink: 0 }}/>
          <div style={{ padding: "12px 20px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Logo size={20}/>
            <IconBtn kind="close"/>
          </div>
          <div style={{ padding: "0 12px", flex: 1 }}>
            <DrawerGroup label="Workspace">
              <DrawerItem icon="home"    label="Übersicht"/>
              <DrawerItem icon="trip"    label="Trips" badge="1" active/>
              <DrawerItem icon="compare" label="Ortsvergleich"/>
              <DrawerItem icon="archive" label="Archiv" badge="8"/>
            </DrawerGroup>
            <DrawerGroup label="Konfiguration">
              <DrawerItem icon="channels" label="Kanäle"/>
              <DrawerItem icon="settings" label="Einstellungen"/>
            </DrawerGroup>
          </div>
          <div style={{ padding: "16px 20px", borderTop: "1px solid var(--g-rule)", display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%", background: "var(--g-accent)",
              color: "#fff", fontSize: 13, fontWeight: 600,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>GH</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Gregor Henemm</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>henemm.com</div>
            </div>
            <IconBtn kind="external"/>
          </div>
          <div style={{ height: 34, flexShrink: 0 }}/>
        </aside>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Modal · Vollbild ─────────────────── */
function PatternModal() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Trip löschen?"
          eyebrow="Bestätigung erforderlich"
          leftIcon="close"
          right={<button style={{ padding: "0 12px", minHeight: 44, background: "transparent", border: "none", fontSize: 14, color: "var(--g-ink-3)" }}>Abbrechen</button>}
        />

        <ScreenScroll padding={20}>
          {/* Big icon */}
          <div style={{ display: "flex", justifyContent: "center", marginTop: 12, marginBottom: 14 }}>
            <div style={{
              width: 80, height: 80, borderRadius: "50%",
              background: "rgba(168,50,50,0.10)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <MIcon kind="trash" size={36} color="var(--g-bad)"/>
            </div>
          </div>

          <h2 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", margin: 0, marginBottom: 8, textAlign: "center" }}>
            "KHW 403" wirklich löschen?
          </h2>
          <p style={{ fontSize: 14, color: "var(--g-ink-3)", lineHeight: 1.5, textAlign: "center", marginBottom: 24 }}>
            Alle Etappen, Wegpunkte, Metriken-Konfigs und gespeicherten Briefings dieses Trips gehen verloren.
          </p>

          <Card padding={14} style={{ background: "rgba(168,50,50,0.06)", borderLeft: "3px solid var(--g-bad)", marginBottom: 20 }}>
            <Eyebrow style={{ color: "var(--g-bad)", marginBottom: 6 }}>Wird mit gelöscht</Eyebrow>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.8 }}>
              <li>13 Etappen mit Wegpunkten</li>
              <li>Metriken-Preset · 14 Spalten</li>
              <li>Alert-Schwellen</li>
              <li>23 archivierte Briefings</li>
            </ul>
          </Card>

          <MField label="Tippe »LÖSCHEN« zum Bestätigen">
            <MInput placeholder="LÖSCHEN"/>
          </MField>
        </ScreenScroll>

        <div style={{
          padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8, flexShrink: 0,
        }}>
          <MBtn variant="ghost" size="lg" style={{ flex: 1 }}>Abbrechen</MBtn>
          <MBtn variant="danger" size="lg" style={{ flex: 1.4, background: "var(--g-bad)", color: "#fff", border: "1px solid var(--g-bad)" }}>Endgültig löschen</MBtn>
        </div>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Bottom-Sheet · expanded ─────────────────── */
function PatternBottomSheet() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar title="Trips" eyebrow="Workspace" leftIcon="menu" right={<IconBtn kind="plus"/>}/>
        <div style={{ flex: 1, padding: 16, opacity: 0.35 }}>
          <Card padding={14} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>KHW 403</div>
          </Card>
        </div>
        <BottomNav active="trips"/>
      </div>
      {/* Sheet overlay */}
      <div style={{ position: "absolute", inset: 6, borderRadius: 32, overflow: "hidden", pointerEvents: "none" }}>
        <div style={{ position: "absolute", inset: 0, background: "rgba(26,26,24,0.42)" }}/>
        <div style={{
          position: "absolute", left: 0, right: 0, bottom: 0, height: "55%",
          background: "var(--g-card)",
          borderTopLeftRadius: 18, borderTopRightRadius: 18,
          display: "flex", flexDirection: "column",
        }}>
          <div style={{ display: "flex", justifyContent: "center", paddingTop: 8 }}>
            <span style={{ width: 36, height: 4, borderRadius: 2, background: "var(--g-rule)" }}/>
          </div>
          <div style={{ padding: "8px 20px 12px", display: "flex", alignItems: "flex-start", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <Eyebrow style={{ marginBottom: 4 }}>Aktionen · aktiver Trip</Eyebrow>
              <div style={{ fontSize: 18, fontWeight: 600 }}>KHW 403</div>
            </div>
            <IconBtn kind="close"/>
          </div>
          <div style={{ padding: "0 20px 20px" }}>
            {[
              { icon: "send", label: "Briefing jetzt senden", sub: "Manueller Trigger" },
              { icon: "external", label: "Email-Vorschau", sub: "Nächstes Briefing" },
              { icon: "bell", label: "Alert-Konfiguration", sub: "Schwellen & Δ-Regeln" },
              { icon: "edit", label: "Bearbeiten", sub: "Wegpunkte, Profil, Kanäle" },
              { icon: "trash", label: "Löschen", danger: true },
            ].map((it, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 14,
                padding: "14px 4px", minHeight: 56,
                borderBottom: i < 4 ? "1px solid var(--g-rule-soft)" : "none",
              }}>
                <span style={{
                  width: 40, height: 40, borderRadius: "var(--g-r-3)",
                  background: it.danger ? "rgba(168,50,50,0.08)" : "var(--g-paper-deep)",
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  <MIcon kind={it.icon} size={20} color={it.danger ? "var(--g-bad)" : "var(--g-ink)"}/>
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 500, color: it.danger ? "var(--g-bad)" : "var(--g-ink)" }}>{it.label}</div>
                  {it.sub && <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2 }}>{it.sub}</div>}
                </div>
                <MIcon kind="chevron" size={16} color="var(--g-ink-4)"/>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Toasts · 4 Varianten gestapelt ─────────────────── */
function PatternToasts() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar title="Toasts · 4 Varianten" eyebrow="Notifications" leftIcon="back"/>
        <ScreenScroll padding={16}>
          <Eyebrow style={{ marginBottom: 8 }}>Info · neutral</Eyebrow>
          <ToastStatic kind="info" msg="Briefing-Zeitplan aktualisiert. Nächstes Briefing 18:00." action="OK"/>

          <div style={{ height: 12 }}/>
          <Eyebrow style={{ marginBottom: 8 }}>Success · grün</Eyebrow>
          <ToastStatic kind="success" hint="Gesendet · 06:00" msg="Morgen-Briefing an 2 Kanäle ausgeliefert." action="Anzeigen"/>

          <div style={{ height: 12 }}/>
          <Eyebrow style={{ marginBottom: 8 }}>Warning · gelb</Eyebrow>
          <ToastStatic kind="warn" hint="Schwellwert nahe" msg="Wind 48 km/h — Schwelle 50 km/h." action="Details"/>

          <div style={{ height: 12 }}/>
          <Eyebrow style={{ marginBottom: 8 }}>Error · rot</Eyebrow>
          <ToastStatic kind="error" hint="Kanal Signal offline" msg="Briefing konnte nicht zugestellt werden. SMS-Fallback aktiviert." action="Erneut"/>

          <div style={{ height: 24 }}/>
          <Eyebrow style={{ marginBottom: 8 }}>Position</Eyebrow>
          <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.6 }}>
            Toasts erscheinen über der Bottom-Nav (16 px Abstand zu allen Rändern). Auto-Dismiss nach 4 s, persistent für Errors.
          </div>
        </ScreenScroll>
        <BottomNav active="home"/>
      </div>
    </PhoneFrame>
  );
}

function ToastStatic({ kind, msg, action, hint }) {
  const map = {
    info:    { bg: "var(--g-ink)",   fg: "var(--g-paper)" },
    success: { bg: "var(--g-good)",  fg: "#fff" },
    warn:    { bg: "var(--g-warn)",  fg: "#fff" },
    error:   { bg: "var(--g-bad)",   fg: "#fff" },
  };
  const t = map[kind] || map.info;
  return (
    <div style={{
      background: t.bg, color: t.fg, borderRadius: "var(--g-r-3)",
      padding: "12px 16px", display: "flex", alignItems: "center", gap: 12,
      boxShadow: "var(--g-shadow-2)",
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        {hint && (
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.7, marginBottom: 2 }}>{hint}</div>
        )}
        <div style={{ fontSize: 14, lineHeight: 1.4 }}>{msg}</div>
      </div>
      {action && (
        <button style={{
          background: "transparent", border: "none", color: t.fg,
          fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em",
          fontFamily: "var(--g-font-mono)", cursor: "pointer", minHeight: 44, padding: "0 4px",
        }}>{action}</button>
      )}
    </div>
  );
}

/* ─────────────────── States: Loading / Empty / Error ─────────────────── */
function PatternStates() {
  return (
    <PhoneFrame height={1100}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar title="States" eyebrow="Loading · Empty · Error" leftIcon="back"/>
        <ScreenScroll padding={16}>
          {/* Loading */}
          <Eyebrow style={{ marginBottom: 8 }}>Loading · Skeleton</Eyebrow>
          <Card padding={14} style={{ marginBottom: 14 }}>
            <SkeletonRow w="60%" h={12}/>
            <div style={{ height: 8 }}/>
            <SkeletonRow w="40%" h={10}/>
            <div style={{ height: 14 }}/>
            <SkeletonRow w="100%" h={48}/>
            <div style={{ height: 8 }}/>
            <SkeletonRow w="100%" h={48}/>
          </Card>

          {/* Empty */}
          <Eyebrow style={{ marginBottom: 8 }}>Empty · keine Daten</Eyebrow>
          <Card padding={20} style={{ marginBottom: 14, textAlign: "center" }}>
            <div style={{
              width: 56, height: 56, borderRadius: "var(--g-r-3)",
              background: "var(--g-card-alt)", margin: "8px auto 14px",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <MIcon kind="trip" size={28} color="var(--g-ink-3)"/>
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Noch keine Trips</div>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 16, maxWidth: 260, margin: "0 auto 16px" }}>
              Lege deinen ersten Trip an — wir berechnen ETAs und Wegpunkte automatisch aus deinen GPX-Files.
            </div>
            <MBtn variant="primary" size="lg" icon={<MIcon kind="plus" size={16} color="var(--g-paper)"/>}>Ersten Trip anlegen</MBtn>
          </Card>

          {/* Error */}
          <Eyebrow style={{ marginBottom: 8 }}>Error · Netzwerk</Eyebrow>
          <Card padding={20} style={{ marginBottom: 14, textAlign: "center", borderLeft: "3px solid var(--g-bad)" }}>
            <div style={{
              width: 56, height: 56, borderRadius: "var(--g-r-3)",
              background: "rgba(168,50,50,0.10)", margin: "8px auto 14px",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <MIcon kind="bell" size={28} color="var(--g-bad)"/>
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Briefing konnte nicht laden</div>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 8 }}>
              Verbindung zu Wetterdienst MeteoBlue verloren. Wir versuchen es alle 30 s erneut.
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginBottom: 16 }}>
              ERR_NET_502 · 14:32:08
            </div>
            <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
              <MBtn variant="ghost" size="md">Details</MBtn>
              <MBtn variant="primary" size="md">Jetzt erneut</MBtn>
            </div>
          </Card>

          {/* Permission-Hint */}
          <Eyebrow style={{ marginBottom: 8 }}>Permission · Hint</Eyebrow>
          <Card padding={14} style={{ background: "var(--g-accent-tint)", borderLeft: "3px solid var(--g-accent)" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <MIcon kind="bell" size={24} color="var(--g-accent)"/>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Benachrichtigungen aktivieren?</div>
                <div style={{ fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5, marginBottom: 10 }}>
                  Sonst kommen Alerts nur per Signal/SMS — Push wäre schneller.
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <MBtn variant="ghost" size="md">Später</MBtn>
                  <MBtn variant="accent" size="md">Aktivieren</MBtn>
                </div>
              </div>
            </div>
          </Card>
        </ScreenScroll>
        <BottomNav active="home"/>
      </div>
    </PhoneFrame>
  );
}

function SkeletonRow({ w = "100%", h = 12 }) {
  return (
    <div style={{
      width: w, height: h, borderRadius: 4,
      background: "linear-gradient(90deg, var(--g-card-alt) 0%, var(--g-paper-deep) 50%, var(--g-card-alt) 100%)",
    }}/>
  );
}

/* ─────────────────── Wizard-Abbruch · Sheet ─────────────────── */
function PatternWizardCancel() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar title="GPX-Import" eyebrow="Schritt 2 von 4 · Neuer Trip" leftIcon="close"
                   right={<button style={{ padding: "0 12px", minHeight: 44, background: "transparent", border: "none", fontSize: 14, color: "var(--g-ink-3)" }}>Abbrechen</button>}/>
        <div style={{ display: "flex", gap: 4, padding: "8px 16px 12px", borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0, opacity: 0.4 }}>
          {[1,2,3,4].map(n => (
            <div key={n} style={{ flex: 1, height: 3, borderRadius: 2, background: n <= 2 ? "var(--g-accent)" : "var(--g-rule)" }}/>
          ))}
        </div>
        <div style={{ flex: 1, padding: 16, opacity: 0.35 }}>
          <Card padding={14}>
            <Eyebrow>Etappen-Liste · 3</Eyebrow>
            <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6 }}>2 GPX hochgeladen, 1 Pausentag …</div>
          </Card>
        </div>
      </div>

      {/* Sheet overlay */}
      <div style={{ position: "absolute", inset: 6, borderRadius: 32, overflow: "hidden", pointerEvents: "none" }}>
        <div style={{ position: "absolute", inset: 0, background: "rgba(26,26,24,0.42)" }}/>
        <div style={{
          position: "absolute", left: 0, right: 0, bottom: 0,
          background: "var(--g-card)",
          borderTopLeftRadius: 18, borderTopRightRadius: 18,
          display: "flex", flexDirection: "column", maxHeight: "70%",
        }}>
          <div style={{ display: "flex", justifyContent: "center", paddingTop: 8 }}>
            <span style={{ width: 36, height: 4, borderRadius: 2, background: "var(--g-rule)" }}/>
          </div>
          <div style={{ padding: "12px 20px 20px" }}>
            <Eyebrow style={{ marginBottom: 4 }}>Trip-Anlage abbrechen?</Eyebrow>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 6, letterSpacing: "-0.01em" }}>
              Du hast schon Etappen importiert.
            </div>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 20 }}>
              Speichere als Entwurf und mach später weiter, oder verwirf alles.
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button style={{
                display: "flex", alignItems: "center", gap: 12, padding: "14px 14px",
                background: "var(--g-accent)", color: "#fff", border: "1px solid var(--g-accent)",
                borderRadius: "var(--g-r-3)", cursor: "pointer", minHeight: 56, textAlign: "left",
              }}>
                <MIcon kind="check" size={20} color="#fff"/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>Als Entwurf speichern</div>
                  <div style={{ fontSize: 12, opacity: 0.85, marginTop: 2 }}>In Trips-Liste als Draft. Fortsetzen jederzeit möglich.</div>
                </div>
              </button>

              <button style={{
                display: "flex", alignItems: "center", gap: 12, padding: "14px 14px",
                background: "var(--g-card)", color: "var(--g-ink)", border: "1px solid var(--g-rule)",
                borderRadius: "var(--g-r-3)", cursor: "pointer", minHeight: 56, textAlign: "left",
              }}>
                <MIcon kind="back" size={20} color="var(--g-ink-2)"/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>Weiter editieren</div>
                  <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2 }}>Zurück zum Wizard.</div>
                </div>
              </button>

              <button style={{
                display: "flex", alignItems: "center", gap: 12, padding: "14px 14px",
                background: "transparent", color: "var(--g-bad)", border: "1px solid var(--g-rule)",
                borderRadius: "var(--g-r-3)", cursor: "pointer", minHeight: 56, textAlign: "left",
              }}>
                <MIcon kind="trash" size={20} color="var(--g-bad)"/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>Verwerfen</div>
                  <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2 }}>Eingaben gehen verloren.</div>
                </div>
              </button>
            </div>
          </div>
          <div style={{ height: 34 }}/>
        </div>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Push-Permission · Pre-Prompt ───────────────────
 * Eigener Vollbild-Screen, der NACH erster Alert-Konfig (oder erstem Trip) erscheint.
 * Tappt User "Aktivieren" → erst dann erscheint der native iOS/Android-Permission-Dialog.
 * Tappt User "Später" → Pre-Prompt wird in 7 Tagen oder bei nächster Alert-Auslösung wieder gezeigt.
 */
function PatternPushPermission() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopoBg opacity={0.16}/>

        <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column", padding: "24px 20px 0" }}>

          {/* Top: Skip-Link */}
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
            <button style={{
              padding: "8px 12px", minHeight: 44, background: "transparent",
              border: "none", fontSize: 14, color: "var(--g-ink-3)", cursor: "pointer", fontWeight: 500,
            }}>Überspringen</button>
          </div>

          {/* Hero Icon */}
          <div style={{ display: "flex", justifyContent: "center", marginTop: 24, marginBottom: 24 }}>
            <div style={{
              width: 88, height: 88, borderRadius: 24,
              background: "var(--g-accent)",
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 8px 24px rgba(196,90,42,0.32)",
              position: "relative",
            }}>
              <MIcon kind="bell" size={42} color="#fff"/>
              <span style={{
                position: "absolute", top: 14, right: 14,
                width: 14, height: 14, borderRadius: "50%",
                background: "var(--g-bad)", border: "3px solid var(--g-accent)",
              }}/>
            </div>
          </div>

          {/* Copy */}
          <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: 0, marginBottom: 10, textAlign: "center", lineHeight: 1.2 }}>
            Push-Alerts aktivieren?
          </h1>
          <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55, textAlign: "center", marginBottom: 24, padding: "0 8px" }}>
            Push ist die schnellste Route für kritische Wetter-Alerts —
            spürbar schneller als Email oder SMS. Du behältst die volle Kontrolle, was wann ankommt.
          </div>

          {/* Bullets */}
          <div style={{ marginBottom: 28 }}>
            <PushBullet icon="check" text="Sofort-Alert bei Gewitter, Sturm oder kritischer Wetteränderung"/>
            <PushBullet icon="check" text="Nur Trip-Alerts, kein Marketing — versprochen"/>
            <PushBullet icon="check" text="Ruhezeit & Kanäle bleiben pro Trip konfigurierbar"/>
          </div>

          {/* Spacer */}
          <div style={{ flex: 1 }}/>

          {/* Action-Stack */}
          <div style={{
            paddingBottom: "calc(20px + env(safe-area-inset-bottom))",
            display: "flex", flexDirection: "column", gap: 8,
          }}>
            <MBtn variant="accent" size="xl" block>Aktivieren</MBtn>
            <MBtn variant="quiet" size="lg" block>Später erinnern</MBtn>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textAlign: "center", marginTop: 8, letterSpacing: "0.06em" }}>
              Erscheint einmalig nach erster Alert-Konfig.
            </div>
          </div>
        </div>
      </div>
    </PhoneFrame>
  );
}

function PushBullet({ icon, text }) {
  return (
    <div style={{ display: "flex", gap: 12, padding: "10px 0", alignItems: "flex-start" }}>
      <span style={{
        width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
        background: "rgba(61,107,58,0.12)",
        display: "flex", alignItems: "center", justifyContent: "center",
        marginTop: 1,
      }}>
        <MIcon kind={icon} size={14} color="var(--g-good)"/>
      </span>
      <div style={{ flex: 1, fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55 }}>{text}</div>
    </div>
  );
}

window.PatternAppShellDrawer = PatternAppShellDrawer;
window.PatternModal = PatternModal;
window.PatternBottomSheet = PatternBottomSheet;
window.PatternToasts = PatternToasts;
window.PatternStates = PatternStates;
window.PatternWizardCancel = PatternWizardCancel;
window.PatternPushPermission = PatternPushPermission;
