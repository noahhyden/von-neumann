/** Site chrome ported from noahhyden.com: a sticky nav and a footer, so the two sites read as one hand. */
import type { Child } from "pimas/dom";
import { For } from "pimas/flow";
import { AzulejoBand } from "./azulejo.js";
import { GitHubIcon, LinkedInIcon, Mark } from "./icons.js";

const REPO = "https://github.com/noahhyden/von-neumann";
const SITE = "https://noahhyden.com";

export const NAV_MODULES: [string, string][] = [
  ["wall", "Electronics wall"],
  ["mission", "Full mission"],
  ["fleet", "Fleet"],
  ["swarm", "Swarm"],
  ["spine", "Across scales"],
  ["probe", "Single probe"],
  ["launch", "Launch economics"],
  ["power", "Power budget"],
];

const LINK = "font-family:var(--sans); font-size:14px;";
const linkStyle = (active: boolean) => `${LINK} color:${active ? "var(--ink)" : "var(--granite)"}; ${active ? "font-weight:500;" : ""}`;

/** Closes the native details after a pick so the panel does not hang over the new surface. */
const closeMenu = (e: MouseEvent) => (e.currentTarget as HTMLElement).closest("details")?.removeAttribute("open");

export function Nav(props: { surface: string }): Child {
  const onModule = () => NAV_MODULES.some(([s]) => s === props.surface);
  return (
    <nav style="position:sticky; top:0; z-index:10; background:var(--nav-bg); backdrop-filter:blur(8px);">
      <div style="max-width:var(--wrap); margin:0 auto; min-height:64px; padding:8px 40px; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px 28px;">
        <a href="/" style="display:inline-flex; align-items:center; gap:11px; font-family:var(--serif); font-weight:600; font-size:19px; letter-spacing:-.01em; color:var(--ink); white-space:nowrap;">
          <Mark size={34} />
          <span>The Arithmetic of Self-Replication<span style="color:var(--falu);">.</span></span>
        </a>

        <div style="display:flex; flex-wrap:wrap; align-items:center; gap:8px 28px;">
          <details class="nav-menu" name="vn-nav">
            <summary class="nav-summary" style={linkStyle(onModule())}>Modules<span class="nav-chevron" aria-hidden="true">▾</span></summary>
            <div class="nav-panel">
              <For each={NAV_MODULES}>
                {([s, label]: [string, string]) => (
                  <a href={`/${s}`} class="ln" onClick={closeMenu} style={`${linkStyle(props.surface === s)} display:block; padding:6px 0; white-space:nowrap;`}>{label}</a>
                )}
              </For>
            </div>
          </details>
          <a href="/papers" class="ln" style={linkStyle(props.surface === "papers")}>Papers</a>
          <a href="/sources" class="ln" style={linkStyle(props.surface === "sources")}>Sources</a>
        </div>

        <div style="display:flex; align-items:center; gap:18px;">
          <a href={REPO} target="_blank" rel="noopener" aria-label="Source on GitHub" style="display:inline-flex; color:var(--granite);"><GitHubIcon /></a>
          <a href="https://www.linkedin.com/in/noah-hyden/" target="_blank" rel="noopener" aria-label="LinkedIn" style="display:inline-flex; color:var(--granite);"><LinkedInIcon /></a>
        </div>
      </div>
    </nav>
  );
}

const HEAD = "font-family:var(--mono); font-size:var(--fs-tiny); letter-spacing:var(--track-label); text-transform:uppercase; color:var(--granite); margin-bottom:14px;";
const LIST = "list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:10px;";
const ITEM = "font-family:var(--sans); font-size:14px; color:var(--ink);";

export function Footer(): Child {
  return (
    <footer style="position:relative; overflow:hidden; background:var(--surface); margin-top:40px;">
      <AzulejoBand height={120} opacity={0.15} pattern="quatrefoil" />

      <div style="position:relative; max-width:var(--wrap); margin:0 auto; padding:40px; display:flex; flex-wrap:wrap; justify-content:space-between; gap:32px 40px;">
        <div style="flex:1 1 280px; min-width:0;">
          <div style="display:flex; align-items:center; gap:12px; font-family:var(--serif); font-weight:600; font-size:21px; letter-spacing:-.01em; margin-bottom:10px;">
            <Mark size={38} />
            <span>The Arithmetic of Self-Replication<span style="color:var(--falu);">.</span></span>
          </div>
          <p style="font-family:var(--sans); font-size:14px; line-height:1.55; color:var(--granite); margin:0; max-width:42ch;">
            Source-checked models of self-replicating space manufacturing. Every number traces to published research.
          </p>
        </div>

        <div style="display:flex; gap:40px; flex-wrap:wrap;">
          <div>
            <div style={HEAD}>Surfaces</div>
            <ul style={LIST}>
              <li><a href="/" class="ln" style={ITEM}>Overview</a></li>
              <li><a href="/mission" class="ln" style={ITEM}>Full mission</a></li>
              <li><a href="/papers" class="ln" style={ITEM}>Papers</a></li>
              <li><a href="/sources" class="ln" style={ITEM}>Sources</a></li>
            </ul>
          </div>
          <div>
            <div style={HEAD}>Elsewhere</div>
            <ul style={LIST}>
              <li><a href={REPO} target="_blank" rel="noopener" class="ln" style={ITEM}>GitHub</a></li>
              <li><a href={SITE} class="ln" style={ITEM}>noahhyden.com</a></li>
            </ul>
          </div>
        </div>
      </div>

      <div style="position:relative; background:var(--footer-tint);">
        <div style="max-width:var(--wrap); margin:0 auto; padding:22px 40px; font-family:var(--mono); font-size:var(--fs-tiny); line-height:1.7; color:var(--granite);">
          &copy; 2026 Noah Hyden
        </div>
      </div>
    </footer>
  );
}
