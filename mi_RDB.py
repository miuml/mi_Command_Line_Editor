#! /usr/bin/env python

"""
Database Session

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
import re
import sys
import psycopg2

# Local
_MODULE_DIR = os.path.abspath("../Modules")
if _MODULE_DIR not in sys.path:
    sys.path.append(_MODULE_DIR)
from mi_Error import *
from mi_Structured_File import Structured_File

# Diagnostic
import pdb # debug

# The variable 'x' is always a cursor in this module.

# Command used when deferring constraints
DEFER_CMD = 'set constraints %s deferred'

class db_Session:
    """ The miUML Editor Database Session"""

    def __init__( self ):
        self.load_deferrals()
        try:
            self.conn = psycopg2.connect( "dbname=miUML" )
        except:
            raise mi_Error( "Cannot connect to miUML database." )

        self.conn.set_session(
                isolation_level='serializable', readonly=False, autocommit=False
            )
        self.x = self.conn.cursor()
        try: # Set the search path
            self.x.execute( "set search_path to mi, mitrack, miuml, mitype, midom, miclass, "
                    "mirel, miform, mirrid, mistate, mipoly" )
            self.conn.commit()
        except:
            raise mi_Error( "Cannot set the db search_path." )
        self.x.close()

    def load_deferrals( self ):
        """ Loads a dictionary of api_calls with required constraint deferrals """
        self.deferrals = {}

        # Read the file lines into a single 'deferrals' section
        self.dfdata = Structured_File( os.path.join( "Resources", "rdb.mi" ) )

        current_api = ""
        for record in self.dfdata.sections['deferrals']:
            # Each record in the deferrals section (the only section)
            # is either indented or it isn't.
            if record.startswith( ' ' ):
                # Indented, add the constraint deferral to the current api_call
                self.deferrals[current_api].append( record.strip() )
            else:
                # Not indented, add a new api_call
                current_api = record
                self.deferrals[current_api] = []

    def exec_command( self, cmd, pvals, ovals, diagnostic_on, verbose_on ):
        """
        Execute a command and return the result

        """
        self.x = self.conn.cursor()

        # Set any deferrals required by this api
        api_name = cmd.split('(')[0] # Left side of api, minus (params)
        if api_name in self.deferrals: # Any constraints to defer?
            # make a csv list of constraints and defer them for this transaction
            defer_cmd = "set constraints " + ", ".join( self.deferrals[api_name] ) + " deferred"

            if verbose_on:
                defer_string = str( self.x.mogrify( defer_cmd ) ).lstrip( "b" )
                print(  "====> [{}]".format( defer_string[1:-1] ) ) # strip single or double quotes

            self.x.execute( defer_cmd )

        scmd = "select * from " + cmd
        if verbose_on:
            cmd_string = str( self.x.mogrify( scmd, pvals ) ).lstrip( "b" ) # convert from b string
            print(  "----> [{}]".format( cmd_string[1:-1] ) ) # strip single or double quotes
        if diagnostic_on:
            return None, None
        try:
            self.x.execute( scmd, pvals )
            self.conn.commit()
        except Exception as e:
            self.x.close()
            raise mi_DB_Error( e.pgcode, e.pgerror )
        relations = self.x.fetchall()
        self.x.close()
        return relations, ovals

    def close( self ):
        """Closes the session"""
        self.conn.close()



if __name__ == '__main__':
    db = db_Session()
    #app_command = "select UI_new_modeled_domain( p_name:=%s, p_alias:=%s )"
    #pvals = [ "Air Traffic Control", "ATC" ]
    app_command = "select * from UI_getall_domains()"
    pvals = []
    rows, attrs = db.exec_command( app_command, pvals )
    hlen = 0
    for a in attrs:
        print(a, end="\t")
        hlen += len(a) + 3
    else:
        print("="*hlen)
    for r in rows:
        print(r)
    else:
        print("="*hlen)
    db.close()
