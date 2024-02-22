from sqlalchemy import (create_engine,text)
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DATABASE_URL')

def insertImageBase64(name, data):
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("""
        INSERT INTO test (name, data)
        VALUES (:name, :data)
        RETURNING *;
    """)
    
    result = conn.execute(sql_text, {
        'name': name,
        'data': data
    }).fetchone()
    
    conn.commit()
    conn.close()
    return result

def selectImageBase64():
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("SELECT * FROM test;")
    result = conn.execute(sql_text).fetchall()
    
    conn.close()
    return result
