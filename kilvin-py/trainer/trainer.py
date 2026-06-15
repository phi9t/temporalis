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


# Tensor suffix legend used below:
# b=batch, t=sequence/time, d=embedding dimension, h=heads,
# r=head dimension, vocab=vocabulary size.
#
# Example: x_btd means a tensor shaped [batch, sequence/time, embedding dim].


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

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        batch, seq_len, embed_dim = x_btd.shape  # x_btd: [b, t, d] = [batch, seq, embed]
        head_dim = embed_dim // self.n_head  # head_dim is r.

        # One learned projection makes queries, keys, and values at once:
        # qkv_bt3d: [b, t, 3 * d] = [batch, seq, 3 * embed].
        #
        # For each token position:
        # - query asks "what am I looking for?"
        # - key says "what do I contain?"
        # - value carries "what information should flow if I am attended to?"
        qkv_bt3d = self.qkv(x_btd)
        q_btd, k_btd, v_btd = qkv_bt3d.split(embed_dim, dim=2)  # each: [b, t, d]

        # Split the embedding into independent heads, then put heads before seq
        # because PyTorch attention expects [b, h, t, r] =
        # [batch, heads, seq, head_dim].
        q_bhtr = q_btd.view(batch, seq_len, self.n_head, head_dim).transpose(1, 2)
        k_bhtr = k_btd.view(batch, seq_len, self.n_head, head_dim).transpose(1, 2)
        v_bhtr = v_btd.view(batch, seq_len, self.n_head, head_dim).transpose(1, 2)

        # Attention forms scores with Q @ K.T for every head, scales them by
        # sqrt(head_dim), applies a causal mask plus softmax over earlier
        # sequence positions, then uses those weights to blend the values.
        attn_out_bhtr = F.scaled_dot_product_attention(q_bhtr, k_bhtr, v_bhtr, is_causal=True)

        # attn_out_bhtr: [b, h, t, r] -> attn_out_btd: [b, t, d].
        # In full names: [batch, heads, seq, head_dim] -> [batch, seq, embed].
        attn_out_btd = attn_out_bhtr.transpose(1, 2).contiguous().view(batch, seq_len, embed_dim)
        return self.proj(attn_out_btd)


class Block(nn.Module):
    """A small GPT-2-era transformer block for teaching.

    Modern frontier models usually swap in pieces such as RMSNorm, SwiGLU MLPs,
    and more complex MoE routing. Those choices are outside this trainer's
    scope: this file keeps the older, compact shape so the QKV attention path is
    easy to inspect. For a repo-local bridge to a more modern Qwen3-style
    training recipe, see docs/qwen3-kilvin-extension.md.
    """

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

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        x_btd = x_btd + self.attn(self.ln1(x_btd))
        return x_btd + self.mlp(self.ln2(x_btd))


class TinyGPT(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        n_layer: int,
        n_head: int,
        n_embd: int,
        seq_len: int,
    ) -> None:
        super().__init__()
        self.seq_len = seq_len
        self.tok_emb = nn.Embedding(vocab_size, n_embd)
        # GPT-2 learned a position vector and added it to each token vector.
        # Most current large models instead use RoPE-style rotary position
        # information inside attention. See docs/qwen3-kilvin-extension.md for
        # the repo's Qwen3 long-context discussion.
        self.pos_emb = nn.Embedding(seq_len, n_embd)
        self.blocks = nn.ModuleList(Block(n_embd, n_head) for _ in range(n_layer))
        self.ln_f = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)

    def forward(self, idx_bt: torch.Tensor) -> torch.Tensor:
        _, seq_len = idx_bt.shape  # idx_bt: [b, t]
        pos_t = torch.arange(seq_len, device=idx_bt.device)
        x_btd = self.tok_emb(idx_bt) + self.pos_emb(pos_t)
        for block in self.blocks:
            x_btd = block(x_btd)
        logits_bt_vocab = self.head(self.ln_f(x_btd))
        return logits_bt_vocab


def make_training_batch(
    data_t: torch.Tensor,
    batch_size: int,
    seq_len: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Sample random next-token training examples from one long token stream.

    `data_t` is a 1-D tensor of token ids. Each sampled start offset produces:
    - input_tokens_bt / input_tokens: [batch, seq], the visible token sequence
    - target_tokens_bt / target_tokens: [batch, seq], the next-token targets shifted one step right

    Example for one row with seq=4:
        input  = data_t[i : i + 4]
        target = data_t[i + 1 : i + 5]

    Cross-entropy then compares model logits at each sequence position against
    the token that comes immediately after that position in the original text.
    """

    starts_b = torch.randint(len(data_t) - seq_len - 1, (batch_size,))
    input_tokens_bt = torch.stack([data_t[i : i + seq_len] for i in starts_b])
    target_tokens_bt = torch.stack([data_t[i + 1 : i + seq_len + 1] for i in starts_b])
    return input_tokens_bt, target_tokens_bt


def main() -> int:
    run_id = env_str("RUN_ID", "local")
    data_path = Path(env_str("DATA_PATH", "data/input.txt"))
    out_dir = Path(env_str("OUT_DIR", "out"))
    n_layer = env_int("N_LAYER", 4)
    n_head = env_int("N_HEAD", 4)
    n_embd = env_int("N_EMBD", 128)
    seq_len = env_int("BLOCK_SIZE", 128)
    batch_size = env_int("BATCH_SIZE", 8)
    max_steps = env_int("MAX_STEPS", 200)
    lr = env_float("LEARNING_RATE", 3e-4)
    log_every = env_int("LOG_EVERY", 10)
    torch.manual_seed(env_int("SEED", 1337))

    text = data_path.read_text(encoding="utf-8")
    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    data_t = torch.tensor([stoi[ch] for ch in text], dtype=torch.long)

    model = TinyGPT(len(chars), n_layer, n_head, n_embd, seq_len)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"run_id={run_id} vocab={len(chars)} params={n_params}", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    first_loss, final_loss = 0.0, 0.0
    start = time.time()
    for step in range(1, max_steps + 1):
        input_tokens_bt, target_tokens_bt = make_training_batch(data_t, batch_size, seq_len)
        logits_bt_vocab = model(input_tokens_bt)
        loss_0d = F.cross_entropy(
            logits_bt_vocab.view(-1, logits_bt_vocab.size(-1)),
            target_tokens_bt.view(-1),
        )
        opt.zero_grad()
        loss_0d.backward()
        opt.step()
        final_loss = loss_0d.item()
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
