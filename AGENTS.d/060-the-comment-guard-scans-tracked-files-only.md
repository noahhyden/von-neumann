## The comment guard scans TRACKED files only

`make lint-rules` reads `git ls-files`, so a clean run over a tree whose new file is still untracked proves nothing about the file you just wrote - `git add` first, or pass the paths as arguments.
