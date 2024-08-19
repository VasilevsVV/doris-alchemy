#! /usr/bin/python3

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import logging
from typing import Any, Dict, List, Optional, Sequence
from sqlalchemy import Column, Table, log, exc, text
from sqlalchemy.dialects.mysql.base import MySQLDDLCompiler, MySQLIdentifierPreparer, MySQLDialect
from sqlalchemy.dialects.mysql import reflection as _reflection
from sqlalchemy.engine.interfaces import ReflectedTableComment, ReflectedForeignKeyConstraint
from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql
from sqlalchemy.engine import Connection
from sqlalchemy.util import topological

from doris_alchemy import datatype
from sqlalchemy.sql import sqltypes
# from sqlalchemy.sql.ddl import CreateTable
from sqlalchemy.schema import CreateTable, SchemaConst

from doris_alchemy.const import TABLE_KEY_OPTIONS, TABLE_PROPERTIES_SORT_TUPLES

from doris_alchemy.datatype import HASH, RANDOM, RenderedMixin
from doris_alchemy.util import format_properties, join_args_with_quote


logger = logging.getLogger(__name__)


class DorisDDLCompiler(MySQLDDLCompiler):
    def __init__(self, *args, **kw):
        super(DorisDDLCompiler, self).__init__(*args, **kw)
        self.dialect: DorisDialectMixin
    
    
    def visit_create_table(self, create: CreateTable, **kw):
        table: Table = create.element
        preparer = self.preparer

        text = "\nCREATE "
        if table._prefixes:
            text += " ".join(table._prefixes) + " "

        text += "TABLE "
        if create.if_not_exists:
            text += "IF NOT EXISTS "

        text += preparer.format_table(table) + " "

        create_table_suffix = self.create_table_suffix(table)
        if create_table_suffix:
            text += create_table_suffix + " "

        text += "("

        separator = "\n"

        # if only one primary key, specify it along with the column
        # first_pk = False primary key is not supported
        for create_column in create.columns:
            column = create_column.element
            # assert column.primary_key is False
            try:
                processed = self.process(create_column)
                if processed is not None:
                    text += separator
                    separator = ", \n"
                    text += "\t" + processed
                # if column.primary_key:
                #     first_pk = True
            except exc.CompileError as ce:
                raise exc.CompileError(
                    "(in table '%s', column '%s'): %s"
                    % (table.description, column.name, ce.args[0])
                ) from ce

        text += "\n)\n%s\n\n" % self.post_create_table(table)
        return text



    def __compile_table_arg(self, option: str, arg: Any, table_name: str) -> Optional[str]:
        option = option.replace("_", " ")
        # if option in _reflection._options_of_type_string:
        if option == 'COMMENT':
            arg = self.sql_compiler.render_literal_value(arg, sqltypes.String())
            return f'{option} {arg}'
        if option in TABLE_KEY_OPTIONS:
            if isinstance(arg, str):
                return '{} {}'.format(option, join_args_with_quote(arg))
            else:
                assert isinstance(arg, Sequence)
                return '{} {}'.format(option, join_args_with_quote(*arg))
        if option in ['PARTITION BY', 'DISTRIBUTED BY']:
            assert isinstance(arg, RenderedMixin)
            return '{} {}'.format(option, arg.render())
        if option == 'PROPERTIES':
            assert isinstance(arg, dict)
            return '{} {}'.format(option, format_properties(**arg))
        if option == 'ENGINE':
            assert isinstance(arg, str)
            return f'{option} {arg}'
        return None


    def post_create_table(self, table: Table):
        "Builds top level CREATE TABLE options, like ENGINE and COLLATE."

        table_opts = []
        opts = {}
        for k, v in table.kwargs.items():
            if k.startswith("%s_" % self.dialect.name):
                opts[k[len(self.dialect.name) + 1:].upper()] = v
        if table.comment is not None:
            opts["COMMENT"] = table.comment
        pk = table.primary_key
        if opts.get('AUTOGEN_PRIMARY_KEY', False) and len(pk) > 0:
            pk_key = tuple(c.name for c in pk)
            if 'UNIQUE_KEY' not in opts:
                opts['UNIQUE_KEY'] = pk_key
            if 'DISTRIBUTED_BY' not in opts:
                opts['DISTRIBUTED_BY'] = HASH(pk_key)
                
            
        sorted_opts = topological.sort(TABLE_PROPERTIES_SORT_TUPLES, opts)
        for opt in sorted_opts:
            __arg = opts[opt]
            __compiled = self.__compile_table_arg(opt, __arg, table.name)
            if __compiled:
                table_opts.append(__compiled)
        return "\n".join(table_opts)
    
    def visit_create_column(self, create, first_pk=False, **kw):
        column = create.element
        if column.system:
            return None
        text = self.get_column_specification(column, first_pk=first_pk)
        const = " ".join(
            self.process(constraint) for constraint in column.constraints
        )
        if const:
            text += " " + const
        return text
    
    def get_column_specification(self, column: Column, **kw):
        """Builds column DDL."""
        if (
            self.dialect.is_mariadb is True
            and column.computed is not None
            and column._user_defined_nullable is SchemaConst.NULL_UNSPECIFIED
        ):
            column.nullable = True
        colspec = [
            self.preparer.format_column(column),
            self.dialect.type_compiler_instance.process(
                column.type, type_expression=column
            ),
        ]

        if column.computed is not None:
            colspec.append(self.process(column.computed))

        is_timestamp = isinstance(
            column.type._unwrapped_dialect_impl(self.dialect),
            sqltypes.TIMESTAMP,
        )

        if not column.nullable:
            colspec.append("NOT NULL")

        # see: https://docs.sqlalchemy.org/en/latest/dialects/mysql.html#mysql_timestamp_null  # noqa
        elif column.nullable and is_timestamp:
            colspec.append("NULL")

        comment = column.comment
        if comment is not None:
            literal = self.sql_compiler.render_literal_value(
                comment, sqltypes.String()
            )
            colspec.append("COMMENT " + literal)

        else:
            default = self.get_column_default_string(column)
            if default is not None:
                colspec.append("DEFAULT " + default)
        return " ".join(colspec)


