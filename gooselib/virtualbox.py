"""
This module handles all acces to the virtual box. The most important variable is
the *vbm, short for VBoxManage.
"""

from subprocess import Popen, call, check_output, PIPE, CalledProcessError, STDOUT, check_call

import collections
import re
import os

import logging

log = logging.getLogger('goose.lib')

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
#                log.debug(cmd)
                result = check_output(cmd, stderr=STDOUT, universal_newlines=True)
                return result
            except CalledProcessError as e:
                print('In "', ' '.join(cmd), '"an error occured')
                print(e.output)
                raise

        return function

    def import_(self, filename):
        filename = os.path.realpath(filename)
        if not os.path.exists(filename): 
            raise ValueError('{!r} does not exist'.format(filename))
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
