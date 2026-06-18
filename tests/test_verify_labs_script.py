from pathlib import Path


def test_verify_labs_script_documents_required_validation_steps() -> None:
    script_path = Path("scripts/verify_labs.ps1")

    assert script_path.exists()

    script = script_path.read_text(encoding="utf-8")

    required_fragments = [
        "$ErrorActionPreference = \"Stop\"",
        "PYTHONIOENCODING",
        "-B",
        "-m pytest",
        "labs\\fintech-platform",
        "labs\\fintech-platform\\demo.py",
        ".\\labs",
    ]

    for fragment in required_fragments:
        assert fragment in script
