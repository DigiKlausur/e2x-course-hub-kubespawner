import os

"""Get the data files for this package."""


def get_data_files():
    """Walk up until we find share/e2x_course_hub_kubespawner"""
    import sys
    from os.path import abspath, dirname, exists, join, split

    path = abspath(dirname(__file__))
    starting_points = [path]
    if not path.startswith(sys.prefix):
        starting_points.append(sys.prefix)
    for path in starting_points:
        # walk up, looking for prefix/share/jupyter
        while path != "/":
            share_e2x_course_hub = join(path, "share", "e2x_course_hub_kubespawner")
            if exists(share_e2x_course_hub):
                return share_e2x_course_hub
            path, _ = split(path)
    # didn't find it, give up
    return ""


# Package managers can just override this with the appropriate constant
DATA_FILES_PATH = get_data_files()
KUBESPAWNER_TEMPLATE_PATH = os.path.join(DATA_FILES_PATH, "templates", "kubespawner")
JUPYTERHUB_TEMPLATE_PATH = os.path.join(DATA_FILES_PATH, "templates", "jupyterhub")
