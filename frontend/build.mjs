/**
 * Build: bundle the client app (src/main.tsx) into dist/app.js with pimas bundled
 * in, and copy index.html beside it. One interactive page, one bundle - the
 * smallest honest pipeline. Reports the gzipped JS the page ships.
 */
import { build as esbuild } from "esbuild";
import { gzipSync } from "node:zlib";
import { mkdir, writeFile, rm, readFile, cp, readdir } from "node:fs/promises";
import { join } from "node:path";

const ROOT = import.meta.dirname;
const OUT = join(ROOT, "dist");

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
  minify: true,
  legalComments: "none",
  metafile: true,
});

await cp(join(ROOT, "index.html"), join(OUT, "index.html"));

// Report shipped size.
const js = await readFile(join(OUT, "app.js"));
const gz = gzipSync(js).length;
console.log(`dist/app.js  ${(js.length / 1024).toFixed(1)} KB raw  ·  ${(gz / 1024).toFixed(1)} KB gz`);
const files = await readdir(OUT);
console.log(`dist/: ${files.join(", ")}`);
