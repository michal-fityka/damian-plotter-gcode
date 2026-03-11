from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .gcode import generate_gcode
from .image_pipeline import PipelineError, process_image_to_paths
from .schemas import GenerateParams

app = FastAPI(title="Plotter G-code API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate")
async def generate(
    file: UploadFile = File(...),
    output_width_mm: float = Form(180.0),
    feed_rate: int = Form(2500),
    threshold: int = Form(170),
    use_adaptive_threshold: bool = Form(False),
    invert: bool = Form(True),
    max_dimension: int = Form(1200),
    min_component_area: int = Form(30),
    potrace_turdsize: int = Form(4),
    rdp_epsilon_px: float = Form(1.5),
    min_path_length_px: float = Form(15.0),
    flip_y: bool = Form(True),
    pen_up_cmd: str = Form("M5"),
    pen_down_cmd: str = Form("M3 S1000"),
):
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Pusty plik.")

        params = GenerateParams(
            output_width_mm=output_width_mm,
            feed_rate=feed_rate,
            threshold=threshold,
            use_adaptive_threshold=use_adaptive_threshold,
            invert=invert,
            max_dimension=max_dimension,
            min_component_area=min_component_area,
            potrace_turdsize=potrace_turdsize,
            rdp_epsilon_px=rdp_epsilon_px,
            min_path_length_px=min_path_length_px,
            flip_y=flip_y,
            pen_up_cmd=pen_up_cmd,
            pen_down_cmd=pen_down_cmd,
        )

        paths_mm, meta = process_image_to_paths(image_bytes, params)
        gcode = generate_gcode(
            paths_mm,
            feed_rate=params.feed_rate,
            pen_up_cmd=params.pen_up_cmd,
            pen_down_cmd=params.pen_down_cmd,
        )

        out_dir = Path("generated")
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / "output.gcode"
        out_file.write_text(gcode, encoding="utf-8")

        return FileResponse(
            path=out_file,
            media_type="text/plain",
            filename="output.gcode",
            headers={"X-Plotter-Meta": json.dumps(meta)},
        )
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd generowania G-code: {e}") from e


@app.get("/config")
def config() -> JSONResponse:
    return JSONResponse({"defaults": GenerateParams().model_dump()})
