#!/usr/bin/env python

import click
from click.testing import CliRunner
from clikan import configure, clikan, add, promote, show, regress, delete, refresh, read_data, read_config_yaml, write_data
import os
import pathlib
import tempfile
import pytest

# add fixture to clear data before each test
@pytest.fixture(autouse=True)
def clear_data():
    config = read_config_yaml()
    write_data(config, {"data": {}, "deleted": {}})

@pytest.fixture
def add_one_task():
    runner = CliRunner()
    runner.invoke(add, ["n_--task_test"])

@pytest.fixture
def add_three_tasks():
    runner = CliRunner()
    runner.invoke(add, ["n_--task_test_multi_1", "n_--task_test_multi_2", "n_--task_test_multi_3"])

# Configure Tests


def test_command_help():
    runner = CliRunner()
    result = runner.invoke(clikan, ["--help"])
    assert result.exit_code == 0
    assert 'Usage: clikan [OPTIONS] COMMAND [ARGS]...' in result.output
    assert 'clikan: CLI personal kanban' in result.output


def test_command_version():
    version_file = open(os.path.join('./', 'VERSION'))
    version = version_file.read().strip()

    runner = CliRunner()
    result = runner.invoke(clikan, ["--version"])
    assert result.exit_code == 0
    assert 'clikan, version {}'.format(version) in result.output


def test_command_configure(tmp_path):
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        with runner.isolation(
            input=None,
            env={"CLIKAN_HOME": tmpdirname},
            color=False
        ):
            result = runner.invoke(clikan, ["configure"])
            assert result.exit_code == 0
            assert 'Creating' in result.output


def test_command_configure_existing():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(clikan, ["configure"])
        result = runner.invoke(clikan, ["configure"])

        assert 'Config file exists' in result.output


## Single Argument Tests

# Add Tests
def test_command_a():
    runner = CliRunner()
    result = runner.invoke(clikan, ["a", "n_--task_test"])
    assert result.exit_code == 0
    assert 'n_--task_test' in result.output


# Show Tests

def test_no_command(add_one_task):
    runner = CliRunner()
    result = runner.invoke(clikan, [])
    assert result.exit_code == 0
    assert 'n_--task_test' in result.output


def test_command_s(add_one_task):
    runner = CliRunner()
    result = runner.invoke(clikan, ["s"])
    assert result.exit_code == 0
    assert 'n_--task_test' in result.output


def test_command_show(add_one_task):
    runner = CliRunner()
    result = runner.invoke(show)
    assert result.exit_code == 0
    assert 'n_--task_test' in result.output

def test_command_not_show():
    runner = CliRunner()
    result = runner.invoke(show)
    assert result.exit_code == 0
    assert 'blahdyblah' not in result.output


# Promote Tests

def test_command_promote(add_one_task):
    runner = CliRunner()
    result = runner.invoke(clikan, ['promote', '1'])
    assert result.exit_code == 0
    assert 'Promoting task 1 to in-progress.' in result.output
    result = runner.invoke(clikan, ['promote', '1'])
    assert result.exit_code == 0
    assert 'Promoting task 1 to done.' in result.output


# Delete Tests


def test_command_delete(add_one_task):
    runner = CliRunner()
    result = runner.invoke(clikan, ['delete', '1'])
    assert result.exit_code == 0
    assert 'Removed task 1.' in result.output
    result = runner.invoke(clikan, ['delete', '1'])
    assert result.exit_code == 0
    assert 'No existing task with' in result.output

# Refresh Tests

def test_command_refresh(add_three_tasks):
    runner = CliRunner()
    runner.invoke(clikan, ['delete', '1'])
    result = runner.invoke(clikan, ['refresh'])
    assert result.exit_code == 0
    assert 'Refreshing task numbers.' in result.output
    
    config = read_config_yaml()
    data = read_data(config).get('data', {})

    assert len(data) == 2
    print(data[1][1] == "n_--task_test_multi_2")

## Multiple Argument Tests

# Add Tests
def test_command_a_multi():
    runner = CliRunner()
    result = runner.invoke(clikan, ["a", "n_--task_test_multi_1", "n_--task_test_multi_2", "n_--task_test_multi_3"])
    assert result.exit_code == 0
    assert 'n_--task_test' in result.output


