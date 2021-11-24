import os

class StateMachine:
    def __init__(self, tasks, args, logger):
        self.tasks = tasks
        self.args = args
        self.logger = logger
        self.states = self.tasks

        self.current_state_index = 0
        self.previous_state_index = 0
        self.next_state_index = 0
        self.num_states = len(self.states)
        self.first_state_index = 0
        self.last_state_index = self.num_states - 1

    def get_current_state_in_range(self):
        return 0 <= self.get_current_state() <= self.num_states - 1

    def get_statemachine_at_beginning(self):
        return self.current_state_index == self.first_state_index

    def get_statemachine_at_end(self):
        # We run one element over the end because in our main while loop
        # we check the condition BEFORE entering the loop
        # If we didn't do +1 the last command of the last subtask would
        # never be run because the loop would not be entered.
        return self.current_state_index == self.last_state_index + 1

    def get_current_state(self):
        return self.current_state_index

    def set_current_state(self, index):
        self.current_state_index = index

    def get_previous_state(self):
        return self.previous_state_index

    def set_previous_state(self):
        current_state_index = self.get_current_state()

        if not self.get_current_state_in_range():
            raise Exception("Invalid state: Panick! Bye!")
        else:
            if not self.get_statemachine_at_beginning():
                self.set_current_state(current_state_index - 1)
                self.next_state_index = current_state_index
                return True
            else:
                self.logger.log(f'Tried to set previous state. We are at first state {self.current_state_index}. Not doing anything!', 'info')
                return False

    def get_next_state(self):
        return self.next_state_index

    def set_next_state(self):
        current_state_index = self.get_current_state()

        if not self.get_current_state_in_range():
            raise Exception("Invalid state: Panick! Bye!")
        else:
            if not self.get_statemachine_at_end():
                self.set_current_state(current_state_index + 1)
                self.previous_state_index = current_state_index
                return True
            else:
                self.logger.log(f'Tried to set next state. We are already at last state {self.current_state_index}. Not doing anything!', 'info')
                return False

    def reset(self):
        self.next_state_index = 0
        self.set_current_state(0)
        self.previous_state_index = 0
        self.first_state_index = 0

    def test_me_dry_run(self, start_state=0, direction='forward'):
        self.current_state_index = start_state

        if direction == 'forward':
            while self.get_current_state_in_range():
                if not self.set_next_state():
                    break
                self.logger.log(f'Current state:{self.current_state_index}', 'info')
                os.system('sleep 0.1')
        elif direction == 'backwards':
            while self.get_current_state_in_range():
                if not self.set_previous_state():
                    break
                self.logger.log(f'Current state:{self.current_state_index}', 'info')
                os.system('sleep 0.1')
        elif direction == 'forward-roundtrip':
            while self.get_current_state_in_range():
                if not self.set_next_state():
                    break
                self.logger.log(f'Current state:{self.current_state_index}', 'info')
                os.system('sleep 0.1')
            while self.get_current_state_in_range():
                if not self.set_previous_state():
                    break
                self.logger.log(f'Current state:{self.current_state_index}', 'info')
                os.system('sleep 0.1')
        elif direction == 'backwards-roundtrip':
            while self.get_current_state_in_range():
                if not self.set_previous_state():
                    break
                self.logger.log(f'Current state:{self.current_state_index}', 'info')
                os.system('sleep 0.1')
            while self.get_current_state_in_range():
                if not self.set_next_state():
                    break
                self.logger.log(f'Current state:{self.current_state_index}', 'info')