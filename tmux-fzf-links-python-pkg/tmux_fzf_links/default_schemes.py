#===============================================================================
#   Author: (c) 2024 Andrea Alberti
#===============================================================================
    
try:
    import magicc
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
import logging
import re
import sys
import shlex
from .export import OpenerType, SchemeEntry, PreHandledMatch, colors, heuristic_find_file, configs
from .errors_types import NotSupportedPlatform, FailedResolvePath

# >>> GIT SCHEME >>>

def git_post_handler(match:re.Match[str]) -> tuple[str,...]:
    return (f"https://github.com/{match.group(0)}",)

git_scheme:SchemeEntry = {
        "tags": ("git",),
        "opener":OpenerType.BROWSER,
        "post_handler": git_post_handler,
        "pre_handler": lambda m: {
            "display_text": f"{colors.rgb_color(0,255,115)}{m.group(0)}{colors.reset_color}",
            "tag": "git"
        },
        "regex": re.compile(r"(ssh://)?git@\S*")
    }

# <<< GIT SCHEME <<<

# >>> CODE ERROR SCHEME >>>

def code_error_pre_handler(match: re.Match[str]) -> PreHandledMatch | None:
    file = match.group("file")
    line = match.group("line")

    # fully resolved path
    resolved_path = heuristic_find_file(file)

    if resolved_path is None:
        # drop the match if it cannot resolve the path
        return None

    display_text = f"{colors.rgb_color(255,0,0)}{file}, line {line}{colors.reset_color}"

    suffix = resolved_path.suffix

    if suffix == '.py':
        tag = 'Python'
    else:
        # fallback case
        tag = 'code err.'

    return {"display_text": display_text, "tag": tag}

def code_error_post_handler(match:re.Match[str]) -> tuple[str,...]:
    # Handle error messages appearing on the command line
    # and create an appropriate link to open the affected file 

    file=match.group('file')

    # fully resolved path
    resolved_path = heuristic_find_file(file)

    if resolved_path is None:
        raise FailedResolvePath("could not resolve the path of: {file}")

    line=match.group('line')

    return (f"{resolved_path.resolve()}:{line}",)

code_error_scheme:SchemeEntry = {
            "tags": ("code err.","Python"),
            "opener": OpenerType.EDITOR,
            "post_handler": code_error_post_handler,
            "pre_handler": code_error_pre_handler,
            "regex": re.compile(r"File \"(?P<file>...*?)\"\, line (?P<line>[0-9]+)")
        }

# <<< CODE ERROR SCHEME <<<

# >>> URL SCHEME >>>

url_scheme:SchemeEntry = {
        "tags": ("url",),
        "opener": OpenerType.BROWSER,
        "post_handler": None,
        "pre_handler": lambda m: {
            "display_text": f"{colors.rgb_color(200,0,255)}{m.group(0)}{colors.reset_color}",
            "tag": "url"
        },
        "regex": re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&//=]*")
    }

# <<< URL SCHEME <<<

# >>> FILE SCHEME >>>

def file_pre_handler(match: re.Match[str]) -> PreHandledMatch | None:
    # Get the matched file path
    link1 = match.group('link1')
    link2 = match.group('link2')
    
    if link1:
        file_path_str = link1
    else:
        file_path_str = link2

    if file_path_str is None:
        return None

    # Return the fully resolved path
    resolved_path = heuristic_find_file(file_path_str)
    
    if resolved_path:
        tag="dir" if resolved_path.is_dir() else "file"
        if colors.enabled:
            color_code=colors.get_file_color(resolved_path)
            display_text = f"\033[{color_code}m{str(resolved_path)}\033[0m"
        else:
            display_text = f"{str(resolved_path)}"
        return { 
            "display_text":display_text,
            "tag": tag
            }
    else:
        return None

def file_post_handler(match:re.Match[str]) -> tuple[str,...]:

    file_path_str = match.group(0)
    
    resolved_path = heuristic_find_file(file_path_str)
    if resolved_path is None:
        raise FailedResolvePath("could not resolve the path of: {file}")

    resolved_path_str = str(resolved_path.resolve())

    is_binary=True # we assume a binary file as the fallback case
    if resolved_path.is_file:
        if MAGIC_AVAILABLE:
            # Use `magic` to get the MIME type of the file
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(str(resolved_path))
            if mime_type.startswith('text/'):
                is_binary = False  
        else:
            # Open the file in binary mode and read a portion of it
            with resolved_path.open('rb') as file:
                chunk = file.read(1024)  # Read the first 1024 bytes
                if b'\0' not in chunk:      # Check for null bytes
                    is_binary = False

    if is_binary:
        if sys.platform == "darwin":
            return ('open','-R', resolved_path_str,)
        elif sys.platform == "linux":
            return ('xdg-open', resolved_path_str,)
        elif sys.platform == "win32":
            return ('explorer', resolved_path_str,)
        else:
            raise NotSupportedPlatform(f"platform {sys.platform} not supported")
    else:
        args = shlex.split(configs.editor_open_cmd)
        args.append(resolved_path_str)
        return tuple(args)

file_scheme:SchemeEntry = {
        "tags": ("file","dir"),
        "opener": OpenerType.CUSTOM,
        "post_handler": file_post_handler,
        "pre_handler": file_pre_handler,
        "regex": re.compile(r"(\'(?P<link1>\~?[a-zA-Z0-9_\/\-\:\. ]+)\'|(?P<link2>\~?[a-zA-Z0-9_\/\-\:\.]+))")
    }

# <<< FILE SCHEME <<<

# Define schemes
default_schemes: list[SchemeEntry] = [
        url_scheme,
        file_scheme,
        git_scheme,
        code_error_scheme
    ]

__all__ = ["default_schemes"]
