"""PyTorch LSTM baseline for univariate daily demand (train-on-the-fly for MVP)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


@dataclass(frozen=True)
class LSTMForecastOutput:
    predictions: list[dict]
    metrics: dict


class _LSTMRegressor(nn.Module):
    def __init__(self, input_size: int = 1, hidden_size: int = 32, num_layers: int = 1) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class LSTMForecastModel:
    """
    Sliding-window LSTM trained on the available daily history.
    Produces positive demand forecasts; falls back if history is too short.
    """

    def __init__(
        self,
        window_size: int = 14,
        epochs: int = 40,
        batch_size: int = 8,
        lr: float = 1e-2,
    ) -> None:
        self.window_size = window_size
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr

    def fit_predict(
        self,
        daily_series: pd.DataFrame,
        horizon_days: int,
    ) -> LSTMForecastOutput:
        if daily_series.empty:
            raise ValueError("daily_series is empty; cannot fit LSTM model.")
        if horizon_days < 1:
            raise ValueError("horizon_days must be >= 1.")

        df = daily_series.copy()
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").drop_duplicates(subset=["ds"], keep="last")
        y = df["y"].astype(float).values

        # Minimum history: need window + a few points
        min_len = self.window_size + 5
        if len(y) < min_len:
            # Fallback: repeat last smoothed level
            level = float(np.mean(y[-max(1, len(y) // 3) :]))
            preds = self._flat_forecast(df["ds"].iloc[-1], horizon_days, level)
            return LSTMForecastOutput(
                predictions=preds,
                metrics={
                    "model": "lstm_fallback_constant",
                    "reason": "insufficient_history",
                    "training_points": int(len(y)),
                    "required_points": min_len,
                },
            )

        series = y.reshape(-1, 1)
        mean = series.mean(axis=0, keepdims=True)
        std = series.std(axis=0, keepdims=True) + 1e-6
        norm = (series - mean) / std

        X_list: list[np.ndarray] = []
        Y_list: list[np.ndarray] = []
        for i in range(self.window_size, len(norm)):
            X_list.append(norm[i - self.window_size : i])
            Y_list.append(norm[i])
        X_arr = np.stack(X_list, axis=0).astype(np.float32)
        Y_arr = np.stack(Y_list, axis=0).astype(np.float32)

        device = torch.device("cpu")
        model = _LSTMRegressor().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        tensor_x = torch.from_numpy(X_arr).to(device)
        tensor_y = torch.from_numpy(Y_arr).to(device)
        dataset = TensorDataset(tensor_x, tensor_y)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        model.train()
        for _ in range(self.epochs):
            for xb, yb in loader:
                optimizer.zero_grad()
                pred = model(xb)
                loss = loss_fn(pred.squeeze(-1), yb)
                loss.backward()
                optimizer.step()

        # Recursive multi-step forecast in normalized space
        model.eval()
        last_window = norm[-self.window_size :].copy()
        forecasts_norm: list[float] = []
        with torch.no_grad():
            for _ in range(horizon_days):
                inp = torch.from_numpy(last_window.reshape(1, self.window_size, 1).astype(np.float32)).to(
                    device
                )
                nxt = model(inp).item()
                forecasts_norm.append(nxt)
                last_window = np.vstack([last_window[1:], [[nxt]]])

        denorm = np.array(forecasts_norm).reshape(-1, 1) * std + mean
        denorm = np.maximum(denorm, 0.0)

        last_date = df["ds"].max()
        preds: list[dict] = []
        for i in range(horizon_days):
            day = (last_date + pd.Timedelta(days=i + 1)).date().isoformat()
            val = float(denorm[i, 0])
            preds.append(
                {
                    "ds": day,
                    "yhat": val,
                    "yhat_lower": max(0.0, val * 0.85),
                    "yhat_upper": val * 1.15,
                }
            )

        metrics = {
            "training_points": int(len(y)),
            "horizon_days": horizon_days,
            "model": "lstm",
            "window_size": self.window_size,
        }
        return LSTMForecastOutput(predictions=preds, metrics=metrics)

    @staticmethod
    def _flat_forecast(last_ds: pd.Timestamp, horizon_days: int, level: float) -> list[dict]:
        preds: list[dict] = []
        for i in range(horizon_days):
            day = (last_ds + pd.Timedelta(days=i + 1)).date().isoformat()
            preds.append(
                {
                    "ds": day,
                    "yhat": level,
                    "yhat_lower": max(0.0, level * 0.9),
                    "yhat_upper": level * 1.1,
                }
            )
        return preds
