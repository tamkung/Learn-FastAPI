from fastapi import File, UploadFile
from typing import List
import pandas as pd 
import os
import base64

from app.file.model import insertImageBase64, selectImageBase64

async def up_img(file: UploadFile = File(...)):
    size = await file.read()
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    with open("uploads/"+file.filename, "wb") as f:
        f.write(size)
    
    if len(size) >= 1000000:
        size = str(round(len(size)/1000000, 2))+" MB"
    else:
        size = str(round(len(size)/1000, 2))+" KB"
    
    result = {
        "status": 200,
        "message": "Upload Success",
        "data": {
            "file_name": file.filename,
            "size": size
        }
    }
    return result

async def up_multi_file(files: List[UploadFile] = File(...)):
    file_data = []
    for file in files:
        size = await file.read()
        if not os.path.exists("uploads"):
            os.makedirs("uploads")
        with open("uploads/"+file.filename, "wb") as f:
            f.write(size)

        if len(size) >= 1000000:
            size = str(round(len(size)/1000000, 2))+" MB"
        else:
            size = str(round(len(size)/1000, 2))+" KB"
        
        file_data.append({
            "file_name": file.filename,
            "size": size
        })
    
    result = {
        "status": 200,
        "message": "Upload Success",
        "data": file_data
    }
    return result
