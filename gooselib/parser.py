"""
Contains esential parser tools, both

"""

import logging
import sys

log = logging.getLogger("gooselib.parser")

class ParseError(Exception):
    
    msg = "Could not parse {0.cmd!r} with args {0.args}"

    def __init__(self, cmd, args):
        self.cmd = cmd
        self.args = args

    def __str__(self):
        return ParseError.msg.format(self)
        
def str2bool(v):
  return v.lower() in ("yes", "true", "t", "1") 

class Rule (object):

    def __init__(self, name, function, default=None, nargs='', location=None):
        self.name = name
        self.parse = function
        self.nargs = nargs
        self.default = default
        self.location = location if location else name

    def handle(self, context, args):
        try:
            if self.nargs in ('*', '+'):
                if not hasattr(context, self.location):
                    setattr(context, self.location, [])
                getattr(context, self.location).append(self.parse(*args))
            else:
                setattr(context, self.location, self.parse(*args))
        except Exception as e:
            log.error("Error found in %s %s", self, args)
            raise e
    def ensure_default(self, context):
        if not hasattr(context, self.location):
            setattr(context, self.location, self.default)

class Context (object):
    pass

class Parser (object):
    
    def __init__(self, lookup):
        self.lookup = lookup
        self._context = Context()

    def handle_lines(self, stream, prefix):
        log.debug('Handeling stream with prefix=%r', prefix)
        for line in stream:
            if not line.startswith(prefix): continue
            words = line[len(prefix):].strip()
            self.parse(words.split())
    
    def handle_commandline(self, args=sys.argv):
        log.debug('Handeling commandline arguments %s', args)
        for arg in args:
            if not arg.startswith('--'): continue
            cmd, cmd_args = arg[2:].split('=')
            self.parse([cmd] + cmd_args.rsplit(',', 1))

    def parse(self, words):
        log.debug('Parsing words: %s', words)
        cmd, args = words[0], words[1:]
        try: self.lookup[cmd].handle(self._context, args)
        except KeyError:
            raise ParseError(cmd, args)

    @property
    def context(self):
        for rule in self.lookup.values():
            rule.ensure_default(self._context)
        return self._context

    @classmethod
    def from_rules(cls, rules):
        return cls({rule.name: rule for rule in rules})

