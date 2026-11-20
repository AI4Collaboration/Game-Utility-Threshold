"""Separate, versioned Design 1 experiments; never mutate canonical games."""

from .games import GAMES, PrivateGame, get_game

__all__ = ["GAMES", "PrivateGame", "get_game"]
