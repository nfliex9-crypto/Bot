"""
AI Training API Routes.

POST /training/train          – trigger model training
GET  /training/status         – training status + last report
GET  /training/evaluate       – evaluate current model
POST /training/reload         – hot-swap to latest model
GET  /training/registry       – list model versions
POST /training/rollback/{ver} – rollback to a specific version
"""
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.training.dataset_builder import DatasetBuilder
from app.training.trainer import ModelTrainer
from app.training.evaluator import ModelEvaluator
from app.core.ai.model_registry import ModelRegistry
from app.utils.logging_config import get_structured_logger

logger = get_structured_logger("training_api")
router = APIRouter(prefix="/training", tags=["AI Training"])

_last_report: dict = {}
_training_lock = asyncio.Lock()


class TrainRequest(BaseModel):
    days_history: int = Field(180, ge=7, le=730)
    synthetic_samples: int = Field(1000, ge=0, le=10000)
    n_estimators: int = Field(300, ge=50, le=2000)
    max_depth: int = Field(12, ge=3, le=50)
    calibrate: bool = True
    save: bool = True


@router.post("/train")
async def trigger_training(req: TrainRequest, background_tasks: BackgroundTasks):
    """
    Trigger model training in the background.
    Uses DB trades (if available) + synthetic augmentation.
    """
    if _training_lock.locked():
        raise HTTPException(status_code=409, detail="Training already in progress")

    background_tasks.add_task(_train_task, req)
    return {"message": "Training started", "config": req.model_dump()}


async def _train_task(req: TrainRequest):
    global _last_report
    async with _training_lock:
        try:
            logger.info(f"Training started: {req.model_dump()}", extra={"ai_log": True})
            trainer = ModelTrainer(
                n_estimators=req.n_estimators,
                max_depth=req.max_depth,
                calibrate=req.calibrate,
            )
            report = await trainer.train_from_db(
                days=req.days_history,
                synthetic_boost=req.synthetic_samples,
                save=req.save,
            )
            _last_report = {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "report": report,
            }

            # Auto-reload into registry
            if req.save:
                registry = ModelRegistry()
                registry.load_latest()
                logger.info(
                    f"Model trained & loaded: AUC={report.get('cv_auc_mean')}",
                    extra={"ai_log": True}
                )

        except Exception as e:
            _last_report = {
                "status": "error",
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat(),
            }
            logger.error(f"Training failed: {e}", exc_info=True)


@router.get("/status")
async def training_status():
    """Return last training run result."""
    registry = ModelRegistry()
    return {
        "last_training": _last_report,
        "active_model_version": registry.active_version,
        "loaded_versions": len(registry.list_versions()),
    }


@router.get("/evaluate")
async def evaluate_model(
    synthetic_samples: int = 500,
):
    """Evaluate the active model on a synthetic held-out dataset."""
    registry = ModelRegistry()
    version = registry.get_active_model()

    if version is None:
        raise HTTPException(status_code=404, detail="No active model loaded")

    builder = DatasetBuilder()
    features_list, labels = builder.generate_synthetic(synthetic_samples, seed=999)

    evaluator = ModelEvaluator(model_path=version.path)
    report = evaluator.evaluate(features_list, labels)
    return report


@router.post("/reload")
async def reload_model():
    """Hot-swap to the latest saved model without restarting."""
    registry = ModelRegistry()
    ok = registry.load_latest()
    if not ok:
        raise HTTPException(status_code=404, detail="No model file found to reload")
    return {
        "message": "Model reloaded",
        "version": registry.active_version,
        "loaded_at": datetime.utcnow().isoformat(),
    }


@router.get("/registry")
async def list_registry():
    """List all tracked model versions."""
    registry = ModelRegistry()
    return {
        "active_version": registry.active_version,
        "versions": registry.list_versions(),
    }


@router.post("/rollback/{version}")
async def rollback_model(version: str):
    """Roll back to a previously loaded model version."""
    registry = ModelRegistry()
    ok = registry.rollback(version)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Version '{version}' not found")
    return {"message": f"Rolled back to {version}", "active_version": registry.active_version}
