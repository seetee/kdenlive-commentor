# Roadmap

## Simplification pass (ponytail-review of `ad328aa~1..1549135`)

Line numbers are against `kdenlive_commentor.py` at 1549135. Run `python3 -m unittest`
after each item — idempotency and non-destructiveness are the contract.

- [ ] **L61-69** — drop `_version()`; `--version` can use `f'%(prog)s {__version__}'`.
      Kills the importlib lookup and the duplicated `1.0.0` (or make pyproject's
      version dynamic from `__version__`). *-8*
- [ ] **L455-481** — `_prune_chapter_section` and `_prune_orphan_section` are the same
      loop with a different "is managed" test. One `_prune_section(episode, title,
      is_managed)`. *-10*
- [ ] **L792-796, L805-807** — `--new` and the `new` positional are two spellings of one
      command; the `Path('new').is_dir()` guard exists only to disambiguate them.
      Keep `new`, delete the flag and the guard. *-8*
- [ ] **L415-423** — `_chapter_names`: `list(dict.fromkeys(dict(TALLY_NAMES)[i.upper()]
      for i, _ in _TALLY_TOKEN_RE.findall(text)))`. *-6*
- [ ] **L556-560** — chapter count via `next((genexp), 0)` → one `sum(...)`. *-4*
- [ ] **L106-108** — inline `_strip_attribution` into its single caller at L158. *-4*
- [ ] **L546-550** — Titel-length check re-walks lines L541 already walked; fold into a
      `next(...)`. *-3*
- [ ] **L384, L417** — `{k: v for k, v in TALLY_NAMES}` → `dict(TALLY_NAMES)`.
- [ ] **.github/workflows/test.yml L11** — drop `"3.13"`; 3.10 and 3.14 bracket a
      stdlib-only script.

Net: **-45 lines** (-31 if `--show` stays).

### Deferred / judgement call

- [ ] **L522-531, L797-800** — `--show` reprints a section of a Markdown file the user
      already has open. Cut only if it goes unused in practice. *-14*
