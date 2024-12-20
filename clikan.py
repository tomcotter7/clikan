from rich import print
from rich.console import Console
from rich.table import Table
import click
from click_default_group import DefaultGroup
import yaml
import os
import sys
import collections
import datetime
import configparser
from importlib import metadata

from typing import Any
from pydantic import BaseModel
# __version__ = metadata.version("jsonschema")


VERSION = metadata.version('clikan')


class Entry(BaseModel):
    task: str
    status: str
    last_updated: str 
    target_date: str|None
    desc: str

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
    home = get_clikan_home()
    current = os.path.join(home, ".current")
    if not os.path.exists(current):
        with open(current, 'w') as project_file:
            project_file.write("default")
    setup_project("default")
    


def parse_date(date: str) -> datetime.datetime:
    if date in ["today", "tomorrow", "nextweek"]:
        today = datetime.datetime.now()
        if date == "today":
            return today
        if date == "tomorrow":
            return today + datetime.timedelta(days=1)
        if date == "nextweek":
            return today + datetime.timedelta(days=7)

    return datetime.datetime.fromisoformat(date)

@clikan.command()
@click.argument('task', nargs=1)
def expand(task):
    """Add a short description to the task, for more detail"""
    config = read_config_yaml()
    dd = read_data(config)
    item = dd['data'].get(int(task))

    if item is None:
        click.echo('No existing task with that id: %d' % int(task))
        return

    if item.desc:
        click.echo(f"Task title: {item.task}")
        click.echo(f"Task description: {item.desc}")
    else:
        click.echo(f"Task {task} has no description yet. Use 'edit' to add one.")

@clikan.command()
@click.argument('task', nargs=1)
@click.option("--date", "-d", help="Planned date to complete task. Must be in the form of 'YYYY-MM-DD HH:MM'")
def add(task, date):
    """Add a task in todo"""


    config = read_config_yaml()
    dd = read_data(config)

    if ('limits' in config and 'taskname' in config['limits']):
        taskname_length = config['limits']['taskname']
    else:
        taskname_length = 40

    if len(task) > taskname_length:
        click.echo('Task must be at most %s chars, Brevity counts: %s'
                   % (taskname_length, task))
    else:
        todos, _, _ = split_items(dd)
        if ('limits' in config and 'todo' in config['limits'] and
                int(config['limits']['todo']) <= len(todos)):
            click.echo('No new todos, limit reached already.')
        else:
            target_date = None
            if date:
                target_date = timestamp(parse_date(date))

            od = collections.OrderedDict(sorted(dd['data'].items()))
            new_id = 1
            if bool(od):
                new_id = next(reversed(od)) + 1

            entry = Entry(task=task, status='todo', last_updated=timestamp(), target_date=target_date, desc="")
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
                item.status = 'deleted'
                item.last_updated = timestamp()
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
def promote(ids):
    """Promote task"""
    config = read_config_yaml()
    dd = read_data(config)
    _, inprogs, _ = split_items(dd)

    for id in ids:
        try:
            item = dd['data'].get(int(id))
            if item is None:
                click.echo('No existing task with that id: %s' % id)
            elif item.status == 'todo':
                if ('limits' in config and 'wip' in config['limits'] and
                        int(config['limits']['wip']) <= len(inprogs)):
                    click.echo(
                        'Can not promote, in-progress limit of %s reached.'
                        % config['limits']['wip']
                    )
                else:
                    click.echo('Promoting task %s to in-progress.' % id)
                    item.status = 'inprogress'
                    item.last_updated = timestamp()
                    dd['data'][int(id)] = item
            elif item.status == 'inprogress':
                click.echo('Promoting task %s to done.' % id)
                item.status = 'done'
                item.last_updated = timestamp()
                dd['data'][int(id)] = item
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
        elif item.status == 'done':
            click.echo('Regressing task %s to in-progress.' % id)
            item.status = 'inprogress'
            item.last_updated = timestamp()
            dd['data'][int(id)] = item
        elif item.status == 'inprogress':
            click.echo('Regressing task %s to todo.' % id)
            item.status = 'todo'
            item.last_updated = timestamp()
            dd['data'][int(id)] = item
        else:
            click.echo('Already in todo, can not regress %s' % id)

    write_data(config, dd)
    if ('repaint' in config and config['repaint']):
        display()

