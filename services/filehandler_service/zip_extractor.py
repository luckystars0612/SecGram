from zipfile import ZipFile
from message_broker import send_to_bot_service

def extract_zip(file_path):
    with ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall("extracted/")
        data = {"source": file_path, "content": "Files extracted"}
        send_to_bot_service(data)

if __name__ == "__main__":
    extract_zip("example.zip")