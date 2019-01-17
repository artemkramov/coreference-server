from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer

Base = declarative_base()


class Word(Base):
    __tablename__ = "word"
    ID = Column(Integer, primary_key=True)
    RawText = Column(String)
    DocumentID = Column(String)
    WordOrder = Column(Integer)
    PartOfSpeech = Column(String)
    Lemmatized = Column(String)
    IsPlural = Column(Integer)
    Gender = Column(String)
    EntityID = Column(String)
    RawTagString = Column(String)
    CoreferenceGroupID = Column(String)
