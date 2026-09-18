from e2x_course_hub.contract import (
    InfrastructureCatalogOptions,
    SpawnRole,
    SpawnRoleOptions,
    SpawnSelection,
)
from pydantic import BaseModel

from .image import Image, ImageFamilyDefinitions
from .profiles import ProfileDefinition, ProfileDefinitions
from .resources import Resources, ResourceTierDefinitions


class SpawnRoleDefinitions(BaseModel):
    """Definitions for a specific spawn role, including profiles and resource tiers."""

    profile_definitions: ProfileDefinitions
    resource_tier_definitions: ResourceTierDefinitions

    def to_options(self) -> SpawnRoleOptions:
        return SpawnRoleOptions(
            profile_options=self.profile_definitions.to_options(),
            resource_tier_options=self.resource_tier_definitions.to_options(),
        )


class InfrastructureCatalogDefinitions(BaseModel):
    """The complete infrastructure catalog definitions, including image families and spawn roles."""

    image_family_definitions: ImageFamilyDefinitions
    spawn_role_definitions: dict[SpawnRole, SpawnRoleDefinitions]

    def to_options(self) -> InfrastructureCatalogOptions:
        return InfrastructureCatalogOptions(
            image_family_options=self.image_family_definitions.to_options(),
            spawn_role_options={
                role: definitions.to_options()
                for role, definitions in self.spawn_role_definitions.items()
            },
        )

    def get_profile_for_selection(self, spawn_selection: SpawnSelection) -> ProfileDefinition:
        """
        Get the profile definition for a given spawn selection.
        Args:
            spawn_selection (SpawnSelection): The spawn selection to get the profile for.
        Returns:
            ProfileDefinition: The profile definition corresponding to the spawn selection.
        """
        role_definitions = self.spawn_role_definitions.get(spawn_selection.spawn_role)
        if not role_definitions:
            raise ValueError(f"No definitions found for spawn role: {spawn_selection.spawn_role}")

        return role_definitions.profile_definitions.get_profile_definition(
            spawn_selection.profile_name
        )

    def get_resources_for_selection(self, spawn_selection: SpawnSelection) -> Resources:
        """
        Get the resources for a given spawn selection.
        Args:
            spawn_selection (SpawnSelection): The spawn selection to get the resources for.
        Returns:
            Resources: The resources corresponding to the spawn selection.
        """
        role_definitions = self.spawn_role_definitions.get(spawn_selection.spawn_role)
        if not role_definitions:
            raise ValueError(f"No definitions found for spawn role: {spawn_selection.spawn_role}")

        return role_definitions.resource_tier_definitions.get_resources(
            spawn_selection.resource_tier_name
        )

    def get_image_for_selection(self, spawn_selection: SpawnSelection) -> Image:
        """
        Get the image for a given spawn selection.
        Args:
            spawn_selection (SpawnSelection): The spawn selection to get the image for.
        Returns:
            Image: The image corresponding to the spawn selection.
        """
        return self.image_family_definitions.get_image_for_selection(spawn_selection)
