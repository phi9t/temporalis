from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINER_SOURCE = ROOT / "kilvin-py" / "trainer" / "trainer.py"


def test_attention_code_documents_sequence_shapes_and_qkv_math() -> None:
    source = TRAINER_SOURCE.read_text(encoding="utf-8")

    for expected in [
        "[batch, seq, embed]",
        "[batch, seq, 3 * embed]",
        "[batch, heads, seq, head_dim]",
        "Q @ K.T",
        "causal",
        "softmax",
        "values",
    ]:
        assert expected in source


def test_trainer_uses_seq_len_internally_while_preserving_block_size_env() -> None:
    source = TRAINER_SOURCE.read_text(encoding="utf-8")

    assert 'env_int("BLOCK_SIZE", 128)' in source
    assert "seq_len" in source
    assert "self.block_size" not in source
    assert "block_size = env_int" not in source


def test_trainer_documents_modern_transformer_scope_and_qwen3_pointer() -> None:
    source = TRAINER_SOURCE.read_text(encoding="utf-8")

    for expected in [
        "GPT-2-era",
        "RMSNorm",
        "SwiGLU",
        "MoE",
        "RoPE",
        "docs/qwen3-kilvin-extension.md",
    ]:
        assert expected in source


def test_batching_is_named_and_documents_input_target_shapes() -> None:
    source = TRAINER_SOURCE.read_text(encoding="utf-8")

    for expected in [
        "def make_training_batch(",
        "input_tokens: [batch, seq]",
        "target_tokens: [batch, seq]",
        "next-token targets",
    ]:
        assert expected in source


def test_tensor_names_use_compact_dimension_suffixes() -> None:
    source = TRAINER_SOURCE.read_text(encoding="utf-8")

    for expected in [
        "b=batch",
        "t=sequence/time",
        "d=embedding dimension",
        "h=heads",
        "r=head dimension",
        "vocab=vocabulary size",
        "x_btd",
        "qkv_bt3d",
        "q_bhtr",
        "attn_out_bhtr",
        "attn_out_btd",
        "idx_bt",
        "pos_t",
        "input_tokens_bt",
        "target_tokens_bt",
        "logits_bt_vocab",
        "data_t",
    ]:
        assert expected in source
