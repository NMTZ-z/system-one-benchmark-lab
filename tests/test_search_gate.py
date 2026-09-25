from __future__ import annotations

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.router import DecisionRouter
from local_system_one.workflows.search_gate import SearchGate, SearchGateRequest


class FakeRuntime:
    name = "mlx"

    def __init__(self, probability_true: float = 0.2):
        self.probability_true = probability_true
        self.predict_calls = 0

    def token_count(self, state, question):
        return 220

    def predict(self, state, question):
        self.predict_calls += 1
        return {
            "type": "noul",
            "noul": self.probability_true,
            "confidence": abs(self.probability_true - 0.5) * 2.0,
            "action": {"act_probability": 1.0},
        }


def make_gate(probability_true: float = 0.2) -> tuple[SearchGate, FakeRuntime]:
    runtime = FakeRuntime(probability_true)
    engine = DecisionEngine(
        mlx=runtime,
        ane=None,
        router=DecisionRouter(),
        health=ANEHealthGate(available=False),
    )
    return SearchGate(engine), runtime


def test_current_freshness_is_hard_search():
    gate, runtime = make_gate()
    result = gate.decide(
        SearchGateRequest(
            task="Who is the current CEO of this company?",
            freshness="current",
        )
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "volatile_public_fact"
    assert runtime.predict_calls == 0


def test_provided_only_is_hard_no_search():
    gate, runtime = make_gate(probability_true=0.95)
    result = gate.decide(
        SearchGateRequest(
            task="Rewrite this paragraph more clearly.",
            source_scope="provided_only",
            context={"text": "hello"},
        )
    )
    assert result["should_search"] is False
    assert result["decision_source"] == "rule"
    assert runtime.predict_calls == 0


def test_current_language_is_search_without_hint():
    gate, runtime = make_gate()
    result = gate.decide(SearchGateRequest(task="今天北京天气怎么样？"))
    assert result["should_search"] is True
    assert result["reason"] == "live_public_fact"
    assert runtime.predict_calls == 0


def test_model_confident_no_search():
    gate, runtime = make_gate(probability_true=0.2)
    result = gate.decide(
        SearchGateRequest(task="Explain the difference between a list and a tuple.")
    )
    assert result["should_search"] is False
    assert result["decision_source"] == "model"
    assert result["reason"] == "model_confident_local_answer"
    assert runtime.predict_calls == 1


def test_model_uncertainty_searches_conservatively():
    gate, runtime = make_gate(probability_true=0.45)
    result = gate.decide(
        SearchGateRequest(task="Tell me about a named product that may have changed.")
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "model"
    assert result["reason"] == "model_uncertain_conservative_search"
    assert runtime.predict_calls == 1


def test_volatile_named_role_is_hard_search_without_current_word():
    gate, runtime = make_gate(probability_true=0.01)
    result = gate.decide(SearchGateRequest(task="OpenAI 的 CEO 是谁？"))
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "volatile_public_fact"
    assert runtime.predict_calls == 0


def test_today_smalltalk_is_not_forced_to_web():
    gate, runtime = make_gate(probability_true=0.1)
    result = gate.decide(SearchGateRequest(task="瑶瑶，今天乖不乖？"))
    assert result["should_search"] is False
    assert result["decision_source"] == "model"
    assert runtime.predict_calls == 1


def test_connected_app_task_is_not_public_web():
    gate, runtime = make_gate(probability_true=0.95)
    result = gate.decide(SearchGateRequest(task="检查飞书任务板里有没有新的审核任务。"))
    assert result["should_search"] is False
    assert result["decision_source"] == "rule"
    assert result["reason"] == "connected_app_data"
    assert runtime.predict_calls == 0


def test_rewrite_without_structured_hint_is_not_public_web():
    gate, runtime = make_gate(probability_true=0.95)
    result = gate.decide(SearchGateRequest(task="把这句话润色得更自然：项目已经完成。"))
    assert result["should_search"] is False
    assert result["decision_source"] == "rule"
    assert result["reason"] == "bounded_transform_task"
    assert runtime.predict_calls == 0


def test_transform_words_inside_engineering_task_do_not_force_no_web():
    gate, runtime = make_gate(probability_true=0.8)
    result = gate.decide(
        SearchGateRequest(
            task=(
                "审议大小模型动态路由方案。简单杂活如润色、翻译应走轻量模型，"
                "并核验官方参数是否准确。"
            )
        )
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "explicit_public_web_instruction"
    assert runtime.predict_calls == 0


def test_explicit_official_docs_lookup_overrides_connected_app_language():
    gate, runtime = make_gate(probability_true=0.1)
    result = gate.decide(
        SearchGateRequest(
            task="调用小红书连接器采样社区数据，并查验官方 API 文档中的参数说明。"
        )
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "explicit_public_web_instruction"
    assert runtime.predict_calls == 0


def test_mentioning_feishu_in_public_evidence_task_does_not_force_local_no_web():
    gate, runtime = make_gate(probability_true=0.1)
    result = gate.decide(
        SearchGateRequest(task="整理飞书案例的公开事实，并把证据来源 URL 补完整。")
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "explicit_public_web_instruction"
    assert runtime.predict_calls == 0


def test_configured_model_question_is_not_hard_local_rule():
    gate, runtime = make_gate(probability_true=0.2)
    result = gate.decide(
        SearchGateRequest(task="我给你配置了 GPT 模型，他们都能做什么？")
    )
    assert result["decision_source"] == "model"
    assert runtime.predict_calls == 1


def test_local_git_review_is_classified_separately_from_connected_apps():
    gate, runtime = make_gate(probability_true=0.95)
    result = gate.decide(
        SearchGateRequest(
            task="Review the current staged changes with git diff in the local repository."
        )
    )
    assert result["should_search"] is False
    assert result["reason"] == "local_file_or_repo"
    assert runtime.predict_calls == 0


def test_cross_platform_hotspot_research_keeps_public_web_even_with_connector():
    gate, runtime = make_gate(probability_true=0.1)
    result = gate.decide(
        SearchGateRequest(
            task=(
                "调用 xiaohongshu-mcp 做站内验证，同时侦察全网上升期热点，"
                "覆盖知乎、B站、微博和 GitHub Trending，并附原始链接。"
            )
        )
    )
    assert result["should_search"] is True
    assert result["reason"] == "explicit_public_web_instruction"
    assert runtime.predict_calls == 0


def test_long_workflow_that_mentions_rewrite_is_not_hard_transform():
    gate, runtime = make_gate(probability_true=0.8)
    task = (
        "你是每日新闻总编辑 Agent，负责新闻采集、深度改写、质量初审和推送。"
        + "需要先采集最新新闻并核验来源，然后再改写。" * 40
    )
    result = gate.decide(SearchGateRequest(task=task))
    assert result["should_search"] is True
    assert result["reason"] != "bounded_transform_task"
    assert runtime.predict_calls == 1
