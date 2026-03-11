from pydantic import BaseModel


class GenerateParams(BaseModel):
    output_width_mm: float = 180.0
    feed_rate: int = 2500
    threshold: int = 170
    use_adaptive_threshold: bool = False
    invert: bool = True
    max_dimension: int = 1200
    min_component_area: int = 30
    potrace_turdsize: int = 4
    rdp_epsilon_px: float = 1.5
    min_path_length_px: float = 15.0
    flip_y: bool = True
    pen_up_cmd: str = "M5"
    pen_down_cmd: str = "M3 S1000"
