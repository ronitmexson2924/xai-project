"""The performance model: a small neural network (multilayer perceptron) predicting P(correct).

Trained with scikit-learn (`app.ml.train`), then stored as plain weights in JSON and run here in
numpy. That keeps it inspectable (LRP needs the weights), fast, and independent of library
versions: nothing is unpickled at start-up.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.features import FEATURE_NAMES

ARTIFACT = Path(__file__).parent / "artifacts" / "performance_model.json"


@dataclass(frozen=True)
class PerformanceModel:
    mean: np.ndarray  # input standardisation (fitted on the training data)
    scale: np.ndarray
    weights: list[np.ndarray]  # one (n_in, n_out) matrix per layer; ReLU between, sigmoid at end
    biases: list[np.ndarray]
    background: np.ndarray  # a sample of training inputs: the reference for SHAP, LIME and DiCE
    card: dict[str, Any] = field(default_factory=dict)  # metrics and provenance (model card)

    def __post_init__(self) -> None:
        if len(self.mean) != len(FEATURE_NAMES):
            raise ValueError("the model was trained on a different feature set; retrain it")

    # --- inference -------------------------------------------------------------------------

    def standardise(self, x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, dtype=float) - self.mean) / self.scale

    def activations(self, x: np.ndarray) -> list[np.ndarray]:
        """Inputs of every layer and the final logit: [z0 (standardised x), a1, ..., logit]."""
        a = self.standardise(np.atleast_2d(x))
        out = [a]
        for i, (w, b) in enumerate(zip(self.weights, self.biases, strict=True)):
            a = a @ w + b
            if i < len(self.weights) - 1:
                a = np.maximum(a, 0.0)
            out.append(a)
        return out

    def logit(self, x: np.ndarray) -> np.ndarray:
        return self.activations(x)[-1][:, 0]

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """P(correct) for each row of x."""
        return 1.0 / (1.0 + np.exp(-self.logit(x)))

    def grad_logit(self, x: np.ndarray) -> np.ndarray:
        """d logit / d x (raw feature units) for one input: used by the counterfactual search."""
        acts = self.activations(x)
        grad = np.ones((1, 1))
        for i in range(len(self.weights) - 1, -1, -1):
            grad = grad @ self.weights[i].T
            if i > 0:
                grad = grad * (acts[i] > 0)
        return (grad / self.scale)[0]

    # --- storage ---------------------------------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        return {
            "features": list(FEATURE_NAMES),
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "weights": [w.tolist() for w in self.weights],
            "biases": [b.tolist() for b in self.biases],
            "background": self.background.round(6).tolist(),
            "card": self.card,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PerformanceModel":
        if tuple(data["features"]) != FEATURE_NAMES:
            raise ValueError("the model was trained on a different feature set; retrain it")
        return cls(
            mean=np.array(data["mean"]),
            scale=np.array(data["scale"]),
            weights=[np.array(w) for w in data["weights"]],
            biases=[np.array(b) for b in data["biases"]],
            background=np.array(data["background"]),
            card=data.get("card", {}),
        )

    def save(self, path: Path = ARTIFACT) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1) + "\n")


@lru_cache(maxsize=1)
def load(path: Path = ARTIFACT) -> PerformanceModel:
    return PerformanceModel.from_json(json.loads(path.read_text()))
