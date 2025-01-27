"""
Support for pyproject.toml.

There are two ways of declaring Python versions in a pyproject.toml:
classifiers like

    Programming Language :: Python :: 3.8

and tool.poetry.dependencies.python keyword.

check-python-versions supports both.
"""
import io
from io import StringIO
from typing import List, Optional, TextIO, Union, cast

from tomlkit import TOMLDocument, dumps, load

from .base import Source
from .setup_py import (
    compute_python_requires,
    get_versions_from_classifiers,
    parse_python_requires,
    update_classifiers,
)
from ..utils import FileLines, FileOrFilename, is_file_object, open_file, warn
from ..versions import SortedVersionList


PYPROJECT_TOML = 'pyproject.toml'

CLASSIFIERS = 'classifiers'
DEPENDENCIES = 'dependencies'
PYTHON = 'python'
PYTHON_REQUIRES = 'requires-python'

# poetry TOML keywords
TOOL = 'tool'
POETRY = 'poetry'
BUILD_SYSTEM = 'build-system'
BUILD_BACKEND = 'build-backend'
REQUIRES = 'requires'

# setuptools TOML keywords
PROJECT = 'project'
SETUPTOOLS = 'setuptools'

# flit TOML keywords
FLIT = 'flit'


def load_toml(filename: FileOrFilename) -> Optional[TOMLDocument]:
    """Utility method that returns a TOMLDocument."""
    table: Optional[TOMLDocument] = None
    # tomlkit has two different API to load from file name or file object
    if isinstance(filename, str) or isinstance(filename, StringIO):
        with open_file(filename) as fp:
            table = load(fp)
    if isinstance(filename, io.TextIOWrapper):
        table = load(filename)
    return table


def is_poetry_toml(table: TOMLDocument) -> bool:
    """Utility method to know if pyproject.toml is for poetry."""

    if POETRY in table.get(TOOL, {}):
        return True

    if BUILD_SYSTEM in table:
        if POETRY in table[BUILD_SYSTEM].get(BUILD_BACKEND, ''):
            return True
        if any(POETRY in x for x in table[BUILD_SYSTEM].get(REQUIRES, [])):
            return True

    return False


def is_setuptools_toml(table: TOMLDocument) -> bool:
    """Utility method to know if pyproject.toml is for setuptool."""

    if BUILD_SYSTEM in table:
        if SETUPTOOLS in table[BUILD_SYSTEM].get(BUILD_BACKEND, ''):
            return True
        if any(SETUPTOOLS in x for x in table[BUILD_SYSTEM].get(REQUIRES, [])):
            return True

    #  "[tool.setuptools] table is still in beta"
    #  "These configurations are completely optional
    #    and probably can be skipped when creating simple packages"
    if SETUPTOOLS in table.get(TOOL, {}):
        return True

    return False


def is_flit_toml(table: TOMLDocument) -> bool:
    """Utility method to know if pyproject.toml is for flit."""

    if FLIT in table.get(TOOL, {}):
        return True

    if BUILD_SYSTEM in table:
        if FLIT in table[BUILD_SYSTEM].get(BUILD_BACKEND, ''):
            return True
        if any(FLIT in x for x in table[BUILD_SYSTEM].get(REQUIRES, [])):
            return True

    return False


def _get_poetry_classifiers(table: TOMLDocument) -> List[str]:
    if TOOL not in table:
        return []
    if POETRY not in table[TOOL]:
        return []
    if CLASSIFIERS not in table[TOOL][POETRY]:
        return []
    return cast(List[str], table[TOOL][POETRY][CLASSIFIERS])


def _get_setuptools_flit_classifiers(table: TOMLDocument) -> List[str]:
    if PROJECT not in table:
        return []
    if CLASSIFIERS not in table[PROJECT]:
        return []
    return cast(List[str], table[PROJECT][CLASSIFIERS])


def _get_pyproject_toml_classifiers(
    filename: FileOrFilename = PYPROJECT_TOML,
) -> List[str]:
    _classifiers = []
    table = load_toml(filename)
    if is_poetry_toml(table):
        _classifiers = _get_poetry_classifiers(table)
    if is_setuptools_toml(table) or is_flit_toml(table):
        _classifiers = _get_setuptools_flit_classifiers(table)

    return _classifiers


def _get_poetry_python_requires(table: TOMLDocument) -> Optional[str]:
    if TOOL not in table:
        return None
    if POETRY not in table[TOOL]:
        return None
    if DEPENDENCIES not in table[TOOL][POETRY]:
        return None
    if PYTHON not in table[TOOL][POETRY][DEPENDENCIES]:
        return None
    return cast(str, table[TOOL][POETRY][DEPENDENCIES][PYTHON])


def _get_setuptools_flit_python_requires(table: TOMLDocument) -> Optional[str]:
    if PROJECT not in table:
        return None
    if PYTHON_REQUIRES not in table[PROJECT]:
        return None
    return cast(str, table[PROJECT][PYTHON_REQUIRES])


def _get_pyproject_toml_python_requires(
    filename: FileOrFilename = PYPROJECT_TOML,
) -> Optional[str]:
    _python_requires = None
    table = load_toml(filename)
    if is_poetry_toml(table):
        _python_requires = _get_poetry_python_requires(table)
    if is_setuptools_toml(table) or is_flit_toml(table):
        _python_requires = _get_setuptools_flit_python_requires(table)

    return _python_requires