@clikan.command()
@click.argument('id', nargs=1)
@click.option('--task', "-t", help="New task name")
@click.option("--date", "-d", help="Planned date to complete task. Must be in the form of 'YYYY-MM-DD HH:MM'")
@click.option("--desc", help="Description of the task")
def edit(id, task, date, desc):
    """Edit task"""
    config = read_config_yaml()
    dd = read_data(config)

    if ('limits' in config and 'taskname' in config['limits']):
        taskname_length = config['limits']['taskname']
    else:
        taskname_length = 40

    if task and len(task) > taskname_length:
        click.echo('Task must be at most %s chars, Brevity counts: %s'
                   % (taskname_length, task))
        return

    item = dd['data'].get(int(id))
    if item is None:
        click.echo('No existing task with id: %s' % id)
    elif task is None and date is None and desc is None:
        click.echo('Nothing to edit.')
    else:
        new_item = item.model_copy()
        if task:
            new_item.task = task
        if date:
            if date == "None":
                new_item.target_date = None
            else:
                new_item.target_date = timestamp(parse_date(date))
        if desc:
            new_item.desc = desc
        
        new_item.last_updated = timestamp()
        dd['data'][int(id)] = new_item
        click.echo('Edited task %s.' % id)
        write_data(config, dd)

    if ('repaint' in config and config['repaint']):
        display()


@clikan.command()
@click.option('--all', '-a', is_flag=True, help="Refresh all tasks across all projects")
def refresh(all: bool):
    """Refresh the task numbers and remove done tasks."""

    click.echo('Refreshing task numbers.')
    
    def refresh(dd: dict[str, dict[int, Entry]]) -> dict[str, dict[int, Entry]]:

        new_data: dict[int, Entry] = {i+1: value for i, value in enumerate(dd['data'].values()) if value.status != 'done'}
        dd['data'] = new_data
        dd['deleted'] = {}
        return dd
    
    if not all:
        config = read_config_yaml()
        dd = read_data(config)
        refresh(dd)
        write_data(config, dd)
        if ('repaint' in config and config['repaint']):
            display()
        return

    projects = [f[1:-5] for f in os.listdir(get_clikan_home()) if f.endswith(".yaml")]
    for project in projects:
        config = read_config_yaml(project)
        dd = read_data(config)
        refresh(dd)
        write_data(config, dd)


@clikan.command()
@click.argument('name', required=False)
def switch(name: str|None = None):
    """Switch to a different project"""
    if name is None:
        name = "default"
    home = get_clikan_home()
    config_path = os.path.join(home, f".{name}.yaml")
    if not os.path.exists(config_path):
        click.confirm("Project %s does not exist. Create?" % name, abort=True)
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
    projects = [f[1:-5] for f in os.listdir(home) if f.endswith(".yaml") if f != f".{current_project}.yaml"]
    click.echo("\nAvailable Projects:")
    click.echo("-" * 20)  # Adding a separator line
    
    click.secho(f"→ {current_project} (active)", fg="green", bold=True)
    
    for project in projects:
        project_name = project
        click.echo(f"  {project_name}")
    
    click.echo("-" * 20)
    click.echo(f"Total projects: {len(projects) + 1}\n")

@clikan.command()
@click.argument('name')
def delproj(name: str):
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

@clikan.command()
@click.option('--all', '-a', is_flag=True, help="Show all tasks due today across all projects")
def today(all: bool):
    """Show tasks due today"""
    display(all, True)

# Use a non-Click function to allow for repaint to work.

def draw_table(todos, inprogs, dones, project):
    console = Console()
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

