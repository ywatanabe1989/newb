# greetlib

A tiny example package whose docs `newb` verifies. `greetlib` formats a
friendly greeting from a name.

## Install

```bash
pip install greetlib
```

## Quick start

```python
from greetlib import greet

print(greet("Ada"))   # -> "Hello, Ada!"
```

## When NOT to use

`greetlib` is a teaching example for the `newb` verdict workflow. Do not
use it in production — it has no real value beyond demonstrating how a
README is graded.

## Parallelism

`greetlib` does not run anything in parallel; it is a pure formatting
function. There is no `--parallel` flag and no `-j` option.
