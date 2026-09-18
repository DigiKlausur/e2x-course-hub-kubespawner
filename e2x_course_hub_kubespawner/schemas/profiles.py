from typing import Self

from e2x_course_hub.contract import (
    ProfileOption,
    ProfileOptions,
)
from pydantic import BaseModel, model_validator

from ..utils import PlaceholderContext, resolve_placeholders


class ProfileDefinition(BaseModel):
    """A profile definition for a specific spawn role."""

    display_name: str
    description: str | None = None
    environment: dict[str, str | float | int | bool] = {}
    mounts: list[str] = []
    has_archive_mounts: bool = False

    def to_option(self) -> ProfileOption:
        """Convert the profile definition to a ProfileOption."""
        return ProfileOption(
            display_name=self.display_name,
            description=self.description,
        )

    def resolve_environment(self, ctx: PlaceholderContext) -> dict[str, str | float | int | bool]:
        """Resolve placeholders in the environment using the standard context."""
        return resolve_placeholders(self.environment, ctx)


class ProfileDefinitions(BaseModel):
    """A collection of profile definitions for a specific spawn role."""

    default_profile: str
    profiles: dict[str, ProfileDefinition]

    @model_validator(mode="after")
    def _validate_default_profile(self) -> Self:
        if self.default_profile not in self.profiles:
            raise ValueError(
                f"default_profile '{self.default_profile}' "
                f"not in profiles: {list(self.profiles.keys())}"
            )
        return self

    def to_options(self) -> ProfileOptions:
        """Convert the profile definitions to ProfileOptions."""
        return ProfileOptions(
            default_profile=self.default_profile,
            profiles={name: profile.to_option() for name, profile in self.profiles.items()},
        )

    def get_profile_definition(self, profile_name: str | None) -> ProfileDefinition:
        """Get the profile definition for a given profile name."""
        if profile_name is None:
            return self.profiles[self.default_profile]
        profile_definition = self.profiles.get(profile_name)
        if not profile_definition:
            raise ValueError(f"No profile definition found for profile name: {profile_name}")
        return profile_definition
