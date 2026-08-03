"""Generation provider boundary; jobs depend on this contract, never on Qwen directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class ProviderName(StrEnum):
    QWEN = "qwen"
    OMNIGEN = "omnigen"
    FLUX = "flux"


@dataclass(frozen=True)
class ProviderDescriptor:
    name: ProviderName
    model_version: str
    revision: str
    license_name: str
    production_eligible: bool


class MascotGenerationProvider(ABC):
    descriptor: ProviderDescriptor

    @abstractmethod
    def generate(self, references: list[bytes], prompt: str, seed: int) -> bytes:
        """Generate one PNG. Concrete providers run only inside a GPU worker."""


QWEN = ProviderDescriptor(ProviderName.QWEN, "Qwen-Image-Edit-2511", "main", "Apache-2.0", True)
OMNIGEN = ProviderDescriptor(ProviderName.OMNIGEN, "OmniGen2", "main", "Apache-2.0", True)
FLUX = ProviderDescriptor(ProviderName.FLUX, "FLUX.2-klein-9B", "main", "FLUX Non-Commercial", False)
