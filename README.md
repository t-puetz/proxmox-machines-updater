# proxmox-machines-updater

Example run commands:

```
 python3 main.py --debug-level debug --proxmox-ips <node1-ip>,<node-ip2> --no-reboot --whitelist server1.domain.com, server2.domain.com --threaded

 python3 main.py --debug-level info --proxmox-ips <node1-ip> --blacklist server.domain.com --serialized

 python3 main.py --debug-level warning --test-and-exit --proxmox-ips <node1-ip>,<node2-ip> --threaded

 python3 main.py --debug-level critical --test-and-run --no-reboot --proxmox-ips <node1-ip>,<node2-ip> --threaded
```

Flags:
```
--serialized                     Runs downtime on linux server via SSH one in a row
--threaded                       Runs downtime on linux server via SSH theaded (for experts: via ThreadPool.starmap())
--proxmox-ips                    Add comma seperated of Proxmoxes to manage
--ssh-port-proxmox               SSH Port to access Proxmox(es)
--ssh-private-key-proxmox        Path to private key to use for connecting to Proxmox(es). Default $HOME/.ssh/id_rsa.pub
--ssh-passphrase-proxmox         Passphrase to use for keyfile for Proxmox(es)
--ssh-password-proxmox           Password to use for SSH authentification for Proxmox(es)
--ssh-port-servers               SSH Port to access Servers (on Proxmox(es))
--ssh-private-key-servers        Path to private key to use for connecting to servers. Default $HOME/.ssh/id_rsa.pub
--ssh-passphrase-servers         Passphrase to use for keyfile (servers)
--ssh-password-servers           Password to use for SSH authentification (servers)
--blacklist                      Comma seperated list of servers HOSTNAMES (IPs won\'t work) not to work on
--whitelist                      Comma seperated list of servers HOSTNAMES (IPs won\'t work) TO EXCLUSIVELY work on. A whitelist  
                                 cancels a blacklist.
--test-and-exit                  Run two simple test subtasks on the servers AND EXIT
--test-and-run                   Run two simple test subtasks on the servers AND RUN REGULARLY AFTERWARDS
--debug-level                    Provide loglevel you want to be printed.
--no-reboot                      Skip last subtask that reboots the machine(s).
```

###### Important notes:

* The hostnames provided for the blacklist and whitelist flags must ALWAYS match the actual hostname in FQDN. 
  If you have a node WITHOUT .domain.com, e.g. node4 you must ONLY provide node4 as the string.

* Your systems should never be more than one distro release behind. Blacklist these servers, please!

* Most of the time the Ubuntu do-release-upgrade will not upgrade the Ubuntu release because it does not have
  all upgrades yet for this release. Just run the script again (If you just want to run it on those specific Ubuntu servers, use a whitelist)

* I would still generally advice you to run the script twice!


