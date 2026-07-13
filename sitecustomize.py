"""
Python auto-imports this module at startup when it is on sys.path.

Some local Windows sessions set dead proxy placeholders such as
127.0.0.1:9. Google auth respects those variables and then fails before the
dashboard can load data. Clearing only those broken local placeholders keeps
normal deployment/network proxy settings untouched.
"""

import os


def _clear_dead_local_proxy():
    proxy_names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )
    for name in proxy_names:
        value = os.environ.get(name, "")
        if "127.0.0.1:9" in value or "localhost:9" in value:
            os.environ.pop(name, None)


_clear_dead_local_proxy()
