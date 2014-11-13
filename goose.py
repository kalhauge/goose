"""
This is the library part of GoOSE.

"""

from functools import partial

from subprocess import Popen, call, check_output, PIPE, CalledProcessError, STDOUT, check_call

from random import randrange
import time
import threading
import re
import time
import os
import sys
import collections


import warnings

import logging
log = logging.getLogger('goose')

class SSHHandler:

    def __init__(self, box, user, password=None, identity=None, port=None):
        self.box = box
        self.user = user
        self.password = password
        self.identity = identity
        self.port = port

    def ssh_command(self, command):
        return (
            'ssh -p {port}'
            ' -o StrictHostKeyChecking=no' 
            ' -o UserKnownHostsFile=/dev/null'
            ' -o LogLevel=quiet' +
            (' -i {identity}' if self.identity else '') + 
            ' {user}@127.0.0.1 {cmd!r}'
        ).format(
            port=self.box.port,
            identity=self.identity,
            user=self.user, 
            cmd=command
        )
    def run(self, command, stdin=None):
        cmd = self.ssh_command(command)

        if stdin:
            p = Popen(cmd, universal_newlines=True, stdin=PIPE, stdout=PIPE, shell=True)
            if not self.identity:
                time.wait(1)
                print(self.password)
                p.stdin.write(self.password)
                p.stdin.flush()
            for line in stdin:
                print(line, file=p.stdin)
            p.stdin.close()
            return p.stdout
        else:
            return check_output(cmd, universal_newlines=True, shell=True)

    def copy(self, from_, to, use_cache=True):
        if os.path.isdir(from_):
            from tarfile import TarFile
            if not os.path.exists('goose_cache'):
                os.mkdir('goose_cache')

            filename = to.replace('/', '_')

            cache_file = os.path.join('goose_cache', filename + '.tar.gz')
            if not os.path.exists(cache_file) or not use_cache:
                tar = TarFile.open(cache_file, 'w:gz')
                tar.add(os.path.realpath(from_), arcname='.')
                tar.close()
            
            cmd = self.ssh_command('mkdir -p {0}; tar zxf - -C {0}'.format(to))
            p = Popen(cmd, stdin=PIPE, shell=True)
            with open(cache_file,'rb') as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(0, os.SEEK_SET)
                b = f.read(10240)
                while b:
                    sys.stderr.write('Progress: {:0.2f}%\r'.format(f.tell()/size * 100))
                    sys.stderr.flush()
                    p.stdin.write(b)
                    b = f.read(10240)
                p.stdin.close()
                sys.stderr.write('\n')
            p.wait()
            return p.poll()
        else:
            cmd = (
                'scp -r -P {port}'
                ' -o StrictHostKeyChecking=no' 
                ' -o UserKnownHostsFile=/dev/null'
                ' -o LogLevel=quiet' +
                (' -i {identity}' if self.identity else '') +
                ' {from_} {user}@127.0.0.1:{to}'
            ).format(
                port=self.box.port,
                identity=self.identity,
                user=self.user, 
                to=to,
                from_=from_
            )
            return check_call(cmd, universal_newlines=True, shell=True)

    def fetch(self, to, from_):
        cmd = (
            'scp -r -P {port}'
            ' -o StrictHostKeyChecking=no' 
            ' -o UserKnownHostsFile=/dev/null'
            ' -o LogLevel=quiet' + 
            (' -i {identity}' if self.identity else '') + 
            ' {user}@127.0.0.1:{from_} {to}'
        ).format(
            port=self.box.port,
            identity=self.identity,
            user=self.user, 
            to=to,
            from_=from_
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

