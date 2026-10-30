"""Checks a loaded catalog by resolving every profile the way a spawn would.

Using the same code as spawning means a catalog that passes cannot fail later on
placeholders, unknown mounts or conflicting mount paths.
"""

from .errors import CatalogError
from .schemas.catalog import InfrastructureCatalogDefinitions
from .utils import PlaceholderContext

_SAMPLE_CONTEXT = PlaceholderContext(
    username="validation-user",
    course_id="validation-course",
    term_id="validation-term",
)
# A second term, so archive mounts are checked against the mounts of the current term
_SAMPLE_ARCHIVE_TERM_ID = "validation-archive-term"


def find_catalog_errors(catalog: InfrastructureCatalogDefinitions) -> list[str]:
    """Resolve the environment and mounts of every profile, returning all errors found."""
    errors = []
    for role, role_definitions in catalog.spawn_role_definitions.items():
        for name, profile in role_definitions.profile_definitions.profiles.items():
            where = f"Profile '{name}' of role '{role.value}'"
            try:
                profile.resolve_environment(_SAMPLE_CONTEXT)
            except CatalogError as e:
                errors.append(f"{where}, environment: {e}")
            try:
                catalog.resolve_mounts(
                    profile, _SAMPLE_CONTEXT, archive_term_ids=[_SAMPLE_ARCHIVE_TERM_ID]
                )
            except CatalogError as e:
                errors.append(f"{where}, mounts: {e}")
    return errors
