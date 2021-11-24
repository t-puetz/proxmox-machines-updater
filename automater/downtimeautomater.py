import fabric
import paramiko
import invoke
import socket
from multiprocessing.pool import ThreadPool


class DowntimeAutomater:
    def __init__(self, args, connect_kwargs, linux_servers, ServerSorter):
        self.args = args
        self.ServerSorter = ServerSorter
        self.connect_kwargs = connect_kwargs
        # Any non-productive test task should strat with 'test'
        # because the statemachine will not be invoked on them
        # if startswith('test') == True
        self.linux_subtasks = ['test', 'test2', 'ubuntu-upgrade-policy', 'update', 'download-upgrades',
                               'install-upgrades', 'release-upgrade', 'autoclean', 'reboot']

        if not self.args.test_and_run and not self.args.test_and_exit:
            self.linux_subtasks = ['ubuntu-upgrade-policy', 'update', 'download-upgrades',
                                   'install-upgrades', 'release-upgrade', 'autoclean', 'reboot']

        if self.args.no_reboot and (self.args.test_and_run or self.args.test_and_exit):
            self.linux_subtasks = ['test', 'test2', 'ubuntu-upgrade-policy', 'update', 'download-upgrades',
                                   'install-upgrades', 'release-upgrade', 'autoclean']

        if self.args.no_reboot and not self.args.test_and_run and not self.args.test_and_exit:
            self.linux_subtasks = ['ubuntu-upgrade-policy', 'update', 'download-upgrades',
                                   'install-upgrades', 'release-upgrade', 'autoclean']
        self.linux_servers = linux_servers
        self.logger = None

    def run_linux_subtask(self, connection, subtask, logger):
        # Step 0 - For Ubuntu hosts change upgrade policy from LTS
        # to normal if Ubuntu is LTS release
        serverobj = self.ServerSorter.get_server_by_hostname(connection.host, self.linux_servers)
        os = serverobj.os

        if subtask not in self.linux_subtasks:
            raise Exception(f'run_linux_subtask(): Invalid subtask {subtask}. Subtask should be one of: {self.linux_subtasks}')

        if subtask == 'test':
            cmd = 'hostname'
        elif subtask == 'test2':
            cmd = 'echo test2'
        elif subtask == 'ubuntu-upgrade-policy':
            if os.lower().startswith('ubuntu'):
                cmd = "sed -i 's:Prompt=lts:Prompt=normal:' /etc/update-manager/release-upgrades"
            elif os.lower().startswith('debian'):
                cmd = "echo 'Debian system. No need to change upgrade policy. Task will not do anything but echoing this message.'"
        elif subtask == 'update':
            cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive; apt-get update -y'
        elif subtask == 'download-upgrades':
            cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive; apt-get -d upgrade -y'
        elif subtask == 'install-upgrades':
            cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive; apt-get -o Dpkg::Options::="--force-confdef" --allow-change-held-packages upgrade -y'
        elif subtask == 'release-upgrade':
            if os.lower().startswith('ubuntu'):
                cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive; do-release-upgrade -f DistUpgradeViewNonInteractive --mode=server'
            elif os.lower().startswith('debian'):
                cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive ; apt-get -o Dpkg::Options::="--force-confdef" --allow-downgrades --allow-remove-essential --allow-change-held-packages dist-upgrade -y'
        elif subtask == 'autoremove':
            cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive; apt-get autoremove -y'
        elif subtask == 'autoclean':
            cmd = 'export TERM=xterm-256color; export DEBIAN_FRONTEND=noninteractive; apt-get autoclean -y'
        elif subtask == 'reboot' and not self.args.no_reboot:
            cmd = 'reboot'

        result = {}
        hostnames_that_failed = []
        errors = {}
        hostname = connection.host

        logger.log(f'Will run subtask {subtask} now on host {hostname}', 'info')

        # Start running the command on the serial or threading group
        # If a GroupException is raised instead of a regular GroupResult
        # intercept the error and get the hostnames of servers
        # where these errors occurs.
        #
        # The regular results (GroupResults, a Collection which is a dict like object)
        # then becomes e.result (GroupException)

        try:
            result = connection.run(cmd, warn=True, hide=True)

            logger.log(f"""Command {result.command} on host {hostname}\n
------ Stdout:\n{result.stdout}\n
------ Stderr:\n{result.stderr}\n------""", 'info')

            # E.g. I treat The following packages have been kept back: as if it was an error
            # also it occurs in stdout. That is Why we pass both stderr and stdout.
            errors[hostname] = result.stdout + '\n' + result.stderr

            logger.log(f'Found something in stderr: might or might not be critical. {result.stderr}', 'critical')
            hostnames_that_failed.append(hostname)
            self.error_handler(connection, logger, error=errors[hostname])

        except Exception as e:
            logger.log(f'An Exception was thrown:\n{e}\n', 'error')
            logger.log(f'The result (the error\'s value) is of type:\n{type(result)}\n', 'error')
            if isinstance(result, socket.gaierror):
                logger.log(f'FAILED: Network socket.gaierror on {hostname}. Error: {result}', 'error')
                hostnames_that_failed.append(hostname)
            elif isinstance(result, paramiko.ssh_exception.AuthenticationException):
                logger.log('FAILED: Authentication failed on {hostname}. Error: {result}', 'error')
                hostnames_that_failed.append(hostname)
            elif isinstance(result, invoke.UnexpectedExit):
                logger.log(f'FAILED: UnexpectedExit on {hostname} most likely due to a remote command error: {e}', 'error')
                errors[hostname] = e
                self.error_handler(connection, logger, error=errors[hostname])
                hostnames_that_failed.append(hostname)
            elif isinstance(result, Exception):
                logger.log(f'FAILED: Unknown error for {hostname}. Error: {result}!', 'error')
                hostnames_that_failed.append(hostname)

        for hostname in hostnames_that_failed:
            if connection.host == hostname:
                logger.log(f'Second and last dull try to fix occured errors. All errors found are: {errors})', 'debug')
                if hostname in errors:
                    logger.log(f'Gonna try to fix error on {hostname} second and last time.', 'debug')
                    # Try to fix the error a second time
                    # If this won't work we abort
                    error = errors[hostname]
                    self.error_handler(connection, logger, error=error)
                    try:
                        result = connection.run(cmd, warn=True)
                        logger.log(f'Trying for the last time to fix {error}. Result was: {result}', 'debug')
                        if not result.stderr:
                            continue
                        return False
                    except:
                        return False

                logger.log(f'Closing connection for failed server: {connection.host}', 'info')

        # Subtask successfully finished
        return True

    def execute_linux_downtime_on_single_server(self, hostname, statemachine, logger):
        logger.log(f'Executing execute_linux_downtime for server {hostname}', 'debug')
        logger.log(f'Will open connection for: {hostname} now...', 'info')
        connection = fabric.Connection(host=hostname, user='root', port=self.args.ssh_port_servers, connect_kwargs=self.connect_kwargs)
        logger.log(f'execute_linux_downtime_on_single_server(): Connection created: {connection}', 'info')

        statemachine.tasks = self.linux_subtasks

        while not statemachine.get_statemachine_at_end():
            subtask = self.linux_subtasks[statemachine.get_current_state()]

            if statemachine.get_current_state() == 0:
                 logger.log('\n\n\n\n\n', 'info')

            logger.log(f'Current state/subtask:\n{statemachine.get_current_state()}/{subtask} ON {connection.host}\n', 'info')
            subtask_success = self.run_linux_subtask(connection, subtask, logger)

            if subtask_success:
                logger.log(f'run_linux_subtask() returned successfully: {subtask_success}. Continuing to next task :)\n', 'info')
                statemachine.set_next_state()
                logger.log(f'Moving from to next subtask \n{statemachine.get_current_state()}\n ON {connection.host} ', 'info')
            else:
                logger.log(f'run_linux_subtask() for subtask {statemachine.get_current_state()}/{subtask} ON {connection.host} returned with error: {not subtask_success}. Breaking subtask main loop!', 'info')
                return False

        return True

    def execute_linux_downtime_threaded(self, statemachine_map, server_logobj_map):
        argsmap = []
        MAX_THREADS = 16
        threads = 2
        chunks = {'chunksize': None}

        for hostname1, statemachine in statemachine_map.items():
            server_logobj = server_logobj_map[hostname1]
            argsmap.append([hostname1, statemachine, server_logobj])

        if MAX_THREADS < len(argsmap):
            import math
            chunks['chunksize'] = math.floor(len(argsmap) / MAX_THREADS)

            if isinstance(chunks['chunksize'], float):
                chunks['chunksize'] = math.ceil(chunks['chunksize'])

            threads = MAX_THREADS
        else:
            threads = len(argsmap)

        with ThreadPool(processes=MAX_THREADS) as pool:
            pool.starmap(self.execute_linux_downtime_on_single_server, argsmap, **chunks)

    def error_handler(self, cxn, logger, error=None):
        # This function will handle UnexpectedExits
        # or alternatively messages from stderr
        # that did not cause an unexpected exit
        # Because these errors happen when a remote command
        # exits with an error

        if error == invoke.UnexpectedExit:
            if error.result.stderr.find('The following packages have been kept back') != -1:
                logger.log('Will handle "The following packages have been kept back" apt-error now:\n\n', 'warning')

                error.result = error.result.split('\n')
                index = error.result.index('The following packages have been kept back:')
                kept_back_pkgs = []

                for i in range(index + 1, (len(error.result) - 1)):
                    kept_back_pkgs.append(error.result[i])

                # Remove the last line which look something like this:
                # 0 upgraded, 0 newly installed, 0 to remove and 1 not upgraded.
                counter = 0

                while kept_back_pkgs:
                    line = kept_back_pkgs[counter]
                    line_is_of_interest = line.find('upgrade') != -1 and line.find('newly') != -1 and line.find('remove') != -1
                    if line_is_of_interest:
                        kept_back_pkgs.remove(line)
                        break
                    else:
                        counter += 1

                kept_back_pkgs = ' '.join(kept_back_pkgs)
                result = cxn.run(f'apt-get install -y {kept_back_pkgs}', warn=True)
                logger.log(f'To handle "apt packages kept back"-error I ran {result.command} on host {cxn.host}\nStdout:\n{result.stdout}\nStderr:\n{result.stderr}', 'info')
            elif error.result.stderr.find('--fix-broken') != -1:
                logger.log('Will handle "apt --fix-broken install" apt-error now (as unexpectedExit error):\n\n', 'warning')
                cxn.run('apt-get --fix-broken install', warn=True)
            elif error.result.stderr.find('--fix-missing') != -1:
                logger.log('Will handle "apt --fix-missing install" apt-error now (as unexpectedExit error):\n\n', 'warning')
                cxn.run('apt-get --fix-missing install', warn=True)
            else:
                logger.log('Unknown stderr error. Not fixing anything!', 'info')

        if isinstance(error, str):
            if error.find("you must manually run 'dpkg --configure -a'") != -1:
                logger.log('Will handle "dpkg was interrupted, you must manually run \'dpkg --configure -a\'" error', 'warning')
                cxn.run('dpkg --configure -a', warn=True)
            elif error.find("Could not get lock /var/lib/dpkg/lock") != -1:
                logger.log('Will handle "Could not get lock /var/lib/dpkg/lock" error', 'info')
                cxn.run('kill -9 `pgrep apt`; kill -9 `pgrep dpkg`; -rfv /var/lib/dpkg/lock', warn=True)
            elif error.find('--fix-broken') != -1:
                logger.log('Will handle "apt --fix-broken install" apt-error now (as stderr string):\n\n', 'warning')
                cxn.run('apt-get --fix-broken install', warn=True)
            elif error.find('--fix-missing') != -1:
                logger.log('Will handle "apt --fix-missing install" apt-error now (as stderr string):\n\n', 'warning')
                cxn.run('apt-get --fix-missing install', warn=True)
            elif error.find('hostname: command not found') != -1:
                # Stupid, made up scenario just for testing
                logger.log('Will handle "hostname: command not found" error', 'info')
                cxn.run('echo "Not actually fixing the error :P. This is just for function testing."', warn=True)
            elif error.find('The following packages have been kept back') != -1:
                logger.log('Will handle "The following packages have been kept back" in stdout as if it was an apt-error now:\n\n', 'warning')

                error = error.split('\n')
                index = error.index('The following packages have been kept back:')
                kept_back_pkgs = []

                for i in range(index + 1, (len(error) - 1)):
                    kept_back_pkgs.append(error[i])

                # Remove the last line which look something like this:
                # 0 upgraded, 0 newly installed, 0 to remove and 1 not upgraded.
                counter = 0

                while kept_back_pkgs:
                    line = kept_back_pkgs[counter]
                    line_is_of_interest = line.find('upgrade') != -1 and line.find('newly') != -1 and line.find('remove') != -1
                    if line_is_of_interest:
                        kept_back_pkgs.remove(line)
                        break
                    else:
                        counter += 1

                kept_back_pkgs = ' '.join(kept_back_pkgs)
                result = cxn.run(f'apt-get install -y {kept_back_pkgs}', warn=True)
                logger.log(f'To handle "apt packages kept back"-error I ran {result.command} on host {cxn.host}\nStdout:\n{result.stdout}\nStderr:\n{result.stderr}', 'info')
            else:
                logger.log('Unknown stderr error. Not fixing anything!', 'info')
