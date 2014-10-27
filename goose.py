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
import collections

Nat = collections.namedtuple('Nat', 
    ('name', 'type', 'host_ip', 'host_port', 'client_ip', 'client_port')
)

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

    def info(self, name):
        output = self.showvminfo(name, machinereadable=True)
        info_dict = {}
        for line in output.split('\n'):
            if line:
                name, result = line.split('=')
                info_dict[name] = result.strip('"')

        return info_dict
        

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
    cmd += ' '.join(command)
    call(cmd, shell=True)

class SSHHandler:

    def __init__(self, box, user, identity, close_on_end=True):
        self.box = box
        self.user = user
        self.identity = identity
        self.close_on_end = close_on_end

    def __enter__(self):
        self.box.start()
        return self

    def __exit__(self, type, value, traceback):
        if self.close_on_end:
            self.box.stop()

    def run(self, command, stdin=None):
        cmd = (
            'ssh -p {port}'
            ' -o StrictHostKeyChecking=no' 
            ' -o UserKnownHostsFile=/dev/null'
            ' -o LogLevel=quiet'
            ' -i {identity}'
            ' {user}@127.0.0.1 {cmd!r}'
        ).format(
            port=self.box.port,
            identity=self.identity,
            user=self.user, 
            cmd=command
        )
        if stdin:
            p = Popen(cmd, universal_newlines=True, stdin=PIPE, stdout=PIPE, shell=True)
            for line in stdin:
                print(line, file=p.stdin)
            p.stdin.close()
            return p.stdout
        else:
            return check_output(cmd, universal_newlines=True, shell=True)

    def copy(self, from_, to):
        cmd = (
            'scp -r -P {port}'
            ' -o StrictHostKeyChecking=no' 
            ' -o UserKnownHostsFile=/dev/null'
            ' -o LogLevel=quiet'
            ' -i {identity}'
            ' {from_} {user}@127.0.0.1:{to}'
        ).format(
            port=self.box.port,
            identity=self.identity,
            user=self.user, 
            from_=from_,
            to=to
        )
        return check_output(cmd, universal_newlines=True, shell=True)

    def exists(self, remotefile):
        cmd = '[ -e {} ] && echo -n "True" || echo -n "False"'.format(remotefile)
        output = self.run(cmd)
        return output == 'True'

    def __repr__(self):
        return ('SSHandler(box={0.box}, '
            'user={0.user!r}, '
            'identity={0.identity!r}, ' 
            'close_on_end={0.close_on_end})'
        ).format(self)

class Box:

    def __init__(self, name, port=None):
        self._name = name
        self._port = port

    def start(self, port=None):
        if not self.is_running():
            self.port = port if not port is None else randrange(3000, 10000)
            vbm.startvm(self.name, type='headless')
        return self

    def stop(self):
        if self.is_running():
            vbm.controlvm(self.name, 'poweroff')
            self.port = None
        return self

    def get_ssh_handler(*args, **kwargs):
        return SSHHandler(*args, **kwargs)

    def ssh(self, login, command, identity_file=None):
        run_ssh(self.port, login, command, identity_file)

    def destroy(self):
        if self.is_loaded():
            vbm.unregistervm(self.name, delete=True) 
        return self

    def modify(self, **kwargs):
        if self.is_running():
            raise ValueError('VirtualMachine running, can not alter values')
        vbm.modifyvm(self.name, **kwargs)
        return self

    def is_running(self):
        return self.name in vbm.running()

    def is_loaded(self):
        return self.name in vbm.vms()

    def set_name(self, name):
        self.modify(name=name)
        self._name = name

    def sync(self):
        info = vbm.info(self.name)
        port = None
        for i in range(100):
            name = 'Forwarding({})'.format(i)
            if name in info:
                nat = Nat(*info[name].split(','))
                if nat.name == 'ssh' or nat.client_port == '22':
                    port = int(nat.host_port)
                    break
            else:
                break
        self._port = port
        return self

    name = property(lambda self: self._name, set_name)

    def set_port(self, port):
        if port == self._port:
            return
        elif port is None:
            self.modify(natpf1=('delete', 'ssh'))
        else:
            if not self._port is None:
                self.modify(natpf1=('delete', 'ssh'))
            self.modify(natpf1="ssh,tcp,,{},,22".format(port))
        self._port = port

    port = property(lambda self: self._port, set_port)

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
            return Box(name).sync()
        else:
            raise ValueError('%r is not a file nor a virtual box' % name)