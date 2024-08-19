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
from abc import ABC, abstractmethod
import logging
import re
from typing import Iterable, Optional, List, Any, Sequence, Type, Dict
from sqlalchemy import Numeric, Integer, Float
from sqlalchemy.sql import sqltypes
from sqlalchemy.sql.type_api import TypeEngine

from doris_alchemy.util import ensure_sequence
from doris_alchemy.util import join_args_with_quote

logger = logging.getLogger(__name__)


class TINYINT(Integer):  # pylint: disable=no-init
    __visit_name__ = "TINYINT"


class LARGEINT(Integer):  # pylint: disable=no-init
    __visit_name__ = "LARGEINT"


class DOUBLE(Float):  # pylint: disable=no-init
    __visit_name__ = "DOUBLE"


class HLL(Numeric):  # pylint: disable=no-init
    __visit_name__ = "HLL"


class BITMAP(Numeric):  # pylint: disable=no-init
    __visit_name__ = "BITMAP"


class QUANTILE_STATE(Numeric):  # pylint: disable=no-init
    __visit_name__ = "QUANTILE_STATE"

class AGG_STATE(Numeric):  # pylint: disable=no-init
    __visit_name__ = "AGG_STATE"

class ARRAY(TypeEngine):  # pylint: disable=no-init
    __visit_name__ = "ARRAY"

    @TypeEngine.python_type.getter
    def python_type(self) -> Optional[Type[List[Any]]]:
        return list


class MAP(TypeEngine):  # pylint: disable=no-init
    __visit_name__ = "MAP"

    @TypeEngine.python_type.getter
    def python_type(self) -> Optional[Type[Dict[Any, Any]]]:
        return dict


class STRUCT(TypeEngine):  # pylint: disable=no-init
    __visit_name__ = "STRUCT"

    @TypeEngine.python_type.getter
    def python_type(self) -> Optional[Type[Any]]:
        return None


_type_map = {
    # === Boolean ===
    "boolean": sqltypes.BOOLEAN,
    # === Integer ===
    "tinyint": sqltypes.SMALLINT,
    "smallint": sqltypes.SMALLINT,
    "int": sqltypes.INTEGER,
    "bigint": sqltypes.BIGINT,
    "largeint": LARGEINT,
    # === Floating-point ===
    "float": sqltypes.FLOAT,
    "double": DOUBLE,
    # === Fixed-precision ===
    "decimal": sqltypes.DECIMAL,
    "decimalv3": sqltypes.DECIMAL,
    # === String ===
    "varchar": sqltypes.VARCHAR,
    "char": sqltypes.CHAR,
    "json": sqltypes.JSON,
    "jsonb": sqltypes.JSON,
    "text": sqltypes.TEXT,
    "string": sqltypes.String,
    # === Date and time ===
    "date": sqltypes.DATE,
    "datev2": sqltypes.DATE,
    "datetime": sqltypes.DATETIME,
    "datetimev2": sqltypes.DATETIME,
    # === Structural ===
    'array': ARRAY,
    'map': MAP,
    'struct': STRUCT,
    'hll': HLL,
    'quantile_state': QUANTILE_STATE,
    'bitmap': BITMAP,
    'agg_state': AGG_STATE,
}


def parse_sqltype(type_str: str) -> TypeEngine:
    type_str = type_str.strip().lower()
    match = re.match(r"^(?P<type>\w+)\s*(?:\((?P<options>.*)\))?", type_str)
    if not match:
        logger.warning(f"Could not parse type name '{type_str}'")
        return sqltypes.NULLTYPE
    type_name = match.group("type")

    if type_name not in _type_map:
        logger.warning(f"Did not recognize type '{type_name}'")
        return sqltypes.NULLTYPE
    type_class = _type_map[type_name]
    return type_class()


class RenderedMixin(ABC):
    @abstractmethod
    def render(self) -> str:
        pass


class HASH(RenderedMixin):
    def __init__(self, keys: Sequence[str]|str, buckets: Optional[int] = None):
        self.keys: Iterable[str] = ensure_sequence(keys)
        self.buckets = buckets or 'auto'

    def render(self) -> str:
        keys_str = 'HASH' + join_args_with_quote(*self.keys)
        buckets_str = f'BUCKETS {self.buckets}'
        return keys_str + ' ' + buckets_str


class RANGE(RenderedMixin):
    def __init__(self, keys: Sequence[str]|str, part_info: Sequence = tuple()):
        self.keys: Iterable[str] = ensure_sequence(keys)
        self.part_info = ensure_sequence(part_info)

    def render(self) -> str:
        keys_str = 'RANGE' + join_args_with_quote(*self.keys)
        if len(self.part_info) > 0:
            part_str = ',\n    '.join([str(val) for val in self.part_info])
            part_str = '(\n    ' + part_str + '\n)'
        else:
            part_str = '()'
        return keys_str + ' ' + part_str


class RANDOM(RenderedMixin):
    def __init__(self, buckets: Optional[int]=None):
        self.buckets = buckets or 'auto'

    def render(self) -> str:
        keys_str = 'RANDOM'
        keys_str += f' BUCKETS {self.buckets}'
        return keys_str
