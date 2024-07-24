import os
from typing import Any
import json
import torch
from torch import Tensor
import torch.nn.functional as F
from torchpq.clustering import KMeans
import numpy as np
import imageio


def log_transform(x):
    return torch.sign(x) * torch.log1p(torch.abs(x))


def inverse_log_transform(y):
    assert (
        y.max() < 20
    ), "Probably mixed up linear and log values for xyz. These going in here are supposed to be quite small (log scale)"
    return torch.sign(y) * (torch.expm1(torch.abs(y)))


def _compress_means(
    compress_dir: str, params: Tensor, n_sidelen: int
) -> dict[str, Any]:
    params = log_transform(params)
    grid = params.reshape((n_sidelen, n_sidelen, -1))

    grid_mins = torch.amin(grid, dim=(0, 1))
    grid_maxs = torch.amax(grid, dim=(0, 1))
    grid_norm = (grid - grid_mins) / (grid_maxs - grid_mins)
    img_norm = grid_norm.detach().cpu().numpy()
    img = (img_norm * 65535).astype(np.uint16)
    np.savez_compressed(os.path.join(compress_dir, "means.npz"), arr=img)

    meta = {
        "shape": list(params.shape),
        "mins": grid_mins.tolist(),
        "maxs": grid_maxs.tolist(),
    }
    return meta


def _decompress_means(compress_dir: str, meta: dict[str, Any]) -> Tensor:
    img = np.load(os.path.join(compress_dir, "means.npz"))["arr"]
    img_norm = img / 65535.0
    grid_norm = torch.tensor(img_norm, dtype=torch.float32)
    grid_mins = torch.tensor(meta["mins"], dtype=torch.float32)
    grid_maxs = torch.tensor(meta["maxs"], dtype=torch.float32)
    grid = grid_norm * (grid_maxs - grid_mins) + grid_mins

    params = grid.reshape(meta["shape"])
    params = inverse_log_transform(params)
    return params


def _compress_scales(
    compress_dir: str, params: Tensor, n_sidelen: int
) -> dict[str, Any]:
    grid = params.reshape((n_sidelen, n_sidelen, -1))

    grid_mins = torch.amin(grid, dim=(0, 1))
    grid_maxs = torch.amax(grid, dim=(0, 1))
    grid_norm = (grid - grid_mins) / (grid_maxs - grid_mins)
    img_norm = grid_norm.detach().cpu().numpy()
    img = (img_norm * 255).astype(np.uint8)
    imageio.imwrite(os.path.join(compress_dir, "scales.png"), img)

    meta = {
        "shape": list(params.shape),
        "mins": grid_mins.tolist(),
        "maxs": grid_maxs.tolist(),
    }
    return meta


def _decompress_scales(compress_dir: str, meta: dict[str, Any]) -> Tensor:
    img = imageio.imread(os.path.join(compress_dir, "scales.png"))
    img_norm = img / 255.0
    grid_norm = torch.tensor(img_norm, dtype=torch.float32)
    grid_mins = torch.tensor(meta["mins"], dtype=torch.float32)
    grid_maxs = torch.tensor(meta["maxs"], dtype=torch.float32)
    grid = grid_norm * (grid_maxs - grid_mins) + grid_mins

    params = grid.reshape(meta["shape"])
    return params


def _compress_sh0(compress_dir: str, params: Tensor, n_sidelen: int) -> Tensor:
    grid = params.reshape((n_sidelen, n_sidelen, -1))

    grid_mins = torch.amin(grid, dim=(0, 1))
    grid_maxs = torch.amax(grid, dim=(0, 1))
    grid_norm = (grid - grid_mins) / (grid_maxs - grid_mins)
    img_norm = grid_norm.detach().cpu().numpy()
    img = (img_norm * 255).astype(np.uint8)
    imageio.imwrite(os.path.join(compress_dir, "sh0.png"), img)

    meta = {
        "shape": list(params.shape),
        "mins": grid_mins.tolist(),
        "maxs": grid_maxs.tolist(),
    }
    return meta


def _decompress_sh0(compress_dir: str, meta: dict[str, Any]) -> Tensor:
    img = imageio.imread(os.path.join(compress_dir, "sh0.png"))
    img_norm = img / 255.0
    grid_norm = torch.tensor(img_norm, dtype=torch.float32)
    grid_mins = torch.tensor(meta["mins"], dtype=torch.float32)
    grid_maxs = torch.tensor(meta["maxs"], dtype=torch.float32)
    grid = grid_norm * (grid_maxs - grid_mins) + grid_mins

    params = grid.reshape(meta["shape"])
    return params


