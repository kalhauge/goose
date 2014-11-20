"""
Adding ssh connections to the boxes
"""
import os
import sys
from io import StringIO 
from tarfile import TarFile

import time
import threading
import paramiko

import logging

log = logging.getLogger('goose.lib')

class SSHClient:

    def __init__(self,
            hostname, port, username=None, key_filename=None,
            password=None, cache='goose_cache'
    ):
        self.hostname = hostname
        self.port = port 
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.cache = cache
        
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        self.client.connect(
            self.hostname, self.port, self.username, 
            password=self.password,
            key_filename=self.key_filename, 
            timeout=10.0,
        )

    def run(self, cmd, in_=None, out=sys.stdout, err=sys.stderr):

        chan = self.client.get_transport().open_session()

        ##chan.setblocking(1)
        ##chan.settimeout(1000) 
        WINDOW_SIZE = 2048

        stopped = threading.Event()
        def transfer(read, check, stream):
            def inner_function():
                while not stopped.is_set():
                    while check():
                        stream.write(read(WINDOW_SIZE))
                    stream.flush()
                    stopped.wait(0.5)

                while check():
                    stream.write(read(WINDOW_SIZE))
                    stream.flush()
            
            return inner_function
       
        log.debug('Running %s', cmd)  
        chan.exec_command(cmd)

        out_thread = threading.Thread(
            target=transfer(chan.recv, chan.recv_ready, out))
        err_thread = threading.Thread(
            target=transfer(chan.recv_stderr, chan.recv_stderr_ready, err))

        try:
            out_thread.start()
            err_thread.start()
         
            if in_:
                b = in_.read(WINDOW_SIZE)
                while b:
                    chan.sendall(b)
                    b = in_.read(WINDOW_SIZE)
                chan.shutdown_write()
            
            while not chan.exit_status_ready(): 
                time.sleep(1)
                
            exit = chan.recv_exit_status() 
        except:
            log.debug('Error occured while runnig %s', cmd)
            log.debug('Done running %s', exit)
        finally:
            stopped.set()

            out_thread.join()
            err_thread.join()

            chan.close()

        return exit 

    def exists(self, name):
        val = self.run('test -e {} && echo true || (echo false; false)'.format(name)) == 0
        log.debug('exist, %s .. %s', name, val)
        return val

    def push(self, local, remote):
        if os.path.isdir(local):
            if not os.path.exists(self.cache): os.mkdir(self.cache)

            cached_local = local.replace('/', '_') + '.tar.gz'
            cached_file = os.path.join(self.cache, cached_local) 
            
            if not os.path.exists(cached_file):
                tar = TarFile.open(cached_file, 'w:gz')
                tar.add(os.path.realpath(local), arcname='.')
                tar.close()

            with open(cached_file,'rb') as f:
                return self.run(
                    'mkdir -p {0}; tar zxf - -C {0}'.format(remote),
                    in_=ProcessFile(f)
                )
        else:
            with open(local) as f:
                return self.run(
                    'cat > {0}'.format(remote),
                    in_=ProcessFile(f)
                )

    def pull(self, remote, local):
        with open(local, 'w') as f:
            return self.run(
                'cat {0}'.format(remote),
                out=f
            )

    def close(self):
        return self.client.close()

class ProcessFile:

    def __init__(self, i):
        self.i = i
        i.seek(0, os.SEEK_END)
        self.size = i.tell()
        i.seek(0, os.SEEK_SET)

    def read(self, size):
        b = self.i.read(size)
        if b:
            sys.stderr.write('Progress: {:0.2f}%\r'.format(self.i.tell()/self.size * 100))
        return b
       
    def close(self):
        sys.stderr.write('\n')
        self.i.close()




