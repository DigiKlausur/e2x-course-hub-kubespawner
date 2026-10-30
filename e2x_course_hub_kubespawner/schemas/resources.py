from typing import Self

from e2x_course_hub.contract import (
    ResourceTierOption,
    ResourceTierOptions,
    SpawnRole,
)
from pydantic import BaseModel, ConfigDict, RootModel, model_validator

from ..errors import UnknownResourceTierError
from ..utils import require_all_spawn_roles


class Resources(BaseModel):
    """Resource specifications for a specific resource tier."""

    model_config = ConfigDict(extra="forbid")

    cpu_guarantee: float = 0.001
    cpu_limit: float = 2.0
    mem_guarantee: str = "1.0G"
    mem_limit: str = "2.0G"


class ResourceTierDefinition(BaseModel):
    """A definition for a specific resource tier."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
            raise UnknownResourceTierError(tier_name, self.tiers)

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
            raise UnknownResourceTierError(tier_name, self.tiers)
        return tier_definition.resources


class ResourceTierCatalog(RootModel[dict[SpawnRole, ResourceTierDefinitions]]):
    """The resource tier file: the tier definitions of every spawn role, keyed by role."""

    @model_validator(mode="after")
    def _require_tiers_for_all_roles(self) -> Self:
        require_all_spawn_roles(self.root, "resource tiers")
        return self
