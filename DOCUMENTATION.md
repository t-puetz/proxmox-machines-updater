### Documentation

The program was written and developed in Python 3.8 and 3.9. Please don't use versions lower than 3.8.
The program contains the objects Logger, DowntimeAutomater, ProxmoxCrawler, Server, ServerSorter and StateMachine
which all get used by the object Program which finally ends in the method Program.run() which gets executed in
main()

#### Objects

#### Logger

*Object that provides a way to log messages to the screen or to a file. A log contains the criticality level, the date and the message.*

**Logger(now, args, hostname, folder)**


- __init__(now, args, hostname, folder):

    - now:  Datetime in format yyyy-mm-dd_hh-mm-ss
    - args: Arguments provided to the program parsed by **argparser**. Needed to know the log level the user chose
      (--debug-level \<value\>)
    - hostname: What host are the log messages about. 'main' is allowed as a string for generic messages of the main program thread.
    - folder: Per hostname a unique logging folder and file to log to


- log(msg, level, printout=False):

    - msg:       String that contains the log message
    - level:     String stating the log/criticality level - Must be one of debug, info, warning, critical, and error.
    - printout:  Keyword argument that configures whether or not the message should be printed to the screen.

    returns None implicitely


- write_log_file(folder, log_message):

    - folder:      Same as folder passed to log()
    - log_message: Same as msg passed to log()

    returns None implicitely


#### Server

*Object that provides the smallest element for our final data structure: A list of server objects.
In ProxmoxCrawler we first start of using a primitive, native list or dictionary datatype which then
later is transformed into server objects by Program.transform_server_info_to_proper_server_obj().*

**Server(proxmox, name, ip, _id, vtype, os)**

- __init__(proxmox, name, ip, _id, vtype, os):

    - proxmox: String containing the name of the proxmoxserver, e.g. Proxmoxsm27
    - name   : String containing the hostname of the server
    - ip     : ID of the corresponding LXC or KVM machine
    - vtype  : String that is either 'LXC' or 'KVM' to react to the different kinds of virtualizations we use for a server.
    - os     : The oprating system of the server (cleaned up and simplified by methods that run until this point).


#### ProxmoxCrawler

*Crawls proxmoxes for their servers and the configuration of those server by first establishing a SSH connection, then
pct list and qm list. The data is pre-filtered by ignoring stopped and blacklisted servers. KVM servers get some data
added in the last step because not all their data can be extracted in the first try by qm list*

**ProxmoxCrawler(args, connect_kwargs, logger, proxmox_ip)**

- __init__(args, connect_kwargs, logger, proxmox_ip):

    - args          : Flags used for this programs, parsed by Argparser.
    - connect_kwargs: Dictionary that Fabric uses to have all the special SSH connection parameters it needs, such as password or
      passphrase. This contains data for connecting to the proxmox machines. Note: User and Port are not part of this dictionary, but
      are provided as keyword args to Fabric.connection()
    - logger:         The logger object for this Proxmox
    - proxmox_ip:     IP of this Proxmox. One ProxmoxCrawler is instanctiated per Proxmox IP the user provided via the
                      *--proxmox-ips* \<comma separated list of IPs\> flag
    
- get_connections_fab_single():

  returns fabric.Connection(self.proxmox_ip, user='root', port=self.port, connect_kwargs=self.connect_kwargs) which is
  a Fabric connection object that allows you to interact with the Proxmox, e.g. for running commands etc.

- get_stopped_servers_single_proxmox(vtype):

  Will run *qm list | awk '(NR>1)' | awk '{print $2":"$3}'* or *pct list | awk '(NR>1)' | awk '{print $3":"$2}'* on a server
  depending on its virtualization type. This will reveal the status of the server. It will then accumulate a dictionary of servers
  that are in state 'stopped'. It returns that dictionary so we can filter those servers out later on.
    
    - vtype: String either containing 'LXC' or 'KVM' specifying the virtualization type of the server
      This helps the method to decide whether to run pct list or qm list, respectively

    returns: Dictionary[hostname] = status

