#!/usr/bin/env python3
"""
基线不变性测试 — 验证策略文件未发生任何修改。
"""

import hashlib
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_MANIFEST = PROJECT_ROOT / "research" / "local_migration" / "BASELINE_MANIFEST.json"
STRATEGY_FILE = PROJECT_ROOT / "微盘股-母版-20260627.py"


def get_manifest():
    if not BASELINE_MANIFEST.exists():
        raise FileNotFoundError("BASELINE_MANIFEST.json 不存在: %s" % BASELINE_MANIFEST)
    with open(BASELINE_MANIFEST, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def test_strategy_file_exists():
    """策略文件必须存在。"""
    assert STRATEGY_FILE.exists(), "策略文件不存在: %s" % STRATEGY_FILE


def test_manifest_exists():
    """清单文件必须存在。"""
    assert BASELINE_MANIFEST.exists(), "清单文件不存在: %s" % BASELINE_MANIFEST


def test_strategy_sha256_matches_manifest():
    """当前策略文件的 SHA-256 必须与清单中记录的一致。"""
    manifest = get_manifest()
    expected = manifest.get("strategy_sha256", "")
    assert expected, "清单中 strategy_sha256 为空"
    actual = compute_sha256(STRATEGY_FILE)
    assert actual == expected, (
        "SHA-256 不匹配!\n  期望: %s\n  实际: %s\n  文件可能已被修改" % (expected, actual)
    )


def test_strategy_commit_matches():
    """清单中的提交 ID 必须与冻结基线一致。"""
    manifest = get_manifest()
    expected = "8290ca3b0368aa6496ac801ee02ae4456fea8987"
    actual = manifest.get("strategy_commit", "")
    assert actual == expected, (
        "提交 ID 不匹配!\n  期望: %s\n  实际: %s" % (expected, actual)
    )


def test_critical_params_unchanged():
    """关键冻结参数必须与策略文件一致。"""
    with open(STRATEGY_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查参数值
    checks = {
        "phase_cycle = 15": "g.phase_cycle = 15" in content,
        "phase_offsets = [0, 3, 6, 9, 12]": "[0, 3, 6, 9, 12]" in content,
        "stocknum = 10": "g.stocknum = 10" in content,
        "min_list_days = 375": "g.min_list_days = 375" in content,
        "defensive_months = [1, 4]": "[1, 4]" in content,
        "defensive_etfs = [511880.XSHG]": "511880.XSHG" in content,
        "use_risk_filter = True": "g.use_risk_filter = True" in content,
        "trade_enabled = True": "g.trade_enabled = True" in content,
    }

    failed = [k for k, v in checks.items() if not v]
    assert not failed, "以下关键参数未在策略文件中找到: %s" % "; ".join(failed)


def test_strategy_not_modified_by_test():
    """测试本身不应修改策略文件。"""
    # 仅验证文件没有被重写
    original_sha = compute_sha256(STRATEGY_FILE)
    manifest = get_manifest()
    expected_sha = manifest.get("strategy_sha256", "")
    # 重新验证（与 test_strategy_sha256_matches_manifest 相同，但保护性验证）
    assert original_sha == expected_sha, (
        "策略文件在测试期间被修改!\n  SHA-256 已从 %s 变为 %s" % (expected_sha, original_sha)
    )


def test_git_diff_clean_for_motherboard():
    """检查 git diff 不应包含母版策略的修改。"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", str(STRATEGY_FILE)],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        diff_output = result.stdout.strip()
        assert not diff_output, (
            "git diff 显示母版策略被修改:\n%s" % diff_output[:2000]
        )
    except FileNotFoundError:
        # git 不存在时跳过
        pass
