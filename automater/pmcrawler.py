import fabric

class ProxmoxCrawler:
    def __init__(self, args, connect_kwargs, logger, proxmox_ip):
        self.proxmox_ip = proxmox_ip
        self.port = args.ssh_port_proxmox
        self.connect_kwargs = connect_kwargs
        self.connection = None
        self.args = args
        self.logger = logger
        self.collected_attributes = {}

    def get_connections_fab_single(self):
        return fabric.Connection(self.proxmox_ip, user='root', port=self.port, connect_kwargs=self.connect_kwargs)

    def get_stopped_servers_single_proxmox(self, vtype):
        result = {}
        connection = self.get_connections_fab_single()
        stopped_servers = {}

        # Let's first find out what servers are shutdown/offline
        # So we can ignore them
        # awk prints something like this: test-machine.domain.com:stopped
        if vtype == 'KVM':
            cmd = "qm list | awk '(NR>1)' | awk '{print $2\":\"$3}'"
        elif vtype == 'LXC':
            cmd = "pct list | awk '(NR>1)' | awk '{print $3\":\"$2}'"

        result = connection.run(cmd, warn=True, hide=True)

        primitive_map = result.stdout.split('\n')
        primitive_map = filter(lambda x: x, primitive_map)

        for mapping in primitive_map:
            hostname = mapping.split(':', 1)[0]
            status = mapping.split(':', 1)[1]

            if status == 'stopped':
                stopped_servers[hostname] = status

        self.logger.log(f'Found stopped servers: {stopped_servers}\nStopped servers will be ignored on next loop.\n', 'info')

        connection.close()

        return stopped_servers

    def get_machine_attributes_single_proxmox(self, vtype):
        connection = self.get_connections_fab_single()
        stopped_servers = self.get_stopped_servers_single_proxmox(vtype)

        # The following for loop
        # are our foundation for getting our
        # preliminary data structure
        # (That will later be transformed to proper Server objects)
        if vtype == 'KVM':
            cmd = "for id in $(qm list | awk 'NR>1 {print $1}' | tr '\\n' ' '); do printf \"id: $id\\n\"; qm config $id;printf '======\\n';done"
        elif vtype == 'LXC':
            cmd = "for id in $(pct list | awk 'NR>1 {print $1}' | tr '\\n' ' '); do printf \"id: $id\\n\"; pct config $id;printf '======\\n';done"

        result = connection.run(cmd, warn=True, hide=True)

        # Take the ouput of pct config
        # (That I prepended by id: <id> manually)
        # and transform it into a native python dict
        # put all the dicts into a list

        # {'Proxmox': proxmox, 'Servers': [{}, {}, ...]}
        servers = []
        proxmox = connection.host
        proxmox_server_map = {'Proxmox': proxmox, 'Servers': servers}

        blocks = result.stdout.split('======\n')
        blocks = filter(lambda x: x, blocks)

        for block in blocks:
            current_server = {}
            keyvals = block.split('\n')
            keyvals = filter(lambda x: x, keyvals)

            for keyval in keyvals:
                key, val = keyval.split(': ', 1)

                # Now we apply the blacklist and treat stopped servers as if they also were blacklisted
                if (key == 'name' or key == 'hostname') and (val in self.args.blacklist or val in list(stopped_servers.keys())):

                    if val in self.args.blacklist:
                        info_msg = f"key: {key}, value: {val} found in blacklist.\n"
                        info_msg += 'Marking said server by naming it "BLACKLISTED".\n'
                        info_msg += 'Servers with a hostname of "BLACKLISTED" will be ignored\n'
                        debug_msg = 'when we build up the final, proper list of Server objects\n'
                        debug_msg += 'from this preliminary data structure.\n\n'
                    elif val in list(stopped_servers.keys()):
                        info_msg = f"key: {key}, value: {val} found to be in state stopped. Ignoring same as if it was blacklisted.\n"
                        debug_msg = ''

                    self.logger.log(info_msg, 'info')
                    self.logger.log(debug_msg, 'debug')

                    val = 'BLACKLISTED'

                current_server[key] = val

            servers.append(current_server)
            connection.close()

        return proxmox_server_map

    def add_missing_data_to_kvm_servers_single_proxmox(self, proxmox_kvm_server_map):
        # In case of Linux KVM OS will only be shown as 'l26'
        # Which says nothing about the underlying distribution
        # Windows by the way shows something nice like win10

        # We also after this need to get the IP-Address of the KVM
        # So lets prepare some connections to run some commands

        linux_distro_os = ''
        kvm_ip = ''

        connection = self.get_connections_fab_single()

        # Servers where ostype name evaluation or ip evaluation failed
        # will be deleted from the map later so that they will be
        # ignored for the downtime automation
        failed_evaluations = {}

        for kvm_server in proxmox_kvm_server_map['Servers']:
            # Create new key for ip
            kvm_server['ip'] = ''

            cmd_get_os = "qm guest cmd " + kvm_server['id'] + " get-osinfo | grep pretty-name | cut -d':' -f2 | tr -d '\"' | sed 's:^ ::' | tr -d '\\n'"
            cmd_get_ip = "qm guest cmd " + kvm_server['id'] + " network-get-interfaces | grep ip-address | grep -v ip-addresses | grep -v ip-address-type | grep -v '127\\.0\\.0\\.1' | tr -d ' ' | tr -d '\"' | tr -d ',' | grep -v ip-address::: | grep -v fe80 | grep -v 2a02 | cut -d':' -f2"

            if kvm_server['ostype'] == 'l26':
                linux_distro_os = connection.run(cmd_get_os, warn=True, hide=True).stdout.replace(',', '')
                # Add the name of the Linux Distro
                kvm_server['ostype'] = linux_distro_os

            kvm_ip = connection.run(cmd_get_ip, warn=True, hide=True).stdout
            # We could have more than one adapter and IP
            ips = kvm_ip.split('\n')

            if len(ips) > 1:
                # Server has many IPs
                ips = list(filter(lambda x: x, ips))
                kvm_server['ip'] = ips
            else:
                # Server has ONE IP
                kvm_server['ip'] = kvm_ip

            # Last resort if ostype was not evaluated correctly at first try
            if kvm_server['ip'] and not kvm_server['ostype']:
                ip = kvm_server['ip'][0] if isinstance(kvm_server['ip'], list) else kvm_server['ip']
                connection2 = fabric.Connection(ip, user='root', port=22, connect_kwargs=self.connect_kwargs)
                kvm_server['ostype'] = connection2.run('cat /etc/os-release | grep ID | grep "debian\|ubuntu" | sed "s/ID=//" |  tr -d "\\n"', warn=True, hide=True).stdout
                connection2.close()

            # These server will be deleted before this function returns
            # We cannot work without the server's IP or OS
            if not kvm_server['ip'] or not kvm_server['ostype']:
                self.logger.log(
                    f'IP or OS name of {kvm_server} could not be identified. Marking the server for removal from downtime!',
                    'info')
                failed_evaluations[connection.host] = kvm_server

        connection.close()

        for kvm_server in proxmox_kvm_server_map['Servers']:
            for incomplete_kvm_server in failed_evaluations.values():
                if kvm_server == incomplete_kvm_server:
                    self.logger.log(f'IP or OS name of {incomplete_kvm_server} could not be identified. Removing the server from downtime-automation. Take care manually!', 'info')
                    proxmox_kvm_server_map['Servers'].remove(incomplete_kvm_server)

        return proxmox_kvm_server_map
