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

# The directory where the editor is launched is not necessarily the same
# as the source code directory, particularly if a symbolic link is used.
# We'll need it to get the correct path names of any command files specified
# as arguments.
launch_dir = os.getcwd()

# Local modules and resource directories are easiest to find if we ensure
# that the current directory is the source code directory.
# So we go there immediately.  Realpath is used in case we are launched with
# a symbolic link.
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
verbose = False

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
        if '-v' in argv[1:]:
            verbose = True
        # Make a list of absolute path names relative to the launch
        # directory for each command file provided
        cmd_files = [
                os.path.abspath( os.path.join( launch_dir,f ) )
                for f in argv[1:] if not f.startswith('-')
            ]

# Launch an interactive editing session
Session( launch_dir,
    ("miUML Editor", "UI_", os.path.join( "Resources", "api_def.mi" )),
    cmd_files, interactive, piped_input, diagnostic, verbose
)
