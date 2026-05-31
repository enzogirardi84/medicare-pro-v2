"""Motor de Reglas de Negocio (Business Rules Engine) para prepagas.
DSL en JSON: cada tenant define sus reglas sin modificar codigo.
Evalua snapshots consolidados y dispara eventos del sistema.
"""
from __future__ import annotations

import datetime
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. DSL DE REGLAS (JSON)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RuleCondition:
    """Condicion de una regla de negocio.

    Se evalua contra el snapshot consolidado y el contexto actual.
    """
    field: str = ""               # "news2_score" | "edad" | "diagnostico" | "tenant_id"
    operator: str = ">"           # ">" | "<" | "==" | "!=" | "in" | "contains" | "regex"
    value: Any = None             # Valor a comparar


@dataclass
class RuleAction:
    """Accion a ejecutar cuando la regla se cumple."""
    action_type: str = ""         # "webhook" | "notificacion" | "alerta_interna" | "email" | "sms"
    target: str = ""              # URL del webhook, email, etc.
    payload_template: dict = field(default_factory=dict)
    priority: int = 0             # 0=normal, 1=alta, 2=critica


@dataclass
class BusinessRule:
    """Regla de negocio configurable por tenant.

    Ejemplo JSON:
    {
        "rule_id": "aval-high-news2",
        "tenant_id": "aval",
        "name": "Paciente mayor 65+ con NEWS2 > 5",
        "enabled": true,
        "conditions": [
            {"field": "news2_score", "operator": ">", "value": 5},
            {"field": "edad", "operator": ">=", "value": 65}
        ],
        "actions": [
            {"action_type": "webhook", "target": "https://aval.api/alert",
             "payload_template": {"severity": "high", "type": "news2"},
             "priority": 2}
        ],
        "cooldown_seconds": 300
    }
    """
    rule_id: str = ""
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    enabled: bool = True
    conditions: list[RuleCondition] = field(default_factory=list)
    actions: list[RuleAction] = field(default_factory=list)
    cooldown_seconds: float = 300.0      # evitar spam
    last_fired: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. EVALUADOR DE REGLAS
# ═══════════════════════════════════════════════════════════════════

