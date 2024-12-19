# clikan-ext: CLI (Personal) Kanban (extended)

> [!NOTE]
> > This is a fork of [clikan](https://github.com/kitplummer/clikan) originally created by [Kit Plummer](https://github.com/kitplummer). This fork extends the original project with additional commands. The original project is not longer maintained.

clikan is a super simple command-line utility for tracking tasks following the Japanese Kanban (boarding) style.

## Installation

$ `git clone git@github.com:tomcotter7/clikan.git`
$ `cd clikan`
$ `pip install .`

### Create a `.clikan.yaml` in your $HOME directory

```yaml
---
clikan_data: /Users/kplummer/.clikan.dat
limits:
  todo: 10
  wip: 3
  done: 10
  taskname: 40
repaint: true
```

* `clikan_data` is the datastore file location.
* `limits:todo` is the max number of items allowed in the todo column, keep this small - you want a smart list, not an ice box of ideas here.
* `limits:wip` is the max number of items allowed in in-progress at a given time.  Context-switching is a farce, focus on one or two tasks at a time.
* `limits:done` is the max number of done items visible, they'll still be stored.  It's good to see a list of done items, for pure psyche.
* `limits:taskname` is the max length of a task text.
* `repaint` is used to tell `clikan` to show the display after every successful command - default is false/off.

-- or --

$ `clikan configure`

to create a default data file location.

## Usage

See `clikan --help` once installed for a list of commands.

All commands can be run with their shortest possible unique form.  For example, `clikan add` can be run as `clikan a`.

## Development

Install the package in editable mode:

$ `pip install -e .`

This repo is open for PRs.

### Testing

There is a basic test suite available in `clikan_test.py`.

To run it, make sure ~/.clikan.dat is empty, or specify a test locale
with the `CLIKAN_HOME` environment variable the you can run:

```
CLIKAN_HOME=/tmp pytest clikan_test.py
```

The project uses this environment variable feature to test different functional configuration scenarios internally to the test suite.

## License

```
MIT License

Copyright 2018 Kit Plummer

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
