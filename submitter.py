import os
import subprocess
import shutil
from abc import abstractmethod

from colt import Colt, Plugin, PluginLoader
from jinja2 import Template, Environment, meta


class Folder:
    """simple context manager to enter (and leave) a folder"""

    def __init__(self, folder):
        self._folder = folder

    def __enter__(self):
        self._current = os.getcwd()
        os.chdir(self._folder)

    def __exit__(self, type, value, traceback):
        os.chdir(self._current)        


def copy_file(origin, destination, name=None):
    """copy a file from `origin` to `destination`"""
    origin = os.path.abspath(origin)
    if name is not None:
        destination = os.join(destination, name)
    destination = os.path.abspath(destination)
    shutil.copy(origin, destination)


def render_file(original, outname, data):
    """read an jinja2 template file, render it and write it to `outname`"""
    with open(original, 'r') as fh:
        tmpl = Template(fh.read())

    with open(outname, 'w') as fh:
        out = tmpl.render(data)
        fh.write(out)


class SubmitScript(Plugin):

    _is_plugin_factory = True

    keys = {"queue", "input", "output", 
            "nodes", "ntasks_per_node", "mem_per_cpu"}

    _header_values = {
        'no-requeue': None,
        'partition': '{{queue}}',
        'job-name': '{{input}}',
        'output': '{{output}}',
        'nodes': '{{nodes}}',
        'ntasks-per-node': '{{ntasks_per_node}}',
        'time': '{{time}}',
        'mem-per-cpu': '{{mem_per_cpu}}',
    }

    tmpl = Template("""
{{header}}

{{command}}



""")

    _questions = "method = "

    env = Environment()

    _command = ""
    

    @classmethod
    def add_sbatch(self, name, value):
        self._sbatch_values[name] = value

    @classmethod
    def _extend_questions(cls, questions):
        questions.generate_cases("method", {name: plugin.questions
                                            for name, plugin in cls.plugins.items()})

    @classmethod
    def from_config(cls, config, general=None):
        return cls(config, general)

    def __init__(self, config, general):
        self._config = config
        self._general = general

    def submit_calc(self, time):
        self.setup()
        submit_script = self.render(time)
        #
        data = self.write(submit_script)
        #
        if self._general['write_only'] is True:
            print("Only files written")
            return
        #
        self.submit(data=data)
        if self._general['delete'] is True:
            self.delete(data=data)
        # 
        self.show()

    def setup(self):
        pass

    def write(self, submit_file):
        with open(self._general['submit_file'], 'w') as fh:
            fh.write(submit_file)

    def submit(self, *, data=None):
        """submit calculations"""
        subprocess.run([f"sbatch {self._general['submit_file']}"], shell=True)

    def show(self):
        """display some info"""
        user = os.environ.get('USER', None)
        if user is not None:
            subprocess.run([f'squeue -u {user}'], shell=True)

    def delete(self, *, data=None):
        if config['delete'] is True:
            os.remove(self._general['submit_file'])

    def render(self, time):
        self._general.update({'time': time})
        out = {name: self._general[name] for name in self.keys}
        out['input'] = os.path.basename(out['input'])
        #
        out['command'] = self.command
        out['header'] = self.header
        return self.tmpl.render(out)

    @property
    def command(self):
        return self._render_var(self._command)

    @property
    def header(self):
        header = "\n".join(self._render_header_line(name, value)
                           for name, value in self._header_values.items())
        
        return header + "\n\n"

    def _render_var(self, var):
        tpl = Template(var)
        ast = self.env.parse(var)
        needed = meta.find_undeclared_variables(ast)
        out = {}
        for var in needed:
            res = self._general.get(var)
            if res is not None: 
                out[var] = res
                continue
            res = self._config.get(var)
            if res is not None: 
                out[var] = res
                continue
            raise KeyError(f"key '{var}' unknown")
        return tpl.render(out) 

    def _render_header_line(self, name, value):
        if value is None:
            return f"#SBATCH --{name}"
        return f"#SBATCH --{name}={self._render_var(value).strip()}"


class SubmitMultipleScript(SubmitScript):
    """submit multiple files based on some input"""
    _register_plugin = False
    _is_plugin_specialisation = True
    _copy_files = []
    _template_files = []

    @abstractmethod
    def generate_folder_names(self):
        raise NotImplementedError("needed for MultipleSubmitScript")

    @property
    def copy_files(self):
        return self._copy_files

    @property
    def template_files(self):
        return self._template_files

    def render_data(self, idx, folder):
        return self._config

    def write(self, submit_file):
        folders = self.generate_folder_names()

        # write submitfiles, copy files, ...
        for idx, folder in folders:
            os.makedirs(folder, exist_ok=True)
            for filename in self.copy_files:
                copy_file(filename, folder)

            for filename in self.template_files:
                render_file(filename, os.path.join(folder, filename), self.render_data(idx, folder))
            with Folder(folder):
                # write ssubmitfile
                with open(os.path.basename(self._general['submit_file']), 'w') as fh:
                    fh.write(submit_file)
        return folders

    def submit(self, *, data=None):
        """submit calculations"""
        for idx, folder in data:
            with Folder(folder):
                subprocess.run([f"sbatch {self._general['submit_file']}"], shell=True)

    def show(self):
        """display some info"""
        user = os.environ.get('USER', None)
        if user is not None:
            subprocess.run([f'squeue -u {user}'], shell=True)

    def delete(self, *, data):
        for idx, folder in data:
            with Folder(folder):
                os.remove(os.path.basename(self._general['submit_file']))


class Submitter(Colt):

    """submits one calculation using the settings"""

    queues = {
        'ultrashort': '2-06:00:00',
        'short': '00:30:00',
        'medium': '72:00:00',
        'long': '240:00:00',
    }

    _questions = """
    # name of the qchem input file
    input = :: existing_file

    # name of the output
    output = :: str, optional

    # select timeout queue
    queue  = medium :: str :: [ultrashort, short, medium, long]

    # Number of cores
    ntasks_per_node = :: int

    # Number of nodes
    nodes = 1 :: int

    # memory per cpu in GB
    mem_per_cpu = 2 :: float

    # delete the submit file
    delete = True :: bool

    # write only the submission script
    write_only = False :: bool

    # submit file name
    submit_file = submit_file_sbatch.sh :: file

    """

    plugins = SubmitScript

    loader_paths = ['~/templates/submitter']

    @classmethod
    def _extend_questions(cls, questions):
        questions.add_questions_to_block(cls.plugins.questions)

    @classmethod
    def run(cls):
        for path in cls.loader_paths:
            PluginLoader(os.path.abspath(os.path.expanduser(path)), ignorefile='ignore')
        return cls.from_commandline()

    @classmethod
    def from_config(cls, config):
        plugin = cls._generate_plugin(config)
        return plugin.submit_calc(cls.queues[config['queue']])
        #

    @classmethod
    def _generate_plugin(cls, config):
        if config['output'] is None:
            config.update({'output': os.path.basename(config['input']) + ".out"}) 

        return cls.plugins.plugin_from_config(config['method'], general=config)
