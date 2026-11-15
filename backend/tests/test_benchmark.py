import importlib.util
from pathlib import Path


def test_benchmark_measurement_script_is_importable():
    script = Path(__file__).resolve().parents[1] / "scripts" / "benchmark.py"
    spec = importlib.util.spec_from_file_location("daar_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.measure)