def display(all: bool = False, today: bool = False):
    """Show tasks in clikan"""
    config = read_config_yaml()
    dd = read_data(config)


    if not all:
        todos, inprogs, dones = split_items(dd, today=today)
        todos = '\n'.join([str(x) for x in todos])
        inprogs = '\n'.join([str(x) for x in inprogs])
        dones = '\n'.join([str(x) for x in dones])

        draw_table(todos, inprogs, dones, read_current_project())
        return

    projects = [f for f in os.listdir(get_clikan_home()) if f.endswith(".yaml")]
    for project in projects:
        p = project[1:-5]
        config = read_config_yaml(p)
        dd = read_data(config)
        todos, inprogs, dones = split_items(dd, today=today)
        todos = '\n'.join([str(x) for x in todos])
        inprogs = '\n'.join([str(x) for x in inprogs])
        dones = '\n'.join([str(x) for x in dones])
        if todos or inprogs or dones:
            draw_table(todos, inprogs, dones, p)

@clikan.command()
@click.option('--all', '-a', is_flag=True, help="Show all projects")
def show(all):
    display(all, False)


def read_data(config: dict[str, Any]) -> dict[str, dict[int, Entry]]:
    """Read the existing data from the config datasource"""
    try:
        with open(config["clikan_data"], 'r') as stream:
            try:
                data = yaml.safe_load(stream)
                return {
                        "data": {
                            int(k): Entry(
                                status=v[0],
                                task=v[1],
                                last_updated=v[2],
                                target_date=v[3],
                                desc=v[4] if len(v) > 4 else ''
                            )
                            for k, v in data["data"].items()
                        },
                        "deleted": {
                            int(k): Entry(
                                status=v[0],
                                task=v[1],
                                last_updated=v[2],
                                target_date=v[3],
                                desc=v[4] if len(v) > 4 else ''
                            )
                            for k, v in data["deleted"].items()
                        }
                }
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


def write_data(config: dict[str, Any], data: dict[str, dict[int, Entry]]):
    """Write the data to the config datasource"""
    formatted_data = {
        "data": {
            k: [v.status, v.task, v.last_updated, v.target_date, v.desc] for k, v in data["data"].items()
        },
        "deleted": {
            k: [v.status, v.task, v.last_updated, v.target_date, v.desc] for k, v in data["deleted"].items()
        }
    }
    with open(config["clikan_data"], 'w') as outfile:
        yaml.dump(formatted_data, outfile, default_flow_style=False, allow_unicode=True, width=float('inf'))


def get_clikan_home():
    home = os.environ.get('CLIKAN_HOME')
    if not home:
        home = os.path.expanduser('~/.clikan/')
        if not os.path.exists(home) :
            os.makedirs(home)
    return home

def read_current_project() -> str:

    home = get_clikan_home().rstrip("/")
    with open(home + "/.current", 'r') as project_file:
        project = project_file.read().strip()
        if not project:
            project = "default"
        return project

def read_config_yaml(project:str|None=None):
    """Read the app config from ~/.clikan.yaml"""
   
    if not project:
        project = project if (project := read_current_project()) else "default"

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


def split_items(dd: dict[str, dict[int, Entry]], today: bool=False):
    todos = []
    inprogs = []
    dones = []

    for key, value in dd['data'].items():
        key = f"{key}*" if value.desc else key
        s = f"[{key}] {value.task}"
        target_date = parse_timestamp(value.target_date) if value.target_date else None
        is_today = target_date and target_date.date() == datetime.datetime.now().date()
        is_overdue = target_date and target_date.date() < datetime.datetime.now().date()
        if today and not (is_today or is_overdue):
            continue
        
        if is_today:
            s = f"[bold blue]{s}[/bold blue]"
        if is_overdue:
            s = f"[bold red]{s}[/bold red]"
        if value.status == 'todo':
            todos.append(s)
        elif value.status == 'inprogress':
            inprogs.append(s)
        else:
            dones.append(s)

    return todos, inprogs, dones

def parse_timestamp(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, '%Y-%b-%d %H:%M:%S')

def timestamp(dt: datetime.datetime = datetime.datetime.now()) -> str:
    return '{:%Y-%b-%d %H:%M:%S}'.format(dt)
