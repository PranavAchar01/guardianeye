"""Dense-crowd counting via CSRNet density maps.

Per-person detection dies when a fan is 5 px tall. CSRNet (VGG16 frontend +
dilated backend, trained on ShanghaiTech) predicts a density map whose sum is
the person count — the standard tool for packed stands. Its per-cell sums
replace detection counts in the density grid, while YOLO still tracks the
individuals it can resolve.
"""

from __future__ import annotations

import numpy as np

# ImageNet statistics used by the standard CSRNet training pipeline.
_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)

# The common CSRNet training recipe bilinearly downsamples ground-truth
# density maps to the network's stride-8 output without renormalizing mass,
# so the model learns count/64 per pixel. Verified empirically on countable
# footage crops (raw sum 2.2 vs ~140 visible people).
MASS_SCALE = 64.0


def _build_csrnet():
    import torch.nn as nn

    def make_layers(cfg, in_channels, dilation=1):
        layers: list[nn.Module] = []
        for v in cfg:
            if v == "M":
                layers.append(nn.MaxPool2d(kernel_size=2, stride=2))
            else:
                layers.append(
                    nn.Conv2d(in_channels, v, kernel_size=3, padding=dilation, dilation=dilation)
                )
                layers.append(nn.ReLU(inplace=True))
                in_channels = v
        return nn.Sequential(*layers), in_channels

    class CSRNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.frontend, ch = make_layers(
                [64, 64, "M", 128, 128, "M", 256, 256, 256, "M", 512, 512, 512], 3
            )
            self.backend, ch = make_layers([512, 512, 512, 256, 128, 64], ch, dilation=2)
            self.output_layer = nn.Conv2d(ch, 1, kernel_size=1)

        def forward(self, x):
            return self.output_layer(self.backend(self.frontend(x)))

    return CSRNet()


class CrowdCounter:
    """CSRNet wrapper: BGR frame in, per-pixel people-density map out."""

    def __init__(self, weights_path: str, device: str = "cpu"):
        import torch

        self.device = device
        self.model = _build_csrnet()
        with torch.serialization.safe_globals(
            [np._core.multiarray.scalar, np.dtype, np.dtypes.Float64DType]
        ):
            ck = torch.load(weights_path, map_location="cpu", weights_only=True)
        state = ck.get("model_state_dict", ck.get("state_dict", ck)) if isinstance(ck, dict) else ck
        self.model.load_state_dict(state)
        self.model.to(device).eval()

    def count_map(self, frame_bgr: np.ndarray) -> np.ndarray:
        """(H, W) float32 map of people-per-pixel; .sum() is the crowd count."""
        import cv2
        import torch

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgb = (rgb - np.array(_MEAN, dtype=np.float32)) / np.array(_STD, dtype=np.float32)
        x = torch.from_numpy(rgb.transpose(2, 0, 1))[None].to(self.device)
        with torch.no_grad():
            dm = self.model(x)[0, 0].float().cpu().numpy()  # stride-8 density map
        h, w = frame_bgr.shape[:2]
        total = float(dm.sum()) * MASS_SCALE
        # Upsample for per-cell aggregation, preserving total mass.
        full = cv2.resize(dm, (w, h), interpolation=cv2.INTER_LINEAR)
        s = full.sum()
        if s > 1e-9:
            full *= total / s
        return np.clip(full, 0.0, None).astype(np.float32)
