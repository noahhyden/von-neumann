## Three shapes a comment sweep must not touch

A one-line-comment sweep must not touch `//` inside regex literals, column-aligned trailing comments on code lines, or pragma runs like `noqa` / `type: ignore` / `eslint-disable`; grep `PRAGMAS` in `check_one_line_comments.py` for the full exempt list.
