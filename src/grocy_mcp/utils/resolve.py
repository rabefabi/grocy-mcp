"""Helpers for resolving Grocy entity names to IDs with ambiguity handling."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..client import GrocyClient


def _normalize(value: str) -> str:
    return value.strip().lower()


def _score(name: str, query: str) -> float:
    return SequenceMatcher(None, _normalize(name), _normalize(query)).ratio()


def resolve_by_name(
    items: list[dict[str, Any]],
    query: str,
    *,
    id_key: str = "id",
    name_key: str = "name",
    entity_label: str = "item",
    min_score: float = 0.55,
    reject_low_confidence: bool = False,
) -> dict[str, Any]:
    """
    Resolve an entity by name with exact > fuzzy matching and ambiguity details.

    Returns:
        {
          "ok": bool,
          "id": int | None,
          "name": str | None,
          "confidence": "high" | "medium" | "low" | "none",
          "matches": [{"id": int, "name": str, "score": float}],
          "error": str | None,
          "suggestion": str | None,
        }
    """
    query_norm = _normalize(query)
    if not query_norm:
        return {
            "ok": False,
            "id": None,
            "name": None,
            "confidence": "none",
            "matches": [],
            "error": f"{entity_label} name is required",
            "suggestion": None,
        }

    exact = [i for i in items if _normalize(str(i.get(name_key, ""))) == query_norm]
    if len(exact) == 1:
        hit = exact[0]
        return {
            "ok": True,
            "id": hit.get(id_key),
            "name": hit.get(name_key),
            "confidence": "high",
            "matches": [
                {"id": hit.get(id_key), "name": hit.get(name_key), "score": 1.0}
            ],
            "error": None,
            "suggestion": None,
        }

    if len(exact) > 1:
        candidates = [
            {"id": i.get(id_key), "name": i.get(name_key), "score": 1.0} for i in exact
        ]
        return {
            "ok": False,
            "id": None,
            "name": None,
            "confidence": "none",
            "matches": candidates,
            "error": f"Multiple {entity_label}s match '{query}'",
            "suggestion": f"Use {entity_label}_id instead of name",
        }

    scored = []
    for item in items:
        name = str(item.get(name_key, ""))
        if not name:
            continue
        ratio = _score(name, query)
        if query_norm in _normalize(name) or _normalize(name) in query_norm:
            ratio = max(ratio, 0.82)
        scored.append({"id": item.get(id_key), "name": name, "score": round(ratio, 3)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    matches = [m for m in scored if m["score"] >= min_score][:5]

    if not matches:
        return {
            "ok": False,
            "id": None,
            "name": None,
            "confidence": "none",
            "matches": scored[:5],
            "error": f"No {entity_label} found for '{query}'",
            "suggestion": f"Create the {entity_label} first or provide {entity_label}_id",
        }

    top = matches[0]
    confidence = (
        "high" if top["score"] >= 0.9 else "medium" if top["score"] >= 0.7 else "low"
    )

    if (
        len(matches) > 1
        and abs(matches[0]["score"] - matches[1]["score"]) < 0.08
        and confidence != "high"
    ):
        return {
            "ok": False,
            "id": None,
            "name": None,
            "confidence": confidence,
            "matches": matches,
            "error": f"Ambiguous {entity_label} name '{query}'",
            "suggestion": f"Choose one of the suggested {entity_label}s or provide {entity_label}_id",
        }

    if reject_low_confidence and confidence == "low":
        return {
            "ok": False,
            "id": None,
            "name": None,
            "confidence": confidence,
            "matches": matches,
            "error": f"No confident {entity_label} match for '{query}'",
            "suggestion": f"Check the spelling or provide {entity_label}_id instead of name",
        }

    return {
        "ok": True,
        "id": top["id"],
        "name": top["name"],
        "confidence": confidence,
        "matches": matches,
        "error": None,
        "suggestion": None,
    }


def resolve_name_and_id(
    name: str | None,
    entity_id: int | None,
    resolve: Callable[[str], dict[str, Any]],
    *,
    entity_label: str = "item",
    required: bool = False,
) -> dict[str, Any]:
    """
    Resolve an entity a caller named by name, by ID, or by both.

    Only an ID: returned as is, without a lookup. Only a name: ``resolve(name)``.
    Both: the name is resolved and must land uniquely on that ID; a different
    entity, no match or an ambiguous name gives ``ok: False``. Neither:
    ``ok: False`` if ``required``, otherwise ``ok`` with ``id: None``.

    Returns the ``resolve_by_name`` shape (ok, id, name, matches, error,
    suggestion).
    """
    if not name and entity_id is None and required:
        return {
            "ok": False,
            "id": None,
            "name": None,
            "matches": [],
            "error": f"Either {entity_label}_name or {entity_label}_id is required",
            "suggestion": None,
        }
    if not name:
        return {
            "ok": True,
            "id": entity_id,
            "name": None,
            "matches": [],
            "error": None,
            "suggestion": None,
        }

    resolved = resolve(name)
    if entity_id is None:
        return resolved
    if resolved["ok"] and int(resolved["id"]) == int(entity_id):
        return resolved

    if resolved["ok"]:
        error = (
            f"{entity_label} name '{name}' matches '{resolved['name']}' "
            f"(ID {resolved['id']}), not ID {entity_id}"
        )
    else:
        error = f"{resolved['error']}; cannot confirm ID {entity_id}"
    return {
        "ok": False,
        "id": None,
        "name": None,
        "matches": resolved.get("matches", []),
        "error": error,
        "suggestion": (
            f"Pass only the {entity_label} name or only its ID, "
            "or a name and an ID of the same one"
        ),
    }


def resolve_object(
    client: GrocyClient,
    object_type: str,
    name: str | None,
    entity_id: int | None,
    *,
    entity_label: str,
    required: bool = False,
    **resolve_kwargs: Any,
) -> dict[str, Any]:
    """``resolve_name_and_id`` for a Grocy object table (products, locations, ...).

    The table is fetched only when a name is given. ``resolve_kwargs`` go to
    ``resolve_by_name``.
    """
    return resolve_name_and_id(
        name,
        entity_id,
        lambda query: resolve_by_name(
            client.get(f"/api/objects/{object_type}"),
            query,
            entity_label=entity_label,
            **resolve_kwargs,
        ),
        entity_label=entity_label,
        required=required,
    )


def resolution_error(resolved: dict[str, Any]) -> dict[str, Any]:
    """The ``{error, matches, suggestion}`` fields of a failed resolution."""
    return {
        "error": resolved["error"],
        "matches": resolved.get("matches", []),
        "suggestion": resolved.get("suggestion"),
    }
