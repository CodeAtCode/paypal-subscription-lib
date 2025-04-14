# PayPal Subscription (Python) Library
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)   

This Python library allows you to interact with the PayPal REST API to manage subscriptions with variable pricing. It includes functionality for creating, updating, suspend and verifying subscriptions, as well as managing products and plans.

Note: When the subscription is approved the user receive an email from Paypal to inform that a new automatic payment is approved, and of course one about the payment itself.

## Addendum

To simplify and avoid to use also the PayPal SDK this library implements methods like `create_order` and `verify_payment` so can be used also for single payments.

## Usage Example

This example demonstrates how to create a CLI app that creates or updates a PayPal subscription and a FastAPI server with a webhook to save the PayPal identifier in an SQLite database. This setup allows you to check if a plan exists and in case update it automatically.

### Dependencies

Install the required dependencies:

```bash
pip install fastapi uvicorn requests
```

### Environment

Set up your environment variables in a .env file:

```
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_client_secret
PAYPAL_SANDBOX=True  # Set to False for production
```

### Payment script

The payment script creates or updates a subscription and sends an email with a PayPal approval link to the user.  
This script can be extended to use other library methods, such as `suspend_subscription`, to manage subscriptions further.

`payment_request.py`

```python
#!/usr/bin/env python
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from paypal_subscription import PayPalAPI

paypal_api = PayPalAPI()

# Define subscription details
identifier = ""
name = "Subscription Name"
description = "Subscription Description"
price = "10.00"
currency = "EUR"
subscriber_email = "user@example.com"
return_url = "http://localhost:8000/return_url/"
cancel_url = "http://localhost:8000/cancel_url/"

# Connect to SQLite database
conn = sqlite3.connect('subscriptions.db')
cursor = conn.cursor()

# Retrieve identifier from the database (assuming it's stored there)
cursor.execute("SELECT id FROM subscriptions WHERE email = ?", (subscriber_email,))
result = cursor.fetchone()

if result:
    identifier = result[0]
else:
    raise ValueError("Subscription identifier not found in the database.")

# Create or update the subscription
subscription = paypal_api.create_or_update_subscription(
    identifier=identifier,
    name=name,
    description=description,
    price=price,
    currency=currency,
    subscriber_email=subscriber_email,
    return_url=return_url,
    cancel_url=cancel_url
)

# Get the approval link
approval_link = subscription['links'][0]['href']

# Send email with the approval link
def send_email(to_address, subject, body):
    from_address = "your_email@example.com"
    password = "your_email_password"

    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.example.com', 587)
    server.starttls()
    server.login(from_address, password)
    text = msg.as_string()
    server.sendmail(from_address, to_address, text)
    server.quit()

# Email details
subject = "Approve Your Subscription"
body = f"Please click the following link to approve your subscription: {approval_link}"

# Send the email
send_email(subscriber_email, subject, body)

print("Subscription approval link sent to the subscriber's email.")
```

### FastAPI server

The FastAPI server handles the return URL webhook to save the subscription identifier in the SQLite database.  
This server can be extended to save additional payment details.

```python
from fastapi import FastAPI, Request
from paypal_subscription import PayPalAPI
import sqlite3

app = FastAPI()
paypal_api = PayPalAPI()

# Set up SQLite database
conn = sqlite3.connect('subscriptions.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT,
        price TEXT,
        email TEXT,
        status TEXT
    )
''')
conn.commit()

def save_subscription_to_db(subscription_id: str, name: str, description: str, price: str, email: str, status: str):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO subscriptions (id, name, description, price, email, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (subscription_id, name, description, price, email, status))
    conn.commit()

@app.post("/return_url/")
async def return_url(request: Request):
    data = await request.json()
    subscription_id = data.get("subscription_id")
    subscription_details = paypal_api.verify_subscription(subscription_id=subscription_id, payer_id="email")

    if subscription_details["status"] == "success":
        save_subscription_to_db(
            subscription_id=subscription_id,
            name=subscription_details["name"],
            description=subscription_details["description"],
            price=subscription_details["price"],
            email=subscription_details["payer_email"],
            status=subscription_details["subscription_status"]
        )
        return {"message": "Subscription saved successfully"}
    else:
        return {"message": "Subscription verification failed"}
```

### Run

Execute the payment request:

```
payment_request.py
```

Run the web server:
```
uvicorn main\:app --reload

```
