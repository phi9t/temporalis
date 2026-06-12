"""Tiny char-level GPT-2-style trainer. CPU-only, configured entirely by env vars."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


def env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


class CausalSelfAttention(nn.Module):
    def __init__(self, n_embd: int, n_head: int) -> None:
        super().__init__()
        self.n_head = n_head
        self.qkv = nn.Linear(n_embd, 3 * n_embd)
        self.proj = nn.Linear(n_embd, n_embd)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, t, c = x.shape
        q, k, v = self.qkv(x).split(c, dim=2)
        q = q.view(-1, t, self.n_head, c // self.n_head).transpose(1, 2)
        k = k.view(-1, t, self.n_head, c // self.n_head).transpose(1, 2)
        v = v.view(-1, t, self.n_head, c // self.n_head).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.proj(y.transpose(1, 2).contiguous().view(-1, t, c))


class Block(nn.Module):
    def __init__(self, n_embd: int, n_head: int) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn = CausalSelfAttention(n_embd, n_head)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd),
            nn.GELU(),
            nn.Linear(4 * n_embd, n_embd),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        return x + self.mlp(self.ln2(x))


class TinyGPT(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        n_layer: int,
        n_head: int,
        n_embd: int,
        block_size: int,
    ) -> None:
        super().__init__()
        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, n_embd)
        self.pos_emb = nn.Embedding(block_size, n_embd)
        self.blocks = nn.ModuleList(Block(n_embd, n_head) for _ in range(n_layer))
        self.ln_f = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        _, t = idx.shape
        pos = torch.arange(t, device=idx.device)
        x = self.tok_emb(idx) + self.pos_emb(pos)
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


def main() -> int:
    run_id = env_str("RUN_ID", "local")
    data_path = Path(env_str("DATA_PATH", "data/input.txt"))
    out_dir = Path(env_str("OUT_DIR", "out"))
    n_layer = env_int("N_LAYER", 4)
    n_head = env_int("N_HEAD", 4)
    n_embd = env_int("N_EMBD", 128)
    block_size = env_int("BLOCK_SIZE", 128)
    batch_size = env_int("BATCH_SIZE", 8)
    max_steps = env_int("MAX_STEPS", 200)
    lr = env_float("LEARNING_RATE", 3e-4)
    log_every = env_int("LOG_EVERY", 10)
    torch.manual_seed(env_int("SEED", 1337))

    text = data_path.read_text(encoding="utf-8")
    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    data = torch.tensor([stoi[ch] for ch in text], dtype=torch.long)

    model = TinyGPT(len(chars), n_layer, n_head, n_embd, block_size)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"run_id={run_id} vocab={len(chars)} params={n_params}", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    first_loss, final_loss = 0.0, 0.0
    start = time.time()
    for step in range(1, max_steps + 1):
        ix = torch.randint(len(data) - block_size - 1, (batch_size,))
        xb = torch.stack([data[i : i + block_size] for i in ix])
        yb = torch.stack([data[i + 1 : i + block_size + 1] for i in ix])
        logits = model(xb)
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), yb.view(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        final_loss = loss.item()
        if step == 1:
            first_loss = final_loss
        if step % log_every == 0 or step == 1 or step == max_steps:
            print(f"step={step} loss={final_loss:.4f}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "checkpoint.pt")
    (out_dir / "metrics.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "steps": max_steps,
                "first_loss": round(first_loss, 4),
                "final_loss": round(final_loss, 4),
                "params": n_params,
                "vocab_size": len(chars),
                "seconds": round(time.time() - start, 2),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"TRAINING_DONE run_id={run_id} final_loss={final_loss:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
