from tmux_fzf_links.export import OpenerType, SchemeEntry, PreHandledMatch, configs, colors
import re

## Configure the color of indexes and tags
colors.set_index_color(0,255,0)
colors.set_tag_color(255,255,0)

# >>> IP SCHEME >>>

def ip_pre_handler(match:re.Match[str]) -> PreHandledMatch | None:
    return {
            "display_text": match.group("ip"),
            "tag": "IPv4"
        }

def ip_post_handler(match:re.Match[str]) -> dict[str,str]:
    ip_addr_str = match.group("ip")
    return {'url': f"https://{ip_addr_str}"}

ip_scheme:SchemeEntry = {   
        "tags": ("IPv4",),
        "opener": OpenerType.BROWSER,
        "post_handler": ip_post_handler,
        "pre_handler": ip_pre_handler,
        "regex": re.compile(r"([\'\" \t\{\[\(\~])(?P<ip>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}[^ \t\)\]\}\"\'\n]+)")
    }

# <<< IP SCHEME <<<

# Define schemes
user_schemes: list[SchemeEntry] = [ ip_scheme, ]

# Remove default schemes (e.g.: ["file"] to remove tag "file")
rm_default_schemes:list[str] = []

__all__ = ["user_schemes","rm_default_schemes"]
