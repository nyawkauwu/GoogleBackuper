from os import path, walk, makedirs

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from progress.bar import IncrementalBar

import zipfile
from datetime import datetime
import subprocess
from shutil import rmtree

folder_name = "GoogleBackuper"
folder_id = ""  # Will be filled

SCOPES = ["https://www.googleapis.com/auth/drive.metadata",
          'https://www.googleapis.com/auth/drive.file']


def auth_service():
    creds = None
    if path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    try:
        service = build("drive", "v3", credentials=creds)
        global folder_id
        if not folder_id:
            results = (
                service.files()
                .list(pageSize=1,
                      q=f"name = '{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed = false",
                      spaces="drive",
                      fields="nextPageToken, files(id)")
                .execute()
            )
            items = results.get("files", [])
            if not items:
                print(f"Creating {folder_name} folder...")
                file_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                }
                file = service.files().create(body=file_metadata, fields="id").execute()
                folder_id = file.get("id")
            else:
                folder_id = items[0]['id']
            print(f"Folder ID: {folder_id}")
        return service
    except HttpError as error:
        print(f"An error occurred: {error}")


def upload_file(fpath, name=False):
    if not name:
        name = path.basename(fpath)
    print(f"Uploading {name} to Google Drive...")
    try:
        service = auth_service()
        file_metadata = {"name": name, "parents": [folder_id]}
        media = MediaFileUpload(fpath)
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        print(f'File ID: {file.get("id")}')

    except HttpError as error:
        print(f"An error occurred: {error}")
        file = None

    return file.get("id")


def get_files():
    service = auth_service()
    results = (
        service.files()
        .list(pageSize=10, fields="nextPageToken, files(id, name, mimeType)")
        .execute()
    )
    items = results.get("files", [])
    if not items:
        print("No files found.")
        return
    print("Files:")
    for item in items:
        print(f"{item['name']} ({item['id']}, {item['mimeType']})")


def create_backup(fpath, name, additional_files=[], ignore=[]):
    dt = datetime.now()
    strdate = dt.strftime("%d-%m-%Y-%H:%M")
    fname = f"./temp/{name}-{strdate}.zip"
    files_counter = len(additional_files)
    for root, dirs, files in walk(fpath):
        for i in ignore:
            if i in dirs:
                dirs.remove(i)
        for file in files:
            if file not in ignore:
                files_counter += 1
    bar = IncrementalBar('Creating ZIP', max=files_counter)
    with zipfile.ZipFile(fname, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in walk(fpath):
            for i in ignore:
                if i in dirs:
                    dirs.remove(i)
            for file in files:
                if file not in ignore:
                    zipf.write(path.join(root, file),
                               path.relpath(path.join(root, file),
                                            path.join(fpath, '..')))
                    bar.next()
        for i in additional_files:
            zipf.write(i, path.basename(i))
            bar.next()
    print()
    return fname


def pg_backup(user, password, database, filename, host="localhost", port=5432):
    print(f"Backing up {filename}...")
    cmd = f"pg_dump -U {user} {database} -p {port} -h {host}"
    with open(f"./temp/{filename}", 'w') as f:
        subprocess.call(cmd.split(), stdout=f, env={"PGPASSWORD": password})

    return f"./temp/{filename}"


def clean_up():
    print(f"Cleaning up temp directory...")
    rmtree('./temp')


def main():
    if not path.exists('./temp'):
        makedirs('temp')
    # Put your code here
    # postgres_backup = pg_backup('postgres', 'password', 'database', 'database.sql')
    # backup = create_backup('../myproject/', 'myproject', [postgres_backup])
    # upload_file(backup)
    clean_up()
    print("Completed!")


if __name__ == "__main__":
    main()
