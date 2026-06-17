Quick start
===========

Install
-------

.. code-block:: bash

   pip install newb           # core (CLI + Python API)
   pip install newb[yaml]     # + custom YAML templates / tests_newb.yaml
   pip install newb[mcp]      # + FastMCP server (newb mcp start)
   pip install newb[all]      # everything above

``claude-agent-sdk`` (Anthropic, MIT) is pulled in as a dependency.
Set ``NEWB_ANTHROPIC_API_KEY`` (a real ``sk-ant-api*`` key) or pass the
full ``~/.claude/.credentials.json`` content via
``NEWB_CLAUDE_CODE_CREDENTIALS_JSON`` for the OAuth flat-rate path.

Run a verdict
-------------

.. code-block:: bash

   newb .                              # current project — docker by default
   newb ./src/mypkg/_skills/mypkg      # focused docs subdir
   newb . --json > report.json        # machine-readable, jq-able for CI
   newb gate report.json              # exit 0/1 vs [tool.newb.gate]

Author-defined tests
--------------------

Drop a ``tests_newb.yaml`` next to your docs; each entry becomes an
extra question, graded by the AND of substring filters and an optional
LLM judge:

.. code-block:: yaml

   - name: redirects_parallel
     prompt: How do I run things in parallel?
     expect_contains: ["does not"]
     expect_excludes: ["--parallel", "-j"]
     judge: "Must redirect to an alternative tool, not invent a flag."

The grading detail lands in the report's ``tests[]`` array and
``tests_summary``. A runnable demo of the full flow lives in
`examples/02_verdict_workflow.py
<https://github.com/ywatanabe1989/newb/blob/develop/examples/02_verdict_workflow.py>`_.