class RulesEngine:
    """Motor de reglas de negocio.

    Evalua condiciones contra un contexto y ejecuta acciones.
    Cada regla tiene cooldown para evitar spam de alertas.
    """

    def __init__(self):
        self._rules: dict[str, BusinessRule] = {}
        self._action_hooks: dict[str, list[Callable]] = {}

    def load_rule_from_json(self, rule_json: dict) -> BusinessRule:
        """Carga una regla desde un dict JSON."""
        conditions = [
            RuleCondition(**c) for c in rule_json.get("conditions", [])
        ]
        actions = [
            RuleAction(**a) for a in rule_json.get("actions", [])
        ]
        rule = BusinessRule(
            rule_id=rule_json.get("rule_id", str(uuid.uuid4())),
            tenant_id=rule_json.get("tenant_id", ""),
            name=rule_json.get("name", ""),
            description=rule_json.get("description", ""),
            enabled=rule_json.get("enabled", True),
            conditions=conditions,
            actions=actions,
            cooldown_seconds=rule_json.get("cooldown_seconds", 300),
        )
        self._rules[rule.rule_id] = rule
        log_event("rules_engine", f"loaded:{rule.rule_id}:{rule.name}")
        return rule

    def load_rules_bulk(self, rules_list: list[dict]) -> int:
        """Carga multiples reglas desde una lista JSON."""
        count = 0
        for r in rules_list:
            self.load_rule_from_json(r)
            count += 1
        return count

    def register_action_hook(self, action_type: str, hook: Callable):
        """Registra un hook para un tipo de accion.

        El hook recibe (rule, action, context) y se ejecuta
        cuando una regla dispara una accion de ese tipo.
        """
        if action_type not in self._action_hooks:
            self._action_hooks[action_type] = []
        self._action_hooks[action_type].append(hook)

    async def evaluate(self, context: dict) -> list[dict]:
        """Evalua todas las reglas activas contra un contexto.

        Args:
            context: Dict con datos del snapshot y metadatos.
                    Ej: {"news2_score": 7, "edad": 72, "tenant_id": "aval",
                         "paciente_id": "p1", "diagnostico": "neumonia"}

        Returns:
            Lista de acciones ejecutadas.
        """
        triggered: list[dict] = []
        now = time.time()

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            # Cooldown
            if now - rule.last_fired < rule.cooldown_seconds:
                continue

            # Evaluar condiciones
            if self._evaluate_conditions(rule.conditions, context):
                rule.last_fired = now

                for action in rule.actions:
                    result = await self._execute_action(rule, action, context)
                    triggered.append(result)

        return triggered

    def _evaluate_conditions(self, conditions: list[RuleCondition],
                              context: dict) -> bool:
        """Evalua todas las condiciones (AND logico)."""
        for cond in conditions:
            if not self._evaluate_single(cond, context):
                return False
        return True

    @staticmethod
    def _evaluate_single(cond: RuleCondition, context: dict) -> bool:
        """Evalua una condicion individual."""
        actual = context.get(cond.field)
        expected = cond.value

        if cond.operator == ">":
            try:
                return float(actual) > float(expected)
            except (ValueError, TypeError):
                return False
        elif cond.operator == ">=":
            try:
                return float(actual) >= float(expected)
            except (ValueError, TypeError):
                return False
        elif cond.operator == "<":
            try:
                return float(actual) < float(expected)
            except (ValueError, TypeError):
                return False
        elif cond.operator == "<=":
            try:
                return float(actual) <= float(expected)
            except (ValueError, TypeError):
                return False
        elif cond.operator == "==":
            return str(actual) == str(expected)
        elif cond.operator == "!=":
            return str(actual) != str(expected)
        elif cond.operator == "in":
            return str(actual) in [str(v) for v in (expected or [])]
        elif cond.operator == "contains":
            return str(expected) in str(actual)
        return False

    async def _execute_action(self, rule: BusinessRule, action: RuleAction,
                               context: dict) -> dict:
        """Ejecuta una accion de regla."""
        # Construir payload
        payload = dict(action.payload_template)
        payload.update({
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "tenant_id": rule.tenant_id,
            "timestamp": time.time(),
            "context": {k: v for k, v in context.items()
                        if k not in ("_payload", "_private")},
        })

        result = {
            "action_type": action.action_type,
            "target": action.target,
            "rule_id": rule.rule_id,
            "payload": payload,
            "executed_at": time.time(),
        }

        # Ejecutar hooks registrados
        hooks = self._action_hooks.get(action.action_type, [])
        for hook in hooks:
            try:
                await hook(rule, action, context)
            except Exception as exc:
                log_event("rules_engine", f"hook_error:{action.action_type}:{type(exc).__name__}")

        log_event("rules_engine", f"fired:{rule.rule_id}:{action.action_type}:{action.target[:40]}")
        return result

    def get_rules(self, tenant_id: Optional[str] = None) -> list[dict]:
        """Obtiene reglas, opcionalmente filtradas por tenant."""
        rules = self._rules.values()
        if tenant_id:
            rules = [r for r in rules if r.tenant_id == tenant_id]
        return [
            {
                "rule_id": r.rule_id,
                "tenant_id": r.tenant_id,
                "name": r.name,
                "enabled": r.enabled,
                "conditions": [{"field": c.field, "operator": c.operator, "value": c.value}
                               for c in r.conditions],
                "actions": [{"action_type": a.action_type, "target": a.target,
                             "priority": a.priority} for a in r.actions],
                "cooldown_seconds": r.cooldown_seconds,
                "last_fired": r.last_fired,
            }
            for r in rules
        ]

    def delete_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None


__all__ = [
    "RulesEngine",
    "BusinessRule",
    "RuleCondition",
    "RuleAction",
]
