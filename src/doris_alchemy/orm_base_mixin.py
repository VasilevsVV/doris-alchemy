from typing import Any, Dict, Optional, Sequence, Tuple
from sqlalchemy import Engine, MetaData, String, Table, Text
from sqlalchemy.orm import DeclarativeBase
from doris_alchemy.datatype import HASH, RANGE
from doris_alchemy.datatype import RANDOM
from doris_alchemy.orm_base import METADATA


class DorisBaseMixin:
    metadata = METADATA
    
    __table_args__:Dict[str, Any]
    __table_args__ = {
        'doris_properties': {"replication_allocation": "tag.location.default: 1"}
        }
    __tablename__: str
    
    doris_distributed_by: HASH|RANDOM
    doris_partition_by: HASH|RANDOM|RANGE
    doris_properties: dict
    doris_autogen_primary_key: bool
    doris_unique_key: str|Sequence[str]
    doris_duplicate_key: str|Sequence[str]
    doris_aggregate_key: str|Sequence[str]
    
    type_annotation_map = {
        str: String().with_variant(Text, 'doris')
    }
    
    
    def __init_subclass__(cls, **kw: Any) -> None:
        cls.type_annotation_map = {
            str: String().with_variant(Text, 'doris')
        }
        
        if cls.__table_args__ is None:
            cls.__table_args__ = {}
        # super_table_args = cls.__base_table_args()
        # cls.__table_args__.update(super_table_args)
        if hasattr(cls, 'doris_distributed_by'):
            cls.__table_args__['doris_distributed_by'] = getattr(cls, 'doris_distributed_by')
        if hasattr(cls, 'doris_partition_by'):
            cls.__table_args__['doris_partition_by'] = getattr(cls, 'doris_partition_by')
        if hasattr(cls, 'doris_unique_key'):
            cls.__table_args__['doris_unique_key'] = getattr(cls, 'doris_unique_key')
        if hasattr(cls, 'doris_autogen_primary_key') and cls.doris_autogen_primary_key:
            cls.__table_args__['doris_autogen_primary_key'] = True
            
        super().__init_subclass__()
    
    
    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__
        if '_sa_instance_state' in d:
            d.pop('_sa_instance_state')
        return d

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}{self.to_dict()}'
    
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