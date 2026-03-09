"""
Model Registry.

Manages model versions with:
  - Load-on-demand from disk
  - Thread-safe hot-swap (swap the active model without restarting)
  - Version tracking (metadata written alongside each model)
  - Automatic rollback if new model fails validation
  - Background file-watcher to auto-reload when a new model is deployed

Usage:
    registry = ModelRegistry()
    classifier = registry.get_active_model()
    proba = classifier.predict(...)

Hot-swap:
    registry.load_version("models/trading_model_v2.joblib")
    # All subsequent calls to get_active_model() use the new model
"""
import os
import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import joblib

from app.utils.logger import get_logger

logger = get_logger("model_registry")

UTC = timezone.utc

DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "app", "core", "ai", "models",
)
DEFAULT_MODEL_FILE = os.path.join(DEFAULT_MODEL_DIR, "trading_model.joblib")
REGISTRY_INDEX_FILE = os.path.join(DEFAULT_MODEL_DIR, "registry.json")


class ModelVersion:
    """Wraps a loaded model artefact with version metadata."""

    def __init__(self, path: str, artifact: dict):
        self.path = path
        self.version = artifact.get("version", "unknown")
        self.model = artifact.get("model")
        self.scaler = artifact.get("scaler")
        self.feature_names = artifact.get("feature_names", [])
        self.training_report = artifact.get("training_report", {})
        self.loaded_at = datetime.now(UTC)

    def predict_proba(self, X) -> float:
        """Return probability of positive class for a single sample (1-D array)."""
        import numpy as np
        X = np.array(X).reshape(1, -1)
        X = np.nan_to_num(X, nan=0.0, posinf=2.0, neginf=-2.0)
        if self.scaler:
            X = self.scaler.transform(X)
        return float(self.model.predict_proba(X)[0][1])

    def get_feature_importance(self) -> dict:
        from app.core.ai.features import FEATURE_NAMES
        _rf = getattr(self.model, "estimator", self.model)
        if hasattr(_rf, "feature_importances_"):
            imp = dict(zip(FEATURE_NAMES, _rf.feature_importances_))
            return dict(sorted(imp.items(), key=lambda x: x[1], reverse=True))
        return {}

    @property
    def metadata(self) -> dict:
        return {
            "version": self.version,
            "path": self.path,
            "loaded_at": self.loaded_at.isoformat(),
            "training_report": self.training_report,
        }


class ModelRegistry:
    """
    Thread-safe model registry with hot-swap support.

    Lifecycle:
    1. On init: loads the latest available model (or None)
    2. On load_version(): atomically swaps the active model
    3. Background watcher: polls model file for changes and auto-reloads
    """

    _instance: Optional["ModelRegistry"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._lock = threading.RLock()
        self._active: Optional[ModelVersion] = None
        self._versions: Dict[str, ModelVersion] = {}
        self._watcher_running = False
        self._watcher_thread: Optional[threading.Thread] = None

        os.makedirs(DEFAULT_MODEL_DIR, exist_ok=True)

        # Try to load the default model
        self._load_initial()

    def get_active_model(self) -> Optional[ModelVersion]:
        """Return the currently active ModelVersion (thread-safe)."""
        with self._lock:
            return self._active

    def load_version(self, path: str, validate: bool = True) -> bool:
        """
        Load a model from `path` and hot-swap it as the active version.

        If validation fails, keeps the previous model active.
        Returns True on success.
        """
        if not os.path.exists(path):
            logger.error(f"Model not found: {path}")
            return False

        try:
            artifact = joblib.load(path)
            new_version = ModelVersion(path, artifact)

            if validate and not self._validate(new_version):
                logger.warning(f"Model validation failed for {path}, keeping previous")
                return False

            with self._lock:
                old = self._active
                self._active = new_version
                self._versions[new_version.version] = new_version

            self._write_index()
            logger.info(
                f"Model hot-swapped: {new_version.version} from {path} "
                f"(prev: {old.version if old else 'none'})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load model from {path}: {e}")
            return False

    def load_latest(self) -> bool:
        """Reload the default model file."""
        return self.load_version(DEFAULT_MODEL_FILE)

    def list_versions(self) -> list:
        """List all loaded versions with metadata."""
        with self._lock:
            return [v.metadata for v in self._versions.values()]

    def rollback(self, version: str) -> bool:
        """Switch back to a previously loaded version."""
        with self._lock:
            if version not in self._versions:
                logger.warning(f"Version {version} not in registry")
                return False
            self._active = self._versions[version]
        logger.info(f"Rolled back to version {version}")
        return True

    def start_watcher(self, poll_interval: float = 30.0):
        """
        Start background thread that polls for model file changes.
        Auto-reloads when mtime changes.
        """
        if self._watcher_running:
            return
        self._watcher_running = True
        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            args=(poll_interval,),
            daemon=True,
            name="ModelRegistryWatcher",
        )
        self._watcher_thread.start()
        logger.info(f"Model watcher started (poll={poll_interval}s)")

    def stop_watcher(self):
        self._watcher_running = False

    @property
    def active_version(self) -> Optional[str]:
        with self._lock:
            return self._active.version if self._active else None

    # ── Private ────────────────────────────────────────────────────────

    def _load_initial(self):
        if os.path.exists(DEFAULT_MODEL_FILE):
            success = self.load_version(DEFAULT_MODEL_FILE, validate=False)
            if success:
                logger.info(f"Registry: loaded initial model from {DEFAULT_MODEL_FILE}")
            else:
                logger.warning("Registry: initial model load failed")
        else:
            logger.info("Registry: no model file found, registry empty")

    def _validate(self, version: ModelVersion) -> bool:
        """Quick sanity check: can we get a prediction?"""
        try:
            import numpy as np
            from app.core.ai.features import FEATURE_NAMES
            X = np.zeros(len(FEATURE_NAMES))
            proba = version.predict_proba(X)
            return 0.0 <= proba <= 1.0
        except Exception as e:
            logger.warning(f"Model validation error: {e}")
            return False

    def _watch_loop(self, poll_interval: float):
        last_mtime = 0.0
        while self._watcher_running:
            try:
                if os.path.exists(DEFAULT_MODEL_FILE):
                    mtime = os.path.getmtime(DEFAULT_MODEL_FILE)
                    if mtime > last_mtime and last_mtime > 0:
                        logger.info("Model file changed, hot-swapping...")
                        self.load_latest()
                    last_mtime = mtime
            except Exception as e:
                logger.error(f"Watcher error: {e}")
            time.sleep(poll_interval)

    def _write_index(self):
        """Persist registry metadata to disk."""
        try:
            index = {
                "active_version": self.active_version,
                "versions": [v.metadata for v in self._versions.values()],
                "updated_at": datetime.now(UTC).isoformat(),
            }
            with open(REGISTRY_INDEX_FILE, "w") as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write registry index: {e}")
