import textwrap
from io import StringIO
from typing import List

import pytest

from check_python_versions.sources.pyproject import (
    get_python_requires,
    get_supported_python_versions,
    get_toml_content,
    is_flit_toml,
    is_poetry_toml,
    is_setuptools_toml,
    load_toml,
    update_python_requires,
)
from check_python_versions.versions import Version


def v(versions: List[str]) -> List[Version]:
    return [Version.from_string(v) for v in versions]


def test_get_supported_python_versions(tmp_path):
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [project]
            name='foo'
            classifiers=[
                'Programming Language :: Python :: 2.7',
                'Programming Language :: Python :: 3.6',
                'Programming Language :: Python :: 3.10',
            ]
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"
    """))
    assert get_supported_python_versions(str(filename)) == v(['2.7', '3.6', '3.10'])


def test_get_supported_python_versions_keep_comments(tmp_path):
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [project]
            name='foo'
            # toml comment
            classifiers=[
                'Programming Language :: Python :: 2.7',
                'Programming Language :: Python :: 3.6',
                'Programming Language :: Python :: 3.10',
            ]
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"
    """))

    assert get_toml_content(str(filename)) == ['[project]',
                                               '    name=\'foo\'',
                                               '    # toml comment',
                                               '    classifiers=[',
                                               '        \'Programming Language :: Python :: 2.7\',',
                                               '        \'Programming Language :: Python :: 3.6\',',
                                               '        \'Programming Language :: Python :: 3.10\',',
                                               '    ]',
                                               '[build-system]',
                                               '    requires = ["setuptools", "setuptools-scm"]',
                                               '    build-backend = "setuptools.build_meta"',
                                               '']


def test_update_supported_python_versions_not_a_list(tmp_path, capsys):
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [project]
            name='foo'
            classifiers='''
                Programming Language :: Python :: 2.7
                Programming Language :: Python :: 3.6
            '''
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"
    """))
    assert get_supported_python_versions(str(filename)) == []
    assert (
        "The value passed to classifiers is not a list"
        in capsys.readouterr().err
    )


def test_get_python_requires(tmp_path, fix_max_python_3_version):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=3.6"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    fix_max_python_3_version(7)
    assert get_python_requires(str(pyproject_toml)) == v(['3.6', '3.7'])
    fix_max_python_3_version(10)
    assert get_python_requires(str(pyproject_toml)) == v([
        '3.6', '3.7', '3.8', '3.9', '3.10',
    ])


def test_get_python_requires_not_specified(tmp_path, capsys):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(textwrap.dedent("""\
        [project]
            name='foo'
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    assert get_python_requires(str(pyproject_toml)) is None
    assert capsys.readouterr().err.strip() == 'The value passed to python dependency is not a string'


def test_get_python_requires_not_a_string(tmp_path, capsys):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = [">=3.6"]
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    assert get_python_requires(str(pyproject_toml)) is None
    assert (
        'The value passed to python dependency is not a string'
        in capsys.readouterr().err
    )


def test_update_python_requires(tmp_path, fix_max_python_3_version):
    fix_max_python_3_version(7)
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=3.4"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    result = update_python_requires(str(filename), v(['3.5', '3.6', '3.7']))
    assert result is not None
    assert "\n".join(result) == textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=3.5"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """)


def test_update_python_requires_file_object(fix_max_python_3_version):
    fix_max_python_3_version(7)
    fp = StringIO(textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=3.4"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    fp.name = "pyproject.toml"
    result = update_python_requires(fp, v(['3.5', '3.6', '3.7']))
    assert result is not None
    assert "\n".join(result) == textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=3.5"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """)


def test_update_python_requires_when_missing(capsys):
    fp = StringIO(textwrap.dedent("""\
        [project]
            name='foo'
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    fp.name = "pyproject.toml"
    result = update_python_requires(fp, v(['3.5', '3.6', '3.7']))
    assert result is None
    assert capsys.readouterr().err == ""


def test_update_python_requires_preserves_style(fix_max_python_3_version):
    fix_max_python_3_version(2)
    fp = StringIO(textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=2.7,!=3.0.*"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """))
    fp.name = "pyproject.toml"
    result = update_python_requires(fp, v(['2.7', '3.2']))
    assert "\n".join(result) == textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = ">=2.7,!=3.0.*,!=3.1.*"
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"            
    """)


def test_update_python_requires_multiline_error(capsys):
    fp = StringIO(textwrap.dedent("""\
        [project]
            name='foo'
            requires-python = '>=2.7, !=3.0.*'
        [build-system]
            requires = ["setuptools", "setuptools-scm"]
            build-backend = "setuptools.build_meta"
    """))
    fp.name = "pyproject.toml"
    result = update_python_requires(fp, v(['2.7', '3.2']))
    assert result == ['[project]',
                      "    name='foo'",
                      '    requires-python = ">=2.7, !=3.0.*, !=3.1.*, !=3.3.*, !=3.4.*, !=3.5.*, !=3.6.*, !=3.7.*, '
                      '!=3.8.*, !=3.9.*, !=3.10.*, !=3.11.*"',
                      '[build-system]',
                      '    requires = ["setuptools", "setuptools-scm"]',
                      '    build-backend = "setuptools.build_meta"',
                      '']


def test_setuptools_toml_from_tools(tmp_path):
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [tool.setuptools.packages]
            name='foo'       
    """))
    _table = load_toml(str(filename))
    assert is_setuptools_toml(_table)
    assert not is_poetry_toml(_table)
    assert not is_flit_toml(_table)


def test_setuptools_toml_from_build_backend(tmp_path):
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [build-system]
            build-backend = "setuptools.build_meta"
    """))
    _table = load_toml(str(filename))
    assert is_setuptools_toml(_table)
    assert not is_poetry_toml(_table)
    assert not is_flit_toml(_table)


def test_setuptools_toml_from_build_requires(tmp_path):
    filename = tmp_path / "pyproject.toml"
    filename.write_text(textwrap.dedent("""\
        [build-system]
            requires = ["setuptools"]
    """))
    _table = load_toml(str(filename))
    assert is_setuptools_toml(_table)
    assert not is_poetry_toml(_table)
    assert not is_flit_toml(_table)