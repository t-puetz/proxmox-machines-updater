import os
import datetime
import argparse
import getpass

from automater.downtimeautomater import DowntimeAutomater
from automater.logger import Logger
from automater.pmcrawler import ProxmoxCrawler
from automater.server import Server
from automater.srvsorter import ServerSorter
from automater.statemachine import StateMachine


class Program:
    def __init__(self):
        self.version = '0.5.0'
        self.argparser = argparse.ArgumentParser(description='Downtime Automater')
        self.now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.main_logging_folder_prefix = './downtime_automation_run_main_logfolder_'
        self.main_logging_folder = ''
        self.mainlogger = None
        self.args = None
        self.proxmox_ips = []
        self.blacklist = []
        self.whitelist = []
        self.connect_kwargs_proxmoxes = {}
        self.connect_kwargs_servers = {}
        self.proxmox_logger_subfolder_prefix = f'logs_downtime_automation_run_'
        self.proxmox_logger_subfolder = ''
        self.proxmox_crawler_objs = []
        self.proxmox_logger_map = {}
        self.kvm_servers_prelim_datastructure = []
        self.lxc_servers_prelim_datastructure = []
        self.kvm_servers_final = []
        self.lxc_servers_final = []
        self.srvsorter = None
        self.all_linux_servers = []
        self.downtime_automater = None
        self.serverlogger_host_map = {}
        self.statemachine_host_map = {}

    def parse_flags(self):
        argparser = self.argparser

        self.argparser.add_argument('--serialized', action='store_true', help='Runs downtime on linux server via SSH one in a row')
        self.argparser.add_argument('--threaded', action='store_true',   help='Runs downtime on linux server via SSH theaded (for experts: via ThreadPool.starmap())')
        self.argparser.add_argument('--proxmox-ips', required=True, help='Add comma seperated of Proxmoxes to manage')
        self.argparser.add_argument('--ssh-port-proxmox', default=22, help='SSH Port to access Proxmox(es)')
        self.argparser.add_argument('--ssh-private-key-proxmox', required=False, default=os.environ['HOME'] + '/.ssh/id_rsa', help='Path to private key to use for connecting to Proxmox(es). Default $HOME/.ssh/id_rsa.pub')
        self.argparser.add_argument('--ssh-passphrase-proxmox', action='store_true', help='Passphrase to use for keyfile for Proxmox(es)')
        self.argparser.add_argument('--ssh-password-proxmox', action='store_true', help='Password to use for SSH authentification for Proxmox(es)')
        self.argparser.add_argument('--ssh-port-servers', default=22, help='SSH Port to access Servers (on Proxmox(es))')
        self.argparser.add_argument('--ssh-private-key-servers', required=False, default=os.environ['HOME'] + '/.ssh/id_rsa', help='Path to private key to use for connecting to servers. Default $HOME/.ssh/id_rsa.pub')
        self.argparser.add_argument('--ssh-passphrase-servers', action='store_true', help='Passphrase to use for keyfile (servers)')
        self.argparser.add_argument('--ssh-password-servers', action='store_true', help='Password to use for SSH authentification (servers)')
        self.argparser.add_argument('--blacklist', default=[], help='Comma seperated list of servers HOSTNAMES (IPs won\'t work) not to work on')
        self.argparser.add_argument('--whitelist', default=[], help='Comma seperated list of servers HOSTNAMES (IPs won\'t work) TO EXCLUSIVELY work on. A whitelist cancels a blacklist.')
        self.argparser.add_argument('--test-and-exit', action='store_true', help='Run two simple test subtasks on the servers AND EXIT')
        self.argparser.add_argument('--test-and-run', action='store_true', help='Run two simple test subtasks on the servers AND RUN REGULARLY AFTERWARDS')
        self.argparser.add_argument('--debug-level', choices=['debug', 'info', 'warning', 'error', 'critical'] , help='Provide loglevel you want to be printed.')
        self.argparser.add_argument('--no-reboot', action='store_true', help='Skip last subtask that reboots the machine(s).')

        self.args = argparser.parse_args()

    def get_datetime_now_intl(self):
        return self.now

    def create_main_logger(self):
        # This logger just logs main()
        time_main_start = self.get_datetime_now_intl()
        main_logging_folder = self.main_logging_folder_prefix + time_main_start
        self.mainlogger = Logger(time_main_start, self.args, 'main', main_logging_folder)

    def parse_proxmox_ips(self):
        self.args.proxmox_ips = list(filter(lambda x: x, self.args.proxmox_ips.split(',')))
        self.proxmox_ips = self.args.proxmox_ips
        self.mainlogger.log(f'Proxmox IPs provided: {self.args.proxmox_ips}', 'info')

    def parse_blacklist(self):
        if self.args.blacklist:
            self.blacklist = list(filter(lambda x: x, self.args.blacklist.split(',')))
            self.blacklist = [] if self.blacklist == ',' else self.blacklist
            self.args.blacklist = self.blacklist
            self.mainlogger.log(f'Blacklisted Servers: {self.blacklist}', 'debug')

    def parse_whitelist(self):
        if self.args.whitelist:
            self.whitelist = list(filter(lambda x: x, self.args.whitelist.split(',')))
            self.blacklist = [] if self.whitelist == ',' else self.whitelist
            self.args.whitelist = self.whitelist
            self.mainlogger.log(f'Whitelisted Servers: {self.whitelist}', 'debug')

    def detect_blacklist_whitelist_conflict(self):
        # A whitelist forbids usage of a blacklist, so empty the blacklist
        if self.whitelist and self.blacklist:
            self.mainlogger.log('Found whitelist AND blacklist. Deactivating blacklist by emptying it.', 'info')
            self.args.blacklist = []
            self.blacklist = []

    def create_connect_kwargs_proxmoxes(self):
        self.connect_kwargs_proxmoxes['key_filename'] = self.args.ssh_private_key_proxmox

        if self.args.ssh_password_proxmox:
            password = getpass.getpass(prompt='SSH Password for Proxmox(es): ')
            self.connect_kwargs_proxmoxes['password'] = password

        if self.args.ssh_passphrase_proxmox:
            passphrase = getpass.getpass(prompt='Passphrase for SSH key file for Proxmox(es): ')
            self.connect_kwargs_proxmoxes['passphrase'] = passphrase

    def create_connect_kwargs_servers(self):
        self.connect_kwargs_servers['key_filename'] = self.args.ssh_private_key_servers

        if self.args.ssh_password_servers:
            password = getpass.getpass(prompt='SSH Password for Servers: ')
            self.connect_kwargs_servers['password'] = password

        if self.args.ssh_passphrase_servers:
            passphrase = getpass.getpass(prompt='Passphrase for SSH key file for Servers: ')
            self.connect_kwargs_servers['passphrase'] = passphrase

    def create_proxmox_crawlers(self):
        # They are pre-downtime stage
        # and will take care of creating the main
        # logging folder for each proxmox
        for proxmox_ip in self.args.proxmox_ips:
            now = self.get_datetime_now_intl()
            self.proxmox_logger_subfolder = self.mainlogger.folder + '/' + self.proxmox_logger_subfolder_prefix + self.get_datetime_now_intl() + '_' + proxmox_ip
            proxmoxlogger = Logger(now, self.args, proxmox_ip, self.proxmox_logger_subfolder)
            self.proxmox_logger_map[proxmox_ip] = proxmoxlogger

            pc = ProxmoxCrawler(self.args, self.connect_kwargs_proxmoxes, proxmoxlogger, proxmox_ip)
            self.proxmox_crawler_objs.append(pc)

    def get_kvm_servers_prelim_datastructure(self):
        for proxmox_crawler in self.proxmox_crawler_objs:
            kvm_map = proxmox_crawler.get_machine_attributes_single_proxmox('KVM')
            kvm_map = proxmox_crawler.add_missing_data_to_kvm_servers_single_proxmox(kvm_map)
            self.mainlogger.log(f'KVM MAP: {kvm_map}', 'debug')
            self.kvm_servers_prelim_datastructure.append(kvm_map)

    def get_lxc_servers_prelim_datastructure(self):
        for proxmox_crawler in self.proxmox_crawler_objs:
            lxc_map = proxmox_crawler.get_machine_attributes_single_proxmox('LXC')
            self.mainlogger.log(f'LXC MAP: {lxc_map}', 'debug')
            self.lxc_servers_prelim_datastructure.append(lxc_map)

    def transform_server_info_to_proper_server_obj(self, vtype):
        if vtype == 'KVM':
            self.mainlogger.log(
                f'Preliminary {vtype} data collected from Proxmox(es) by using qm config:\n {self.kvm_servers_prelim_datastructure}',
                'debug')
        elif vtype == 'LXC':
            self.mainlogger.log(
                f'Preliminary {vtype} data collected from Proxmox(es) by using pct config:\n {self.lxc_servers_prelim_datastructure}',
                'debug')

        if vtype == 'KVM':
            srv_info_preliminary_structure = self.kvm_servers_prelim_datastructure
        else:
            srv_info_preliminary_structure = self.lxc_servers_prelim_datastructure

        for outer_dict in srv_info_preliminary_structure:
            proxmox = outer_dict['Proxmox']
            servers = outer_dict['Servers']

            s = ''

            for server in servers:
                if vtype == 'KVM' and server['name'] != 'BLACKLISTED':
                    s = Server(proxmox, server['name'], server['ip'], server['id'], 'KVM', server['ostype'])#, logger)
                elif vtype == 'LXC' and server['hostname'] != 'BLACKLISTED':
                    # Create a dict {'net-adatper-name': 'ip'}
                    # because we can have more than one adapter

                    ips = {}

                    for key in server.keys():
                        # If the adapter name ever DOES NOT start with net we are screwed!
                        if key.startswith('net') and key[3:].isdigit():
                            # We found something like net0, net1, net2 etc.
                            net_adapter_configval = server[key]

                            ips[key] = ''
                            ip_cidr = ''
                            ip = ''

                            for fieldvalmap in net_adapter_configval.split(','):
                                if fieldvalmap.startswith('ip='):
                                    ip_cidr = fieldvalmap.split('=')[1]
                                    # Remove subnet mask
                                    ip = ip_cidr[0:ip_cidr.rfind('/')]
                                    ips[key] = ip

                    s = Server(proxmox, server['hostname'], ips, server['id'], 'LXC', server['ostype'])#, logger)

                if s and vtype == 'KVM':
                    self.kvm_servers_final.append(s)
                elif s and vtype == 'LXC':
                    self.lxc_servers_final.append(s)
                else:
                    self.mainlogger.log('No servers found.', 'debug')

    def get_kvm_servers_final(self):
        # Transform the crawled data we for now put into a dict
        # with a string key and a key that is a list of server dictionaries
        # into proper server objects
        self.transform_server_info_to_proper_server_obj('KVM')

        # Cast map objects to list
        self.kvm_servers_final = list(self.kvm_servers_final)

        self.mainlogger.log(f'Final collected data KVM servers\n{[serverobj.__str__() for serverobj in self.kvm_servers_final]}',
                       'debug')

    def get_lxc_servers_final(self):
        # Transform the crawled data we for now put into a dict
        # with a string key and a key that is a list of server dictionaries
        # into proper server objects
        self.transform_server_info_to_proper_server_obj('LXC')

        # Cast map objects to list
        self.lxc_servers_final = list(self.lxc_servers_final)

        self.mainlogger.log(f'Final collected data LXC servers\n{[serverobj.__str__() for serverobj in self.kvm_servers_final]}',
                       'debug')

    def filter_servers_for_final_usage(self):
        self.srvsorter = ServerSorter(self.args, self.lxc_servers_final, self.kvm_servers_final, self.mainlogger, self.whitelist)
        self.srvsorter.remove_windows_kvm_servers()
        self.srvsorter.merge_all_linux_servers()
        self.srvsorter.apply_whitelist()
        self.all_linux_servers = self.srvsorter.all_linux_servers

    def create_statemachine_host_and_logger_host_maps(self):
        if self.all_linux_servers:
            self.downtime_automater = DowntimeAutomater(self.args, self.connect_kwargs_servers, self.all_linux_servers, self.srvsorter)

            # Clean up memory from obsolete objects and data
            del(self.srvsorter)
            del(self.lxc_servers_prelim_datastructure)
            del(self.kvm_servers_prelim_datastructure)
            del(self.lxc_servers_final)
            del(self.kvm_servers_final)

            for linux_server in self.all_linux_servers:
                if linux_server:
                    time = self.get_datetime_now_intl()
                    proxmox = linux_server.proxmox
                    proxmox_logger_obj = self.proxmox_logger_map[proxmox]
                    server_log_folder = proxmox_logger_obj.folder + f'/{time}_{linux_server.name}'
                    serverlogger = Logger(time, self.args, linux_server.name, server_log_folder)
                    self.serverlogger_host_map[linux_server.name] = serverlogger
                    self.mainlogger.log(f'Starting downtime. Creating statemachine for: {linux_server}', 'debug')
                    sm = StateMachine(self.downtime_automater.linux_subtasks, self.args, serverlogger)
                    self.statemachine_host_map[linux_server.name] = sm
        else:
            print(f'No servers found nothing to do: {self.kvm_servers_sorted_by_os}')
            self.mainlogger.log(f'No servers found nothing to do: {self.kvm_servers_sorted_by_os}', 'debug')

    def run(self):
        self.parse_flags()

        self.create_main_logger()
        self.mainlogger.log(f'Downtime Automater v{self.version} started...', 'debug')

        self.parse_proxmox_ips()

        self.parse_whitelist()
        self.parse_blacklist()
        self.detect_blacklist_whitelist_conflict()

        self.create_connect_kwargs_proxmoxes()
        self.create_connect_kwargs_servers()
        self.create_proxmox_crawlers()
        self.get_kvm_servers_prelim_datastructure()
        self.get_lxc_servers_prelim_datastructure()
        self.get_kvm_servers_final()
        self.get_lxc_servers_final()

        self.filter_servers_for_final_usage()
        self.create_statemachine_host_and_logger_host_maps()

        if self.args.serialized and self.args.threaded:
            raise Exception('You chose both --threaded and --serialized. Just choose one, please.')

        if self.args.serialized:
            # Serialized version
            for hostname, statemachine in self.statemachine_host_map.items():
                self.downtime_automater.execute_linux_downtime_on_single_server(hostname, statemachine, self.serverlogger_host_map[hostname])
        elif self.args.threaded:
            # Threaded version
            self.downtime_automater.execute_linux_downtime_threaded(self.statemachine_host_map, self.serverlogger_host_map)


def main():
    program = Program()
    program.run()


if __name__ == '__main__':
    main()
