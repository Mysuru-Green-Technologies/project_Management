# create_uploads_folder.py
import os

if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')
    print("Uploads folder created successfully")
else:
    print("Uploads folder already exists")