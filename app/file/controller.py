from fastapi import File, UploadFile
from typing import List
import pandas as pd  

async def up_img(file: UploadFile = File(...)):
    size = await file.read()
    return  { "File Name": file.filename, "size": len(size)}

async def up_multi_file(files: List[UploadFile] = File(...)):
    file = [
        {
            "File Name":file.filename, 
            "Size":len(await file.read())
        } for file in files]
    return  file

async def save_csv(file: UploadFile = File(...)):
    df = pd.read_csv(file.file)
    print("5555")
    df.to_csv("test.csv")
    return  { "File Name": file.filename, "size": len(df)}