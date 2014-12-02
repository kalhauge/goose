from .virtualbox import vbm, Nat

import warnings
import time

import subprocess

from random import randrange

import logging
log = logging.getLogger('goose.lib')

class Box (object):
    
    @classmethod
    def load(cls, filename):
        """
        Loads a box from a file. The file should be a `.ova` file.
        """
        return cls(vbm.import_(filename)).sync()

    @classmethod
    def find(cls, name):
        if name in vbm.vms(): 
            return Box(name).sync()
        else:
            raise ValueError('%r is not a file nor a virtual box' % name)

    def __init__(self, name, port=None, cpus=None, memory=None):
        self._name = name
        self._port = port
        self._cpus = cpus
        self._memory = memory
        self.close_on_end = 0

    def start(self):
        log.debug('Starting %s at %s ..', self, self.port)
        if not self.is_running():
            if self.port is None:
                self.port = randrange(10000, 30000)
            log.debug('Not already running')
            vbm.startvm(self.name, type='headless')
            log.debug('Waiting for boot...')
            time.sleep(6)
            log.debug('Boot done.. ')
        else:
            log.debug('Already started at %s...', self.port)
        log.debug('Successfully started %s.. ', self)
        return self

    def stop(self):
        if self.is_running():
            vbm.controlvm(self.name, 'poweroff')
            # Wait for shutdown
            while self.is_running(): time.sleep(1)
            self.port = None
        return self

    def get_ssh_handler(self, *args, **kwargs):
        from .ssh import SSHClient
        return SSHClient('127.0.0.1', self.port, *args, **kwargs)

    def ssh(self, login, command, identity_file=None):
        if not self.is_running(): raise ValueError('Box not running..')
        cmd = (['ssh'] + 
            ['-p' , str(self.port)] +
            (['-i', identity_file] if identity_file else []) + 
            ['{}@127.0.0.1'.format(login)] + command)
        log.debug('Starting ssh with cmd: %s', ' '.join(cmd))
        subprocess.call(cmd) 

    def destroy(self):
        self.stop()
        if self.is_loaded():
            vbm.unregistervm(self.name, delete=True) 
        return self

    def modify(self, **kwargs):
        if self.is_running():
            raise ValueError('Can not set attributes while box is running')
        vbm.modifyvm(self.name, **kwargs)
        return self

    def export(self, output):
        vbm.export(self.name, output=output)

    def is_running(self):
        return self.name in vbm.running()

    def is_loaded(self):
        return self.name in vbm.vms()

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
        self._memory = int(info['memory'])
        self._cpus = int(info['cpus'])
        return self
  
    def _set(name):
        local = '_' + name
        def func(self, attr):
            if not getattr(self, local) == attr:
                try: 
                    self.modify(**{name:attr})
                    setattr(self, local, attr)
                except ValueError as e:
                    warnings.warn('Box is running, can not set {}, {}'.format(name, e))
        return func

    name = property(lambda self: self._name, _set('name'))
    cpus = property(lambda self: self._cpus, _set('cpus'))
    memory = property(lambda self: self._memory, _set('memory'))

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
        return 'Box(name={0.name!r}, port={0.port!r}, cpus={0.cpus!r}, memory={0.memory!r})'.format(self)

    def __enter__(self):
        return self.start()

    def __exit__(self, type, value, traceback):
        if self.close_on_end:
            log.info('Closeing %s', self)
            time.sleep(self.close_on_end)
            self.stop()
        else:
            log.info('Leaving %s open', self)

