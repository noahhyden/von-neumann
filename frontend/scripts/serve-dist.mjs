/**
 * Serve the built dist/ over HTTP for local preview (issue #23: verify a change
 * renders before merging to main). The page is an ES-module SPA - index.html loads
 * <script type="module" src="./app.js">, which browsers refuse to load over file://
 * (module CORS on an opaque origin), so a bare double-click of dist/index.html shows
 * a blank page. This serves the folder over http://localhost instead.
 *
 * Static-only: esbuild's dev server (already our one build dependency) serves a
 * directory with no entry points and no rebuild - it just hosts the exact bytes
 * `npm run build` produced, so what you see is what pages.yml deploys. Run after a
 * build (or use `npm run preview`, which builds then serves).
 */
import { context } from "esbuild";
import { join } from "node:path";

const DIST = join(import.meta.dirname, "..", "dist");

const ctx = await context({});
// No port given: esbuild picks an open one (starting at 8000) and returns it.
const { host, port } = await ctx.serve({ servedir: DIST });
const shown = host === "0.0.0.0" || host === "::" ? "localhost" : host;
console.log(`Serving dist/ at http://${shown}:${port}  (Ctrl-C to stop)`);
