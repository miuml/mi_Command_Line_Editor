#! /usr/bin/env python

"""
miUML Command Line Editor

This is the main entry point to launch the command line model
editing session.

"""
# --
# Copyright 2012, Model Integration, LLC
# Developer: Leon Starr / leon_starr@modelint.com

# This file is part of the miUML metamodel library.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  The license text should be viewable at
# http://www.gnu.org/licenses/
# --
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

# System
import os
import readline

# Go to real code file directory, in case invoked by symbolic link
# so we can find required relative parent/sibling directories
# We must do this before importing anything local that uses relative paths
os.chdir( os.path.dirname( os.path.realpath(__file__) ) )

# Local
from mi_API import API
from mi_Session import Session

# Diagnostic
import pdb

# Constants
READLINE_INIT_FILE = ".inputrc"

# Set up readline
readline.read_init_file( os.path.join( os.path.expanduser('~'), READLINE_INIT_FILE ) )

interactive = False
cmd_files = None
piped_input = False
diagnostic = False
messages = True

if __name__ == '__main__':
    # Process command line args
    from sys import argv, stdin
    if not stdin.isatty():
        piped_input = True
    if len(argv) > 1:
        if '-i' in argv[1:]:
            interactive = True
        if '-d' in argv[1:]:
            diagnostic = True
        if '-m' in argv[1:]:
            messages = False
        cmd_files = [f for f in argv[1:] if not f.startswith('-')]

# Launch an interactive editing session
Session(
    ("miUML Editor", "UI_", os.path.join( "Resources", "api_def.mi" )),
    cmd_files, interactive, piped_input, diagnostic, messages
)