@log.class_logger
class DorisDialectMixin(MySQLDialect, log.Identified):
    # Caching
    # Warnings are generated by SQLAlchmey if this flag is not explicitly set
    # and tests are needed before being enabled
    supports_statement_cache = False


    name = 'doris'
    preparer = MySQLIdentifierPreparer

    def __init__(self, *args, **kw):
        super(DorisDialectMixin, self).__init__(*args, **kw)
        self.preparer = MySQLIdentifierPreparer
        self.identifier_preparer: MySQLIdentifierPreparer = self.preparer(self)

    def has_table(self, connection: Connection, table_name: str, schema=None, **kw) -> bool:
        self._ensure_has_table_connection(connection)

        if schema is None:
            schema = self.default_schema_name

        assert schema is not None

        full_name = ".".join(
            self.identifier_preparer._quote_free_identifiers(
                schema, table_name
            )
        )

        # DESCRIBE *must* be used because there is no information schema
        # table that returns information on temp tables that is consistently
        # available on MariaDB / MySQL / engine-agnostic etc.
        # therefore we have no choice but to use DESCRIBE and an error catch
        # to detect "False".  See issue #9058

        try:
            with connection.exec_driver_sql(
                f"DESCRIBE {full_name}",
                execution_options={"skip_user_error_events": True},
            ) as rs:
                return rs.fetchone() is not None
        except exc.DBAPIError as e:
            # https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html  # noqa: E501
            # there are a lot of codes that *may* pop up here at some point
            # but we continue to be fairly conservative.  We include:
            # 1146: Table '%s.%s' doesn't exist - what every MySQL has emitted
            # for decades
            #
            # mysql 8 suddenly started emitting:
            # 1049: Unknown database '%s'  - for nonexistent schema
            #
            # also added:
            # 1051: Unknown table '%s' - not known to emit
            #
            # there's more "doesn't exist" kinds of messages but they are
            # less clear if mysql 8 would suddenly start using one of those
            # print('caught exception', e)
            if self._extract_error_code(e.orig) in (1105, 1051):
                if e.orig is None:
                    return False
                info: str = e.orig.args[1].split('detailMessage = ')[-1]
                if info.startswith('Unknown table'):
                    return False
            raise


    def get_schema_names(self, connection: Connection, **kw):
        rp = connection.exec_driver_sql("SHOW schemas")
        return [r[0] for r in rp]

    def get_table_names(self, connection: Connection, schema: Optional[str]=None, **kw):
        """Return a Unicode SHOW TABLES from a given schema."""
        if schema is not None:
            current_schema = schema
        else:
            current_schema = self.default_schema_name
        assert current_schema, 'Failed to establish current schema'

        charset = self._connection_charset

        rp = connection.exec_driver_sql(
            "SHOW FULL TABLES FROM %s"
            % self.identifier_preparer.quote_identifier(current_schema)
        )

        return [
            row[0]
            for row in self._compat_fetchall(rp, charset=charset)
        ]

    def get_view_names(self, connection, schema: Optional[str]=None, **kw):
        if schema is None:
            schema = self.default_schema_name
        assert schema, 'Failed to get schema name'
        charset = self._connection_charset
        rp = connection.exec_driver_sql(
            "SHOW FULL TABLES FROM %s"
            % self.identifier_preparer.quote_identifier(schema)
        )
        return [
            row[0]
            for row in self._compat_fetchall(rp, charset=charset)
            if row[1] in ("VIEW", "SYSTEM VIEW")
        ]

    def get_columns(self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw) -> List[Dict[str, Any]]:
        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(f"schema={schema}, table={table_name}")
        schema = schema or self._get_default_schema_name(connection)

        quote = self.identifier_preparer.quote_identifier
        full_name = quote(table_name)
        if schema:
            full_name = "{}.{}".format(quote(schema), full_name)

        res = connection.execute(text(f"SHOW COLUMNS FROM {full_name}"))
        columns = []
        for record in res:
            column = dict(
                name=record.Field,
                type=datatype.parse_sqltype(record.Type),
                nullable=record.Null == "YES",
                default=record.Default,
            )
            columns.append(column)
        return columns


    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        return {  # type: ignore  # pep-655 not supported
            "name": None,
            "constrained_columns": [],
        }

    def get_unique_constraints(
            self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw
    ) -> List[Dict[str, Any]]:
        return []

    def get_check_constraints(
            self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw
    ) -> List[Dict[str, Any]]:
        return []

    def get_foreign_keys(
            self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw
    ) -> List[ReflectedForeignKeyConstraint]:
        return []

    def get_primary_keys(self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw) -> List[str]:
        pk = self.get_pk_constraint(connection, table_name, schema)
        return pk.get("constrained_columns")  # type: ignore

    def get_indexes(self, connection, table_name, schema=None, **kw):
        return []

    def has_sequence(self, connection: Connection, sequence_name: str, schema: Optional[str] = None, **kw) -> bool:
        return False

    def get_sequence_names(self, connection: Connection, schema: Optional[str] = None, **kw) -> List[str]:
        return []

    def get_temp_view_names(self, connection: Connection, schema: Optional[str] = None, **kw) -> List[str]:
        return []

    def get_temp_table_names(self, connection: Connection, schema: Optional[str] = None, **kw) -> List[str]:
        return []

    def get_table_options(self, connection, table_name, schema=None, **kw):
        return {}

    def get_table_comment(self, connection: Connection, table_name: str, schema: Optional[str] = None, **kw) -> ReflectedTableComment:
        return ReflectedTableComment(text=None)


class DorisDialect_pymysql(DorisDialectMixin, MySQLDialect_pymysql): # type: ignore
    supports_statement_cache = False
    ddl_compiler = DorisDDLCompiler


class DorisDialect_mysqldb(DorisDialectMixin, MySQLDialect_mysqldb): # type: ignore
    supports_statement_cache = False
    ddl_compiler = DorisDDLCompiler


try:
    # using MySQLdb as default driver if available
    import MySQLdb
    DorisDialect = DorisDialect_mysqldb

except ModuleNotFoundError:
    DorisDialect = DorisDialect_pymysql
