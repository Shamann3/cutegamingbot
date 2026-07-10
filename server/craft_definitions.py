"""Рецепты крафта — re-export из content_registry (БД + fallback)."""

from __future__ import annotations

from content_registry import (
    CraftRecipeDef,
    enabled_craft_recipes,
    find_recipe_by_ingredient_pair,
    get_craft_recipe,
    ingredient_pair_key,
    validate_craft_recipes,
)

CRAFT_RECIPES = ()

__all__ = [
    "CRAFT_RECIPES",
    "CraftRecipeDef",
    "enabled_craft_recipes",
    "find_recipe_by_ingredient_pair",
    "get_craft_recipe",
    "ingredient_pair_key",
    "validate_craft_recipes",
]
