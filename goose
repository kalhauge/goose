#!env python3
"""
GO OS Execute

A simple tool for creating copies of virtual boxes, opening them and
destroying them. 

Simple to use and change.

"""

from subprocess import Popen, call, check_output, PIPE, CalledProcessError, STDOUT
from functools import partial

from random import randrange
import threading
import re
import time
import os
import sys

class VBoxMangage: 
    list_regex = re.compile(r'"(.+)"')
    
    def __init__(self, cmd):
        self.cmd = cmd

    def __getattr__(self, name):
        def function(*args, **kwargs):
            cmd = [self.cmd, name]
            
            for arg in args:
                cmd += [str(arg)]

            for key, arg in kwargs.items():
                if arg == True:
                    cmd += ['--'+key]
                elif arg == False:
                    cmd += []
                elif isinstance(arg, tuple):
                    cmd += ['--'+key] + list(arg)
                else:
                    cmd += ['--'+key, str(arg)]
            try:
                result = check_output(cmd, stderr=STDOUT, universal_newlines=True)
                return result
            except CalledProcessError as e:
                print('In "', ' '.join(cmd), '"an error occured')
                print(e.output)
                raise

        return function

    def import_(self, filename):
        output = self.__getattr__('import')(filename)
        mo = re.search(r'Suggested VM name "(.+)"', output, re.MULTILINE)
        return mo.group(1) if mo else None

    def vms(self):
        return self.list_regex.findall(vbm.list('vms'))

    def running(self):
        return self.list_regex.findall(vbm.list('runningvms'))

vbm = VBoxMangage(os.environ.get('VBOX_MANAGE_CMD', '/usr/bin/vboxmanage'))

def run_ssh(port, login, command, identity_file=None):
    cmd = (
        'ssh -p {port}'
        ' -o StrictHostKeyChecking=no' 
        ' -o UserKnownHostsFile=/dev/null'
        ' -o LogLevel=quiet'
    ).format(port=port)
    if identity_file: cmd += ' -i {}'.format(identity_file)
    cmd += ' {}@127.0.0.1 '.format(login)
    cmd += command
    call(cmd, shell=True)

class Box:

    def __init__(self, name, port=None):
        self.name = name
        self.port = port

    def start(self, port=None):
        self.port = port if not port is None else randrange(3000, 10000)
        self.modify(natpf1="ssh,tcp,,{},,22".format(self.port))
        vbm.startvm(self.name, type='headless')
        return self

    def stop(self):
        if self.is_running():
            vbm.controlvm(self.name, 'poweroff')
            try: vbm.modifyvm(self.name, natpf1=('delete', 'ssh'))
            except CalledProcessError: pass
        return self

    def ssh(self, login, command, identity_file=None):
        run_ssh(self.port, login, command, identity_file)

    def destroy(self):
        if self.is_loaded():
            vbm.unregistervm(self.name, delete=True) 
        return self

    def modify(self, **kwargs):
        vbm.modifyvm(self.name, **kwargs)
        return self

    def is_running(self):
        return self.name in vbm.running()

    def is_loaded(self):
        return self.name in vbm.vms()

    def __repr__(self):
        return 'Box(name={0.name!r}, port={0.port!r})'.format(self)

    def __enter__(self):
        return self.start()

    def __exit__(self, type, value, traceback):
        self.stop()
        
    @classmethod
    def load(cls, filename):
        return cls(vbm.import_(filename))

    @classmethod
    def find(cls, name):
        if name in vbm.vms(): 
            return Box(name)
        elif os.path.exists(name):
            return Box.load(name)
        else:
            raise ValueError('%r is not a file nor a virtual box' % name)

def vms():
    for x in vbm.vms():
        print(x)
    return None

def destroy(name: str):
    """
    Destroys the virtual machine given a name.
    """
    box = Box(name)
    if box.is_loaded():
        if box.is_running():
            box.stop()
        box.destroy()


def ssh(
    name: str, 
    login: str, 
    command: str='sh',
    identity_file: str=None, 
):
    with Box.find(name) as box:
        box.ssh(login, command, identity_file)

def start(
    filename: str, 
    port: int=None,
    timeout: float=3.0   
):
    box = Box.load(filename)
    box.start(port)

    return box


INTERFACES = [
    ssh,
    vms,
    start,
    destroy
]

def main():
    from argparse import ArgumentParser
    from inspect import getfullargspec 

    parser = ArgumentParser('GoOSE')
    group = parser.add_subparsers(help="Commands:")

    for func in INTERFACES:
        subparser = group.add_parser(func.__name__,help=func.__doc__)
        subparser.set_defaults(func=func)

        specs = getfullargspec(func)
        no_position_args = len(specs.args) - (
            len(specs.defaults) if specs.defaults else 0
        )
        for i, name in enumerate(specs.args):
            if i < no_position_args:
                subparser.add_argument(name, type=specs.annotations[name])
            else:
                default = specs.defaults[i - no_position_args]
                anotation = specs.annotations[name]
                if anotation == bool:
                    action = 'store_true' if not default else 'store_false'
                    subparser.add_argument(
                        '--' + name, action=action,
                        default = default
                    )
                else:
                    subparser.add_argument(
                        '--' + name, type=anotation,
                        default = default
                    )

    args = vars(parser.parse_args())
    func = args['func']
    del args['func']
    result = func(**args)
    if not result is None:
        print(result)

if __name__ == '__main__':
    main()