# Show Test
def test_command_show_multi(add_three_tasks):
    runner = CliRunner()
    result = runner.invoke(show)
    assert result.exit_code == 0
    assert 'n_--task_test_multi_1' in result.output
    assert 'n_--task_test_multi_2' in result.output
    assert 'n_--task_test_multi_3' in result.output


# Promote Tests
def test_command_promote_multi(add_three_tasks):
    runner = CliRunner()
    result = runner.invoke(clikan, ['promote', '1', '2'])
    assert result.exit_code == 0
    assert 'Promoting task 1 to in-progress.' in result.output
    assert 'Promoting task 2 to in-progress.' in result.output
    result = runner.invoke(clikan, ['promote', '2', '3'])
    assert result.exit_code == 0
    assert 'Promoting task 2 to done.' in result.output
    assert 'Promoting task 3 to in-progress.' in result.output


# Delete Tests
def test_command_delete_multi(add_three_tasks):
    runner = CliRunner()
    result = runner.invoke(clikan, ['delete', '1', '2'])
    assert result.exit_code == 0
    assert 'Removed task 1.' in result.output
    assert 'Removed task 2.' in result.output
    result = runner.invoke(clikan, ['delete', '1', '2'])
    assert result.exit_code == 0
    assert 'No existing task with that id: 1' in result.output
    assert 'No existing task with that id: 2' in result.output

    results = runner.invoke(show)
    assert 'n_--task_test_multi_1' not in results.output
    assert 'n_--task_test_multi_2' not in results.output
    assert 'n_--task_test_multi_3' in results.output


# Repaint Tests
def test_repaint_config_option():
    runner = CliRunner()
    version_file = open(os.path.join('./', 'VERSION'))
    version = version_file.read().strip()
    path_to_config = str(pathlib.Path("./tests/repaint").resolve())
    with runner.isolation(
        input=None,
        env={"CLIKAN_HOME": path_to_config},
        color=False
    ):
        result = runner.invoke(clikan, [])
        assert result.exit_code == 0
        assert 'clikan' in result.output
        result = runner.invoke(clikan, ["a", "n_--task_test"])
        assert result.exit_code == 0
        assert 'n_--task_test' in result.output
        assert version in result.output


def test_no_repaint_config_option():
    runner = CliRunner()
    version_file = open(os.path.join('./', 'VERSION'))
    version = version_file.read().strip()
    path_to_config = str(pathlib.Path("./tests/no_repaint").resolve())
    with runner.isolation(
        input=None,
        env={"CLIKAN_HOME": path_to_config},
        color=False
    ):
        result = runner.invoke(clikan, [])
        assert result.exit_code == 0
        assert 'clikan' in result.output
        result = runner.invoke(clikan, ["a", "n_--task_test"])
        assert result.exit_code == 0
        assert 'n_--task_test' in result.output
        assert version not in result.output


# Limit on task name length tests

def test_taskname_config_option():
    runner = CliRunner()
    version_file = open(os.path.join('./', 'VERSION'))
    version = version_file.read().strip()
    path_to_config = str(pathlib.Path("./tests/taskname").resolve())
    with runner.isolation(
        input=None,
        env={"CLIKAN_HOME": path_to_config},
        color=False
    ):
        result = runner.invoke(clikan, [])
        assert result.exit_code == 0
        assert 'clikan' in result.output
        result = runner.invoke(clikan, ["a", "This is a long task name, more than 40 characters (66 to be exact)"])
        assert result.exit_code == 0
        assert 'This is a long task name, more than 40 characters (66 to be exact)' in result.output


def test_no_taskname_config_option():
    runner = CliRunner()
    version_file = open(os.path.join('./', 'VERSION'))
    version = version_file.read().strip()
    path_to_config = str(pathlib.Path("./tests/no_taskname").resolve())
    with runner.isolation(
        input=None,
        env={"CLIKAN_HOME": path_to_config},
        color=False
    ):
        result = runner.invoke(clikan, [])
        assert result.exit_code == 0
        assert 'clikan' in result.output
        result = runner.invoke(clikan, ["a", "This is a long task name, more than 40 characters (66 to be exact)"])
        assert result.exit_code == 0
        assert 'Brevity counts:' in result.output
