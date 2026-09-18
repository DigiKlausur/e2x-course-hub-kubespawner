from typing import Self

from e2x_course_hub.contract import (
    ResourceTierOption,
    ResourceTierOptions,
)
from pydantic import BaseModel, model_validator


class Resources(BaseModel):
    """Resource specifications for a specific resource tier."""

    cpu_guarantee: float = 0.001
    cpu_limit: float = 2.0
    mem_guarantee: str = "1.0G"
    mem_limit: str = "2.0G"


class ResourceTierDefinition(BaseModel):
    """A definition for a specific resource tier."""

    display_name: str
    description: str
    warning: str | None = None
    metadata: dict[str, str] | None = None
    resources: Resources

    def to_option(self) -> ResourceTierOption:
        return ResourceTierOption(
            display_name=self.display_name,
            description=self.description,
            warning=self.warning,
            metadata=self.metadata,  # This should be key-value from resources
        )


class ResourceTierDefinitions(BaseModel):
    """Definitions for all resource tiers for a specific spawn role."""

    default_tier: str
    tiers: dict[str, ResourceTierDefinition]

    @model_validator(mode="after")
    def _validate_default_tier(self) -> Self:
        if self.default_tier not in self.tiers:
            raise ValueError(
                f"default_tier '{self.default_tier}' not in tiers: {list(self.tiers.keys())}"
            )
        return self

    def assert_resource_selection_exists(self, tier_name: str | None = None) -> None:
        if tier_name and tier_name not in self.tiers:
            raise ValueError(f"Tier '{tier_name}' not found. Available: {list(self.tiers.keys())}")

    def to_options(self) -> ResourceTierOptions:
        return ResourceTierOptions(
            default_tier=self.default_tier,
            tiers={name: tier.to_option() for name, tier in self.tiers.items()},
        )

    def get_resources(self, tier_name: str | None) -> Resources:
        """Get the resources for a given tier name."""
        if tier_name is None:
            return self.tiers[self.default_tier].resources
        tier_definition = self.tiers.get(tier_name)
        if not tier_definition:
            raise ValueError(f"No resource tier definition found for tier name: {tier_name}")
        return tier_definition.resources
