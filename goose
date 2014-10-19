#!env python3
"""
GO OS Execute

A simple tool for creating copies of virtual boxes, opening them and
destroying them. 

Simple to use and change.

"""

from goose import Box, vbm

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