- get_machine_attributes_single_proxmox(vtype):

  This is the first heartpiece of this software. Depending on the vtype the command *for id in $(<qm list or pct list> | awk 'NR>
  \{print $1\}' | tr '\n' ' '); do printf "id: $id\n"; <qm config or pct config> $id;printf '======\n';done* is being run on the Proxmox
  server of choice via Fabric.Connection.run().

  This shell command will give usmost of the information needed about a server and it adds in an artificial seperator "======" that
  the python key later uses to transfer all key value pairs from stdout to a native python dictionary. Only for KVMs we are
  missing some stuff such as the OS on Linux KVMs (which only returns a generic l26 string) or the ip address on all KVMs independent 
  of what OS they are running.

  To understand better how python later transfers the stdout of the run shell command in a for loop, here is an exemplary output
  **for LXC servers**:
     
    . . .

    \======

    id: 21111

    arch: amd64

    cores: 4

    hostname: yourserver.domain.com

    memory: 2048

    nameserver: 10.30.0.254

    net0: name=eth0,bridge=vmbr0,gw=10.30.0.254,hwaddr=3E:8E:25:A5:7C:BA,ip=10.30.0.1/24,tag=30,type=veth

    ostype: ubuntu

    rootfs: CEPH-LXC-DEV:vm-21111-disk-0,size=16G

    searchdomain: domain.com

    swap: 0

    \======

    . . .
    
    - vtype: String either containing 'LXC' or 'KVM' specifying the virtualization type of the server
      This helps the method to decide whether to run pct list or qm list, respectively

- add_missing_data_to_kvm_servers_single_proxmox(proxmox_kvm_server_map):

  As described above this adds all the missing information we need for KVMs such as the IP address or the OS (just for Linux)

    - proxmox_kvm_server_map: List with python dictionaries describing our preliminary server information we obtained from
      get_machine_attributes_single_proxmox().

      This data structure is only preliminary. Our aim is is to get a list of real Server objects! The preliminary data structure
      will be deleted by using del() before the program is run.


#### ServerSorter

*Deals with lists of server objects and sorts it for us after certain criteria*

**ProxmoxCrawler(args, lxc_servers, kvm_servers, logger, whitelist)**

- __init__(args, lxc_servers, kvm_servers, logger, whitelist):

    - args: Arguments provided to the program parsed by **argparser**. Needed to know the log level the user chose.
    -  lxc_servers: Unfiltered list of proper Server objects of vtype LXC obtained by 
      Program.transform_server_info_to_proper_server_obj(vtype).
    - kvm_servers: Same as lxc_servers but for servers of type KVM.
    - logger: Logger object
    - whitelist: whitelist provided by the user using the --whitelist \<comma-separated list of FQDN hostnames\> flag

- remove_windows_kvm_servers():

    Looks at the current/original self.kvm_servers property and removes Windows servers by looking for servers that have their 
    name property start with 'win'.

    It writes this new filtered list back into the self.kvm_servers property, so it effectively overwrites it and it also
    **returns that list without windows servers**

- get_server_by_hostname(hostname, serverlist):

    Gets a server object according to hostname and server object list provided.

    - hostname:   Hostname of the server to look for
    - serverlist: Serverlist to look in

    Returns server object if server is found, otherwise None.

- apply_whitelist():

    Runs only when whitelist provided via --whitelist is not empty. It accumulates those servers in the whitelist, finds their
    corresponding server objects and just overwrite self.all_linux_servers.

    Implicitely returns None


#### StateMachine

*Has the abality to walk through the states which in our case are equal to all downtime subtasks to be done. It always nows the
current, the next and the previous state, can go back and forward, it can reset the states and it can tel whether it is at the end
or the beginning of its state/task list. It can also detect whether or not the current state index is inside the state list range*

**StateMachine(tasks, args, logger)**

- __init__(tasks, args, logger):

    - tasks: A list of tasks (the words task(s) and state(s) are interchangable)
    - args: Arguments provided to the program parsed by **argparser**. Needed to know the log level the user chose.
    - logger: Logger object. There will always be one StateMachine with its unique Logger object per server


- get_current_state_in_range(): 

  Checks whether or not the current state index is in range.
  Returns boolean.

- get_statemachine_at_beginning():

  Checks whether or not the StateMachine is currently at the beginning of its tasks/states.
  Returns boolean.

- get_statemachine_at_end():

  Checks whether or not the StateMachine is currently at the end of its tasks/states. Note this important comment in the code:

        # return self.current_state_index == self.last_state_index + 1
        # We run one element over the end because in our main while loop
        # we check the condition BEFORE entering the loop
        # If we didn't do +1 the last command of the last subtask would
        # never be run because the loop would not be entered.
  
  Returns boolean.
    
- get_current_state():

  Returns the current state as list index. The statemachine always knows about states as list indices, so starting at 0, NOT AS human
  readable counted numbers starting from one!

- set_current_stet(index):
  Implicitely returns None
    - index: Index of next state to set.

- get_previous_state() and get_next_state() work analogously to get_current_state()

- set_previous_state():

  Analogous to set_current_state but takes no index parameter because it calculates the previous index itself.
  It first gets the current state index. It first checks whether ot not the current state is in range by calling self
  get_current_state_in_range(). If that is not the case Exception("Invalid state: Panick! Bye!") is raised.

  If that is the case and the state is **NOT** the first state self.set_current_state(current_state_index - 1) is called
  and self.next_state_index is assigned the current state index. The function then returns True.
  
  Otherwise the logger will log an info "Tried to set previous state. We are at first state {self.current_state_index}. Not doing
  anything!" and the function will return False.

- set_next_state():

  Works more analogous to set_previous_state(), but of course the logic is the opposite.
  Returns a boolean.

- reset():

  Resets the StateMachine by setting the all state indices (next, current, previous and first) to 0, again.
  Implicitely returns None.

- test_me_dry_run():

  Function to test the statemachine. Is not used inside the program. Can move forward and backwards in single steps or
  do a complete forward and backward roundtrip automatically.


#### DowntimeAutomater

*This object includes the last two of our very important heartpieces. Firstly the method run_linux_subtask() can run
a single subtask which is to be done on the Server (subtask = task = state are all interchangable). The second heartpiece
is the while loop inside execute_linux_downtime_on_single_server() that iterates uses a StateMachine to iterate through 
all tasks which are to be done on a server. execute_linux_downtime_on_single_server() as the name says only deals with a single
server. It gets a unique StateMachine and a unique Logger object and the task is finally executed by using run_linux_subtask() 
as a helper function inside the StateMachine while loop.*

*Note: The threading capability of the downtime-automater software is realized by using execute_linux_downtime_threaded()
which internally uses multiprocessing.pool.ThreadPool.starmap() to call execute_linux_downtime_on_single_server()*

*Note2: The object property self.linux_subtasks defines a list of strings that name the subtasks to be run on a server.
That list differs depending on whether or not flags such as --no-reboot, --test-and-exit, --test-and-run where provided.*



**DowntimeAutomater(args, connect_kwargs, linux_servers, ServerSorter)**

- __init__(args, connect_kwargs, linux_servers, ServerSorter):

    - args: Arguments provided to the program parsed by **argparser**. Needed to know the log level the user chose.
    - connect_kwargs: Dictionary that Fabric uses to have all the special SSH connection parameters it needs, such as password or
      passphrase. This contains data for connecting to the servers: User and Port are not part of this dictionary, but
      are provided as keyword args to Fabric.connection()
    - linux_servers: All linux servers that are acknoledgable for the downtime
    - ServerSorter: ServerSorter object. Needed to call ServerSorter.get_server_by_hostname(connection.host, self.linux_servers)
      inside run_linux_subtask() to get the corresponding server to the connection object that was passed to it.

- run_linux_subtask(connection, subtask, logger):

  Each subtask is a string. That string decides what shell command is passed as a string to connection.run().
  The method can try and fix a few primitive errors via error_handlr() method that can occur in apt/dpkg.
  It tries that twice without checking whether or not it was successful. 
  **Possible errors of shell commands during the update/upgrade/release-upgrade make this software such a challenge. 
  This is why your server should never be more than one release behind and especially why you might have to run the
  program more than once.**

    - connection: Fabric.connection object for the server to run the downtime task on.
    - subtask: String specifying the subtask to execute.
    - logger: Unique logger object per server.

  Servers that fail on the first command run are put into a list. If the server is still erroneous in the second try
  the method will return False, otherwise it will return True.

- execute_linux_downtime_on_single_server(hostname, statemachine, logger):

  Takes the hostname of a server to et a connection object from fabric.Connection internally.
  It also gets its own staemachine and logger object so that the downtime can be run on each server seperately with
  unique and separate status and logging information.
  The StateMachine object's property self.tasks just gets assigned the self.linux_subtasks list from the DowntimeAutomater property.

  The function then enters our final core functionality - the while loop that calls self.run_linux_subtask() and if sucessful
  sets the next state/subtask or otherwise quits. The user can then extactly see in the coressponding proxmox folder and the
  corresponding server folder+logfile what happned.

    - hostname: Hostname of the server to run the subtask on
    - statemachine: Unique StateMachine object per server
    - logger: Unique logger object per server

- execute_linux_downtime_threaded(statemachine_map, server_logobj_map):
    - statemachine_map:  Dictonary - Key is the hostname, value is a unique StateMachine object for that server 
    - server_logobj_map: Dictonary - Key is the hostname, value is a unique Logger object for that server 

  Both mapps are needed to pass the unique arguments to each instance of execute_linux_downtime_on_single_server() 
  when they are being called by pool.starmap() in a threaded manner.

- error_handler(cxn, logger, error=None):
  Can handle the following primitive errors that occured either as a real Error or where found in std.err as a string:
   
  - Errors:
    - apt/dpkg warning: "The following packages have been kept back" (Behaviour: Install all kept packages)
    - apt/dpkg error: Use apt-get --fix-broken install to fix installation (Behaviour: Run apt-get --fix-broken install)
    - apt/dpkg error: Use apt-get --fix-missing install to fix installation (Behaviour: Run apt-get --fix-missing install)
  
  - Strings found in result.stderr:
    - apt/dpkg error: you must manually run 'dpkg --configure -a' (Behaviour: Runs you must manually run 'dpkg --configure -a')
    - apt/dpkg error: Could not get lock /var/lib/dpkg/lock (Behaviour: Kills apt and dpkg and removes the lock file)
    - apt/dpkg warning: "The following packages have been kept back" (Behaviour: Install all kept packages)
    - apt/dpkg error: Use apt-get --fix-broken install to fix installation (Behaviour: Run apt-get --fix-broken install)
    - apt/dpkg error: Use apt-get --fix-missing install to fix installation (Behaviour: Run apt-get --fix-missing install)
    - Hostname command not found error was just for testing where I removes the hostname binary from a system. This has nothing to
      do with the real world program
    
  Like anything else in the program these steps are being logged and should be looked for in the downtime logfiles.

  - Arguments:
    - cxn: Connection to server to run commands on where errors occured
    - logger: Unique server Logger object
    - error: Keyword argument which decides whether real Errors or stderr Strings should be dealt with. 

#### Program
*The glue that combines all Objects and their methods in such a way that we get the desired program functionality. All this
is funneled into Program.run() which is finally being called in main() that is called if \_\_name\_\_ == "\_\_main\_\_"*

It also holds the program's name and semantic version number in self.version and self.argparser, respectively.*

**Program()**:

- __init()__:
  The object aaccumulates all necessary behaviour and data internally and needs no arguments.
  Its properties store the most necessary initial default data or they serve as sinks for data that gets generated
  while the methods are being run.

- parse_flags():
  Parses the flags being passed to the program on the shell. We use long flags exclusively.
  The flags and their function can be found in README.md.

  The method is basically just a wrapper aroung Argparser. The result of argparser.parse_args() finally gets written into self.args.

- get_datetime_now_intl():
  Returns the current time by returning self.now which is assigned the value of datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S").
  So it is actually the time the object was instanciated.

- create_main_logger():
  Gets the current time and uses that + the default main logger folder name to create a folder name string to pass to the Logger
  object that is then being instanciated. Main logger objects loggs everything in the main routine of the program and nothing server
  specific! It provides the entry point for all other log subfolders and files.

- parse_proxmox_ips():
  More than one Proxmox IP must be passed to the program in a comma separated list to --proxmox-ips. That list is here being splitted
  at the comma character to create a list.

- parse_blacklist():
  Same with Proxmox IPs just for the blacklist. The blacklist ist applied in the very early steps of completing the crawled 
  Proxmox data. AIs a server name found in a blacklist server.name will just be overwritten by the string "BLACKLISTED" and
  then will be ignored in a certain loop.

- parse_whitelist():
  Same with Proxmox IPs just for the whitelist. The whitelist is used much later in the ServerSorter.apply_whitelist().
  Because a whitelist overwrites a blacklist the whitelist is applied simply by overwriting all the servers in ServerSorter
  all_linux_servers. Just to be sure the blacklist is also emptied.

- detect_blacklist_whitelist_conflict():
  Because a whitelist overwrites a blacklist the whitelist is applied simply by overwriting all the servers in ServerSorter
  all_linux_servers. Just to be sure the blacklist is also emptied.

- create_connect_kwargs_proxmoxes():
  If --ssh-private-key-proxmox or --ssh-passphrase-proxmox are provides, those passwords get written into a dictionary
  that can be used to connect to the Proxmox servers. Username and IP ARE NOT PART OF THAT DICTIONARY!
  Note: Concerning the connect kwargs this means that we can only ever have the same password or key passphrase for ALL Proxmoxes.

- create_connect_kwargs_servers():
  Same as create_connect_kwargs_proxmoxes but for servers. 
  Note: Concerning the connect kwargs this means that we can only ever have the same password or key passphrase for ALL servers.

- create_proxmox_crawlers():
  Creates a ProxmoxCrawler object for each Proxmox and a Logger objects for each of the ProxmoxCrawler objects.
  The list of ProxmoxCrawler objects is safed into Program.create_proxmox_crawler_objs

- get_kvm_servers_prelim_datastructure():
  Goes through the list of ProxmoxCrawler objects and executes:
    ```
    kvm_map = proxmox_crawler.get_machine_attributes_single_proxmox('KVM')
    kvm_map = proxmox_crawler.add_missing_data_to_kvm_servers_single_proxmox(kvm_map)
    self.kvm_servers_prelim_datastructure.append(kvm_map)
    ```

  ... to fetch and store all necessary data about KVMs inside the Program property self.kvm_servers_prelim_datastructure.

- get_lxc_servers_prelim_datastructure():
  Goes through the list of ProxmoxCrawler objects and executes:
  ```
  lxc_map = proxmox_crawler.get_machine_attributes_single_proxmox('LXC')
  self.lxc_servers_prelim_datastructure.append(lxc_map)
  ```

  ... to fetch and store all necessary data about LXCs inside the Program property self.lxc_servers_prelim_datastructure.

- transform_server_info_to_proper_server_obj(vtype):
  Depenging on the argument vtype ('KVM' or 'LXC') it takes self.kvm_servers_prelim_datastructure or
  self.kvm_servers_prelim_datastructure, repectively and converts the preliminary datastructure of Python list+dictionaries
  into a list of proper Server objects. The blacklist is applied here!

  It stores the result of the transformation in self.kvm_servers_final or self.lxc_servers_final, respectively.

- get_kvm_servers_final():
  Wrapper around transform_server_info_to_proper_server_obj('KVM').

- get_lxc_servers_final():
  Wrapper around transform_server_info_to_proper_server_obj('LXC').

- filter_servers_for_final_usage():
  Creates a ServerSorter objext that is used to sort the Server object lists for final usage.
  ```
  self.srvsorter = ServerSorter(self.args, self.lxc_servers_final, self.kvm_servers_final, self.mainlogger, self.whitelist)
  self.srvsorter.remove_windows_kvm_servers()
  self.srvsorter.merge_all_linux_servers()
  self.srvsorter.apply_whitelist()
  self.all_linux_servers = self.srvsorter.all_linux_servers
  ```
  It first removes all Windows servers, then merges all LXC and KVM Linux servers, THEN APPLIES THE WHITELIST.

  The final Server object list is being stored in the Program property self.all_linux_servers.

- create_statemachine_host_and_logger_host_maps():
  If linux_servers for final usage do exist it instanciates a DowntimeAutomater object. It then cleans up some memory from
  obsolete data. Each Linux server is then iterated through. Its info is used to create a unique Logger object with a unique subfolder
  and file UNDER the main logger folder. That unique Logger object is then passed to the constructor of the unique StateMachine each
  server also gets.

  From that self.statemachine_host_map and self.serverlogger_host_map are filled. Both are a dictionary with the server's hostname
  as a key and the StateMachine object or Logger object as value, respectively. Those maps are later super important to
  allow execute_linux_downtime_threaded() to call execute_linux_downtime_on_single_server() in a threaded manner by passing the unique
  arguments to each instance of execute_linux_downtime_on_single_server.

- run():

  Where everything comes together:

  ```
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
  ```

  This final code piece in main.py (Where the Program class also resides) then runs our program:

  ```
  def main():
      program = Program()
      program.run()


    if __name__ == '__main__':
        main()
    ```
