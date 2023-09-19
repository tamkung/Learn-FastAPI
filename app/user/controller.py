from pydantic import BaseModel
from app.user.model import (
    select_users,
    select_user,
    insert_user,
    update_user,
    delete_user_by_id,
)

class User(BaseModel):
    first_name: str
    last_name: str
    email: str
    active: bool

async def get_users():
    try:
        data_query = select_users()
    except Exception as e:
        raise e
    
    result = []
    for item in data_query:
        result.append({
            "id": item.id,
            "first_name": item.first_name,
            "last_name": item.last_name,
            "email": item.email,
            "active": item.active,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        })
    
    status = "success"
    message = "User retrieved successfully"
    return {
        "status": status,
        "message": message,
        "data": result
    }

async def get_user(user_id: str):
    try:
        data_query = select_user(user_id)
    except Exception as e:
        raise e
    
    result = {
        "id": data_query.id,
        "first_name": data_query.first_name,
        "last_name": data_query.last_name,
        "email": data_query.email,
        "active": data_query.active,
        "created_at": data_query.created_at,
        "updated_at": data_query.updated_at
    }
    
    status = "success"
    message = "User retrieved successfully"
    return {
        "status": status,
        "message": message,
        "data": result
    }

async def create_user(user: User):
    try:
        data_query = insert_user(user)
    except Exception as e:
        raise e
    print(data_query)
    
    result = {
        "id": data_query.id,
        "first_name": data_query.first_name,
        "last_name": data_query.last_name,
        "email": data_query.email,
        "active": data_query.active,
        "created_at": data_query.created_at,
        "updated_at": data_query.updated_at
    }
    
    status = "success"
    message = "User created successfully"
    return {
        "status": status,
        "message": message,
        "data": result
    }

async def edit_user(user_id: str, user: User):
    try:
        data_query = update_user(user_id, user)
    except Exception as e:
        raise e
    
    result = {
        "id": data_query.id,
        "first_name": data_query.first_name,
        "last_name": data_query.last_name,
        "email": data_query.email,
        "active": data_query.active,
        "created_at": data_query.created_at,
        "updated_at": data_query.updated_at
    }
    
    status = "success"
    message = "User updated successfully"
    return {
        "status": status,
        "message": message,
        "data": result
    }

async def delete_user(user_id: str):
    try:
        data_query = delete_user_by_id(user_id)
    except Exception as e:
        raise e
    
    result = {
        "id": data_query.id,
        "first_name": data_query.first_name,
        "last_name": data_query.last_name,
        "email": data_query.email,
        "active": data_query.active,
        "created_at": data_query.created_at,
        "updated_at": data_query.updated_at
    }
    
    status = "success"
    message = "User deleted successfully"
    return {
        "status": status,
        "message": message,
        "data": result
    }