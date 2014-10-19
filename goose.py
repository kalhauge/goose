"""
This is the library part of GoOSE.

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
