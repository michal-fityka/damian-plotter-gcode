from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from svgpathtools import Arc, CubicBezier, Line, QuadraticBezier, svg2paths2

from .schemas import GenerateParams

Point = tuple[float, float]
PathType = list[Point]


class PipelineError(Exception):
    pass


def distance(p1: Point, p2: Point) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def path_length(path: PathType) -> float:
    if len(path) < 2:
        return 0.0
    return sum(distance(path[i - 1], path[i]) for i in range(1, len(path)))


def point_line_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end

    if (x1, y1) == (x2, y2):
        return distance(point, start)

    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    den = math.hypot(y2 - y1, x2 - x1)
    return num / den


def rdp(points: PathType, epsilon: float) -> PathType:
    if len(points) < 3:
        return points

    start = points[0]
    end = points[-1]

    max_dist = 0.0
    index = 0

    for i in range(1, len(points) - 1):
        d = point_line_distance(points[i], start, end)
        if d > max_dist:
            index = i
            max_dist = d

    if max_dist > epsilon:
        left = rdp(points[: index + 1], epsilon)
        right = rdp(points[index:], epsilon)
        return left[:-1] + right

    return [start, end]


def resize_preserve_aspect(image_bgr: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = image_bgr.shape[:2]
    current_max = max(h, w)
    if current_max <= max_dim:
        return image_bgr

    scale = max_dim / current_max
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess_to_binary(image_bgr: np.ndarray, params: GenerateParams) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.medianBlur(gray, 3)

    if params.use_adaptive_threshold:
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV if params.invert else cv2.THRESH_BINARY,
            31,
            10,
        )
    else:
        _, binary = cv2.threshold(
            gray,
            params.threshold,
            255,
            cv2.THRESH_BINARY_INV if params.invert else cv2.THRESH_BINARY,
        )

    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= params.min_component_area:
            cleaned[labels == i] = 255

    return cleaned


def save_binary_as_pbm(binary: np.ndarray, pbm_path: Path) -> None:
    img = Image.fromarray(binary)
    img = img.convert("1")
    img.save(pbm_path)


def run_potrace(pbm_file: Path, svg_file: Path, turdsize: int) -> None:
    if shutil.which("potrace") is None:
        raise PipelineError("Nie znaleziono programu 'potrace'. Zainstaluj go w systemie.")

    cmd = [
        "potrace",
        str(pbm_file),
        "-s",
        "-o",
        str(svg_file),
        "-t",
        str(turdsize),
        "-a",
        "1.0",
        "-O",
        "0.4",
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def sample_segment(seg: Any) -> list[Point]:
    if isinstance(seg, Line):
        n = 2
    elif isinstance(seg, QuadraticBezier):
        n = 8
    elif isinstance(seg, CubicBezier):
        n = 12
    elif isinstance(seg, Arc):
        n = 12
    else:
        n = 10

    points: list[Point] = []
    for t in np.linspace(0, 1, n):
        z = seg.point(t)
        points.append((float(z.real), float(z.imag)))
    return points


def svg_to_polylines(svg_file: Path) -> list[PathType]:
    paths, _, _ = svg2paths2(str(svg_file))
    polylines: list[PathType] = []

    for path in paths:
        pts: PathType = []
        for seg in path:
            seg_pts = sample_segment(seg)
            if pts and seg_pts and distance(pts[-1], seg_pts[0]) < 1e-9:
                pts.extend(seg_pts[1:])
            else:
                pts.extend(seg_pts)

        if len(pts) >= 2:
            polylines.append(pts)

    return polylines


def simplify_and_filter_paths(paths: list[PathType], params: GenerateParams) -> list[PathType]:
    result: list[PathType] = []

    for path in paths:
        simplified = rdp(path, params.rdp_epsilon_px) if params.rdp_epsilon_px > 0 else path
        if len(simplified) < 2:
            continue
        if path_length(simplified) < params.min_path_length_px:
            continue
        result.append(simplified)

    return result


def sort_paths_nearest(paths: list[PathType]) -> list[PathType]:
    if not paths:
        return []

    remaining = [p[:] for p in paths]
    result: list[PathType] = []
    current = remaining.pop(0)
    result.append(current)
    current_pos = current[-1]

    while remaining:
        best_idx = None
        best_reverse = False
        best_dist = float("inf")

        for i, path in enumerate(remaining):
            d_start = distance(current_pos, path[0])
            d_end = distance(current_pos, path[-1])

            if d_start < best_dist:
                best_idx = i
                best_reverse = False
                best_dist = d_start
            if d_end < best_dist:
                best_idx = i
                best_reverse = True
                best_dist = d_end

        chosen = remaining.pop(best_idx)
        if best_reverse:
            chosen = list(reversed(chosen))
        result.append(chosen)
        current_pos = chosen[-1]

    return result


def scale_paths_to_mm(
    paths_px: list[PathType],
    width_px: int,
    height_px: int,
    output_width_mm: float,
    flip_y: bool,
) -> tuple[list[PathType], float]:
    scale = output_width_mm / width_px
    output_height_mm = height_px * scale

    paths_mm: list[PathType] = []
    for path in paths_px:
        scaled: PathType = []
        for x, y in path:
            x_mm = x * scale
            y_mm = y * scale
            if flip_y:
                y_mm = output_height_mm - y_mm
            scaled.append((x_mm, y_mm))
        paths_mm.append(scaled)

    return paths_mm, output_height_mm


def process_image_to_paths(image_bytes: bytes, params: GenerateParams) -> tuple[list[PathType], dict[str, float]]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        input_file = tmp / "input.png"
        pbm_file = tmp / "input.pbm"
        svg_file = tmp / "vectorized.svg"

        input_file.write_bytes(image_bytes)

        image_bgr = cv2.imread(str(input_file))
        if image_bgr is None:
            raise PipelineError("Nie udało się odczytać obrazu.")

        image_bgr = resize_preserve_aspect(image_bgr, params.max_dimension)
        binary = preprocess_to_binary(image_bgr, params)
        save_binary_as_pbm(binary, pbm_file)
        run_potrace(pbm_file, svg_file, params.potrace_turdsize)

        raw_paths = svg_to_polylines(svg_file)
        filtered_paths = simplify_and_filter_paths(raw_paths, params)
        sorted_paths = sort_paths_nearest(filtered_paths)

        height_px, width_px = binary.shape
        paths_mm, output_height_mm = scale_paths_to_mm(
            sorted_paths,
            width_px=width_px,
            height_px=height_px,
            output_width_mm=params.output_width_mm,
            flip_y=params.flip_y,
        )

        meta = {
            "width_px": float(width_px),
            "height_px": float(height_px),
            "output_width_mm": params.output_width_mm,
            "output_height_mm": output_height_mm,
            "path_count": float(len(paths_mm)),
        }
        return paths_mm, meta
