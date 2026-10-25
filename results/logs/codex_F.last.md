Implemented Task F and regenerated the report.

Changed:

- [README.md](/Users/ziqiwei/6.974_wargame/README.md)
- [docs/PROGRESS.md](/Users/ziqiwei/6.974_wargame/docs/PROGRESS.md)
- [docs/DESIGN.md](/Users/ziqiwei/6.974_wargame/docs/DESIGN.md)
- [docs/ASSUMPTIONS.md](/Users/ziqiwei/6.974_wargame/docs/ASSUMPTIONS.md)
- [code/scripts/06_make_report.py](/Users/ziqiwei/6.974_wargame/code/scripts/06_make_report.py)
- [docs/workshop1/report.md](/Users/ziqiwei/6.974_wargame/docs/workshop1/report.md)
- [docs/workshop1/report.html](/Users/ziqiwei/6.974_wargame/docs/workshop1/report.html)
- New illustrative-day trajectory: [PNG](/Users/ziqiwei/6.974_wargame/results/figures/fig_design_trajectory_2025-03-10.png) and [PDF](/Users/ziqiwei/6.974_wargame/results/figures/fig_design_trajectory_2025-03-10.pdf)

Verification:

- Report regenerates successfully.
- All eight report sections contain content and local links resolve.
- No `nan`, placeholder text, or superseded report sections remain.
- README legacy grep returns only three explicitly labeled legacy lines.
- `.venv/bin/pytest -q`: 35 passed.
- `git diff --check`: clean.
- No files under `data/` were changed.
- Existing experiment tables and solver code were not modified.

All reported result values come from committed tables or configuration/data tables. The only sourcing limitation is runtime metadata: step 07 records 1,033.9 seconds, but steps 01, 02, and 05 do not record runtime, and step 06 writes no metadata. The README states this rather than supplying unsupported estimates. The F4 mechanism explanation is interpretation from the documented solver design, not a table-derived claim.