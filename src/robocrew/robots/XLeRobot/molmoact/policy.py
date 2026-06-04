"""
policy.py — MolmoActPolicy: a thin wrapper around the published MolmoAct2 weights.

SERVER-SIDE ONLY. This is the one torch/transformers file; it is imported solely
by serve.py on the GPU box. The robot box uses RemotePolicyClient instead.

predict_chunk() is frame-agnostic: pass already-model-frame state, get back a
(T, JOINT_COUNT) numpy array of joint targets in model frame.
"""
import os
import shutil

import numpy as np
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForImageTextToText, AutoProcessor


REPO_ID = "allenai/MolmoAct2-SO100_101"
NORM_TAG = "so100_so101_molmoact2"
# Rate at which the model's chunk is meant to play back. Training data is
# 30 fps, so chunk[k] is meant for t_start + k/30 seconds.
ACTION_FPS = 30.0

DTYPES = {
    "float32": torch.float32,
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
}


# Workarounds for bf16/fp16 inference. The published modeling_molmoact2.py:
#   1. Creates the action-flow trajectory hardcoded as float32, causing a dtype
#      mismatch under bf16 weights.
#   2. Calls tensor.numpy() directly, which raises for bf16 (no numpy bf16 dtype).
_PATCHES = [
    (
        """            dtype=torch.float32,
            generator=generator,
        )""",
        """            dtype=next(action_expert.parameters()).dtype,  # patched
            generator=generator,
        )""",
    ),
    (
        "        return value.detach().cpu().numpy().astype(np.float32, copy=False)",
        "        return value.detach().to(torch.float32).cpu().numpy()  # patched",
    ),
]


def _patch_model_for_mixed_dtype(local_dir: str) -> None:
    """Edit the snapshot's modeling_molmoact2.py in place for bf16/fp16. Idempotent."""
    target = os.path.join(local_dir, "modeling_molmoact2.py")
    with open(target, "r") as f:
        src = f.read()
    changed = False
    missing = []
    for needle, replacement in _PATCHES:
        if replacement in src:
            continue
        if needle not in src:
            missing.append(needle.splitlines()[0].strip())
            continue
        src = src.replace(needle, replacement)
        changed = True
    if missing:
        print(f"[MolmoAct] WARNING: dtype patch needles not found: {missing!r}. "
              "bf16/fp16 inference may fail at those sites.")
    if not changed:
        return
    with open(target, "w") as f:
        f.write(src)
    print(f"[MolmoAct] Patched {target} for bf16/fp16 inference.")
    rev = os.path.basename(local_dir.rstrip("/"))
    dyn = os.path.expanduser(
        f"~/.cache/huggingface/modules/transformers_modules/{rev}"
    )
    if os.path.isdir(dyn):
        shutil.rmtree(dyn)
        print(f"[MolmoAct] Cleared dynamic_modules cache at {dyn}.")


class MolmoActPolicy:
    """Wrapper around the published MolmoAct2 model + processor.

    Load with MolmoActPolicy.from_pretrained(); run with predict_chunk().
    """

    REPO_ID = REPO_ID
    NORM_TAG = NORM_TAG
    ACTION_FPS = ACTION_FPS
    DTYPES = DTYPES

    def __init__(self, model, processor, device: str, dtype: torch.dtype,
                 norm_tag: str = NORM_TAG):
        self.model = model
        self.processor = processor
        self.device = device
        self.dtype = dtype
        self.norm_tag = norm_tag

    @classmethod
    def from_pretrained(cls, repo_id: str = REPO_ID, *,
                        dtype: str = "bfloat16", device: str = "cuda",
                        apply_patches: bool = False,
                        norm_tag: str = NORM_TAG) -> "MolmoActPolicy":
        """Download (or reuse cached) weights and load into memory.

        Uses snapshot_download so norm_stats.json (which transformers doesn't
        auto-fetch) is present alongside the model code.
        """
        if dtype not in DTYPES:
            raise ValueError(f"dtype must be one of {list(DTYPES)}, got {dtype!r}")
        torch_dtype = DTYPES[dtype]

        print(f"[MolmoAct] Resolving snapshot for {repo_id}...")
        local_dir = snapshot_download(repo_id)
        if apply_patches and dtype != "float32":
            _patch_model_for_mixed_dtype(local_dir)

        print(f"[MolmoAct] Loading from {local_dir} (dtype={dtype}, device={device})...")
        processor = AutoProcessor.from_pretrained(local_dir, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            local_dir,
            trust_remote_code=True,
            dtype=torch_dtype,
        ).to(device).eval()
        print("[MolmoAct] Model ready.")
        return cls(model=model, processor=processor, device=device,
                   dtype=torch_dtype, norm_tag=norm_tag)

    def predict_chunk(self, images, state: np.ndarray, prompt: str, *,
                      num_steps: int = 10, cuda_graph: bool = False) -> np.ndarray:
        """Predict an action chunk for the given observation.

        Args:
            images: list of PIL Images — [scene, wrist] order.
            state: (JOINT_COUNT,) array in model frame.
            prompt: natural-language task instruction.
            num_steps: continuous-flow solver iterations.
            cuda_graph: enable cuda graphs (faster, more VRAM, needs warm-up).

        Returns:
            (T, JOINT_COUNT) float32 numpy array of joint targets in model frame.
        """
        with torch.inference_mode():
            out = self.model.predict_action(
                processor=self.processor,
                images=images,
                task=prompt,
                state=state,
                norm_tag=self.norm_tag,
                inference_action_mode="continuous",
                enable_depth_reasoning=False,
                num_steps=num_steps,
                normalize_language=True,
                enable_cuda_graph=cuda_graph,
            )
        return _to_chunk_array(out.actions)


def _to_chunk_array(raw_actions) -> np.ndarray:
    if torch.is_tensor(raw_actions):
        raw_actions = raw_actions.detach().to("cpu", dtype=torch.float32).numpy()
    actions = np.asarray(raw_actions, dtype=np.float32)
    if actions.ndim == 3 and actions.shape[0] == 1:
        actions = actions[0]
    if actions.ndim == 1:
        actions = actions[None]
    if actions.ndim != 2:
        raise RuntimeError(f"Unexpected action ndim {actions.ndim}, expected 2-D")
    return actions
