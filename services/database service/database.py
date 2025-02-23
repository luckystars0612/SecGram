from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from message_broker import receive_from_scraper, send_to_bot_service

Base = declarative_base()

class ScrapedData(Base):
    __tablename__ = "scraped_data"
    id = Column(Integer, primary_key=True)
    source = Column(String)
    content = Column(String)

def store_data(data):
    engine = create_engine("sqlite:///data.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    new_data = ScrapedData(source=data["source"], content=data["content"])
    session.add(new_data)
    session.commit()
    send_to_bot_service(data)  # Forward to bot

def main():
    while True:
        data = receive_from_scraper()
        if data:
            store_data(data)

if __name__ == "__main__":
    main()