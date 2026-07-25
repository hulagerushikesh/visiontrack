"""Motion models for prediction: the from-scratch learned residual (RQ2)."""
from .residual import WINDOW, MLPResidual, MotionResidual, residual_features

__all__ = ["WINDOW", "MLPResidual", "MotionResidual", "residual_features"]
