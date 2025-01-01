#!/usr/bin/env python3

#===============================================================================
#   Author: (c) 2024 Andrea Alberti
#===============================================================================

import os
import re
import subprocess
import sys
import shlex
import shutil
import logging
from typing import override

from .export import AppType
from .DefaultSchemes import default_schemes

class PatternNotMatching(Exception):
    """Raise exception when the pattern does not match a string already matched"""

class NoSuitableAppFound(Exception):
    """Raise exception when no suitable app was found to open the link"""

class CommandFailed(Exception):
    """Raise exception when the executed app exits with a nonzero return code"""

class FzfUserInterrupt(Exception):
    """Raise exception when the user cancels fzf modal window"""

class FzfError(Exception):
    """Raise exception when fzf fails"""
    def __init__(self, message: str, returncode: int) -> None:
        super().__init__(message)
        self.returncode:int = returncode

# >>> LOGGER >>>

class TmuxDisplayHandler(logging.Handler):
    @override
    def emit(self, record:logging.LogRecord):
        # Format the log message
        message = self.format(record)
        try:
            # Determine the display command options based on the log level
            display_options = ["tmux", "display-message"]
            if record.levelno >= logging.WARNING:
                display_options.extend(["-d", "0"])  # Pause the message for warnings and errors

            # Include the message
            display_options.append(message)

            # Use tmux display-message to show the log
            _ = subprocess.run(
                display_options,
                check=True,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            # Fallback to console if tmux command fails
            print(f"Failed to display message in tmux: {e}")

def setup_tmux_log_handler() -> TmuxDisplayHandler:

    # === Set up tmux logger ===
    
    # Create and add the TmuxDisplayHandler
    tmux_handler = TmuxDisplayHandler()
    # formatter = logging.Formatter("%(levelname)s: %(message)s")
    formatter = logging.Formatter("fzf-links: %(message)s")
    tmux_handler.setFormatter(formatter)

    return tmux_handler

def setup_file_log_handler(log_filename:str='') -> logging.FileHandler:

    # === Set up file logger ===

    # Configure file log handler and check that the logfile can be written
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    
    return file_handler

def validate_log_level(user_level:str):
    """
    Validates the user-provided log level.
    Falls back to WARNING if the level is invalid.

    Args:
        user_level (str): The log level provided by the user (e.g., 'DEBUG', 'INFO').

    Returns:
        int: A valid logging level.
    """
    # Use the internal mapping of log level names to numeric values
    level_mapping = logging._nameToLevel

    # Convert user input to uppercase for case-insensitive matching
    level = user_level.upper() if isinstance(user_level, str) else ''
    
    # Return the corresponding logging level or fallback to WARNING
    return level_mapping.get(level, logging.WARNING)

# <<< LOGGER <<<

def trim_str(s:str) -> str:
    """Trim leading and trailing spaces from a string."""
    return s.strip()

def remove_escape_sequences(text:str) -> str:
    # Regular expression to match ANSI escape sequences
    ansi_escape_pattern = r'\x1B\[[0-9;]*[mK]'
    # Replace escape sequences with an empty string
    return re.sub(ansi_escape_pattern, '', text)

def set_up_logger(loglevel_tmux:str,loglevel_file:str,log_filename:str) -> logging.Logger:

    # Set up the root logger; note: if you decide to create a child logger
    # the root logger level needs to be configured to allow for messages
    # to pass through.
    logger = logging.getLogger()  # root logger when no argument is provided
    # Allow all log messages to pass through; we control the level using handlers
    logger.setLevel(0)

    # Set up tmux log handler
    tmux_handler = setup_tmux_log_handler()
    tmux_handler.setLevel(validate_log_level(loglevel_tmux))
    logger.addHandler(tmux_handler)
    
    # Set up file log handler and check that the file is writable
    try:
        file_handler = setup_file_log_handler(log_filename)
        file_handler.setLevel(validate_log_level(loglevel_file))
        logger.addHandler(file_handler)
        init_msg="fzf-links tmux plugin started"
        # Send an initialization message to the file handler only
        file_handler.handle(logging.LogRecord(
                name=logger.name,
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg=init_msg,
                args=None,
                exc_info=None,
            ))
    except Exception as e:
        # To be safe, remove the handler if it was added
        for handler in logger.handlers:
            if isinstance(handler,logging.FileHandler):
                logger.removeHandler(handler)
            
        # Set level to zero to make sure that the error is displayed 
        tmux_handler.setLevel(0)
        # Log the error to tmux display and exit 
        logger.error(f"error logging to logfile: {log_filename}")
        sys.exit(1)
        
    return logger

def run_fzf(fzf_display_options:str,choices: list[str]) -> subprocess.CompletedProcess[str]:
    """Run fzf with the given options."""
    # Split the options into a list
    cmd_plus_args: list[str] = shlex.split(fzf_display_options)

    # Add 'fzf-tmux' as the first element
    cmd_plus_args.insert(0, 'fzf-tmux')

    result = subprocess.run(cmd_plus_args, input="\n".join(choices), shell=True, text=True, capture_output=True)
    if result.returncode == 0:
        return result
    elif result.returncode == 130:
        # Allow exit code 130 for user cancellation; see fzf manual
        raise FzfUserInterrupt()
    else:
        raise FzfError(f"fzf failed with exit code {result.returncode}: {result.stderr}", result.returncode)   

def open_link(editor_open_cmd:str, browser_open_cmd:str, link:str, app_type:AppType, logger:logging.Logger):
    """Open a link using the appropriate handler."""

    process: str | None = None

    if app_type==AppType.EDITOR and editor_open_cmd:
        process = editor_open_cmd
    elif app_type==AppType.BROWSER and browser_open_cmd:
        process = browser_open_cmd
    elif shutil.which("xdg-open"):
        process = "xdg-open"
    elif shutil.which("open"):
        process = "open"
    elif app_type==AppType.EDITOR and "EDITOR" in os.environ:
        process = os.environ["EDITOR"]
    elif app_type==AppType.BROWSER and "BROWSER" in os.environ:
        process = os.environ["BROWSER"]

    if process is None:
        raise NoSuitableAppFound("no suitable app was found to open the link")

    # Build the command
    
    # Split the options into a list
    cmd_plus_args: list[str] = shlex.split(link)

    # Add '{process}' as the first element
    cmd_plus_args.insert(0, process)
    
    logger.debug(f"{cmd_plus_args}")

    try:
        # Run the command and capture stdout and stderr
        proc = subprocess.Popen(
            cmd_plus_args,
            shell=False,  # Execute in the user's default shell
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # Decode output to strings
        )

        # Communicate to capture output and error
        _, stderr = proc.communicate()

        # Check for errors or unexpected output
        if proc.returncode != 0:
            raise CommandFailed(f"return code {proc.returncode}: {stderr.decode('utf-8')}")

    except Exception as e:
        raise CommandFailed(f"failed to execute command '{" ".join(cmd_plus_args)}': {e}")

def run(
        history_limit:str='',
        editor_open_cmd:str='',
        browser_open_cmd:str='',
        fzf_display_options:str='',
        path_extension:str='',
        loglevel_tmux:str='',
        loglevel_file:str='',
        log_filename:str=''
    ):

    # Set up the logger
    logger = set_up_logger(loglevel_tmux,loglevel_file,log_filename)

    # Add extra path if provided
    if path_extension and path_extension not in os.environ["PATH"]:
        os.environ["PATH"] = f"{path_extension}:{os.environ['PATH']}"

    # Capture tmux content
    capture_str:list[str]=['tmux', 'capture-pane', '-J', '-p', '-e']

    if history_limit != "screen":
        # It the history limit is not set to screen, then so many extra
        # lines are captured from the buffer history
        capture_str.extend(['-S', f'-{history_limit}'])

    content = subprocess.check_output(
            capture_str,
            shell=False,
            text=True,
        )

    # Remove escape sequences
    content=remove_escape_sequences(content)

    # We use the unique set as an expedient to sort over
    # pre_handled_text while keeping the original text
    seen:set[str] = set()
    items:list[tuple[str,str]] = []

    schemes = default_schemes

    max_len_scheme_names:int = max([len(scheme) for scheme in schemes.keys()])

    # Process each scheme
    for scheme_type,scheme in schemes.items():
        # Use regex.finditer to iterate over all matches
        for match in scheme['regex'].finditer(content):
            # Extract the match string
            matched_text = match.group(0)  # Group 0 contains the entire match
            if scheme['pre_handler']:
                pre_handled_text = scheme['pre_handler'](match)
            else:
                pre_handled_text = matched_text
            if matched_text not in seen:
                seen.add(matched_text)
                # We justify the scheme name for prettier print
                justified_scheme_type=scheme_type.ljust(max_len_scheme_names)
                # We keep a copy of the original matched text for later
                items.append((justified_scheme_type + "  " + pre_handled_text,matched_text,))
    # Clean up no longer needed variables
    del seen

    if items == []:
        logger.info('no link found')
        return

    # Sort items
    sorted_choices = sorted(items, key=lambda x: x[0])

    # Number the items
    numbered_choices = [f"{idx:3d}  {item[0]}" for idx, item in enumerate(sorted_choices, 1)]

    # Run fzf and get selected items
    try:
        # Run fzf and get selected items
        result = run_fzf(fzf_display_options,numbered_choices)
    except FzfError as e:
        logger.error(f"error: unexpected error: {e}")
        sys.exit(1)
    except FzfUserInterrupt as e:
        logger.info("no selection made")
        sys.exit(0)
        
    # Process selected items
    selected_choices = result.stdout.splitlines()

    # Regular expression to parse the selected item from the fzf options
    # Each line is in the format {three-digit number, space, space, 
    selected_item_pattern = r"\s*(?P<idx>\d+)\s+(?P<type>\S+)\s+(?P<link>.+)"

    # Process selected items
    for selected_choice in selected_choices:
        match = re.match(selected_item_pattern, selected_choice)
        if match:
            idx_str:str = match.group("idx")
            scheme_type:str = match.group("type")
            
            try:
                idx:int=int(idx_str,10)
                # pick the original item to be searched again
                # before passing the `match` object to the post handler
                selected_item=sorted_choices[idx-1][1]
            except:
                logger.error(f"error: malformed selection: {selected_choice}")
                continue
            
            scheme = schemes.get(scheme_type,None)
            
            if scheme is None:
                logger.error(f"error: malformed selection: {selected_choice}")
                continue

            match=scheme["regex"].search(selected_item)
            if match is None:
                logger.error(f"error: pattern did not match unexpectedly")
                continue          
      
            # Get the post_handler, which applies after the user selection
            post_handler = scheme.get("post_handler",None)

            # Process the match with the post handler
            if post_handler:
                post_handled_link = post_handler(match)    
            else:
                post_handled_link = match.group(0)
            
            try:
                open_link(editor_open_cmd,browser_open_cmd,post_handled_link, schemes[scheme_type]["app_type"],logger)
            except (NoSuitableAppFound, PatternNotMatching, CommandFailed) as e:
                logger.error(f"error: {e}")
                continue
            except Exception as e:
                logger.error(f"error: unexpected error: {e}")
                continue
        else:
            logger.error(f"error: malformed selection: {selected_choice}")
            continue

if __name__ == "__main__":
    run(*sys.argv[1:])
    # try:
    #     run(*sys.argv[1:])
    # except KeyboardInterrupt:
    #     # root logger
    #     logger=logging.getLogger()
    #     if logger.handlers:
    #         logger.info("script interrupted")
