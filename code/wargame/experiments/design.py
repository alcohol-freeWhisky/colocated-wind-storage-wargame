"""Canonical cells and parser for the design matrix."""

from __future__ import annotations

from typing import Literal, TypedDict


class CellFactors(TypedDict):
    """Normalized factor levels for one design-matrix cell."""

    control: Literal["C", "D"]
    foresight: Literal["P", "F"]
    share: Literal["INJ", "EQ"] | None
    info: Literal["FULL", "PRICE", "NONE"] | None


CELL_ORDER = [
    "C_P",
    "C_F",
    *[
        f"D_{foresight}_{share}_{info}"
        for foresight in ("P", "F")
        for share in ("INJ", "EQ")
        for info in ("FULL", "PRICE", "NONE")
    ],
]


def parse_cell(cell_id: str) -> CellFactors:
    """Parse and validate a canonical design-matrix cell identifier."""

    parts = str(cell_id).upper().split("_")
    if len(parts) == 2 and parts[0] == "C" and parts[1] in {"P", "F"}:
        parsed: CellFactors = {
            "control": "C",
            "foresight": parts[1],  # type: ignore[typeddict-item]
            "share": None,
            "info": None,
        }
    elif (
        len(parts) == 4
        and parts[0] == "D"
        and parts[1] in {"P", "F"}
        and parts[2] in {"INJ", "EQ"}
        and parts[3] in {"FULL", "PRICE", "NONE"}
    ):
        parsed = {
            "control": "D",
            "foresight": parts[1],  # type: ignore[typeddict-item]
            "share": parts[2],  # type: ignore[typeddict-item]
            "info": parts[3],  # type: ignore[typeddict-item]
        }
    else:
        raise ValueError(f"Unknown design-matrix cell: {cell_id!r}")
    canonical = (
        f"{parsed['control']}_{parsed['foresight']}"
        if parsed["control"] == "C"
        else "_".join(
            [
                parsed["control"],
                parsed["foresight"],
                str(parsed["share"]),
                str(parsed["info"]),
            ]
        )
    )
    if canonical not in CELL_ORDER:
        raise ValueError(f"Unknown design-matrix cell: {cell_id!r}")
    return parsed
