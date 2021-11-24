import os

class Logger:
    def __init__(self, now, args, hostname, folder):
        self.now = now
        self.args = args
        self.hostname = hostname
        self.folder = folder

    def log(self, msg, level, printout=False):
        valid_levels = ['debug', 'info', 'warning', 'critical', 'error']
        log_message = ''

        if level not in valid_levels or self.args.debug_level not in valid_levels:
            raise Exception(f'{self.now} - Log level not valid. Must be one of: {valid_levels}\n')

        default_log_level = valid_levels.index('warning')
        level_this_message = valid_levels.index(level)

        if self.args.debug_level:
            level_priority_chosen = valid_levels.index(self.args.debug_level)
            if level_this_message >= level_priority_chosen:
                log_message = f'{level.upper()} LOG - {self.now}:\nMessage: {msg}\n'
        else:
            if level_this_message >= default_log_level:
                log_message = f'{level.upper()} LOG - {self.now}:\nMessage: {msg}\n'

        if printout:
            print(log_message)

        self.write_log_file(self.folder, log_message)

    def write_log_file(self, folder, log_message):
        log_file = folder + f'/{self.hostname}.log'

        if not os.path.exists(folder):
            os.system(f"printf 'Creating log folder {self.folder}\n' ; mkdir -pv {self.folder}")

        if os.path.exists(log_file):
            with open(log_file, 'a+') as logfile:
                logfile.write(log_message)
        else:
            with open(log_file, 'w') as logfile:
                logfile.write(log_message)