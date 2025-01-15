"""Converts a matrix to a table."""

from datetime import timedelta
from typing import Any


def _format_timedelta(time: timedelta) -> str:
    seconds = int(time.total_seconds())
    days = time.days

    messages = [
        (seconds < 10, "just now"),
        (seconds < 60, f"{seconds} seconds ago"),
        (seconds < 120, "a minute ago"),
        (seconds < 3600, f"{seconds // 60} minutes ago"),
        (seconds < 7200, "an hour ago"),
        (seconds < 86400, f"{seconds // 3600} hours ago"),
        (days == 1, "Yesterday"),
        (days < 7, f"{days} days ago"),
        (days < 14, "a week ago"),
        (days < 31, f"{days // 7} weeks ago"),
        (days < 62, "a month ago"),
        (days < 365, f"{days // 30} months ago"),
        (days < 730, "a year ago"),
        (True, f"{days // 365} years ago"),
    ]

    return next(message for condition, message in messages if condition)


def _column_widths(matrix: list[list[Any]], padding: int) -> list[int]:
    matrix_height = len(matrix)
    matrix_width = len(matrix[0])

    widths: list[int] = []

    for x in range(matrix_width):
        width = 0

        for y in range(matrix_height):
            cell: Any = matrix[y][x]
            width = len(_format(cell)) if len(_format(cell)) > width else width

        widths += [width + padding]

    return widths


def _format(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,}"

    if isinstance(value, timedelta):
        return _format_timedelta(value)

    return str(value).title()


def pretty(
    matrix: list[list[Any]],
    padding: int = 2,
    ignore: list[str] | None = None,
) -> str:
    """Create a space-aligned table for monospace fonts."""
    matrix_height = len(matrix)
    matrix_width = len(matrix[0])

    table = ""
    widths = _column_widths(matrix, padding)

    for y in range(matrix_height):
        for x in range(matrix_width):
            if ignore and matrix[0][x] in ignore:
                data = str(matrix[y][x])
            else:
                data = _format(matrix[y][x])

            table += data.ljust(widths[x], " ")

        table += "\n"

    return table


def tabbed(matrix: list[list[Any]]) -> str:
    """Create a tab-seperated table."""
    matrix_height = len(matrix)
    matrix_width = len(matrix[0])

    table = ""

    for y in range(matrix_height):
        for x in range(matrix_width):
            table += _format(matrix[y][x]) + "\t"

        table = table.rstrip("\t") + "\n"

    return table
