"""Per-client detectors. Each module exposes DETECTOR_ID and detect(features: dict, ctx: dict) -> list[Signal]."""
import importlib

MODULES = ["d1_flow_through", "d2_day_zero", "d3_profile_gap", "d4_fan_in", "d5_rare_exit", "d7_fixed_skim", "d8_structuring"]


def __getattr__(name: str):
    if name == "ALL_DETECTORS":
        return [importlib.import_module(f"node.detectors.{m}") for m in MODULES]
    raise AttributeError(name)
