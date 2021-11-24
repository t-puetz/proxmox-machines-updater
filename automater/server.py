class Server:
    def __init__(self, proxmox, name, ip, _id, vtype, os):# logger):
        self.proxmox = proxmox
        self.name = name
        self.ip = ip
        self.id = _id
        self.vtype = vtype
        self.os = os
        #self.logger = logger

    def __str__(self):
        return f'{vars(self)}'

    def __repr__(self):
        return f'{vars(self)}'