# Apache Doris Dialect for SQLAlchemy

This is a fork of [sqlalchemy-doris](https://github.com/actcwlf/sqlalchemy-doris) project.
Which is in turn - a fork of [pydoris](https://pypi.org/project/pydoris/1.0.1/)

This implementation fixes a bunch of issues with typing. And adds support for sqlalchemy ORM.

## Features
* support SQLAlchemy 2.
* support pymysql and mysqlclient as driver.
* support SQLAlchemy table creation
* support for SQLALchemy ORM
* convenient DorisBase class for declaring ORM models

## Installation
Use
```bash
pip install doris-alchemy[pymysql]
```
for pymysql.

Or

```bash
pip install doris-alchemy[mysqldb]
```
for mysqlclient.

Note doris-alchemy uses pymysql as default connector for compatibility. 
If both pymysql and mysqlclient are installed, mysqlclient is preferred.


## Usage
```python

from sqlalchemy import create_engine

engine = create_engine(f"doris+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")
# or
engine = create_engine(f"doris+mysqldb://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")

```

## Create Table (Imperative style)
```python
import sqlalchemy as sa
from sqlalchemy import create_engine
from doris_alchemy import datatype
from doris_alchemy import HASH, RANGE

engine = create_engine(f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")


metadata_obj = sa.MetaData()
table = Table(
    'dummy_table',
    METADATA,
    Column('id', Integer, primary_key=True),
    Column('name', String(64), nullable=False),
    Column('description', Text),
    Column('date', DateTime),
    
    doris_unique_key=('id'),
    doris_partition_by=RANGE('id'),
    doris_distributed_by=HASH('id'),
    doris_properties={"replication_allocation": "tag.location.default: 1"},
)

table.create(engine)

```

SQL is
```sql
CREATE TABLE dummy_table (
        id INTEGER NOT NULL, 
        name VARCHAR(64) NOT NULL, 
        description TEXT, 
        date DATETIME
)
UNIQUE KEY (`id`)
PARTITION BY RANGE(`id`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS auto
PROPERTIES (
    "replication_allocation" = "tag.location.default: 1"
)
```

## Create Table (Declarative style / ORM)
```python
from sqlalchemy import create_engine
from doris_alchemy import datatype, DorisBase
from doris_alchemy import HASH, RANGE

engine = create_engine(f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")

class Dummy(DorisBase):
    __tablename__ = 'dummy_two'
    
    id:             Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name:           Mapped[str] = mapped_column(String(127))
    description:    Mapped[str]
    date:           Mapped[datetime]
    
    __table_args__ = {
        'doris_properties': {"replication_allocation": "tag.location.default: 1"}
        }
    doris_unique_key = 'id'
    doris_distributed_by = HASH('id')
    doris_partition_by = RANGE('id')


DorisBase.metadata.create_all(engine)
```
SQL is 
```sql
CREATE TABLE dummy_two (
        id BIGINT NOT NULL, 
        name VARCHAR(127) NOT NULL, 
        description TEXT NOT NULL, 
        date DATETIME NOT NULL
)
UNIQUE KEY (`id`)
PARTITION BY RANGE(`id`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS auto
PROPERTIES (
    "replication_allocation" = "tag.location.default: 1"
)
```

### Insertin and selecting

```python
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, create_engine
from datetime import datetime

engine = create_engine(f"doris+mysqldb://{USER}:{PWD}@{HOST}:{PORT}/{DB}")

row = {
        'id': 0,
        'name': 'Airbus',
        'description': 'Construction bureau',
        'date': datetime(2024, 2, 10)
    }
    
with Session(engine) as s:
    q = insert(Dummy).values([row])
    s.execute(q)
    sel = select(Dummy)
    res = s.execute(sel)
    print(list(res))
```