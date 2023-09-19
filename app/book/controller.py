from pydantic import BaseModel

book_db = [
    {
        "title":"The C Programming",
        "price": 720
    },
    {
        "title":"Learn Python the Hard Way",
        "price": 870
    },
    {
        "title":"JavaScript: The Definitive Guide",
        "price": 1369
    },
    {
        "title":"Python for Data Analysis",
        "price": 1394
    },
    {
        "title":"Clean Code",
        "price": 1500
    },
]

class Book(BaseModel):
    title: str
    price: float

async def get_books():
    return book_db

async def get_book(book_id: int):
    return book_db[book_id-1]

async def create_book(book: Book):
    book_db.append(book.dict())
    return book_db[-1]

async def edit_book(book_id: int, book: Book):
    result = book.dict()
    book_db[book_id-1].update(result)
    return result

async def delete_book(book_id: int):
    book = book_db.pop(book_id-1)
    return book