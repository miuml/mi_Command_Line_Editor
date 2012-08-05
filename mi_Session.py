#! /usr/bin/env python

"""
Interactive Command Session for miUML Editor

A Session interacts with a user through the command line.
Like any command interpreter, a prompt is displayed and 
commands are accepted and processed one at a time.  A Command
will be rejected if it's syntax is incorrect.  Any output is
displayed in the same window.

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
import re
import sys
import os

# Diagnostic
import pdb

# Local
_MODULE_DIR = os.path.abspath("../Modules")
if _MODULE_DIR not in sys.path:
    sys.path.append(_MODULE_DIR)
from mi_Error import *
from mi_API import API
import mi_RDB

OP, SUB, ARGS = range(3) # enumeration for line parts
UIOP, UIARGS = range(2)
# Class and class based methods used for all singletons
# to save the hassle of creating single object variables

class Session_Spec:
    """
    Session Specification

    Configurable features of a Session are defined here.

    """
    def __init__( self ):
        self.prompt = "* "
        self.version = "1.0.0"
        self.developer = "Leon Starr"
        self.copyright = "Copyright 2012"
        self.title = "miUML Command Line Editor"
        self.license = ("This program is distributed under the GNU Lesser General\n"
                "Public License as part of the miUML metamodel library.")
        self.arg_re = {
                    # example: -s name
                    # Note that names may contain spaces
                    'arg_val':re.compile( r'^-(?P<arg>\w+)\s+(?P<value>\w[\w\/\.\s]*)' ),
                    # example: -c
                    'arg_only':re.compile( r'^-(?P<arg>\w+)\s*(-.*)?$' )
                }

class Session:
    """
    Session Class

    """
    def __init__( self, api_args, cmd_files, interactive, piped_input, diagnostic, messages ):
        self.api_args = api_args
        self.spec = Session_Spec()
        self.messages = messages
        self.diagnostic = diagnostic
        self.api_args
        self.api = API( *api_args )
        self.ui_cmd = {}
        self.ui_alias = {}
        self.exit_commands = ['q', 'quit', 'exit', 'ciao', 'bye']
        self.init_ui_cmd()
        self.editor = mi_RDB.db_Session()
        if piped_input:
            self.mode = "piped"
            self.interact()
            if not cmd_files and not interactive:
                exit(0)
            if interactive:
                # Switch standard input to tty
                sys.stdin = open('/dev/tty', 'r')
        if cmd_files:
            self.mode = "batch"
            self.process_command_files( cmd_files, interactive )
            if not interactive:
                self.editor.close()
                exit(0)
        self.mode = "interactive"
        self.interact()
        self.editor.close()

    def parse_app_args( self, arg_text ):
        """
        Simple version of parse_ui_args which does no validation.  It simply
        produces the arg_map which can be later validated by the api.

        """
        # Later we will fuse both parse_ui/app_args functions
        # but they are separate now for tesing/experimentation

        arg_map = {} # the parsed data goes here

        # No need to parse the arg text if there is a ? in it anywhere
        # as we will just print the complete list of required args
        if "?" in arg_text:
            arg_map["help"] = True  # Detected when building the API command
            return arg_map

        # line is unparsed portion of arg_text
        # strip it and remove any internal single or double quotes
        line = arg_text.strip().replace("'","").replace('"',"")

        match_end = 0 # total length of matched groups for line chopping
        while line:
            r = self.spec.arg_re['arg_val'].match( line )
            if r: # matches arg value pattern, ex: -s domain
                a, v = r.group('arg'), r.group('value').strip('" ') # ex: a is 's', v is 'domain'
                match_end = r.end('value') # End of matched text so we can chop the line
            else:
                r = self.spec.arg_re['arg_only'].match( line )
                if r: # matches arg only pattern, ex: -f
                    a = r.group('arg')
                    match_end = r.end('arg')
                    v = True
                else:
                    raise mi_Syntax_Error( "<op> <subject> [<args>]" )

            # Add arg_map entry a, v
            arg_map[a] = v

            if match_end >= len(line)-1:
                break # The remainder of the line has been matched

            # Chop the parsed text and extraneous whitespace and continue parsing
            line = line[match_end:].lstrip()

        return arg_map


    def parse_ui_args( self, op, arg_text ):
        """
        Parses the args porition of a single text command line to produce an arg_map.
        This is a dictionary of arg:value and switch:True pairs.  The arg_map can be
        later supplied to the op's designated implementation function.

        """
        arg_map = {} # the parsed data goes here
        line = arg_text.strip() # line is unparsed portion of arg_text
        fset = set() # For grouping comparison

        # Build the arg map
        match_end = 0 # total length of matched groups for line chopping
        while line:
            r = self.spec.arg_re['arg_val'].match( line )
            if r: # matches arg value pattern, ex: -s domain
                a, v = r.group('arg'), r.group('value') # ex: a is 's', v is 'domain'
                match_end = r.end('value') # End of matched text so we can chop the line

                # validate( a ) # validate_uiarg(a) or validate_apparg(a)
                if a not in self.ui_cmd[op]['syntax']:
                    # Arg not defined for this op
                    raise mi_Syntax_Error( self.ui_cmd[op]['help'] )

                if self.ui_cmd[op]['syntax'][a]['action'] != 'store':
                    # Arg does not take a value for this op
                    raise mi_Syntax_Error( self.ui_cmd[op]['help'] )
            else:
                r = self.spec.arg_re['arg_only'].match( line )
                if r: # matches arg only pattern, ex: -f
                    a = r.group('arg')
                    match_end = r.end('arg')

                    if a not in self.ui_cmd[op]['syntax']:
                        # Arg not defined for this op
                        raise mi_Syntax_Error( self.ui_cmd[op]['help'] )

                    arg_spec = self.ui_cmd[op]['syntax'][a] # for brevity

                    if arg_spec['action'] == 'store':
                        try:
                            v = arg_spec['default']
                        except KeyError:
                            # Value should have been specified since there was no default
                            raise mi_Syntax_Error( self.ui_cmd[op]['help'] )
                    elif arg_spec['action'] == 'switch':
                        v = True
                    else: # action must be 'store' or 'switch', fatal error
                        raise mi_Error( 'No action defined for flag: ' + a )
                else: # No pattern match for line, bad arg text
                    raise mi_Syntax_Error( self.ui_cmd[op]['help'] )

            # Add arg_map entry a, v, will overwrite any duplicate
            arg_map[ self.ui_cmd[op]['syntax'][a]['var'] ] = v.strip() if v else None

            # Update group
            fset.add(a)
            if match_end >= len(line)-1:
                break # The remainder of the line has been matched

            # Chop the parsed text and extraneous whitespace and continue parsing
            line = line[match_end:].lstrip()

        # Ensure that each required flag has been provided
        # and has a value.  Switches will always carry a True value.
        for flag in self.ui_cmd[op]['syntax']:
            if 'required' not in self.ui_cmd[op]['syntax'][flag]:
                continue # Don't worry about optional flags
            if self.ui_cmd[op]['syntax'][flag]['var'] not in arg_map:
                raise mi_Syntax_Error( self.ui_cmd[op]['help'] )

        # Enforce grouping rules
        if not arg_map and not self.ui_cmd[op].get('grouping'):
            # No groups and no args
            return arg_map

        group_found = False
        # Find 

        for group in self.ui_cmd[op]['grouping']:
            if fset == set(group): # Order doesn't matter, so we use sets
                group_found = True
                break
        if not group_found:
            # There is no legal grouping that corresponds to what we parsed
            raise mi_Syntax_Error( self.ui_cmd[op]['help'] )
        
        return arg_map

    # <<< UI Command Functions

    def ui_refresh( self, arg_map=None ):
        """
        Re-reads the API.

        """
        self.api = API( *self.api_args )

    def ui_help( self, arg_map=None ):
        """
        Prints command line help

        """
        if not arg_map:
            # Print everything, starting with UI commands
            print()
            print("UI Commands")
            print("---")
            print()
            for u in self.ui_cmd:
                print( self.ui_cmd[u]['help'] )
            print()
            print( "Exit with: [ " + " | ".join(self.exit_commands) + " ]" )

            # Print all app commands
            self.api.show_help( arg_map )

            # Print guide to more detailed help
            print( "Type a partial command with a question mark for help on a particular item." )
            print ("   example: help new attr ?" )
            print()


    def ui_toggle_messages( self, arg_map ):
        """
        Toggles messages mode where API calls are printed before being invoked.

        """
        self.messages = not( self.messages )
        print( "Message mode {}".format( "ON" if self.messages else "OFF") )


    def ui_toggle_diagnostic( self, arg_map ):
        """
        Toggles diagnostic mode where API calls are printed, but not invoked.

        """
        self.diagnostic = not( self.diagnostic )
        print( "Diagnostic mode {}".format( "ON" if self.diagnostic else "OFF") )

    
    def ui_focus( self, arg_map ):
        """
        Sets or clears a focus attribute, or clears all focus attributes.

        """
        if 'subject_to_clear' in arg_map:
            # Can't use get() since value might be None
            # Either clear all defaults or the specified subject
            self.api.clear_default( arg_map['subject_to_clear'] )
            return

        if not arg_map.get('subject'):
            # Return all default values (if any have been set)
            for s, v in self.api.get_all_defaults():
                print('{} : {}'.format(s, v))
            return

        # A subject has been specified
        if arg_map.get('value'):
            # Set the subject's default to provided value
            s, v = self.api.set_default( arg_map['subject'], arg_map['value'] )
            return

        # Subject, but no value specified, so return the subject's current default value or None
        s, v = self.api.get_default_for_subject( arg_map['subject'])
        print( '{} : {}'.format(s, v) )


    def ui_process_cmd_file( self, arg_map ):
        """
        Reads and processes a single command file during an interactive
        session.

        """
        try:
            cf = open( arg_map['file'] )
        except IOError:
            mi_File_Error("Could not open", arg_map['file'] )
            return

        self.mode = "file"
        for command in cf:
            try:
                self.process( command )
            except mi_Quiet_Error:
                print( "Command file aborted.")
                return # to interactive session
            finally:
                self.mode = "interactive"

    def init_ui_cmd( self ):
        """
        Build up a list of recognized UI commands with required args.

        """
        self.ui_cmd['read'] = {
                'func':Session.ui_process_cmd_file,
                'syntax':{
                            'f':{'action':'store', 'var':'file'},
                    },
                'grouping':( ('f') ),
                'help':""
            }

        self.ui_cmd['diagnostic'] = {
                'func':Session.ui_toggle_diagnostic,
                'syntax':{},
                'grouping':( () ),
                'help':""
            }

        self.ui_cmd['messages'] = {
                'func':Session.ui_toggle_messages,
                'syntax':{},
                'grouping':( () ),
                'help':""
            }

        self.ui_cmd['refresh'] = {
                'func':Session.ui_refresh,
                'syntax':{},
                'grouping':( () ),
                'help':""
            }

        self.ui_cmd['focus'] = { # name of op
                    'func':Session.ui_focus, # Session function that implements op
                    'syntax':{ # flag specs
                            # action: store or switch, var: name of stored value
                            # 'required' means flag is required, otherwise flag is optional
                            # default:value means user can omit a value
                            # No value is provided with a switch action example:
                            # 'f':{'action':'switch', 'var':'force'},
                            's':{'action':'store', 'var':'subject'},
                            'v':{'action':'store', 'var':'value'},
                            'c':{'action':'store', 'var':'subject_to_clear', 'default':None}
                        },
                    # possible flag groupings on command line
                    # () means that a command with no args is okay
                    'grouping':( (), ('c'), ('s'), ('s', 'v') ),
                    'help':"" # generated below
                }

        self.ui_cmd['h'] = {
                    'func':Session.ui_help,
                    'syntax':{},
#                            's':{'action':'store', 'var':'subject'},
#                            'op':{'action':'store', 'var':'op'}
#                        },
                    'grouping':( () ),
                    'help':""
                }

        self.ui_alias = {
                'h': 'h', 'help' : 'h',
                'focus' : 'focus', 'f' : 'focus',
                'r':'refresh', 'refresh':'refresh',
                'read':'read', 'run':'read',
                'diagnostic':'diagnostic', 'd':'diagnostic',
                'messages':'messages', 'm':'messages'
            }

        # Create help syntax dictionary with entry for each command
        for op in self.ui_cmd:
            args_optional = False
            group_strings = [] # Help string for each grouping
            for grouping in self.ui_cmd[op]['grouping']:
                if not grouping: # Empty grouping means 'no args' is okay
                    args_optional = True
                    continue
                gstr = "" # Help string for this group
                for flag in grouping:
                    fstr = "" # Help string for this flag
                    flag_spec = self.ui_cmd[op]['syntax'][flag] # for brevity
                    # Add flag syntax to help string
                    if flag_spec['action'] == 'store':
                        if 'default' in flag_spec:
                            # stores a default value -f [value]
                            fstr += "-{} [{}] ".format( flag, flag_spec['var'] )
                        else:
                            # stores a required value -f value
                            fstr += "-{} {} ".format( flag, flag_spec['var'] )
                    elif flag_spec['action'] == 'switch':
                            # no value
                            fstr += "-{}".format( flag )
                    # Append to group string
                    gstr += fstr
                # Add the flag help to the current group
                if gstr:
                    group_strings.append( gstr )
            # Join all the groups together with 'or' delimiter
            arg_help = ' | '.join(group_strings)
            # Wrap all args in 'optional' [] braces if the op may be used without args
            #if 'required' not in [f for f in self.ui_cmd[op]['syntax']]:
            if args_optional:
                arg_help = " [ " + arg_help + " ]"
            self.ui_cmd[op]['help'] = op + " " + arg_help

    def process_command_files( self, cmd_files, interactive ):
        """
        Process each command (line) from each command file.  Exits if any command
        fails unless interactive mode has been requested.

        """
        for cmd_fname in cmd_files:
            try:
                cf = open( cmd_fname )
            except:
                mi_File_Error("Could not open", cmd_fname )
            for command in cf:
                try:
                    self.process( command )
                except:
                    # If a command fails, no point in reading the rest of the file
                    # since the error will likely cascade.  Stop processing files.
                    if not interactive:
                        exit(1)
                    return # Will enter an interactive session


    def interact( self ):
        """
        Interactive command loop.  Repeatedly prompts for a raw line of input.

        """
        if self.mode == "piped":
            print()
            print("--- Processing commands from input pipe ---")
            print()
        else:
            # Print start of session message
            print()
            print( self.spec.title +  " " + "Version: " + self.spec.version )
            print()
            print( "Developer: " + self.spec.developer + " / " + self.spec.copyright )
            print( self.spec.license )
            print()
            print ("? <subject> to get valid operations, ex: ? domain")
            print ("<op> <subject> without any args to get required args, ex: new domain")
            print( "h, help for help and q to quit" )
            print()

        # Prompt for commands and process them until a quit command is detected
        while True:
            line = ""
            while not line: # ignore blank lines
                try:
                    if self.mode == "interactive":
                        line = input( self.spec.prompt )
                    else:
                        line = input()
                except EOFError:
                    # We'll get this when processing an input stream
                    if self.mode == "piped":
                        print()
                        print("--- Finished processing input pipe ---")
                        print()
                        return
                    else:
                        print("Ctrl-D detected.")
                        print("Bye.")
                        print()
                        break

            if line in self.exit_commands:
                print("Bye.")
                print()
                break
            try:
                self.process( line )
            except mi_Command_Error:
                # Error message has been printed, continue to next prompt
                continue

    def process( self, line ):
        """
        Process line

        """
        # Initially assume it is a UI command with two parts <UIOP> <UIARGS>
        term = line.split( None, 1 )

        # Is this a valid UI command?
        if term[UIOP] in self.ui_alias:
            # replace alias with official ui command
            term[UIOP] = self.ui_alias[term[UIOP]]
            
            # Split off the arg portion of the command line
            arg_text = "" if len(term) < 2 else term[UIARGS]
            
            # Parse the args
            arg_map = self.parse_ui_args( term[UIOP], arg_text )

            # Execute the UI command
            self.ui_cmd[term[UIOP]]['func']( self, arg_map )
            return

        # Assert: Not a UI command, possibly a legal App command

        # Break the line into 1-3 parts, <op> <subject> <args>
        term = line.split( None, 2 )

        if len(term) < 2: # We need at least an op and a subject
            raise mi_Syntax_Error( "<op> <subject> [arg, ...]" )
            if self.mode in {'batch', 'file'}:
                raise mi_Quiet_Error()
            return

        if len(term) == 2:
            term.append( "" ) # to avoid index error later

        # Assert term is a list of three elements OP, SUB, ARGS
        arg_map = self.parse_app_args( term[ARGS] )
        command = self.api.command_to_call( term[SUB], term[OP], arg_map )
        try:
            relations, attrs = self.editor.exec_command(
                    command['call'], command['pvals'], command['ovals'],
                    self.diagnostic, self.messages
                )
        except mi_DB_Error:
            if self.mode in {'batch', 'file'}:
                raise mi_Quiet_Error()
            return # Non-fatal error was printed

        if attrs: # Any expected return value?
            print("<----")
            hlen = 0
            for a in attrs:
                print(a, end="\t")
                hlen += len(a) + 3
            else:
                print()
                print("="*hlen)
            for r in relations:
                print(r)
            else:
                print("="*hlen)


if __name__ == '__main__':
    import sys
    print( "Bad main: " + sys.modules(__name__) )
