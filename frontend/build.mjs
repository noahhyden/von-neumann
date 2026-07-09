/**
 * Build: bundle the client app (src/main.tsx) into dist/app.js with pimas bundled
 * in, and copy index.html beside it. One interactive page, one bundle - the
 * smallest honest pipeline. Reports the gzipped JS the page ships.
 */
import { build as esbuild } from "esbuild";
import { gzipSync } from "node:zlib";
import { mkdir, writeFile, rm, readFile, cp, readdir } from "node:fs/promises";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

const ROOT = import.meta.dirname;
const OUT = join(ROOT, "dist");

// The papers surface imports src/papers-versions.ts, a git-derived, gitignored
// module (a version = every commit touching papers/<slug>/, see gen-versions.mjs).
// It cannot be committed - its newest entry names the current commit's own SHA - so
// it is generated here at build time, exactly as refs.bib is generated before the
// paper is typeset. It always writes a valid module (empty when git history is
// unavailable), so a shallow clone or a source tarball still builds.
execFileSync("node", [join(ROOT, "..", "papers", "scripts", "gen-versions.mjs")], { stdio: "inherit" });

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });

const result = await esbuild({
  entryPoints: [join(ROOT, "src/main.tsx")],
  bundle: true,
  format: "esm",
  target: "es2022",
  jsx: "automatic",
  jsxImportSource: "pimas",
  outfile: join(OUT, "app.js"),
  // A legal banner (/*! ... */) is preserved through minification: the bundle embeds
  // pimas (MIT), so the distributed artifact carries its notice. See THIRD_PARTY_NOTICES.
  banner: { js: "/*! The Arithmetic of Self-Replication - (c) 2026 Noah Hydén. Code: PolyForm Strict 1.0.0. Bundles pimas (MIT, (c) 2026 Noah Hydén). See THIRD_PARTY_NOTICES. */" },
  minify: true,
  legalComments: "none",
  metafile: true,
});

await cp(join(ROOT, "index.html"), join(OUT, "index.html"));
// Static assets referenced by index.html (the social-card image for link unfurls).
await cp(join(ROOT, "og.svg"), join(OUT, "og.svg"));
// GitHub Pages custom domain: the CNAME must live in the published artifact.
await cp(join(ROOT, "CNAME"), join(OUT, "CNAME"));

// Report shipped size.
const js = await readFile(join(OUT, "app.js"));
const gz = gzipSync(js).length;
console.log(`dist/app.js  ${(js.length / 1024).toFixed(1)} KB raw  ·  ${(gz / 1024).toFixed(1)} KB gz`);
const files = await readdir(OUT);
console.log(`dist/: ${files.join(", ")}`);