def get_supported_python_versions(
    filename: FileOrFilename = PYPROJECT_TOML,
) -> SortedVersionList:
    """Extract supported Python versions from classifiers in pyproject.toml."""
    classifiers = _get_pyproject_toml_classifiers(filename)

    if not classifiers:
        # classifier can be an empty list when nothing found
        return []

    if not isinstance(classifiers, list):
        warn('The value specified for classifiers is not an array')
        return []

    return get_versions_from_classifiers(classifiers)


def get_python_requires(
    pyproject_toml: FileOrFilename = PYPROJECT_TOML,
) -> Optional[SortedVersionList]:
    """Extract supported Python versions from python_requires in
    pyproject.toml."""
    python_requires = _get_pyproject_toml_python_requires(pyproject_toml)
    if not python_requires or not isinstance(python_requires, str):
        # python_requires can be None
        warn('The value specified for python dependency is not a string')
        return None
    return parse_python_requires(python_requires)


def update_supported_python_versions(
    filename: FileOrFilename,
    new_versions: SortedVersionList,
) -> Optional[FileLines]:
    """Update classifiers in a pyproject.toml.

    Does not touch the file but returns a list of lines with new file contents.
    """
    classifiers = _get_pyproject_toml_classifiers(filename)
    # classifiers is an optional list
    if not isinstance(classifiers, list) or not classifiers:
        warn('The value specified for classifiers is not an array')
        return None
    new_classifiers = update_classifiers(classifiers, new_versions)
    return _update_pyproject_toml_classifiers(filename, new_classifiers)


def update_python_requires(
    filename: FileOrFilename,
    new_versions: SortedVersionList,
) -> Optional[FileLines]:
    """Update python dependency in a pyproject.toml, if it's defined there.

    Does not touch the file but returns a list of lines with new file contents.
    """
    python_requires = _get_pyproject_toml_python_requires(filename)
    if python_requires is None:
        return None
    comma = ', '
    if ',' in python_requires and ', ' not in python_requires:
        comma = ','
    space = ''
    if '> ' in python_requires or '= ' in python_requires:
        space = ' '
    new_requires = compute_python_requires(
        new_versions, comma=comma, space=space)
    if is_file_object(filename):
        # Make sure we can read it twice please.
        # XXX: I don't like this.
        cast(TextIO, filename).seek(0)
    return _update_pyproject_python_requires(filename, new_requires)


def _set_poetry_classifiers(
    table: TOMLDocument,
    new_value: Union[str, List[str]],
) -> Optional[FileLines]:
    table[TOOL][POETRY][CLASSIFIERS] = new_value
    _ret = cast(Optional[List[str]], dumps(table).split('\n'))
    return _ret


def _set_setuptools_flit_classifiers(
    table: TOMLDocument,
    new_value: Union[str, List[str]],
) -> Optional[FileLines]:
    table[PROJECT][CLASSIFIERS] = new_value
    _ret = cast(Optional[List[str]], dumps(table).split('\n'))
    return _ret


def _update_pyproject_toml_classifiers(
    filename: FileOrFilename,
    new_value: Union[str, List[str]],
) -> Optional[FileLines]:
    _updated_table: Optional[FileLines] = None
    table = load_toml(filename)
    if is_poetry_toml(table):
        _updated_table = _set_poetry_classifiers(table, new_value)
    if is_setuptools_toml(table) or is_flit_toml(table):
        _updated_table = _set_setuptools_flit_classifiers(table, new_value)

    return _updated_table


def _set_poetry_python_requires(
    table: TOMLDocument,
    new_value: Union[str, List[str]],
) -> Optional[FileLines]:
    table[TOOL][POETRY][DEPENDENCIES][PYTHON] = new_value
    _ret = cast(Optional[FileLines], dumps(table).split('\n'))
    return _ret


def _set_setuptools_flit_python_requires(
    table: TOMLDocument,
    new_value: Union[str, List[str]],
) -> Optional[FileLines]:
    table[PROJECT][PYTHON_REQUIRES] = new_value
    _ret = cast(Optional[FileLines], dumps(table).split('\n'))
    return _ret


def _update_pyproject_python_requires(
    filename: FileOrFilename,
    new_value: Union[str, List[str]],
) -> Optional[FileLines]:
    _updated_table: Optional[FileLines] = []
    table = load_toml(filename)
    if is_poetry_toml(table):
        _updated_table = _set_poetry_python_requires(table, new_value)
    if is_setuptools_toml(table) or is_flit_toml(table):
        _updated_table = _set_setuptools_flit_python_requires(table, new_value)

    return _updated_table


PyProject = Source(
    title=PYPROJECT_TOML,
    filename=PYPROJECT_TOML,
    extract=get_supported_python_versions,
    update=update_supported_python_versions,
    check_pypy_consistency=True,
    has_upper_bound=True,
)

PyProjectPythonRequires = Source(
    title='- python_requires',
    filename=PYPROJECT_TOML,
    extract=get_python_requires,
    update=update_python_requires,
    check_pypy_consistency=False,
    has_upper_bound=False,  # TBH it might have one!
)
