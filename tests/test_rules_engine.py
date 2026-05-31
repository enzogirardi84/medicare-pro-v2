"""Tests para core.rules_engine — Business Rules Engine."""
from __future__ import annotations

import asyncio


class TestRuleCondition:
    def test_load_from_json(self):
        from core.rules_engine import RuleCondition
        cond = RuleCondition(field="news2_score", operator=">", value=5)
        assert cond.field == "news2_score"
        assert cond.operator == ">"


class TestRuleAction:
    def test_defaults(self):
        from core.rules_engine import RuleAction
        action = RuleAction(action_type="webhook", target="https://hook.example")
        assert action.priority == 0


class TestBusinessRule:
    def test_load_from_json(self):
        from core.rules_engine import BusinessRule, RuleCondition, RuleAction
        rule = BusinessRule(
            rule_id="r1", tenant_id="aval",
            name="Alta NEWS2",
            conditions=[RuleCondition(field="news2_score", operator=">", value=5)],
            actions=[RuleAction(action_type="webhook", target="https://aval.api/alert")],
        )
        assert rule.rule_id == "r1"
        assert rule.cooldown_seconds == 300.0


class TestRulesEngine:
    def test_load_rule_from_json(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        rule = engine.load_rule_from_json({
            "rule_id": "r1",
            "tenant_id": "t1",
            "name": "Test Rule",
            "conditions": [{"field": "news2_score", "operator": ">", "value": 5}],
            "actions": [{"action_type": "webhook", "target": "https://hook.test"}],
        })
        assert rule.rule_id == "r1"
        assert len(engine._rules) == 1

    def test_evaluate_single_gt(self):
        from core.rules_engine import RulesEngine, RuleCondition
        engine = RulesEngine()
        assert engine._evaluate_single(RuleCondition(field="edad", operator=">", value=65), {"edad": 70}) is True
        assert engine._evaluate_single(RuleCondition(field="edad", operator=">", value=65), {"edad": 30}) is False

    def test_evaluate_single_eq(self):
        from core.rules_engine import RulesEngine, RuleCondition
        engine = RulesEngine()
        assert engine._evaluate_single(RuleCondition(field="diagnostico", operator="==", value="neumonia"), {"diagnostico": "neumonia"}) is True
        assert engine._evaluate_single(RuleCondition(field="diagnostico", operator="==", value="neumonia"), {"diagnostico": "gripe"}) is False

    def test_evaluate_single_in(self):
        from core.rules_engine import RulesEngine, RuleCondition
        engine = RulesEngine()
        assert engine._evaluate_single(RuleCondition(field="tenant_id", operator="in", value=["aval", "premedic"]), {"tenant_id": "aval"}) is True
        assert engine._evaluate_single(RuleCondition(field="tenant_id", operator="in", value=["aval", "premedic"]), {"tenant_id": "sancor"}) is False

    def test_evaluate_single_contains(self):
        from core.rules_engine import RulesEngine, RuleCondition
        engine = RulesEngine()
        assert engine._evaluate_single(RuleCondition(field="nota", operator="contains", value="urgencia"), {"nota": "paciente en urgencia"}) is True

    def test_evaluate_conditions_and(self):
        from core.rules_engine import RulesEngine, RuleCondition
        engine = RulesEngine()
        conditions = [
            RuleCondition(field="news2_score", operator=">", value=5),
            RuleCondition(field="edad", operator=">=", value=65),
        ]
        assert engine._evaluate_conditions(conditions, {"news2_score": 7, "edad": 70}) is True
        assert engine._evaluate_conditions(conditions, {"news2_score": 7, "edad": 30}) is False

    def test_evaluate_rules(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        engine.load_rule_from_json({
            "rule_id": "r1", "tenant_id": "t1", "name": "High NEWS2",
            "conditions": [{"field": "news2_score", "operator": ">", "value": 5}],
            "actions": [{"action_type": "webhook", "target": "https://hook.test"}],
            "cooldown_seconds": 0,  # sin cooldown para test
        })
        triggered = asyncio.run(engine.evaluate({"news2_score": 8, "tenant_id": "t1"}))
        assert len(triggered) == 1
        assert triggered[0]["action_type"] == "webhook"

    def test_evaluate_rule_not_triggered(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        engine.load_rule_from_json({
            "rule_id": "r2", "tenant_id": "t1", "name": "Low score",
            "conditions": [{"field": "news2_score", "operator": ">", "value": 10}],
            "actions": [{"action_type": "webhook", "target": "https://hook.test"}],
            "cooldown_seconds": 0,
        })
        triggered = asyncio.run(engine.evaluate({"news2_score": 3, "tenant_id": "t1"}))
        assert len(triggered) == 0

    def test_evaluate_disabled_rule(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        engine.load_rule_from_json({
            "rule_id": "r3", "tenant_id": "t1", "name": "Disabled",
            "enabled": False,
            "conditions": [{"field": "news2_score", "operator": ">", "value": 0}],
            "actions": [{"action_type": "webhook", "target": "https://hook.test"}],
            "cooldown_seconds": 0,
        })
        triggered = asyncio.run(engine.evaluate({"news2_score": 20, "tenant_id": "t1"}))
        assert len(triggered) == 0

    def test_get_rules_filtered(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        engine.load_rule_from_json({"rule_id": "r_a", "tenant_id": "t1", "name": "A",
                                     "conditions": [], "actions": []})
        engine.load_rule_from_json({"rule_id": "r_b", "tenant_id": "t2", "name": "B",
                                     "conditions": [], "actions": []})
        rules_t1 = engine.get_rules(tenant_id="t1")
        assert len(rules_t1) == 1
        assert rules_t1[0]["rule_id"] == "r_a"

    def test_delete_rule(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        engine.load_rule_from_json({"rule_id": "del1", "tenant_id": "t1", "name": "Del",
                                     "conditions": [], "actions": []})
        assert engine.delete_rule("del1") is True
        assert engine.delete_rule("nonexistent") is False

    def test_load_rules_bulk(self):
        from core.rules_engine import RulesEngine
        engine = RulesEngine()
        count = engine.load_rules_bulk([
            {"rule_id": "b1", "tenant_id": "t1", "name": "B1", "conditions": [], "actions": []},
            {"rule_id": "b2", "tenant_id": "t1", "name": "B2", "conditions": [], "actions": []},
        ])
        assert count == 2
        assert len(engine._rules) == 2
