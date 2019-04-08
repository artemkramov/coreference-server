from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer

# Set base class for creating of the model
Base = declarative_base()


# Class which represents 'Word' model in database
class DBText(Base):
    __tablename__ = "text"
    ID = Column(Integer, primary_key=True)
    RawText = Column(String)
    DocumentID = Column(String)
