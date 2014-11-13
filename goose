#!/usr/bin/env python2.7 

from gooselib import Box, vbm
import sys
import os
import io
import time

from StringIO import StringIO

from collections import namedtuple

import logging

logging.basicConfig()
log = logging.getLogger('goose')
log.setLevel(logging.DEBUG)

# logging.getLogger('paramiko').setLevel(logging.INFO)

def main(commands):
    log.debug('Parsing file:')
    parser = Parser()
    remote_commands = []
    for command in commands:
        command = command.strip()
        if command.startswith('#goose'):
            args = command.split()
            parser.parse(*args[1:])
        remote_commands += [command] 

    log.debug('Parsing commandline arguments:')
    for arg in sys.argv:
        if arg.startswith('--'):
            key, value = arg[2:].split('=')
            parser.parse(key, *value.split(','))

    context = parser.context

    if context.export and not context.shutdown:
        log.error('Can not export without shuting down')
        sys.exit(-1)

    if not (context.identity or context.password):
        log.error('Neighter password or indentity set')
        sys.exit(-1)
    
    log.debug('Starting box...')
    
    with get_box(context) as box:
        time.sleep(4) 
    
        log.debug('SSH into the box')
        ssh = box.get_ssh_handler(
            username=context.user, 
            password=context.password,
            key_filename=context.identity,
        ) 

        log.info('Runing ssh on %r at port %r.' % (box.name, box.port))
        
        for require in context.require:
            if not ssh.exists(require.remote):
                log.debug('%r does not exist copying from %r', *require)
                ssh.push(require.local, require.remote)
            else:
                log.debug('%r does allready exsits', require.remote)
        
        log.info('Copying over required files')

        cmd_file = StringIO('\n'.join(remote_commands))

        ssh.run('echo "hello"')

        ssh.run('tee /tmp/last_cmds.sh | /bin/bash', in_=cmd_file)

        for produce in context.produce:
            if not ssh.exist(produce.remote):
                log.error('%r does not exist.. %r not created.', *require)
            else:
                log.debug('Copying %s to %s.', *require)
                ssh.pull(produce.remote, produce.local)

        if context.shutdown:
            log.info('Shuting down VirtualMachine')
            out = ssh.run('sudo shutdown now')

    if context.export:
        log.info('Exporting the box to %r', context.export)
        box.export(context.export)
    
    log.info('Done')

def str2bool(v):
  return v.lower() in ("yes", "true", "t", "1") 
class Context():
    
    def __init__(self):
        self.require = list()
        self.produce = list()
        self.reuse = True
        self.shutdown = 0
        self.export = None
        self.port = None
        self.cpus = None
        self.memory = None
        self.email = None
        self.password = None
        self.identity = None

class Parser:

    def __init__(self):
        self.context = Context()

    def baseimage(self, name, filename):
        self.context.baseimage = BaseImage(name, filename)

    def require(self, name, location):
        self.context.require.append(Require(name, os.path.abspath(location)))
        if not os.path.exists(location):
            raise ValueError('%r does not exist' % location)

    def produce(self, name, location):
        self.context.produce.append(Produce(name, os.path.abspath(location)))
    
    def port(self, port):
        self.context.port = int(port)

    def user(self, name):
        self.context.user = name
    
    def cpus(self, number):
        self.context.cpus = number
    
    def memory(self, amount):
        self.context.memory = amount
    
    def password(self, string):
        self.context.password = string

    def identity(self, filename):
        self.context.identity = os.path.abspath(filename)
        if not os.path.exists(filename):
            raise ValueError('%r does not exist' % filename)

    def reuse(self, boolean):
        self.context.reuse = str2bool(boolean) 
    
    def shutdown(self, time):
        self.context.shutdown = int(time) 

    def export(self, path):
        self.context.export = os.path.abspath(path)

    def parse(self, name, *args):
        getattr(self, name)(*args)
            

BaseImage = namedtuple('BaseImage', ['name', 'filename'])
Require = namedtuple('Require', ['remote', 'local'])
Require = namedtuple('Produce', ['remote', 'local'])

def get_box(context):
    try:
        box = Box.find(context.baseimage.name)
    except ValueError:
        log.debug('Box %r not started, loading from filename %r', *context.baseimage)
        box = Box.load(context.baseimage.filename)
        box.name = context.baseimage.name
    else:
        if not context.reuse:
            log.debug(
                'Box %r already loaded, destroying and loading again',
                context.baseimage.name)
            if box.is_running():
                box.stop()
            box.destroy()
            box = Box.load(context.baseimage.filename)
            box.name = context.baseimage.name
    if context.cpus: 
        box.cpus = context.cpus
    else:
        log.debug('No CPUs set, keeping: %s', box.cpus)
    if context.memory: 
        box.memory = context.memory
    else:
        log.debug('No memory set, keeping: %s', box.memory)
    box.close_on_end = context.shutdown
    box.sync()
    log.info('Found box %r', box)
    return box
    


if __name__ ==  '__main__':
    if not sys.argv[-1].startswith('--'):
        with open(sys.argv[-1]) as f:
            main(f)
    else:
        main(sys.stdin)
