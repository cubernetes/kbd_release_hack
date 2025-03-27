# Why?

Detecting key release events is [hard](https://blog.robertelder.org/detect-keyup-event-linux-terminal/).
However, when you hold a key, it takes a certain time until it starts repeating.
This is called the **keyboard repeat delay**. And when it starts repeating,
it repeats at a given rate. This is called the **keyboard repeat rate**.
For consistency of units however, I think one should call them the
**initial keyboard repeat delay** (for short: **initial delay**)
and **keyboard repeat delay** (for short: **repeat delay**) instead.
On Windows systems for example, the initial delay is roughly 250ms and
the repeat delay is 30ms.

# How?

The idea is simple: If a key press was triggered and more time than the inital
delay allows has passed, we must've released the key again. However, if in that
timeframe a second key press was triggered, it must've been the the first repetition
of the key. After that, if more time than the repeat delay allows has passed, we
must've released the key, similar to the first logic.

# But?

It only works on POSIX terminals (i.e. the ones where stty(1) works)

# And?

This trick allows for seemless terminal interactions even over SSH or
in Docker, which are notoriously hard to do!
