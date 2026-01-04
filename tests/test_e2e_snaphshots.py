import pytest
from pathlib import Path
from movfuscator import movfuscate

SAMPLES_DIR = Path(__file__).parent / "e2e" / "samples"

SAMPLE_FILES = sorted(list(SAMPLES_DIR.glob("*.s")))


def id_function(val):
    """Helper to generate clean test IDs based on filenames."""
    if isinstance(val, Path):
        return val.name
    return str(val)


@pytest.mark.parametrize("sample_path", SAMPLE_FILES, ids=id_function)
def test_e2e_transformation_snapshot(snapshot, sample_path):
    """
    End-to-End Snapshot Test:
    1. Reads a sample assembly file (.s).
    2. Runs it through the movfuscator pipeline.
    3. Verifies the generated assembly text matches the stored snapshot.
    """
    if not sample_path.exists():
        pytest.fail(f"Sample file not found: {sample_path}")

    source_code = sample_path.read_text(encoding="utf-8")

    try:
        linearized_asm = movfuscate(source_code)
    except Exception as e:
        pytest.fail(f"Movfuscation failed for {sample_path.name} with error: {e}")

    assert linearized_asm == snapshot(name=f"{sample_path.stem}_obfuscated")
