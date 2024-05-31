"""Converts a matrix to a table."""

from typing import Any


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
