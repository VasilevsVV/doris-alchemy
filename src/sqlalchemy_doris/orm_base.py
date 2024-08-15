from typing import Any, Dict, Optional, Tuple
from sqlalchemy import Engine, MetaData, String, Table, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy_doris.dialect import HASH, RANDOM


METADATA = MetaData()


class DorisBase(DeclarativeBase):
    metadata = METADATA
    
    __table_args__:Dict[str, Any]
    __table_args__ = {
        'doris_properties': {"replication_allocation": "tag.location.default: 1"}
        }
    
    doris_distributed_by: HASH|RANDOM
    doris_properties: dict
    
    type_annotation_map = {
        str: String().with_variant(Text, 'doris')
    }
    
    
    @classmethod
    def __base_table_args(cls) -> dict:
        if '__table_args__' not in DorisBase.__dict__:
            return {}
        table_args = DorisBase.__dict__['__table_args__']
        if isinstance(table_args, dict):
            return table_args
        return {}
    
    
    def __init_subclass__(cls, **kw: Any) -> None:
        if cls.__table_args__ is None:
            cls.__table_args__ = {}
        super_table_args = cls.__base_table_args()
        cls.__table_args__.update(super_table_args)
        assert hasattr(cls, 'doris_distributed_by') or 'doris_distributed_by' in cls.__table_args__,\
            'You must define distributed_by for orm model. Via doris_distributed_by attribute, or __table_args__'
        if hasattr(cls, 'doris_distributed_by'):
            cls.__table_args__['doris_distributed_by'] = getattr(cls, 'doris_distributed_by')
        super().__init_subclass__()


    def __repr__(self) -> str:
        d = self.__dict__
        if '_sa_instance_state' in d:
            d.pop('_sa_instance_state')
        return f'{self.__class__.__name__}({d})'
    
    @classmethod
    def get_table(cls) -> Optional[Table]:
        tname = cls.__tablename__
        schema = cls.__table_args__.get('schema')
        if schema:
            tname = f'{schema}.{tname}'
        __mtd = cls.metadata
        if tname in __mtd.tables:
            return __mtd.tables[tname]
        return None
    
    @classmethod
    def create(cls, eng: Engine) -> None:
        t = cls.get_table()
        assert t is not None, f'Table {cls.__tablename__} is missing from Metadata!!'
        t.create(eng)
    
    
    @classmethod
    def drop(cls, eng: Engine) -> None:
        t = cls.get_table()
        assert t is not None, f'Table {cls.__tablename__} is missing from Metadata!!'
        t.drop(eng)