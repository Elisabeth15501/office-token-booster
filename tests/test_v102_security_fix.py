#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_v102_security_fix.py — v1.0.2 天禧扫描安全整改回归测试

对应天禧 AI 上架扫描报告（detailId 287056）四项发现：
- 中危：build_compare_card 周标签未转义即拼入 HTML
- 低危：--online / use_online_search 联网残留，声明（network.outbound=false）与实现不一致
- 低危：第三方推荐节省数字未经实测验证且未披露
- 信息：CHANGELOG 描述历史修复时嵌入了可复制执行的命令形态
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import report_engine
from report_engine import build_compare_card, generate_html_report
from skill_recommender import (
    recommend_skills,
    format_recommendations_md,
    format_recommendations_html,
)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
ROOT = SCRIPTS.parent


def _make_pc(week):
    """构造一份 period_compare 形状的 dict（week 可注入任意值）。"""
    return {
        "direction": "up",
        "current_week": week,
        "previous_week": week,
        "current": {"saved_tokens": 100, "count": 2, "saved_minutes": 10},
        "previous": {"saved_tokens": 50, "count": 1, "saved_minutes": 5},
        "saved_tokens_pct": 100.0,
        "count_pct": 100.0,
        "saved_minutes_pct": 100.0,
    }


class TestCompareCardEscaping:
    """中危整改：对比卡周标签必须经 esc() 转义。"""

    def test_malicious_script_tag_escaped(self):
        html = build_compare_card(_make_pc("<script>alert(1)</script>"))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_malicious_img_onerror_escaped(self):
        html = build_compare_card(_make_pc('"><img src=x onerror=alert(1)>'))
        assert "<img" not in html  # 不再构成真实标签

    def test_normal_week_label_intact(self):
        html = build_compare_card(_make_pc("2026-W36"))
        assert "2026-W36" in html

    def test_diagnose_collapses_malformed_date(self):
        """正常链路兜底：非法日期折叠为「未知周」，不透传原始值。"""
        tasks = [
            {"date": "<script>x</script>", "type": "周报生成",
             "baseline_tokens": 1000, "skill_tokens": 500,
             "baseline_minutes": 10, "skill_minutes": 2},
            {"date": "2026-09-01", "type": "周报生成",
             "baseline_tokens": 1000, "skill_tokens": 500,
             "baseline_minutes": 10, "skill_minutes": 2},
        ]
        diag = report_engine.diagnose(tasks)
        html = generate_html_report(diag)
        assert "<script>x</script>" not in html


class TestNoOnlineRemnants:
    """低危整改：联网推荐残留清除，与 network.outbound=false 声明一致。"""

    def test_recommend_skills_rejects_online_flag(self):
        with pytest.raises(TypeError):
            recommend_skills([], total_tasks=0, use_online_search=True)

    def test_report_engine_no_online_arg(self):
        src = (SCRIPTS / "report_engine.py").read_text(encoding="utf-8")
        assert "--online" not in src
        assert "use_online_search" not in src

    def test_skill_recommender_no_online_clients(self):
        src = (SCRIPTS / "skill_recommender.py").read_text(encoding="utf-8")
        assert "skillhub_client" not in src
        assert "clawhub_client" not in src
        assert "use_online_search" not in src


class TestUnverifiedDisclosure:
    """低危整改：第三方推荐明确标注「未经本技能实测验证」。"""

    @staticmethod
    def _by_type():
        return [{"task_type": "代码开发", "baseline_tokens": 50000,
                 "skill_tokens": 30000, "count": 5}]

    def test_md_contains_unverified_note(self):
        recs = recommend_skills(self._by_type(), total_tasks=5)
        assert recs
        assert "未经本技能实测验证" in format_recommendations_md(recs)

    def test_html_contains_unverified_note(self):
        recs = recommend_skills(self._by_type(), total_tasks=5)
        assert "未经本技能实测验证" in format_recommendations_html(recs)

    def test_html_report_end_to_end(self):
        tasks = [
            {"date": "2026-09-01", "type": "周报生成",
             "baseline_tokens": 12000, "skill_tokens": 3000,
             "baseline_minutes": 25, "skill_minutes": 3},
            {"date": "2026-08-25", "type": "周报生成",
             "baseline_tokens": 11000, "skill_tokens": 3200,
             "baseline_minutes": 24, "skill_minutes": 4},
        ]
        html = generate_html_report(report_engine.diagnose(tasks))
        assert "未经本技能实测验证" in html
        assert "skillhub_client" not in html