def _compress_shN(compress_dir: str, params: Tensor, n_sidelen: int) -> Tensor:
    kmeans = KMeans(n_clusters=65536, distance="euclidean", verbose=True)
    x = params.reshape(params.shape[0], -1).permute(1, 0).contiguous()
    labels = kmeans.fit(x)
    centroids = kmeans.centroids.permute(1, 0)

    centroids_mins = torch.min(centroids)
    centroid_maxs = torch.max(centroids)
    centroids_norm = (centroids - centroids_mins) / (centroid_maxs - centroids_mins)

    labels = labels.detach().cpu().numpy()
    centroids_norm = centroids_norm.detach().cpu().numpy()
    labels = labels.astype(np.uint16)
    centroids = (centroids_norm * 255).astype(np.uint16)
    np.savez_compressed(
        os.path.join(compress_dir, "shN.npz"), labels=labels, centroids=centroids
    )

    meta = {
        "shape": list(params.shape),
        "mins": centroids_mins.tolist(),
        "maxs": centroid_maxs.tolist(),
    }
    return meta


def _decompress_shN(compress_dir: str, meta: dict[str, Any]) -> Tensor:
    npz_dict = np.load(os.path.join(compress_dir, "shN.npz"))
    labels = npz_dict["labels"]
    centroids = npz_dict["centroids"]

    centroids_norm = centroids / 255.0
    centroids_norm = torch.tensor(centroids_norm, dtype=torch.float32)
    centroids_mins = torch.tensor(meta["mins"], dtype=torch.float32)
    centroids_maxs = torch.tensor(meta["maxs"], dtype=torch.float32)
    centroids = centroids_norm * (centroids_maxs - centroids_mins) + centroids_mins

    params = centroids[labels]
    params = params.reshape(meta["shape"])
    return params


def _compress_quats(compress_dir: str, params: Tensor, n_sidelen: int) -> Tensor:
    grid = params.reshape((n_sidelen, n_sidelen, -1))

    grid_mins = torch.amin(grid, dim=(0, 1))
    grid_maxs = torch.amax(grid, dim=(0, 1))
    grid_norm = (grid - grid_mins) / (grid_maxs - grid_mins)
    img_norm = grid_norm.detach().cpu().numpy()
    img = (img_norm * 255).astype(np.uint8)
    imageio.imwrite(os.path.join(compress_dir, "quats.png"), img)

    meta = {
        "shape": list(params.shape),
        "mins": grid_mins.tolist(),
        "maxs": grid_maxs.tolist(),
    }
    return meta


def _decompress_quats(compress_dir: str, meta: dict[str, Any]) -> Tensor:
    img = imageio.imread(os.path.join(compress_dir, "quats.png"))
    img_norm = img / 255.0
    grid_norm = torch.tensor(img_norm, dtype=torch.float32)
    grid_mins = torch.tensor(meta["mins"], dtype=torch.float32)
    grid_maxs = torch.tensor(meta["maxs"], dtype=torch.float32)
    grid = grid_norm * (grid_maxs - grid_mins) + grid_mins

    params = grid.reshape(meta["shape"])
    return params


def _compress_opacities(compress_dir: str, params: Tensor, n_sidelen: int) -> Tensor:
    grid = params.reshape((n_sidelen, n_sidelen))

    grid_mins = torch.amin(grid, dim=(0, 1))
    grid_maxs = torch.amax(grid, dim=(0, 1))
    grid_norm = (grid - grid_mins) / (grid_maxs - grid_mins)
    img_norm = grid_norm.detach().cpu().numpy()
    img = (img_norm * 255).astype(np.uint8)
    imageio.imwrite(os.path.join(compress_dir, "opacities.png"), img)

    meta = {
        "shape": list(params.shape),
        "mins": grid_mins.tolist(),
        "maxs": grid_maxs.tolist(),
    }
    return meta


def _decompress_opacities(compress_dir: str, meta: dict[str, Any]) -> Tensor:
    img = imageio.imread(os.path.join(compress_dir, "opacities.png"))
    img_norm = img / 255.0
    grid_norm = torch.tensor(img_norm, dtype=torch.float32)
    grid_mins = torch.tensor(meta["mins"], dtype=torch.float32)
    grid_maxs = torch.tensor(meta["maxs"], dtype=torch.float32)
    grid = grid_norm * (grid_maxs - grid_mins) + grid_mins

    params = grid.reshape(meta["shape"])
    return params


def compress_splats(compress_dir: str, splats: dict[str, Tensor]) -> None:
    if not os.path.exists(compress_dir):
        os.makedirs(compress_dir, exist_ok=True)

    n_gs = len(splats["means"])
    n_sidelen = int(n_gs**0.5)

    meta = {}
    for attr_name in splats.keys():
        compress_fn = eval(f"_compress_{attr_name}")
        meta[attr_name] = compress_fn(compress_dir, splats[attr_name], n_sidelen)

    with open(os.path.join(compress_dir, "meta.json"), "w") as f:
        json.dump(meta, f)


def decompress_splats(compress_dir: str) -> dict[str, Tensor]:
    with open(os.path.join(compress_dir, "meta.json"), "r") as f:
        meta = json.load(f)

    splats = {}
    for attr_name, attr_meta in meta.items():
        decompress_fn = eval(f"_decompress_{attr_name}")
        splats[attr_name] = decompress_fn(compress_dir, attr_meta)
    return splats