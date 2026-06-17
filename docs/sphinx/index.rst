newb
====

A fresh AI agent reads only your package's docs and tries to use the
package — pytest-style. If it succeeds, your docs work. If it fails,
your CI tells you which canonical question the docs couldn't answer.

See the project `README <https://github.com/ywatanabe1989/newb>`_ for
the full architecture, security model, and installation matrix.

Five interfaces
---------------

.. list-table::
   :header-rows: 1

   * - Interface
     - How
   * - CLI (primary)
     - ``newb <target>`` — see :doc:`cli`
   * - Python API
     - ``import newb; newb(".")`` — see :doc:`api`
   * - MCP server
     - ``newb mcp start`` (``pip install newb[mcp]``)
   * - Skills
     - ``newb skills list`` — agent-facing ``_skills/`` leaves
   * - HTTP API
     - not applicable — newb has no web surface

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quickstart
   cli
   api
