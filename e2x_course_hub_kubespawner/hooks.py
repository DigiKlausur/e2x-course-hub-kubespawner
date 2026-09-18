from dataclasses import dataclass
from typing import Callable

from e2x_course_hub.contract import SpawnOfferingProvider
from traitlets.config import Config as TraitletsConfig

from .schemas.config import Config
from .spawner_api import K8sSpawnerAPI


@dataclass
class User:
    username: str
    groups: list[str]


def get_profile_list_hook(
    spawn_offering_provider: SpawnOfferingProvider,
    config: Config | None = None,
    sorter: Callable[[str], str] | None = None,
) -> Callable:
    """
    Returns a hook function to retrieve the Kubespawner profile list for a user.

    Args:
        sorter (Callable[[str], str], optional): A function that takes a term_id string
            and returns a sortable string. Defaults to parse_term_for_sorting.
            Example: lambda term: term  # Simple alphabetical sorting
    Returns:
        Callable: The hook function.
    """

    def hook(spawner):
        user = User(
            username=spawner.user.name,
            groups=[g.name for g in spawner.user.groups],
        )
        api = K8sSpawnerAPI(
            spawn_offering_provider=spawn_offering_provider,
            config=config,
            sorter=sorter,
        )
        return [entry.model_dump() for entry in api.get_kubespawner_profile_list(user)]

    return hook


def get_pre_spawn_hook(
    spawn_offering_provider: SpawnOfferingProvider,
    config: Config | None = None,
) -> Callable:
    """
    Returns a hook function to be called before spawning a user's server.

    Args:
        spawn_offering_provider (SpawnOfferingProvider): The provider for spawn offerings.
        config (Config, optional): The configuration object. Defaults to None.

    Returns:
        Callable: The pre-spawn hook function.
    """

    def hook(spawner):
        user = User(
            username=spawner.user.name,
            groups=[g.name for g in spawner.user.groups],
        )
        api = K8sSpawnerAPI(
            spawn_offering_provider=spawn_offering_provider,
            config=config,
        )
        spawner.log.debug(f"User options are: {spawner.user_options}")
        choice_slug = spawner.user_options.get("profile-slug")
        offering = api.get_offering_from_choice_slug(user, choice_slug)
        resolved_offering = api.resolve(user, offering)
        spawner.volume_mounts = [
            mount.model_dump(exclude_unset=True, exclude_none=True, exclude=set(["description"]))
            for mount in resolved_offering.mounts
        ]

    return hook


def configure_autospawn(
    jupyterhub_config: TraitletsConfig,
    auto_spawn_single_course: bool = False,
    auto_spawn_countdown: int = 5,
):
    """
    Configures the autospawn hooks in the given JupyterHub config.

    Args:
        config (Config): The JupyterHub configuration object to modify.
        auto_spawn_single_course (bool): Whether to auto-spawn a single course if only
            one profile is available.
        auto_spawn_countdown (int): The countdown time in seconds before auto-spawning.
    """
    if jupyterhub_config.JupyterHub.template_vars is None:
        jupyterhub_config.JupyterHub.template_vars = {}

    jupyterhub_config.JupyterHub.template_vars.update(
        {
            "auto_spawn_single_course": auto_spawn_single_course,
            "auto_spawn_countdown": auto_spawn_countdown,
        }
    )
