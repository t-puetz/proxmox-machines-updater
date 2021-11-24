from .server import Server


class ServerSorter:
    def __init__(self, args, lxc_servers, kvm_servers, logger, whitelist):
        self.args = args
        self.lxc_servers = lxc_servers
        self.kvm_servers = kvm_servers
        self.all_linux_servers = []
        self.whitelist = whitelist
        self.logger = logger

    def remove_windows_kvm_servers(self):
        kvm_servers_no_windows = []

        for kvm_server in self.kvm_servers:
            if kvm_server.os.startswith('win'):
                continue
            else:
                kvm_servers_no_windows.append(kvm_server)

        self.logger.log(f'ServerSorter.remove_windows_kvm_servers(): Return dict KVM Servers only Linux: {kvm_servers_no_windows}', 'debug')

        self.kvm_servers = kvm_servers_no_windows
        return kvm_servers_no_windows

    def merge_all_linux_servers(self):
        # Merge all linux Servers regardless if KVM or LXC
        # AFTER remove_windows_kvm_servers() !!!
        self.all_linux_servers = self.kvm_servers + self.lxc_servers

    def get_server_by_hostname(self, hostname, serverlist):
        for server in serverlist:
            if server.name == hostname:
                return server

    def apply_whitelist(self):
        if self.whitelist:
            whitelisted_servers = []

            for hostname in self.whitelist:
                server = self.get_server_by_hostname(hostname, self.all_linux_servers)
                whitelisted_servers.append(server)

            self.all_linux_servers = whitelisted_servers
            self.logger.log(f'ServerSorter.apply_whitelist(): Whitelisted servers are:\n{whitelisted_servers}', 'debug')
