"""Orchestrates loading the full infrastructure catalog from the files a Config points to.

Every file is loaded even if an earlier one fails, so all problems are reported at once
in a single CatalogValidationError.
"""

from pathlib import Path
from typing import TypeVar

import yaml
from e2x_course_hub.contract import SpawnRole
from pydantic import BaseModel

from .errors import CatalogValidationError
from .schemas.catalog import InfrastructureCatalogDefinitions, SpawnRoleDefinitions
from .schemas.config import Config, ProfileConfig
from .schemas.image import ImageFamilyDefinitions
from .schemas.mount import MountDefinitions
from .schemas.profiles import ProfileDefinition, ProfileDefinitions
from .schemas.resources import ResourceTierCatalog
from .utils import load_yaml
from .validation import find_catalog_errors

# Everything that can go wrong reading or validating a file.
# ValueError covers pydantic's ValidationError and our CatalogError.
_LOAD_ERRORS = (OSError, yaml.YAMLError, TypeError, ValueError)

Model = TypeVar("Model", bound=BaseModel)


def load_config(config_file: Path) -> Config:
    """Load the top-level config file, raising a CatalogValidationError if it is invalid."""
    try:
        return Config.from_yaml(config_file)
    except _LOAD_ERRORS as e:
        raise CatalogValidationError([f"{config_file}: {e}"]) from e


def _load_model(model: type[Model], path: Path, errors: list[str]) -> Model | None:
    """Load a YAML file into *model*; on failure record the error and return None."""
    try:
        return model.model_validate(load_yaml(path))
    except _LOAD_ERRORS as e:
        errors.append(f"{path}: {e}")
        return None


def _load_profiles(
    profile_config: ProfileConfig, errors: list[str]
) -> dict[str, ProfileDefinition]:
    """Load the profile files of one role, skipping (and recording) the ones that fail."""
    profiles = {}
    for name, path in profile_config.profiles.items():
        profile = _load_model(ProfileDefinition, path, errors)
        if profile is not None:
            profiles[name] = profile
    return profiles


def load_infrastructure_catalog(config: Config) -> InfrastructureCatalogDefinitions:
    """
    Load and validate the complete infrastructure catalog definitions.

    Raises:
        CatalogValidationError: With every problem found in the catalog files.
    """
    errors: list[str] = []
    image_families = _load_model(ImageFamilyDefinitions, config.image_catalog_file, errors)
    resource_tiers = _load_model(ResourceTierCatalog, config.resource_tier_catalog_file, errors)
    mounts = _load_model(MountDefinitions, config.mount_catalog_file, errors)
    profiles = {role: _load_profiles(config.profiles[role], errors) for role in SpawnRole}

    # The None checks are implied by errors, but tell the type checker the files were loaded
    if errors or image_families is None or resource_tiers is None or mounts is None:
        raise CatalogValidationError(errors)

    catalog = InfrastructureCatalogDefinitions(
        image_family_definitions=image_families,
        spawn_role_definitions={
            role: SpawnRoleDefinitions(
                profile_definitions=ProfileDefinitions(
                    default_profile=config.profiles[role].default_profile,
                    profiles=profiles[role],
                ),
                resource_tier_definitions=resource_tiers.root[role],
            )
            for role in SpawnRole
        },
        mount_definitions=mounts,
    )

    errors = find_catalog_errors(catalog)
    if errors:
        raise CatalogValidationError(errors)
    return catalog
