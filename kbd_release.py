#!/usr/bin/env python3

import time
import sys
import select
import termios
import tty
import fcntl
import os
from collections import defaultdict
from typing import Callable

def set_nonblocking(fd) -> None:
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

def set_blocking(fd) -> None:
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

def select_key_events(up_hooks: dict[str, Callable[[], None]], down_hooks: dict[str, Callable[[], None]], kbd_init_delay_ms: int = 270, kbd_repeat_delay_ms: int = 40, select_timeout_ms: int = -1) -> None:
    """Wait for key presses and respect keyboard delay and keyboard repeat delay to deduce key releases.
       Call calibrate_keyboard_delays to get the configuration for your current keyboard.
       The default values were calibrated on a Windows system.
       select_timeout_ms should be at most kbd_repeat_delay_ms/2, preferrably lower.
                         -1 means auto, meaning it will take kbd_repeat_delay_ms/4
    """

    if select_timeout_ms == -1:
        select_timeout_ms = kbd_repeat_delay_ms // 4
        if select_timeout_ms <= 0:
            select_timeout_ms = 1
    pressed = defaultdict(bool) # initially, keys are not pressed down (False)
    is_first_keypress = defaultdict(lambda: True)
    current_delay_ms = defaultdict(int) # default value for int is 0

    while True: # event loop
        fd = sys.stdin.fileno() # get raw file descriptor handle to stdin
        orig = termios.tcgetattr(fd) # to restore stdin mode for later
        set_nonblocking(fd) # set to nonblocking mode to catch multibyte sequences like ^[[A (Up Arrow) when we call read
        try:
            tty.setcbreak(fd) # alternatively: tty.setraw(fd)
            if select.select([sys.stdin], [], [], select_timeout_ms / 1e3)[0]: # I/O multiplexing, with short timeout (must be calibrated to be less than the delay between two repeated key presses (~33ms by default in Windows))
                chars = sys.stdin.read(3) # read up to 3 chars non-blockingly and without needing to press enter (cbreak mode). normally, a single char would suffice, but for some odd reason, when pressing up arrow (^[[A), it doesn't send all 3 bytes into the input buffer (https://chatgpt.com/share/67e59b49-75ec-800a-a346-06fcf3016fba). But this workaround works
                if chars == '\004': # CTRL-D, exit (and run code from finally block)
                    break
                current_delay_ms[chars] = 0 # it's 0 ms ago that a key was pressed
                if not pressed[chars]: # it's the first time this key was received, so it must be a press down
                    if chars in up_hooks:
                        up_hooks[chars]() # callback for press
                    pressed[chars] = True # we are in pressed down state
                    is_first_keypress[chars] = True # it is the first keypress, which means the initial delay is different ("keyboard delay")
                else:
                    is_first_keypress[chars] = False # we received another event, but the key was already pressed down, therefore this can't be the first keypress
            else: # after select_timeout_ms milliseconds, no events occured on stdin (neither key presses, nor key repeats, etc.)
                for chars in pressed.keys():
                    if pressed[chars]: # the key is supposedly pressed down, but we have to check if we've been waiting for longer than the delays allow
                        current_delay_ms[chars] += select_timeout_ms # add to the delay that we've set to 0 initially
                        if is_first_keypress[chars]: # if it's the first keypress, we need to wait a different time
                            if current_delay_ms[chars] > kbd_init_delay_ms:
                                down_hooks[chars]() # callback for release
                                pressed[chars] = False # the key is PROBABLY not pressed down anymore. This will be wrong if kbd_init_delay_ms is lower than the actual delay
                        else: # for subsequent keypresses, we wait a (usually) shorter time
                            if current_delay_ms[chars] > kbd_repeat_delay_ms:
                                down_hooks[chars]() # same callback for release
                                pressed[chars] = False # the key is PROBABLY not pressed down anymore. This will be wrong if kbd_repeat_delay_ms is lower than the actual delay
                                is_first_keypress[chars] = True # this one doesn't matter I think, but let's reset it to the inital state to be sure
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, orig) # restore stdin mode
            set_blocking(fd)

def calibrate_keyboard_delays(n: int = 10, error: int = 4) -> tuple[int, int]:
    """Ask for continuous input to determine the keyboard repeat delays
       n is the number of character to be read. More characters -> better average
       error is the percentage by which to increase the rates to guard against false positives
    """
    print("Please press and hold the spacebar until it says STOP:", flush=True)
    fd = sys.stdin.fileno() # get raw file descriptor handle to stdin
    orig = termios.tcgetattr(fd) # to restore stdin mode for later
    chars = []
    kbd_init_delay_ms = kbd_repeat_delay_ms = 0
    try:
        tty.setcbreak(fd) # alternatively: tty.setraw(fd)
        print(end=f"\r  0/{n}", flush=True)
        for i in range(n):
            chars.append((sys.stdin.read(1), time.monotonic()))
            print(end=f"\r{i+1: >3}/{n}", flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, orig) # restore stdin mode
    kbd_init_delay_ms = round((chars[1][1] - chars[0][1]) * 1000 * (1 + error/100))
    deltas = [b[1] - a[1] for a, b in zip(chars[1:], chars[2:])]
    kbd_repeat_delay_ms = round(sum(deltas)/len(deltas) * 1000 * (1 + error/100))
    input(f"\nSTOP, your initial keyboard repeat delay is {kbd_init_delay_ms} milliseconds, while you average keyboard repeat delay is {kbd_repeat_delay_ms} milliseconds. Press enter to continue\n")
    return kbd_init_delay_ms, kbd_repeat_delay_ms

up_hooks = defaultdict(lambda: lambda: None) # Factory that returns functions that do nothing. I.e.: By default, a hook does nothing
down_hooks = defaultdict(lambda: lambda: None)

# Register hooks
up_hooks['[A'] = lambda: print("Up pressed")
down_hooks['[A'] = lambda: print("Up released")

up_hooks['[B'] = lambda: print("Down pressed")
down_hooks['[B'] = lambda: print("Down released")

kbd_init_delay_ms, kbd_repeat_delay_ms = calibrate_keyboard_delays()

select_key_events(
    up_hooks,
    down_hooks,
    kbd_init_delay_ms,
    kbd_repeat_delay_ms)

print("Program ended")