class TestDocsNoExecutableDownloadCommands:
    """信息整改：发行文档不得包含可复制执行的远程下载/管道命令形态。"""

    @pytest.mark.parametrize("doc", ["CHANGELOG.md", "SKILL.md", "QUICKSTART.md", "README.md"])
    def test_no_pipe_download_patterns(self, doc):
        p = ROOT / doc
        if not p.is_file():
            pytest.skip(f"{doc} 不存在")
        text = p.read_text(encoding="utf-8")
        assert "curl |" not in text
        assert "| bash" not in text
        assert "wget |" not in text


class TestDocsNoSecretLiteralPattern:
    """高危整改：发行文档不得出现「敏感名 + 赋值号 + 字面量」形态。

    起因：ClawHub 静态扫描（SkillSpector）对 ``CHANGELOG.md`` 报
    ``suspicious.exposed_secret_literal``（Critical）——原文在枚举
    ``security_preflight.py`` 自身的 R3 检测模式，写成了一串
    「敏感名=值」的链式形态，被判定为硬编码凭据。

    本测试锁定「文档描述检测规则时不能用赋值形态」，避免同类告警在
    每次改 CHANGELOG 时复发（复发一次 = 一次新版本 + 一次重新审核）。
    本文件位于 tests/，不随分发包发布，故其自身正则不会成为扫描面。
    """

    DOCS = [
        "CHANGELOG.md", "SKILL.md", "README.md", "QUICKSTART.md",
        "RELEASE_NOTES.md", "usage-examples.md", "docs/portability-contract.md",
        "config.yaml", "requirements-optional.txt",
    ]
    # 敏感名 + 赋值号 + 至少 4 位非空白字面量
    ASSIGN = re.compile(
        r"(?i)\b(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token"
        r"|private[_-]?key|token|pwd|password|passwd|credential)s?\s*[=:]\s*\S{4,}"
    )
    # **内联代码包裹**的赋值形态：旧守卫要求赋值号后有 4 位非空白字符，
    # 而写成 `api_key=`（反引号紧跟）只有 1 个非空白字符 → 漏检（v1.0.5 因此复发）。
    ASSIGN_INLINE = re.compile(
        r"(?i)`[a-z_\-]*(?:api[_-]?key|secret|token|password|passwd|pwd|credential)[a-z_\-]*=`"
    )
    # 可执行形态：动态导入 / socket 模块前缀 / 系统命令（文档里出现即可能被判危险）
    EXECUTABLE = {
        "dynamic-import": re.compile(r"__import__\s*\("),
        "socket-prefix": re.compile(r"socket\.[a-z_]+"),
        "system-command": re.compile(r"os\.system|subprocess\.[a-z_]+"),
    }
    # 已知凭据字面量前缀（长度阈值与常见扫描器一致）
    LITERALS = {
        "openai-style key": re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
        "github pat": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
        "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}"),
        "tencent secret id": re.compile(r"\bAKID[A-Za-z0-9]{16,}"),
        "slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    }

    @pytest.mark.parametrize("doc", DOCS)
    def test_no_secret_assignment_literal(self, doc):
        p = ROOT / doc
        if not p.is_file():
            pytest.skip(f"{doc} 不存在")
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            hit = self.ASSIGN.search(line) or self.ASSIGN_INLINE.search(line)
            assert not hit, (
                f"{doc}:{lineno} 出现「敏感名+赋值」形态，"
                f"会被 ClawHub 静态扫描判为 suspicious.exposed_secret_literal：{hit.group()!r}"
            )
            for name, rx in self.LITERALS.items():
                m = rx.search(line)
                assert not m, f"{doc}:{lineno} 出现疑似 {name} 字面量：{m.group()[:12]!r}"

    @pytest.mark.parametrize("doc", DOCS)
    def test_no_executable_form_in_docs(self, doc):
        """文档描述检测规则时，不得写出可执行绕过形态（会触发 Credential Access 类告警）。"""
        p = ROOT / doc
        if not p.is_file():
            pytest.skip(f"{doc} 不存在")
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for name, rx in self.EXECUTABLE.items():
                m = rx.search(line)
                assert not m, (
                    f"{doc}:{lineno} 出现 {name} 可执行形态，"
                    f"文档应改为散文描述并指向 security_preflight.py：{m.group()!r}"
                )


