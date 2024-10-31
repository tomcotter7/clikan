from rich import print
from rich.console import Console
from rich.table import Table
import click
from click_default_group import DefaultGroup
import yaml
import os
import sys
from textwrap import wrap
import collections
import datetime
import configparser
try:
    from importlib import metadata
except ImportError: # for Python<3.8
    import importlib_metadata as metadata
__version__ = metadata.version("jsonschema")


VERSION = metadata.version('clikan')


class Config(object):
    """The config in this example only holds aliases."""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


pass_config = click.make_pass_decorator(Config, ensure=True)


class AliasedGroup(DefaultGroup):
    """This subclass of a group supports looking up aliases in a config
    file and with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        # Step one: bulitin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # Step two: find the config object and ensure it's there.  This
        # will create the config object is missing.
        cfg = ctx.ensure_object(Config)
        read_config(ctx, None, None)

        # Step three: lookup an explicit command aliase in the config
        if cmd_name in cfg.aliases:
            actual_cmd = cfg.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


def read_config(ctx, param, value):
    """Callback that is used whenever --config is passed.  We use this to
    always load the correct config.  This means that the config is loaded
    even if the group itself never executes so our aliases stay always
    available.
    """
    cfg = ctx.ensure_object(Config)
    if value is None:
        value = os.path.join(os.path.dirname(__file__), 'aliases.ini')
    cfg.read_config(value)
    return value


@click.version_option(VERSION)
@click.command(cls=AliasedGroup, default='show', default_if_no_args=True)
def clikan():
    """clikan: CLI personal kanban """

def setup_project(name: str):
    """Setup a new project"""
    home = get_clikan_home()
    data_path = os.path.join(home, f".{name}.dat")
    config_path = os.path.join(home, f".{name}.yaml")
    if (os.path.exists(config_path) and not
            click.confirm('Config file exists. Do you want to overwrite?')):
        return
    with open(config_path, 'w') as outfile:
        conf = {'clikan_data': data_path}
        yaml.dump(conf, outfile, default_flow_style=False)
    click.echo("Creating %s" % config_path)

@clikan.command()
def configure():
    """Place default config file in CLIKAN_HOME or HOME"""
    setup_project("default")
    

@clikan.command()
@click.argument('tasks', nargs=-1)
def add(tasks):
    """Add a tasks in todo"""
    config = read_config_yaml()
    dd = read_data(config)

    if ('limits' in config and 'taskname' in config['limits']):
        taskname_length = config['limits']['taskname']
    else:
        taskname_length = 40

    for task in tasks:
        if len(task) > taskname_length:
            click.echo('Task must be at most %s chars, Brevity counts: %s'
                       % (taskname_length, task))
        else:
            todos, inprogs, dones = split_items(config, dd)
            if ('limits' in config and 'todo' in config['limits'] and
                    int(config['limits']['todo']) <= len(todos)):
                click.echo('No new todos, limit reached already.')
            else:
                od = collections.OrderedDict(sorted(dd['data'].items()))
                new_id = 1
                if bool(od):
                    new_id = next(reversed(od)) + 1
                entry = ['todo', task, timestamp(), timestamp()]
                dd['data'].update({new_id: entry})
                click.echo("Creating new task w/ id: %d -> %s"
                           % (new_id, task))

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()


@clikan.command()
@click.argument('ids', nargs=-1)
def delete(ids):
    """Delete task"""
    config = read_config_yaml()
    dd = read_data(config)

    for id in ids:
        try:
            item = dd['data'].get(int(id))
            if item is None:
                click.echo('No existing task with that id: %d' % int(id))
            else:
                item[0] = 'deleted'
                item[2] = timestamp()
                dd['deleted'].update({int(id): item})
                dd['data'].pop(int(id))
                click.echo('Removed task %d.' % int(id))
        except ValueError:
            click.echo('Invalid task id')

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()


@clikan.command()
@click.argument('ids', nargs=-1)
@click.argument('task', nargs=1)
def promote(ids):
    """Promote task"""
    config = read_config_yaml()
    dd = read_data(config)
    todos, inprogs, dones = split_items(config, dd)

    for id in ids:
        try:
            item = dd['data'].get(int(id))
            if item is None:
                click.echo('No existing task with that id: %s' % id)
            elif item[0] == 'todo':
                if ('limits' in config and 'wip' in config['limits'] and
                        int(config['limits']['wip']) <= len(inprogs)):
                    click.echo(
                        'Can not promote, in-progress limit of %s reached.'
                        % config['limits']['wip']
                    )
                else:
                    click.echo('Promoting task %s to in-progress.' % id)
                    dd['data'][int(id)] = [
                        'inprogress',
                        item[1], timestamp(),
                        item[3]
                    ]
            elif item[0] == 'inprogress':
                click.echo('Promoting task %s to done.' % id)
                dd['data'][int(id)] = ['done', item[1], timestamp(), item[3]]
            else:
                click.echo('Can not promote %s, already done.' % id)
        except ValueError:
            click.echo('Invalid task id')

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()


@clikan.command()
@click.argument('ids', nargs=-1)
def regress(ids):
    """Regress task"""
    config = read_config_yaml()
    dd = read_data(config)

    for id in ids:
        item = dd['data'].get(int(id))
        if item is None:
            click.echo('No existing task with id: %s' % id)
        elif item[0] == 'done':
            click.echo('Regressing task %s to in-progress.' % id)
            dd['data'][int(id)] = ['inprogress', item[1], timestamp(), item[3]]
        elif item[0] == 'inprogress':
            click.echo('Regressing task %s to todo.' % id)
            dd['data'][int(id)] = ['todo', item[1], timestamp(), item[3]]
        else:
            click.echo('Already in todo, can not regress %s' % id)

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()

@clikan.command()
@click.argument('id', nargs=1)
@click.argument('task', nargs=1)
def edit(id, task):
    """Edit task"""
    config = read_config_yaml()
    dd = read_data(config)

    if ('limits' in config and 'taskname' in config['limits']):
        taskname_length = config['limits']['taskname']
    else:
        taskname_length = 40

    if len(task) > taskname_length:
        click.echo('Task must be at most %s chars, Brevity counts: %s'
                   % (taskname_length, task))
        return

    item = dd['data'].get(int(id))
    if item is None:
        click.echo('No existing task with id: %s' % id)
    else:
        entry = [item[0], task, item[2], timestamp()]
        dd['data'][int(id)] = entry
        click.echo('Edited task %s.' % id)

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()


@clikan.command()
def refresh():
    """Refresh the task numbers and remove deleted tasks."""
    config = read_config_yaml()
    dd = read_data(config)
    click.echo('Refreshing task numbers.')
    new_data = {i+1: value for i, value in enumerate(dd['data'].values())}
    dd['data'] = new_data
    dd['deleted'] = {}

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()


@clikan.command()
@click.argument('name', required=False)
def switch(name=None):
    """Switch to a different project"""
    if name is None:
        name = "default"
    home = get_clikan_home()
    config_path = os.path.join(home, f".{name}.yaml")
    if not os.path.exists(config_path):
        click.echo("Project %s does not exist." % name)
        click.echo("Creating project %s." % name)
        setup_project(name)

    click.echo("Switching to project %s." % name)
    with open(home + "/.current", 'w') as project_file:
        project_file.write(name)
    display()

@clikan.command()
def projects():
    """List all projects"""
    home = get_clikan_home()
    current_project = read_current_project()
    projects = [f for f in os.listdir(home) if f.endswith(".yaml") if f != f".{current_project}.yaml"]
    click.echo(f"*{current_project}")
    for project in projects:
        click.echo(project[1:-5])

@clikan.command()
@click.argument('name')
def delproj(name):
    """Delete a project"""
    if name == "default":
        click.echo("Can't delete default project.")
        return

    home = get_clikan_home()
    config_path = os.path.join(home, f".{name}.yaml")
    if not os.path.exists(config_path):
        click.echo("Project %s does not exist." % name)
        return

    if not click.confirm(f"Delete project {name}?"):
        return
    
    config = read_config_yaml()
    data = config["clikan_data"]
    os.remove(config_path)
    os.remove(data)
    click.echo(f"Deleted project {name}")

    with open(home + "/.current", 'w') as project_file:
        project_file.write("default")
    display()


# Use a non-Click function to allow for repaint to work.


def display():
    console = Console()
    """Show tasks in clikan"""
    config = read_config_yaml()
    dd = read_data(config)
    project = read_current_project()
    todos, inprogs, dones = split_items(config, dd)
    if 'limits' in config and 'done' in config['limits']:
        dones = dones[0:int(config['limits']['done'])]
    else:
        dones = dones[0:10]

    todos = '\n'.join([str(x) for x in todos])
    inprogs = '\n'.join([str(x) for x in inprogs])
    dones = '\n'.join([str(x) for x in dones])

    table = Table(show_header=True, show_footer=True)
    table.add_column(
        "[bold yellow]todo[/bold yellow]",
        no_wrap=True,
        footer=f"clikan ({project})"
    )
    table.add_column('[bold green]in-progress[/bold green]', no_wrap=True)
    table.add_column(
        '[bold magenta]done[/bold magenta]',
        no_wrap=True,
        footer="v.{}".format(VERSION)
    )

    table.add_row(todos, inprogs, dones)
    console.print(table)


@clikan.command()
def show():
    display()


def read_data(config):
    """Read the existing data from the config datasource"""
    try:
        with open(config["clikan_data"], 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print("Ensure %s exists, as you specified it "
                      "as the clikan data file." % config['clikan_data'])
                print(exc)
                sys.exit()
    except IOError:
        click.echo("No data, initializing data file.")
        write_data(config, {"data": {}, "deleted": {}})
        with open(config["clikan_data"], 'r') as stream:
            return yaml.safe_load(stream)


def write_data(config, data):
    """Write the data to the config datasource"""
    with open(config["clikan_data"], 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)


def get_clikan_home():
    home = os.environ.get('CLIKAN_HOME')
    if not home:
        home = os.path.expanduser('~/.clikan/')
    return home

def read_current_project():
    home = get_clikan_home().rstrip("/")
    with open(home + "/.current", 'r') as project_file:
        return project_file.read().strip()

def read_config_yaml():
    """Read the app config from ~/.clikan.yaml"""
        
    project = read_current_project()

    home = get_clikan_home()
    try:
        with open(home + f"/.{project}.yaml", 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError:
                print("Ensure %s/.%s.yaml is valid, expected YAML." % home, project)
                sys.exit()
    except IOError:
        print("Ensure %s/.%s.yaml exists and is valid." % home, project)
        sys.exit()


def split_items(config, dd):
    todos = []
    inprogs = []
    dones = []

    for key, value in dd['data'].items():
        if value[0] == 'todo':
            todos.append("[%d] %s" % (key, value[1]))
        elif value[0] == 'inprogress':
            inprogs.append("[%d] %s" % (key, value[1]))
        else:
            dones.insert(0, "[%d] %s" % (key, value[1]))

    return todos, inprogs, dones


def timestamp():
    return '{:%Y-%b-%d %H:%M:%S}'.format(datetime.datetime.now())
