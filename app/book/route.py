from fastapi import APIRouter
from app.book.controller import get_books, get_book, create_book, edit_book, delete_book

router = APIRouter(
    prefix="/book",
    tags=["Book"],
    responses={404: {"message": "Not found"}}
)

router.add_api_route(methods=["GET"], path="/", endpoint=get_books)
router.add_api_route(methods=["GET"], path="/{book_id}", endpoint=get_book)
router.add_api_route(methods=["POST"], path="/", endpoint=create_book)
router.add_api_route(methods=["PUT"], path="/{book_id}", endpoint=edit_book)
router.add_api_route(methods=["DELETE"], path="/{book_id}", endpoint=delete_book)
