"""Settings for locating this provider's own catalog configuration.

Read from the environment so ``K8sInfrastructureCatalogProvider`` can be built
with no constructor arguments, as required by the
``e2x_course_hub.infrastructure_catalog_providers`` entry point contract.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class K8sSpawnerSettings(BaseSettings):
    config_file: Path = Field(validation_alias="E2X_KUBESPAWNER_CONFIG_FILE")
