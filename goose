#!/usr/bin/env python2.7 

from gooselib import Box, vbm, Parser, str2bool, Rule
import sys
import os
import io
import time

from random import randrange

from StringIO import StringIO

from collections import namedtuple

import logging

logging.basicConfig()
log = logging.getLogger('goose')
log.setLevel(logging.DEBUG)

def main(fileo):
    lines = fileo.readlines()
    context = get_context(lines)
    
    with get_box(context) as box:
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
                log.debug('%r does already exists', require.remote)
        
        log.info('Copying over required files')

        cmd_file = StringIO(''.join(lines))
        retval = ssh.run('tee /tmp/last_cmds.sh | /bin/bash', in_=cmd_file)

        if retval == 0:
            for produce in context.produce:
                if not ssh.exists(produce.remote):
                    log.error('%r does not exist.. %r not created.', *produce)
                else:
                    log.debug('Copying %s to %s.', *produce)
                    ssh.pull(produce.remote, produce.local)

            if context.shutdown:
                log.info('Shuting down VirtualMachine..')
                out = ssh.run('sudo shutdown now')
        else:
            box.close_on_end = 0

    if retval != 0: 
        log.error(
            'Recieved return value %s, exiting without destroying, exporting'
            ' or shuting down the machine.', 
            retval
        )
        sys.exit(retval)
    
    if context.export:
        log.info('Exporting the box to %r', context.export)
        box.export(context.export)

    if not context.keep:
        log.info('Destroying the box %s', box)
        box.destroy()
    
    log.info('Done')

def get_box(context):
    """ Returns a box """
    try: 
        box = Box.find(context.baseimage.name)
    except ValueError:
        box = None
    else:
        if not context.reuse: 
            log.debug('Destroying old, Box %s', context.baseimage.name)
            box.destroy()
            box = None
    
    if not box:
        log.info('%r not loaded, getting from filename %r', *context.baseimage)
        box = Box.load(context.baseimage.filename)
        box.name = context.baseimage.name

    if box.is_running():
        log.info("Box is already running no values will be set") 
    else:
        if context.cpus: 
            box.cpus = context.cpus
        else: log.debug('No CPUs set, keeping: %s', box.cpus)

        if context.memory: 
            box.memory = context.memory
        else: log.debug('No memory set, keeping: %s', box.memory)

        if context.port: 
            box.port = context.port
        else: 
            box.port = randrange(10000, 30000)
            log.debug('No port set, choosing: %s', box.port)
        
    box.close_on_end = context.shutdown

    box.sync()
    log.info('Found box %r', box)
    return box

BaseImage = namedtuple('BaseImage', ['name', 'filename'])
Require = namedtuple('Require', ['remote', 'local'])
Produce = namedtuple('Produce', ['remote', 'local'])

parser = Parser.from_rules([
    Rule('require', Require, [], '*'),
    Rule('produce', Produce, [], '*'),
    Rule('baseimage', BaseImage),
    Rule('reuse', str2bool, False),
    Rule('keep', str2bool, False), 
    Rule('port', int, 0),
    Rule('cpus', int, 0),
    Rule('memory', int, 0),
    Rule('shutdown', int, 5),
    Rule('export', str),
    Rule('user', str),
    Rule('password', str),
    Rule('identity', str)
])

def get_context(lines):
    parser.handle_lines(lines, prefix="#goose")
    parser.handle_commandline()
    context = parser.context

    if not context.baseimage:
        log.error("Baseimage must be set")
        sys.exit(1)

    for require in context.require:
        if not os.path.exists(require.local):
            log.error("Could not find file %s", require.local)
            sys.exit(1)

    if not context.shutdown:
        if context.export:
            log.error("Can't export without shutdown")
            sys.exit(1)
    
    if not (context.password or context.identity):
        log.error("Eighter password or identity should be set") 
        sys.exit(1)

    return context

if __name__ ==  '__main__':
    if not sys.argv[-1].startswith('--'):
        with open(sys.argv[-1]) as f: 
            main(f)
    else: main(sys.stdin)
