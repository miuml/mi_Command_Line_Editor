#! /usr/bin/env python

"""
Loads and parses an API

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

# Local
_MODULE_DIR = os.path.abspath("../Modules")
if _MODULE_DIR not in sys.path:
    sys.path.append(_MODULE_DIR)
from mi_Error import *
from mi_Structured_File import Structured_File

# Diagnostic
import pdb # debug

# Type validation functions
def check_bool( ui_type, arg ):
    """
    Verify that arg is boolean, converting it if possible.

    """
    if type( arg ) == str:
        # Convert to boolean if string is understood
        if arg.lower() in { 'false', 'no', 'f', '0' }:
            arg = False
        elif arg.lower() in { 'true', 'yes', 't', '1' }:
            arg = True

    if type( arg ) == int:
        # Non-zero is true if integer
        arg = bool( arg )

    # Any other non-bool type will fail
    return arg, (type( arg ) == bool)

def check_number( ui_type, arg ):
    """
    Convert the arg to a numeric value or fail.

    """
    try:
        arg = ui_type( arg )
        return arg, True
    except ValueError:
        return arg, False

def check_string( ui_type, arg ):
    """
    Verify that the supplied value is a string.

    """
    # For example, a -f <value> arg with missing <value> would have been
    # parsed as a simple flag with a default True value
    return arg, type( arg ) == str

def check_set( ui_type, arg ):
    """
    Here the ui_type is not a Python type class, but a set, which defines
    an application type.  So we just need to both verify that it is a string
    and check for set membership.

    """
    arg = str( arg ) # All set elements are strings, so ensure arg is a string first
    return arg, arg in ui_type


class API:
    """
    API - Defines a set of calls that can be made to an application.

    """
    def __init__( self, name, call_prefix, cmd_file ):

        # Save params
        self.name = name # Name of the API, ex: "miUML Editor"
        self.call_prefix = call_prefix # Prefix fo API calls, ex: "UI_"
        self.cmd_file = cmd_file # Import API from this file, ex: "Resources/api_def.mi"

        # Import command and type records without parsing
        spec = Structured_File( self.cmd_file )

        # Parse the command records
        self.commands = {} # Parsed command data
        self.ops = set() # Used during parsing for context
        self.subjects = set()
        self.build_commands( spec.sections['commands'] )

        # Parse the types records
        self.types = {} # Parsed type data
        self.build_types( spec.sections['types'] )

    def show_help( self, arg_map ):
        """
        Prints out help for app commands.

        """
        print()
        print( self.name + " Commands" )
        print("---")
        print()
        for s in self.commands:
            # Print names and aliases
            print( " / ".join(self.commands[s]['names']) + ": " )
            for op in self.commands[s]['ops']:
                print( "   " + self.commands[s]['ops'][op]['help'] )
            print()
        print("---")

    def command_to_call( self, subject, op, arg_map ):
        """
        Validates a ui command and translates it into a valid API call.
        For diagnostic purposes, the call will be returned as a string.

        """
        # validate the subject
        if subject not in self.commands:
            # Check aliases
            for s in self.commands:
                if subject in self.commands[s].get('names'):
                    subject = s
                    break # skipping else clause
            else:
                raise mi_Bad_Subject( subject )

        # validate the operation
        if op not in self.commands[subject]['ops']:
            raise mi_Bad_Op( ' | '.join( list( self.commands[subject]['ops'].keys() ) ), subject )

        # Assert:  subject and op are valid
        # Weed out any unexpected extra args that the user may have supplied
        op_spec = self.commands[subject]['ops'][op] # for brevity
        required_args = set( op_spec['args'].keys() )
        provided_args = set( arg_map.keys() )

        # Are args missing or is help requested?
        if "help" in provided_args:
            raise mi_Syntax_Error( op_spec['help'] ) # Help requested
        if provided_args - required_args:
            raise mi_Syntax_Error( op_spec['help'] ) # Missing args

        # Assert: No unexpected extra arguments
        # Are there any missing, but expected args?
        missing_args = required_args - provided_args
        for m in missing_args:
            # Is this a focus arg?  If so, a default could have been set by the UI
            # All focus args have 'scope'
            mscope = self.commands[subject]['ops'][op]['args'][m].get('scope')
            if mscope:
                # Is there a UI supplied default registered?  If so, add it to the arg_map
                default_value = self.commands[mscope].get('default')
                if default_value:
                    arg_map[m] = default_value
                    continue # We've filled in the missing value, move on to next missing arg

            # If the missing argument is not optional, fail with a syntax error
            if not self.commands[subject]['ops'][op]['args'][m]['optional']:
                raise mi_Syntax_Error( op_spec['help'] )

        # Assert: arg_map has everything we need to generate a complete api call

        # Generate the db call
        app_call = 'UI_' + op_spec['api_call'] + r'(' # Start with call
        pvals = []
        # Now add any params
        for a in arg_map:
            # If the parameter name defined by the app is different than the
            # arg name, get it (works for both mod and focus args)
            pname = self.commands[subject]['ops'][op]['args'][a].get('app')
            if not pname:
                pname = a # Just use the argument name
                # The arg name matches the app parameter name
                # If this is a focus arg, use the scope name, otherwise, just us a
                # pname = self.commands[subject]['ops'][op]['args'][a].get('scope', a)
                
            # Get the parameter data type expected by the app
            param_type = self.commands[subject]['ops'][op]['args'][a].get('type')
            if not param_type:
                mscope = self.commands[subject]['ops'][op]['args'][a].get('scope')
                param_type = self.commands[subject]['scope']

            # Get the closest ui type
            ui_type = self.types[param_type]

            # The validator selects an appropriate type validation function.  Normally,
            # this is just the ui_type, but set ui_type is a special case as it is
            # an actual set and not a Python type class.
            validator = ui_type if type( ui_type ) != set else set
            arg_map[a], type_ok = type_check[validator]( ui_type, arg_map[a] )
            if not type_ok:
                raise mi_Arg_Type_Error( pname )

            app_call += "p_{}:=%s, ".format( pname )
            pvals.append( arg_map[a] )
        app_call = app_call.rstrip(', ') + ')' # Kill the rightmost ',' and add closing paren

        ovals = self.commands[subject]['ops'][op].get('olist')
        return { 'call':app_call, 'pvals':pvals, 'ovals':ovals }


    def get_default_for_subject( self, subject ):
        """
        Return current default value set for subject or none if not set.

        """
        # Unknown subject
        if subject not in self.commands:
            raise mi_Bad_Subject( subject )

        # Unscopable subject
        if 'scope' not in self.commands[subject]:
            raise mi_Compound_Subject( subject )

        # Default not set yet
        if 'default' not in self.commands[subject]:
            return None

        return subject, self.commands[subject]['default']

    def get_all_defaults( self ):
        """
        Return all default values or None.
        
        """
        return [ (sub, self.commands[sub]['default']) for sub in self.commands
                    if 'default' in self.commands[sub]  ]

    def clear_default( self, subject=None ):
        """
        If a subject is specified, clear its default.
        Otherwise, delete all defaults.

        """
        if not subject:
            for subject in self.commands:
                if 'default' in self.commands[subject]:
                    del self.commands[subject]['default']
            return

        if subject not in self.commands:
            raise mi_Bad_Subject( subject )

        try:
            del self.commands[subject]['default']
        except KeyError:
            # Just ignore the clearing a non-existent default
            pass

    def set_default( self, subject, value ):
        """
        Sets the default value of a Simple Name Subject (as modeled).

        """
        # Verify that subject is defined
        if subject not in self.commands:
            raise mi_Bad_Subject( subject )

        try: # What app specific type is associated with the subject?
            app_type = self.commands[subject]['scope'] # name, nominal, domain_type, ...
        except KeyError:
            # Cannot assign default to a Compound Subject
            raise mi_Compound_Subject( subject )

        # Assert:  The subject is defined and is a Simple Subject

        # We need to store the value using the ui_type
        # to ensure compatibility with the app_type
        ui_type = self.types[app_type] # str, int, float or a set

        # First see if ui_type is a set and the value is not in it
        if isinstance( ui_type, set ) and (value not in ui_type):
            raise mi_Bad_Set_Value( subject, ui_type )

        # Set the default value
        self.commands[subject]['default'] = value
        return subject, value


    def build_commands( self, section ):
        """
        Parses command data read from a structured mi file to produce a dictionary
        mapping user commands and arguments to API calls and parameters.

        """
        # Each type of line that will be processed is defined by a matching regex

        # Subject of a command, ex: 'attr, attribute, a : name' (never indented)
        # yields a list of subject names and an optional colon delimiter followed
        # by the type of the local identifying attribute
        subject_line = re.compile( r'^(?P<names>\w[\w,\s]*)(:\s*(?P<type>\w+))?' )

        # Operation that can be applied to the subject.
        # Yields the name of the op a colon delimiter and the base name of the
        # corresponding API call.
        # example: '    new : new_ind_attr' (must be indented)
        op_line = re.compile( r'^\s+\w+\s*:\s*\w+\s*$')

        # Arguments (one or more) prefixed with an purpose code such as
        # f for focus, m for modify or o for output.  This regex identifies
        # an argument line and its purpose, but does not extract the arg elements
        arg_line = re.compile( r'^\s+(?P<purpose>[fmo])>' )

        # Arg patterns - extract argument data
        # Various patterns are successivly applied to an argument line to match and
        # extract the content of one or more argument records
        arg_patterns = {
            # Focus argument patterns
            'focus':[
                # match [d|domain:domain]
                re.compile( r'(?P<optional>\[)(?P<ui>\w+)\|(?P<app>\w+):(?P<scope>\w+)\]' ),
                # match   cl|client:domain
                re.compile( r'(?P<ui>\w+)\|(?P<app>\w+):(?P<scope>\w+)' ),
                # match [d:domain]
                re.compile( r'(?P<optional>\[)(?P<ui>\w+):(?P<scope>\w+)\]' ),
                # match   client:domain
                re.compile( r'(?P<ui>\w+):(?P<scope>\w+)' ),
                # match   domain
                re.compile( r'(?P<scope>\w+)' )
            ],
            # Modify argument patterns
            'mod':[
                # match [ph|phrase:text]
                re.compile( r'(?P<optional>\[)(?P<ui>\w+)\|(?P<app>\w+):(?P<type>\w+)\]' ),
                #re.compile( r'(?P<ui>\w+)\|(?P<app>\w+):(?P<type>\w+)=(?P<default>\w+)' ),
                # match ph|phrase:text
                re.compile( r'(?P<ui>\w+)\|(?P<app>\w+):(?P<type>\w+)' ),
                # match [ph:text]
                re.compile( r'(?P<optional>\[)(?P<ui>\w+):(?P<type>\w+)\]' ),
                #re.compile( r'(?P<ui>\w+):(?P<type>\w+)=(?P<default>\w+)' ),
                # match ph:text
                re.compile( r'(?P<ui>\w+):(?P<type>\w+)' )
            ],
            # Output (returned) argument pattern
            'out':[ re.compile( r'(?P<o_param>\w+)' ) ]
        }
        
        pcode = { 'f':'focus', 'm':'mod', 'o':'out' }

        # help string pattern
        scoped_type = re.compile( r'@(\w+)@' )

        this_subject = ""
        this_op = ""
        state = "start"
        
        for line in section:
            # extract_sections has removed any blank lines
            # print( "LINE: [{}]".format(line))

            r = subject_line.match( line )
            if r:
                if state == 'subject':
                    raise mi_Error( "Subject [{}] has no ops defined.".format(this_subject) )
                if state != 'start':
                    del op

                subject = { 'ops':{} } # Temporary record to be added to command dict

                # line format is: name_list [: type]
                # Names are csv on the left side of the colon

                if not r.group('names'):
                    raise mi_Error( 'No names specified for subject.' )

                subject['names'] = re.findall( r'\w+', r.group('names') )
                self.subjects.update(subject['names'])
                this_subject = subject['names'][0] # first name is used officially

                # If it's there, get the type on the right side of the colon
                if r.group('type'):
                    subject['scope'] = r.group('type')

                self.commands[this_subject] = subject # ops to be added in next case
                del subject # so we can re-use it later without changing current subject
                state = 'subject' # Next case knows we are inside a subject
                continue # subject line match

            if op_line.match( line ):
                if state == 'start':
                    raise mi_Error( 'Operation found before any subjects.' )
                if state == 'operation':
                    # pp( op )
                    del op

                # Split op name : api_call on the colon
                this_op = line.split(':')[0].strip() # left side of colon
                self.ops.update([this_op]) # add to convenience set
                op = self.commands[this_subject]['ops'][this_op] = { 'args':{} }
                op['api_call'] = line.split(':')[1].strip() # right side of colon
                op['help'] = "{} {} ".format( this_op, this_subject ) # arg names appended later
                state = 'operation' # Next case knows we are inside an operation
                continue # opline match

            r = arg_line.match( line ) # to get the arg_type in re group
            if r:
                if state != 'operation':
                    raise mi_Error( 'Args outside of operation.' )

                # discard [mfo]> prefix and split to list on commas, stripping spaces
                args_rec = re.findall( r'\[?\w[\w\|:]*\]?', line.split('>')[1] ) # right of x>
                purpose = pcode[r.group('purpose')] # map x> to name of purpose

                for a in args_rec:
                    d = next(
                        # Apply each regex defined for the attr purpose (focus, mod or out)
                        # The first match creates dictionary d from the pattern
                        ( p.match(a).groupdict() for p in arg_patterns[purpose] if p.match(a) ),
                            False # returned if there is no match
                    )
                    if not d:
                        # Must be malformed input
                        raise mi_Error(
                            'No pattern matched for arg: [{}] on line\n{}.'.format(a, line)
                        )

                    d['optional'] = True if d.get('optional') else False

                    if d.get('o_param'):
                        if op.get('olist'):
                            # append the o_param
                            op['olist'].append( d.get('o_param') )
                        else:
                            # start a new list with o_param as first item
                            op['olist'] = [ d.get('o_param') ]
                        continue

                    if d.get('ui'):
                        arg_name = d.pop('ui') # Name of the command line argument
                    else:
                        try:
                            arg_name = d['scope']
                        except KeyError:
                            raise mi_Error( 'Scope missing from non-ui arg [{}].'.format(d) )
                    d['purpose'] = purpose
                    if purpose == 'focus':
                        # Type will be that of the local identifier defined for some
                        # subject which we may not have processed yet.  So we save a forward
                        # reference to be filled in with an actual type later.
                        arg_type = "@{}@".format( d['scope'] ) # Forward reference
                    else:
                        # Otherwise, just save the specified type
                        arg_type = "<{}>".format( d['type'] )

                    op['args'][arg_name] = d # add argument to the argset for the current op
                    h = "-{} {}".format( arg_name, arg_type )
                    if d['optional']:
                        h = "[" + h + "] "
                    else:
                        h += " "
                    op['help'] += h
                continue # argline match

            # Error if line is not a subject, operation or arg set
            raise mi_Error('Unrecgonized command in API def file.')

        # All lines processed
        if state == 'subject':
            raise mi_Error( 'Trailing subject [{}] has no operations.'.format(this_subject)  )

        # Wherever a scoped subject is referenced in a help string
        # replace it with a type appropriate for naming that subject

        for s in self.commands: # Each subject
            for op in self.commands[s]['ops']: # Each op

                # Grab the help string which may have one or more scope subject references
                # in @ brackets such as @class@.  Now we must replace each with the
                # corresponding type name found under the subject['scope'] key
                # For example, a class subject is defined by a 'name' type
                # a rel subject would be defined by a 'nominal' type, on the other hand

                h = self.commands[s]['ops'][op]['help'] # h is the help string

                # Now replace each found occurence of <subject> (if any) with
                # the correpsonding type found at self.commands[<subject>]['scope']

                # The sub() function searches h using the scoped_type regex defined up at
                # the top of this function yielding zero or more matches (m) fed into the
                # lambda function.  The lambda simply strips off the @ brackets, 
                # looks up and returns the type for substitution.
                try:
                    h = re.sub(
                        scoped_type,
                        lambda m: "<{}>".format(self.commands[m.group(1).strip('@')]['scope']
                    ), h )
                except KeyError as e:
                    raise mi_Error( 'Cannot resolve scope type for {}'.format(e) )

                # Replace the old help string with the resolved version, and we're done!
                self.commands[s]['ops'][op]['help'] = h.strip()

    def build_types( self, section ):
        """
        Parse each line of text in a type definition section to build up a
        dictionary of types according to this grammar:
        
        type:: <app_type>:<ui_type>
        <app_type>:: [ compound_name | nominal | name | description | ... ]
        <ui_type>:: [ integer | string | float ] | <set>
        <set>:: '[' string_value, ... ']'

        The resultant dictionary has the form: { <app_type> : <type_function> }
        <type_function>:: int, float, str, ...

        """
        #print( 'Building types...' )
        # Type conversion functions will make it easy to convert
        # values entered command session to desired app types
        tfunc_map = { 'string':str, 'integer':int, 'float':float, 'bool':bool }
        for line in section:
            app_type, ui_type = line.strip().split(':')

            if '[' in ui_type:
                self.types[app_type] = {x.strip() for x in ui_type.strip('[]').split('|')}
            else:
                self.types[app_type] = tfunc_map[ui_type.strip()]

# Type validiation function map
type_check = { int:check_number, float:check_number,
        str:check_string, bool:check_bool, set:check_set }
    
if __name__ == '__main__':
    from pprint import pprint as pp
    a = API( name="miUML Editor", call_prefix="UI_", cmd_file="api_def.txt" )
    ac = a.commands # shortcuts for testing
    at = a.types
