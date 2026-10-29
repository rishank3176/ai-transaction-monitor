"""
Customer login and customer-specific endpoints.

Every /customer/* endpoint takes the customer from the session token. The customer
ID is never accepted from the request, so a customer can only ever read or create
their own transactions.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.pipeline import process_transaction
from data import customers

router = APIRouter()

try:                                  
    customers.ensure_schema()
    customers.seed_demo_users()
except Exception as exc:               
    print(f'[auth] account setup skipped: {exc}')


def current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Please log in')
    user = customers.user_from_token(authorization[7:])
    if user is None:
        raise HTTPException(401, 'Session expired, please log in again')
    return user


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=200)


class CustomerTransaction(BaseModel):
    type: Literal['PAYMENT', 'TRANSFER', 'CASH_OUT']
    amount: float = Field(gt=0)


@router.post('/auth/register')
def register(body: RegisterRequest):
    try:
        created = customers.create_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {'ok': True, 'customer_id': created['customer_id']}


@router.post('/auth/login')
def login(body: LoginRequest):
    user = customers.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(401, 'Wrong username or password')
    token = customers.create_session(user['username'])
    return {'token': token, 'username': user['username'], 'customer_id': user['customer_id']}


@router.post('/auth/logout')
def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith('Bearer '):
        customers.delete_session(authorization[7:])
    return {'ok': True}


@router.get('/customer/me')
def me(user: dict = Depends(current_user)):
    return customers.customer_summary(user)


@router.get('/customer/history')
def history(user: dict = Depends(current_user)):
    return customers.customer_history(user['customer_id'])


@router.post('/customer/transaction')
def customer_transaction(body: CustomerTransaction, user: dict = Depends(current_user)):
    try:
        txn_id = customers.submit_portal_transaction(user, body.type, body.amount)
    except customers.InsufficientFunds as exc:
        raise HTTPException(400, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    result = process_transaction(txn_id)
    if result is None:
        raise HTTPException(500, 'Transaction could not be processed')
    result['available_balance'] = customers.available_balance(
        user['customer_id'], user['opening_balance'])
    return result