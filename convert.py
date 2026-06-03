"""zkm-pdf — filesystem-discovery shim; delegates to the zkm_pdf package.

Loaded by core when the plugin is filesystem-discovered (dev-symlink workflow).
Core's _inject_plugin_venv (SB2) adds plugins/zkm-pdf/src/ to sys.path before
loading this file, making zkm_pdf importable here.
"""

from zkm_pdf.convert import convert  # noqa: F401
