"""
Main function declaration for confab console_script.

Confab may be used from within a fabfile or as a library. The main
function here is provided as a simple default way to invoke confab's
tasks:

 -  A single directory root is assumed, with templates, data, generated
    and remotes directories defined as subdirectories.

 -  A host list must be provided on the command line.

For more complex invocation, a custom fabfile may be more appropriate.
"""
import getpass
import os
import sys
from optparse import OptionParser
from fabric.api import hide, settings
from fabric.network import disconnect_all

from confab.api import pull, push, diff, generate
from confab.options import Options
from confab.resolve import resolve_hosts_and_roles
from confab.model import load_model_from_dir

_tasks = {'diff':     (diff,     True,  True),
          'generate': (generate, True,  False),
          'pull':     (pull,     False, True),
          'push':     (push,     True,  True)}


def parse_options():
    """
    Parse command line options.

    Directory and host are required, though directory defaults to the current
    working directory.
    """

    usage = "confab [options] {tasks}".format(tasks="|".join(_tasks.keys()))
    parser = OptionParser(usage=usage)

    parser.add_option('-d', '--directory', dest='directory',
                      default=os.getcwd(),
                      help='directory from which to load configuration [default: %default]')

    parser.add_option('-e', '--environment', dest='environment',
                      default="local",
                      help='environment to operate on [default: %default]')

    parser.add_option('-H', '--hosts', dest='hosts',
                      default="",
                      help='comma-separated list of hosts to operate on')

    parser.add_option('-R', '--roles', dest='roles',
                      default="",
                      help='comma-separated list of roles to operate on')

    parser.add_option('-u', '--user', dest='user',
                      default=getpass.getuser(),
                      help='username to use when connecting to remote hosts')

    parser.add_option('-y', '--yes', dest='assume_yes',
                      action='store_true',
                      default=False,
                      help='automatically answer yes to prompts')

    opts, args = parser.parse_args()
    return parser, opts, args


def main():
    """
    Main command line entry point.
    """
    try:
        # Parse and validate arguments
        parser, options, arguments = parse_options()

        try:
            load_model_from_dir(options.directory)
        except ImportError:
            parser.error('Could not find {settings}'.format(settings=os.path.join(options.directory,
                                                                                  'settings.py')))

        # Normalize and resolve hosts to roles mapping
        try:
            hosts_to_roles = resolve_hosts_and_roles(options.environment,
                                                     options.hosts.split(",") if options.hosts else [],
                                                     options.roles.split(",") if options.roles else [])
        except Exception as e:
            parser.error(str(e))

        # Determine task
        task_name = arguments[0]
        try:
            (task, needs_templates, needs_remotes) = _tasks[task_name]
        except KeyError:
            parser.error('Specified task must be one of: {tasks}'.format(tasks=', '.join(_tasks.keys())))

        # Construct task arguments
        kwargs = {'data_dir': os.path.join(options.directory, 'data')}

        if needs_templates:
            kwargs['generated_dir'] = os.path.join(options.directory, 'generated')
        if needs_remotes:
            kwargs['remotes_dir'] = os.path.join(options.directory, 'remotes')

        # Invoke task once per host/role
        for host, roles in hosts_to_roles.iteritems():
            for role in roles:

                # Scope templates dir by role
                kwargs['templates_dir'] = os.path.join(options.directory, 'templates', role)

                print "Running {task} on '{host}' for '{env}' and '{role}'".format(task=task_name,
                                                                                   host=host,
                                                                                   env=options.environment,
                                                                                   role=role)
                with settings(hide('user'),
                              environment=options.environment,
                              host_string=host,
                              role=role,
                              user=options.user):
                    with Options(assume_yes=options.assume_yes):
                        task(**kwargs)

    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted\n")
        sys.exit(1)
    except:
        sys.excepthook(*sys.exc_info())
        sys.exit(1)
    finally:
        disconnect_all()
    sys.exit(0)
