from __future__ import annotations

from typing import Iterable


Point = tuple[float, float]
Path = list[Point]


def generate_gcode(
    paths_mm: Iterable[Path],
    feed_rate: int = 2500,
    pen_up_cmd: str = "M5",
    pen_down_cmd: str = "M3 S1000",
) -> str:
    lines: list[str] = []
    lines.append("; Image -> SVG -> G-code")
    lines.append("G21")
    lines.append("G90")
    lines.append(pen_up_cmd)

    for path in paths_mm:
        if len(path) < 2:
            continue

        x0, y0 = path[0]
        lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")
        lines.append(pen_down_cmd)

        for x, y in path[1:]:
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}")

        lines.append(pen_up_cmd)

    lines.append("G0 X0.000 Y0.000")
    lines.append(pen_up_cmd)
    return "\n".join(lines)
