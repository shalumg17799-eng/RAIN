"""Typed errors raised by the skills core."""

from typing import Literal

SkillPhase = Literal["input", "execution", "output", "label"]


class SkillNotFoundError(LookupError):
    """No such skill (or no such version of it) is loaded."""


class SkillError(Exception):
    """A skill call failed its contract or raised. The engine turns this into a failed run."""

    def __init__(self, skill: str, version: str, phase: SkillPhase, message: str) -> None:
        super().__init__(f"{skill}@{version} [{phase}]: {message}")
        self.skill = skill
        self.version = version
        self.phase = phase
        self.message = message
