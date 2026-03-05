"""Retrain ML models with latest data.

Usage:
    python scripts/retrain_model.py
    python scripts/retrain_model.py --label-type breakout
    python scripts/retrain_model.py --start-date 2022-01-01 --end-date 2025-12-31

Performs walk-forward training, evaluates model performance,
and saves versioned model artifacts to disk. Intended for weekly cron.
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session
from app.ml.train import ModelTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main(
    start_date: date | None = None,
    end_date: date | None = None,
    label_type: str = "breakout",
) -> None:
    """Run the full training pipeline."""
    async with async_session() as session:
        trainer = ModelTrainer(session)

        logger.info("=" * 60)
        logger.info("Starting model retraining")
        logger.info("Label type: %s", label_type)
        logger.info("Date range: %s to %s", start_date or "auto", end_date or "auto")
        logger.info("=" * 60)

        try:
            result = await trainer.full_training_run(
                start_date=start_date,
                end_date=end_date,
                label_type=label_type,
            )
            logger.info("=" * 60)
            logger.info("Training completed successfully!")
            logger.info("Version: %s", result["version"])
            logger.info("Model path: %s", result["model_path"])
            logger.info("Folds: %d", result["num_folds"])
            logger.info("Features: %d", result["feature_count"])
            logger.info("Samples: %d", result["sample_count"])
            logger.info("Average metrics:")
            for k, v in result["avg_metrics"].items():
                logger.info("  %s: %.4f", k, v)
            logger.info("=" * 60)
        except Exception:
            logger.exception("Training failed")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain ML models")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--label-type",
        choices=["breakout", "max_gain", "risk_reward", "call_pnl"],
        default="breakout",
    )
    args = parser.parse_args()
    asyncio.run(main(args.start_date, args.end_date, args.label_type))