class TestHostUsageScanBounded:
    """隐私加固：宿主用量目录读取必须有边界（深度 / 文件数 / 后缀白名单 / 跳过符号链接）。"""

    def test_depth_limit_enforced(self, tmp_path):
        from host_cost import _iter_trace_files, _SCAN_MAX_DEPTH
        traces = tmp_path / "traces"
        # 真实形态：traces/<session>/trace.json（深度 2）
        ok_dir = traces / ("s" * _SCAN_MAX_DEPTH)
        ok_dir.mkdir(parents=True)
        (ok_dir / "trace_ok.json").write_text('{"effective_tokens": 1}', encoding="utf-8")
        # 超深：traces/a/b/c/d/.../trace_deep.json —— 不得被枚举
        deep = traces
        for i in range(_SCAN_MAX_DEPTH + 2):
            deep = deep / f"d{i}"
        deep.mkdir(parents=True)
        (deep / "trace_deep.json").write_text('{"effective_tokens": 1}', encoding="utf-8")

        names = {p.name for p in _iter_trace_files(traces)}
        assert "trace_ok.json" in names, "深度内的真实 trace 必须仍能读到"
        assert "trace_deep.json" not in names, f"超过深度上限 {_SCAN_MAX_DEPTH} 的文件不得被读取"

    def test_suffix_whitelist_and_symlink_skipped(self, tmp_path):
        from host_cost import _iter_trace_files
        traces = tmp_path / "traces"
        traces.mkdir()
        (traces / "a.json").write_text("{}", encoding="utf-8")
        (traces / "b.jsonl").write_text("{}", encoding="utf-8")
        (traces / "c.txt").write_text("not a trace", encoding="utf-8")
        (traces / "noext").write_text("not a trace", encoding="utf-8")

        names = {p.name for p in _iter_trace_files(traces)}
        assert {"a.json", "b.jsonl"} <= names, "白名单后缀必须被读取"
        assert "c.txt" not in names and "noext" not in names, "非白名单后缀不得被读取"

        outside = tmp_path / "secret.json"
        outside.write_text('{"effective_tokens": 999}', encoding="utf-8")
        try:
            (traces / "link.json").symlink_to(outside)
        except (OSError, NotImplementedError):
            return  # 无符号链接权限的平台（如 Windows 默认）跳过该断言
        assert "link.json" not in {p.name for p in _iter_trace_files(traces)}, \
            "符号链接不得被跟随读取（防止指向目录外）"


class TestLedgerWriteHardening:
    """写回加固：条目校验 + 备份配额，避免写入损坏数据与备份无界堆积。"""

    def test_validate_entry_rejects_non_numeric(self):
        from ledger_agent import _validate_entry
        assert _validate_entry({}) == {}, "空条目应放行（下游按缺省 0 处理）"
        assert _validate_entry({"type": "周报生成", "baseline_tokens": "12000"})["baseline_tokens"] == "12000"
        for bad in ({"skill_tokens": "很多"}, {"baseline_minutes": {"a": 1}}, {"skill_tokens": ["1"]}):
            with pytest.raises(ValueError):
                _validate_entry(bad)

    def test_backup_quota_enforced(self, tmp_path):
        from ledger_agent import _BACKUP_KEEP, _write_ledger_atomic
        ledger_file = tmp_path / "ledger.json"
        for i in range(_BACKUP_KEEP + 5):
            ledger_file.write_text('{"tasks": [%d]}' % i, encoding="utf-8")
            _write_ledger_atomic(ledger_file, {"tasks": [i]}, backup=True)
        backups = sorted(tmp_path.glob("ledger.json.*.bak"))
        assert len(backups) == _BACKUP_KEEP, \
            f"备份份数应被限制在 {_BACKUP_KEEP} 以内，实际 {len(backups)}"

    def test_append_entry_rejects_bad_entry_without_touching_file(self, tmp_path):
        from ledger_agent import append_entry
        ledger_file = tmp_path / "ledger.json"
        ledger_file.write_text('{"tasks": []}', encoding="utf-8")
        before = ledger_file.read_text(encoding="utf-8")
        with pytest.raises(ValueError):
            append_entry(str(ledger_file), {"skill_tokens": "非数字"}, dry_run=False)
        assert ledger_file.read_text(encoding="utf-8") == before, "拒写时原账本必须保持不变"

