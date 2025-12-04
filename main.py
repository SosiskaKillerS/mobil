from http.client import HTTPException

from fastapi import FastAPI
from typing import Literal
from pydantic import BaseModel

app = FastAPI(
    title="FanMonet fake billing api",
    description='Fake billing for our uni mobile application'
)

SubscriptionStatusLiteral = Literal['none', 'pending', 'active']

class SubscriptionStatus(BaseModel):
    status: SubscriptionStatusLiteral

class CreatePaymentResponse(BaseModel):
    payment_id: int
    subscription_status: SubscriptionStatus

class FakeWebhookBody(BaseModel):
    payment_id: int

subscription_store = {
    'user1': SubscriptionStatus(status='none')
}

payments_store: dict[int, dict] = {}
next_payment_id = 1

def get_current_username()->str:
    return 'user1'

@app.get('/subscription', response_model=SubscriptionStatus)
def get_subscription_status() -> SubscriptionStatus:
    username = get_current_username()
    return subscription_store[username]

@app.post('/payments/create', response_model=CreatePaymentResponse)
def create_payment() -> CreatePaymentResponse:
    global next_payment_id

    username = get_current_username()
    sub = subscription_store[username]

    if sub.status == 'active':
        return CreatePaymentResponse(
            payment_id=0,
            subscription_status=sub.status,
        )
    payment_id = next_payment_id
    next_payment_id += 1
    payments_store[payment_id] ={
        'id': payment_id,
        'user': username,
        'status': 'pending',
    }
    subscription_store[username] = SubscriptionStatus(status='pending')
    return CreatePaymentResponse(
        payment_id=payment_id,
        subscription_status='pending',
    )

@app.post('/webhooks/fake_payment', response_model=SubscriptionStatus)
def fake_payment_webhook(body: FakeWebhookBody) -> SubscriptionStatus:
    payment = payments_store.get(body.payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail = 'Payment not found')
    payment['status']='success'
    username = payment['user']
    subscription_store[username] = SubscriptionStatus(status='active')
    return subscription_store[username]
