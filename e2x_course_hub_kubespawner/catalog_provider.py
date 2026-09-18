from e2x_course_hub.contract import (
    InfrastructureCatalogOptions,
)

from .loading import load_infrastructure_catalog
from .schemas.config import Config
from .settings import K8sSpawnerSettings


class K8sInfrastructureCatalog:
    def __init__(self, config: Config | None = None):
        settings = K8sSpawnerSettings()  # pyright: ignore[reportCallIssue], config_file comes from env
        config = config or Config.from_yaml(settings.config_file)
        self._catalog = load_infrastructure_catalog(config)

    @property
    def options(self) -> InfrastructureCatalogOptions:
        return self._catalog.to_options()


class K8sInfrastructureCatalogProvider:
    """Provides the infrastructure catalog for the K8s spawner."""

    @classmethod
    def get_infrastructure_catalog(cls) -> InfrastructureCatalogOptions:
        return K8sInfrastructureCatalog().options
