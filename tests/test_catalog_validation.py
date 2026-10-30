import logging
from types import SimpleNamespace

import pytest
from tornado.web import HTTPError

from e2x_course_hub_kubespawner.cli import main
from e2x_course_hub_kubespawner.errors import CatalogValidationError
from e2x_course_hub_kubespawner.hooks import CATALOG_UNAVAILABLE_MESSAGE, get_profile_list_hook
from e2x_course_hub_kubespawner.loading import load_config, load_infrastructure_catalog


def load(config_file):
    return load_infrastructure_catalog(load_config(config_file))


def assert_invalid(config_file, *expected: str) -> list[str]:
    """Assert loading fails and every expected text appears in one of the errors."""
    with pytest.raises(CatalogValidationError) as exc_info:
        load(config_file)
    errors = exc_info.value.errors
    for text in expected:
        assert any(text in error for error in errors), f"{text!r} not in {errors}"
    return errors


def test_valid_catalog_loads(catalog_data, write_catalog):
    catalog = load(write_catalog(catalog_data))

    assert set(catalog.spawn_role_definitions) == {"student", "grader"}


# Every spawn role is required everywhere


def test_image_family_requires_every_role(catalog_data, write_catalog):
    del catalog_data["images.yaml"]["families"]["datascience"]["images"]["grader"]

    assert_invalid(write_catalog(catalog_data), "images.yaml", "missing: ['grader']")


def test_resource_tiers_require_every_role(catalog_data, write_catalog):
    del catalog_data["tiers.yaml"]["student"]

    assert_invalid(write_catalog(catalog_data), "tiers.yaml", "missing: ['student']")


def test_resource_tiers_reject_unknown_role(catalog_data, write_catalog):
    catalog_data["tiers.yaml"]["grader-readonly"] = catalog_data["tiers.yaml"]["grader"]

    assert_invalid(write_catalog(catalog_data), "tiers.yaml", "grader-readonly")


def test_config_requires_profiles_for_every_role(catalog_data, write_catalog):
    del catalog_data["config.yaml"]["profiles"]["grader"]

    assert_invalid(write_catalog(catalog_data), "config.yaml", "missing: ['grader']")


# Typos in keys


def test_unknown_keys_are_rejected(catalog_data, write_catalog):
    catalog_data["grader.yaml"]["has_archive_mount"] = True

    assert_invalid(write_catalog(catalog_data), "grader.yaml", "has_archive_mount")


# Dry-run of every profile


def test_unknown_mount_in_profile(catalog_data, write_catalog):
    catalog_data["student.yaml"]["mounts"].append("exchange")

    assert_invalid(
        write_catalog(catalog_data), "Profile 'basic' of role 'student'", "Mount 'exchange'"
    )


def test_unknown_placeholder_key(catalog_data, write_catalog):
    catalog_data["student.yaml"]["environment"]["NB_USER"] = "${{inputs.usr}}"

    assert_invalid(write_catalog(catalog_data), "environment", "Parameter 'usr'")


def test_malformed_placeholder(catalog_data, write_catalog):
    catalog_data["mounts.yaml"]["student_home"]["subPath"] = "students/${{input.username}}"

    assert_invalid(write_catalog(catalog_data), "mounts", "Malformed placeholder")


def test_archive_mounts_conflict_without_term_in_mount_path(catalog_data, write_catalog):
    catalog_data["mounts.yaml"]["course_term"]["mountPath"] = "/home/${{inputs.username}}/course"

    assert_invalid(write_catalog(catalog_data), "role 'grader'", "Conflicting mounts")


# Error collection


def test_errors_from_several_files_are_collected(catalog_data, write_catalog):
    del catalog_data["tiers.yaml"]["student"]
    catalog_data["student.yaml"]["has_archive_mount"] = True

    errors = assert_invalid(write_catalog(catalog_data), "tiers.yaml", "student.yaml")
    assert len(errors) == 2


def test_missing_file_is_reported(catalog_data, write_catalog):
    del catalog_data["mounts.yaml"]

    assert_invalid(write_catalog(catalog_data), "mounts.yaml")


# CLI


def test_cli_accepts_valid_catalog(catalog_data, write_catalog, capsys):
    assert main([str(write_catalog(catalog_data))]) == 0
    assert "Catalog is valid" in capsys.readouterr().out


def test_cli_lists_problems_of_invalid_catalog(catalog_data, write_catalog, capsys):
    del catalog_data["tiers.yaml"]["student"]

    assert main([str(write_catalog(catalog_data))]) == 1
    assert "missing: ['student']" in capsys.readouterr().err


# Runtime


def test_hook_shows_unavailable_page_for_invalid_catalog(catalog_data, write_catalog, caplog):
    config_file = write_catalog(catalog_data)
    config = load_config(config_file)
    (config_file.parent / "student.yaml").write_text("display_name: [unclosed")
    spawner = SimpleNamespace(
        user=SimpleNamespace(name="alice", groups=[]),
        log=logging.getLogger("test-spawner"),
    )
    hook = get_profile_list_hook(spawn_offering_provider=None, config=config)  # pyright: ignore[reportArgumentType], not reached

    with pytest.raises(HTTPError) as exc_info:
        hook(spawner)

    assert exc_info.value.status_code == 503
    assert exc_info.value.log_message == CATALOG_UNAVAILABLE_MESSAGE
    assert "student.yaml" in caplog.text
