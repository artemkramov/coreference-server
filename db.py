from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


engine = create_engine('mysql://root@localhost/coreference')
session = sessionmaker()
session.configure(bind=engine)
declarative_base().metadata.create_all(engine)
