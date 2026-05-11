from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from src.config import load_settings
from src.pipeline import run_daily_pipeline


def _write_error_report(base_dir: Path, err: str) -> None:
    report_dir = base_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    (report_dir / f"error-{ts}.log").write_text(err, encoding="utf-8")


def main() -> None:
    settings = load_settings()
    try:
        result = run_daily_pipeline(settings)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        detail = f"{exc}\n\n{traceback.format_exc()}"
        _write_error_report(settings.output_dir, detail)
        raise


if __name__ == "__main__":
    main()
