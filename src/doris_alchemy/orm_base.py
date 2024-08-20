from typing import Any, Dict, Optional, Sequence, Tuple
from sqlalchemy import Engine, MetaData, String, Table, Text
from sqlalchemy.orm import DeclarativeBase
from doris_alchemy.datatype import HASH, RANGE
from doris_alchemy.datatype import RANDOM


class DorisBaseMixin:
    __table_args__:Dict[str, Any]|Tuple
    __table_args__ = {
        'doris_properties': {"replication_allocation": "tag.location.default: 1"}
        }
    __tablename__: str
    
    metadata: MetaData

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


    @classmethod
    def __current_table_args(cls) -> dict:
        if cls.__table_args__ is None:
            return {}
        if isinstance(cls.__table_args__, Dict):
            return cls.__table_args__
        if isinstance(cls.__table_args__, Tuple):
            d = cls.__table_args__[-1]
            if isinstance(d, dict):
                return d
            return {}
        raise Exception(f'{cls.__name__} __table_args__ must be dict or tuple.')


    @classmethod
    def __update_table_args(cls, args: dict) -> None:
        if cls.__table_args__ is None:
            cls.__table_args__ = args
        if isinstance(cls.__table_args__, dict):
            cls.__table_args__.update(args)
        if isinstance(cls.__table_args__, tuple):
            d = cls.__table_args__[-1]
            if isinstance(d, dict):
                d.update(args)
                cls.__table_args__ = cls.__table_args__[:-1] + (d,)
            else:
                cls.__table_args__ = cls.__table_args__ + (args,)


    def __init_subclass__(cls, **kw: Any) -> None:
        # Convenient fix for Mapped[str] type annotation
        # Will automatically map Mapped[str] to Text, instead of String() (which leads to an error)
        cls.type_annotation_map = {
            str: String().with_variant(Text, 'doris')
        }

        # Fixing replication_allocation automatically (if you dont have > 3 backend instances.)
        current_args = cls.__current_table_args()
        if 'doris_properties' not in current_args:
            current_args['doris_properties'] = {"replication_allocation": "tag.location.default: 1"}
        else:
            prop = current_args['doris_properties']
            if 'replication_allocation' not in prop:
                prop['replication_allocation'] = "tag.location.default: 1"
                current_args['doris_properties'] = prop

        # Updating DORIS specific arguments from class attributes.
        if hasattr(cls, 'doris_distributed_by'):
            current_args['doris_distributed_by'] = getattr(cls, 'doris_distributed_by')
        if hasattr(cls, 'doris_partition_by'):
            current_args['doris_partition_by'] = getattr(cls, 'doris_partition_by')
        if hasattr(cls, 'doris_unique_key'):
            current_args['doris_unique_key'] = getattr(cls, 'doris_unique_key')
        if hasattr(cls, 'doris_autogen_primary_key') and cls.doris_autogen_primary_key:
            current_args['doris_autogen_primary_key'] = True
        cls.__update_table_args(current_args)

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
        args = cls.__current_table_args()
        schema = args.get('schema')
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


METADATA = MetaData()

class DorisBase(DorisBaseMixin, DeclarativeBase):
    metadata = METADATA