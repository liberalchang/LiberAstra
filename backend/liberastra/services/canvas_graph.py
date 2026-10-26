"""画布图的纯函数：作用域回溯、拓扑序、环检测、提示词变量替换、节点指纹。

图结构与 React Flow 序列化格式一致：
  nodes: [{id, type: input|function|concat, position: {x, y}, data: {...}}]
  edges: [{id, source, target, sourceHandle?, targetHandle?}]
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from liberastra.providers.base import ProviderError

MEDIA_INPUT_TYPES = ("image", "video", "audio")

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][\w-]*)\s*\}\}")


def _nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return list(graph.get("nodes") or [])


def _edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return list(graph.get("edges") or [])


def node_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(n.get("id")): n for n in _nodes(graph)}


def detect_cycle(graph: dict[str, Any]) -> str | None:
    """返回成环的节点 id；无环返回 None。Kahn 拓扑：有剩余节点即成环。"""
    nodes = node_map(graph)
    indegree = {nid: 0 for nid in nodes}
    for e in _edges(graph):
        target = str(e.get("target"))
        if target in indegree and str(e.get("source")) in nodes:
            indegree[target] += 1
    queue = [nid for nid, deg in indegree.items() if deg == 0]
    seen = 0
    while queue:
        nid = queue.pop()
        seen += 1
        for e in _edges(graph):
            if str(e.get("source")) == nid:
                target = str(e.get("target"))
                if target in indegree:
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        queue.append(target)
    if seen != len(nodes):
        remaining = [nid for nid, deg in indegree.items() if deg > 0]
        return remaining[0] if remaining else None
    return None


def leaf_nodes(graph: dict[str, Any]) -> list[str]:
    """无出边的节点（任意类型）。无选中执行时以它们为目标。"""
    nodes = node_map(graph)
    has_out: set[str] = set()
    for e in _edges(graph):
        has_out.add(str(e.get("source")))
    return [nid for nid in nodes if nid not in has_out]


def resolve_scope(graph: dict[str, Any], target_ids: list[str] | None) -> list[str]:
    """目标节点 + 其全部祖先（反向 BFS)。目标为空时取所有末端节点。"""
    nodes = node_map(graph)
    targets = [t for t in (target_ids or []) if t in nodes]
    if not targets:
        if target_ids:
            raise ProviderError("目标节点不存在于画布中")
        targets = leaf_nodes(graph)
    scope: set[str] = set()
    queue = list(targets)
    while queue:
        nid = queue.pop()
        if nid in scope:
            continue
        scope.add(nid)
        for e in _edges(graph):
            if str(e.get("target")) == nid:
                queue.append(str(e.get("source")))
    return list(scope)


def topo_order(graph: dict[str, Any], scope: list[str]) -> list[str]:
    """scope 内按依赖顺序排列（Kahn)。假定无环（保存时已校验）。"""
    scope_set = set(scope)
    indegree = {nid: 0 for nid in scope}
    for e in _edges(graph):
        source, target = str(e.get("source")), str(e.get("target"))
        if source in scope_set and target in scope_set:
            indegree[target] += 1
    queue = [nid for nid, deg in indegree.items() if deg == 0]
    order: list[str] = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for e in _edges(graph):
            if str(e.get("source")) == nid:
                target = str(e.get("target"))
                if target in indegree:
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        queue.append(target)
    return order


def substitute_prompt(text: str, variables: dict[str, str]) -> str:
    """把 {{varName}} 替换为文本输入节点的内容；未知变量报错。"""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise ProviderError(f"提示词引用了未知变量: {name}")
        return variables[name]

    return _VAR_RE.sub(repl, text)


def canonical_fingerprint(payload: dict[str, Any]) -> str:
    """sha256 over canonical JSON——输入/参数未变则指纹不变，用于增量复用。"""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
