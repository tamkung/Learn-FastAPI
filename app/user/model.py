from sqlalchemy import (create_engine,text)
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DATABASE_URL')

def select_users():
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("SELECT * FROM users;")
    result = conn.execute(sql_text).fetchall()
    
    conn.close()
    return result

def select_user(user_id):
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("SELECT * FROM users WHERE id = :id;")
    result = conn.execute(sql_text, {'id': user_id}).fetchone()
    
    conn.close()
    return result

def insert_user(user):
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("""
        INSERT INTO users (first_name, last_name, email, active)
        VALUES (:first_name, :last_name, :email, :active)
        RETURNING *;
    """)
    
    result = conn.execute(sql_text, {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'active': user.active
    }).fetchone()
    
    conn.commit()
    conn.close()
    return result

def update_user(user_id, user):
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("""
        UPDATE users
        SET first_name = :first_name, last_name = :last_name, email = :email, active = :active
        WHERE id = :id
        RETURNING *;
    """)
    
    result = conn.execute(sql_text, {
        'id': user_id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'active': user.active
    }).fetchone()
    
    conn.commit()
    conn.close()
    return result

def delete_user_by_id(user_id):
    conn = create_engine(DB_URL).connect()
    
    sql_text = text("""
        DELETE FROM users
        WHERE id = :id
        RETURNING *;
    """)
    
    result = conn.execute(sql_text, {
        'id': user_id
    }).fetchone()
    
    conn.commit()
    conn.close()
    return result