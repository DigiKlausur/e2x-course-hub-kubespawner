"""Orchestrates loading the full infrastructure catalog from the files a Config points to."""

from e2x_course_hub.contract import SpawnRole

from .schemas.catalog import InfrastructureCatalogDefinitions
from .schemas.config import Config, ProfileConfig
from .schemas.image import ImageFamilyDefinitions
from .schemas.mount import MountDefinitions
from .schemas.profiles import ProfileDefinition, ProfileDefinitions
from .schemas.resources import ResourceTierDefinitions
from .utils import load_yaml


def load_profile_definitions(profile_config: ProfileConfig) -> ProfileDefinitions:
    """Load and return the profile definitions from the specified files."""
    profile_definitions = {}
    for profile_name, profile_file in profile_config.profiles.items():
        profile_data = load_yaml(profile_file)
        profile_definitions[profile_name] = ProfileDefinition(**profile_data)
    return ProfileDefinitions(
        default_profile=profile_config.default_profile,
        profiles=profile_definitions,
    )


def load_mount_catalog(config: Config) -> MountDefinitions:
    """Load and return the mount catalog from the specified file."""
    return MountDefinitions.from_config_file(config.mount_catalog_file)


def _load_image_family_definitions(config: Config) -> ImageFamilyDefinitions:
    """Load and return the image family definitions from the specified file."""
    image_family_data = load_yaml(config.image_catalog_file)
    return ImageFamilyDefinitions(**image_family_data)


def _load_resource_tier_definitions(
    config: Config, spawn_role: SpawnRole
) -> ResourceTierDefinitions | None:
    """Load and return the resource tier definitions from the specified file."""
    resource_tier_data = load_yaml(config.resource_tier_catalog_file)
    if spawn_role.value not in resource_tier_data:
        return None
    return ResourceTierDefinitions(**resource_tier_data[spawn_role.value])


def load_infrastructure_catalog(config: Config) -> InfrastructureCatalogDefinitions:
    """Load and return the complete infrastructure catalog definitions."""
    image_family_definitions = _load_image_family_definitions(config)
    spawn_role_definitions = {}
    for spawn_role in SpawnRole:
        profile_config = config.profiles.get(spawn_role)
        if profile_config is None:
            continue
        profile_definitions = load_profile_definitions(profile_config)
        resource_tier_definitions = _load_resource_tier_definitions(config, spawn_role)
        if resource_tier_definitions is None:
            continue
        spawn_role_definitions[spawn_role] = {
            "profile_definitions": profile_definitions,
            "resource_tier_definitions": resource_tier_definitions,
        }
    return InfrastructureCatalogDefinitions(
        image_family_definitions=image_family_definitions,
        spawn_role_definitions=spawn_role_definitions,
    )
