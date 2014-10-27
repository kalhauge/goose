#!/usr/bin/env python3 

from goose import Box, vbm
import sys
import os
import io

from collections import namedtuple

import logging

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('goose')

class Context():
    
    def __init__(self):
        self.require = list()
        self.reuse = True
        self.close_after = True
        self.port = None
        self.cpus = None
        self.memory = None
        self.email = None

class Parser:

    def __init__(self):
        self.context = Context()

    def baseimage(self, name, filename):
        self.context.baseimage = BaseImage(name, filename)

    def require(self, name, location):
        self.context.require.append(Require(name, os.path.abspath(location)))
        if not os.path.exists(location):
            raise ValueError('%r does not exist' % location)
   
    def port(self, port):
        self.context.port = int(port)

    def user(self, name):
        self.context.user = name
    
    def cpus(self, number):
        self.context.cpus = number
    
    def memory(self, amount):
        self.context.memory = amount

    def identity(self, filename):
        self.context.identity = os.path.abspath(filename)
        if not os.path.exists(filename):
            raise ValueError('%r does not exist' % filename)

    def reuse(self, boolean):
        self.context.reuse = bool(boolean == 'True')
    
    def close_after(self, boolean):
        self.context.close_after = bool(boolean == 'True')

    def parse(self, name, *args):
        getattr(self, name)(*args)
            

BaseImage = namedtuple('BaseImage', ['name', 'filename'])
Require = namedtuple('Require', ['path', 'location'])

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
    log.info('Found box %r', box.name)
    return box
    
def main(commands):
    parser = Parser()
    remote_commands = []
    for command in commands:
        command = command.strip()
        if command.startswith('#goose'):
            args = command.split()
            parser.parse(*args[1:])
        remote_commands += [command] 

    context = parser.context
    box = get_box(context) 
    
    with box.get_ssh_handler(
        context.user, context.identity, context.close_after, 
        port=context.port
    ) as ssh:
        log.info('Runing ssh on %r at port %r.' % (ssh.box.name, ssh.box.port))
        for require in context.require:
            if not ssh.exists(require.path):
                log.debug('%r does not exist copying from %r', *require)
                ssh.copy(require.location, require.path)
            else:
                log.debug('%r does allready exsits', require.path)
        out = ssh.run(
            'tee /tmp/last_cmds.sh | /bin/bash', 
            stdin=remote_commands
        )
        for line in out:
            print(line[:-1])
        log.info('Done')


if __name__ ==  '__main__':
    if len(sys.argv) == 2:
        with open(sys.argv[1]) as f:
            main(f)
    else:
        main(sys.stdin)
