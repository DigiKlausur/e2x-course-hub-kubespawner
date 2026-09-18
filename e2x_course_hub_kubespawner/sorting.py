import re


def parse_term_for_sorting(term: str) -> str:
    """Parse a term string into a sortable key.

    Examples:
        SS25 -> 25-SS
        WS25 -> 25-WS
        Invalid -> Other

    Returns terms in a format that sorts descending as WS25, SS25, WS24, SS24, ...,
    with unparseable terms grouped under "Other".
    """
    if not term:
        return "Other"

    match = re.match(r"^(WS|SS)(\d+)$", term.strip())
    if not match:
        return "Other"

    semester, year = match.groups()
    return f"{year}-{semester}"
