import re
from types import SimpleNamespace

import pytest
from e2x_course_hub.contract import (
    CourseReference,
    ImageSelection,
    SpawnOffering,
    SpawnRole,
    SpawnSelection,
)
from jinja2 import Environment, FileSystemLoader

from e2x_course_hub_kubespawner._data import KUBESPAWNER_TEMPLATE_PATH
from e2x_course_hub_kubespawner.loading import load_config
from e2x_course_hub_kubespawner.schemas.spawning import (
    OfferingNotPermittedError,
    OfferingUnavailableError,
)
from e2x_course_hub_kubespawner.spawner_api import K8sSpawnerAPI

USER = SimpleNamespace(username="alice", groups=[])


def offering(
    course_id: str,
    role: SpawnRole,
    family: str = "datascience",
    tier: str = "normal",
) -> SpawnOffering:
    return SpawnOffering(
        course=CourseReference(course_id=course_id, term_id="WS25", course_display_name=course_id),
        selection=SpawnSelection(
            spawn_role=role,
            image=ImageSelection(family=family, tag="2026-07-14"),
            resource_tier_name=tier,
            profile_name="basic",
        ),
    )


# INF101: student works, grader names a removed tier. DB200: its only role names a removed family.
STUDENT_OK = offering("INF101", SpawnRole.STUDENT)
GRADER_UNKNOWN_TIER = offering("INF101", SpawnRole.GRADER, tier="huge")
STUDENT_UNKNOWN_FAMILY = offering("DB200", SpawnRole.STUDENT, family="removed")


class FakeOfferingProvider:
    def __init__(self, offerings: list[SpawnOffering]):
        self.offerings = offerings

    def get_spawn_offerings(self, user):
        return self.offerings


@pytest.fixture
def api(catalog_data, write_catalog) -> K8sSpawnerAPI:
    provider = FakeOfferingProvider([STUDENT_OK, GRADER_UNKNOWN_TIER, STUDENT_UNKNOWN_FAMILY])
    return K8sSpawnerAPI(
        spawn_offering_provider=provider,  # pyright: ignore[reportArgumentType], duck-typed fake
        config=load_config(write_catalog(catalog_data)),
    )


def profile_list(api: K8sSpawnerAPI) -> dict[str, dict]:
    """The profile list as KubeSpawner gets it, keyed by course display name."""
    return {
        entry["display_name"]: entry
        for entry in (e.model_dump() for e in api.get_kubespawner_profile_list(USER))
    }


def choices(entry: dict) -> dict[str, dict]:
    return entry["profile_options"]["profile-slug"]["choices"]


def test_only_the_broken_role_is_unavailable(api):
    inf101 = choices(profile_list(api)["INF101 - WS25"])

    assert inf101["INF101.WS25.student"]["unavailable"] is False
    student_image = inf101["INF101.WS25.student"]["kubespawner_override"]["image"]
    assert student_image.endswith("ds-student:2026-07-14")
    assert inf101["INF101.WS25.grader"]["unavailable"] is True
    assert inf101["INF101.WS25.grader"]["kubespawner_override"] == {}


def test_course_with_only_broken_roles_is_still_listed(api):
    db200 = choices(profile_list(api)["DB200 - WS25"])

    assert db200["DB200.WS25.student"]["unavailable"] is True


def test_unavailable_offering_is_logged(api, caplog):
    profile_list(api)

    assert "role='grader'" in caplog.text
    assert "Resource tier 'huge' not found" in caplog.text


def test_resolve_raises_for_unavailable_offering(api):
    with pytest.raises(OfferingUnavailableError) as exc_info:
        api.resolve(USER, GRADER_UNKNOWN_TIER)

    assert "instructor" in exc_info.value.jupyterhub_message
    assert "Resource tier 'huge' not found" in str(exc_info.value)


def test_resolve_works_for_available_offering(api):
    resolved = api.resolve(USER, STUDENT_OK)

    assert resolved.runtime.image.tag == "2026-07-14"


def test_resolve_rejects_offering_of_another_user(api):
    with pytest.raises(OfferingNotPermittedError):
        api.resolve(USER, offering("OTHER", SpawnRole.STUDENT))


# Template


def render_form(api: K8sSpawnerAPI) -> str:
    env = Environment(loader=FileSystemLoader(KUBESPAWNER_TEMPLATE_PATH))
    entries = list(profile_list(api).values())
    for entry in entries:
        entry["slug"] = entry["display_name"].lower().replace(" - ", "-")  # set by KubeSpawner
    return env.get_template("form.html").render(profile_list=entries)


def test_form_shows_notice_and_disabled_button(api):
    html = render_form(api)

    assert "Some environments for this course are unavailable." in html
    assert "This course is currently unavailable." in html
    assert "Launch grader (unavailable)</button>" in html


def elements_with_class(html: str, css_class: str) -> int:
    """Count elements whose class attribute contains *css_class* (ignores the page's JS)."""
    return len(re.findall(rf'class="[^"]*\b{css_class}\b[^"]*"', html))


def test_form_keeps_unavailable_roles_out_of_auto_spawn(api):
    html = render_form(api)

    # Three role buttons in total, only the working student role can be launched
    assert elements_with_class(html, "js-role") == 3
    assert elements_with_class(html, "js-launch-role") == 1
