import os
from typing import Any
from typing import Dict
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth


class PayPalAPI:
    """
    A simple library for PayPal REST API to manage subscriptions with variable pricing.
    """

    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        self.base_url = "https://api.sandbox.paypal.com" if os.getenv("PAYPAL_SANDBOX", "True") == True else "https://api.paypal.com"
        self.access_token = self._get_access_token()
        self.headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        self.plan_id = ""

    def _make_request(self, url: str, method: str, **kwargs) -> Any:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _get_access_token(self) -> str:
        """
        Get an access token from PayPal API.

        Returns:
            str: Access token.
        """
        url = f"{self.base_url}/v1/oauth2/token"
        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials"}

        response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(self.client_id, self.client_secret))
        response.raise_for_status()
        return response.json()["access_token"]

    def subscription_exists(self, subscription_id: str) -> bool:
        """
        Check if a subscription exists in PayPal and return its details if it does.

        Args:
            subscription_id (str): Subscription ID.

        Returns:
            Optional[Dict[str, Bool]]: Subscription details if the subscription exists, False otherwise.
        """
        url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}"
        response = requests.get(url, headers=self.headers)
        if os.getenv("DEBUG", False):
            print(f"Check subscription {response.status_code} for {subscription_id}.")

        if response.status_code == 200:
            _response = response.json()
            self.plan_id = _response.get("plan_id")
            return _response
        elif response.status_code in [400, 404]:
            return False

        response.raise_for_status()
        return False

    def verify_paypal_response(self, token: str, subscription_id: str) -> Dict[str, Any]:
        """
        Verify PayPal response by checking the subscription details.

        Args:
            token (str): PayPal transaction token.
            subscription_id (str): PayPal Payer ID.

        Returns:
            Dict[str, Any]: Verification result.
        """
        if not token or not subscription_id:
            return {"status": "error", "message": "Token or subscription_id missing"}

        try:
            subscription_details = self.subscription_exists(token)
            if subscription_details == False:
                return {"status": "error", "message": "Subscription check failed"}

            if subscription_details.get("id") != token:
                return {"status": "error", "message": "Token does not match subscription"}

            subscriber_info = subscription_details.get("subscriber", {})
            stored_payer_id = subscriber_info.get("subscription_id")

            if stored_payer_id and stored_payer_id != subscription_id:
                return {"status": "error", "message": "subscription_id does not match"}

            status = subscription_details.get("status")
            if os.getenv("DEBUG", False):
                if status == "ACTIVE":
                    print(f"Subscription {token} is active.")
                elif status == "CANCELLED":
                    print(f"Subscription {token} is cancelled.")
                else:
                    print(f"Subscription {token} status: {status}.")

            return {
                "status": "success",
                "subscription_status": subscription_details.get("status"),
                "payer_email": subscriber_info.get("email_address")
            }
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"PayPal API error: {e}"}

    def create_product(self, name: str, description: str, type_: str = "SERVICE", category: str = "SOFTWARE") -> Dict[str, Any]:
        """
        Create a product for subscription.

        Args:
            name (str): Product name.
            description (str): Product description.
            type_ (str): Product type (default is "SERVICE").
            category (str): Product category (default is "SOFTWARE").

        Returns:
            Dict[str, Any]: API response with product details.
        """
        product_data = {
            "name": name,
            "description": description,
            "type": type_,
            "category": category
        }
        url = f"{self.base_url}/v1/catalogs/products"
        return self._make_request(url=url, method="POST", json=product_data, headers=self.headers)

    def create_plan(self, product_id: str, name: str, description: str, price: str, currency: str = "EUR") -> Dict[str, Any]:
        """
        Create a subscription plan.

        Args:
            product_id (str): Product ID.
            name (str): Plan name.
            description (str): Plan description.
            price (str): Plan price.
            currency (str): Currency code (default is "EUR").

        Returns:
            Dict[str, Any]: API response with plan details.
        """
        data = {
            "product_id": product_id,
            "name": name,
            "description": description,
            "billing_cycles": [
                {
                    "frequency": {"interval_unit": "WEEK", "interval_count": 1},
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "total_cycles": 0,
                    "pricing_scheme": {"fixed_price": {"value": price, "currency_code": currency}}
                }
            ],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 3
            }
        }
        url = f"{self.base_url}/v1/billing/plans"
        return self._make_request(url=url, method="POST", json=data, headers=self.headers)

    def update_subscription_price(self, subscription_id: str, new_price: str, currency: str = "EUR") -> Dict[str, Any]:
        """
        Update the subscription price.

        Args:
            subscription_id (str): Subscription ID.
            new_price (str): New subscription price.
            currency (str): Currency code (default is "EUR").

        Returns:
            Dict[str, Any]: API response with updated subscription details.
        """
        url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/revise"
        data = {
            "plan_id": self.plan_id,
            "billing_cycles": [
                {
                    "frequency": {"interval_unit": "WEEK", "interval_count": 1},
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "pricing_scheme": {"fixed_price": {"value": new_price, "currency_code": currency}}
                }
            ]
        }
        return self._make_request(url=url, method="POST", json=data, headers=self.headers)

    def create_subscription(self, plan_id: str, subscriber_email: str, return_url: str, cancel_url: str) -> Dict[str, Any]:
        """
        Create a new subscription.

        Args:
            plan_id (str): Plan ID.
            subscriber_email (str): Subscriber's email.
            return_url (str): URL to redirect to after the subscriber approves the subscription.
            cancel_url (str): URL to redirect to if the subscriber cancels the subscription.

        Returns:
            Dict[str, Any]: API response with subscription details.
        """
        data = {
            "plan_id": plan_id,
            "subscriber": {
                "email_address": subscriber_email
            },
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url
            }
        }

        url = f"{self.base_url}/v1/billing/subscriptions"
        return self._make_request(url=url, method="POST", json=data, headers=self.headers)

    def suspend_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Suspend a subscription by its ID.

        Args:
            subscription_id (str): Subscription ID to suspend.

        Returns:
            Dict[str, Any]: API response with suspension details.
        """
        url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/suspend"
        response = requests.post(url, headers=self.headers)

        if response.status_code == 204:
            return {"status": "success", "message": "Subscription suspended successfully"}
        elif response.status_code == 404:
            return {"status": "error", "message": "Subscription not found"}
        elif response.status_code == 422:
            return {"status": "error", "message": "Subscription already suspended"}
        else:
            response.raise_for_status()
            return {"status": "error", "message": "Failed to suspend subscription"}

    def create_or_update_subscription(self, identifier: str, name: str = "", description: str = "", price: Optional[str] = None, currency: str = "EUR", subscriber_email: Optional[str] = None, return_url: Optional[str] = None, cancel_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new subscription or update an existing one.

        Args:
            identifier (str): Unique identifier for subscription.
            name (Optional[str]): Name of the subscription product/plan.
            description (Optional[str]): Description of the subscription product/plan.
            price (Optional[str]): Price for the subscription.
            currency (str): Currency for the subscription (default is "USD").
            subscriber_email (Optional[str]): Subscriber email (required for new subscription).
            return_url (Optional[str]): Return URL for approval (required for new subscription).
            cancel_url (Optional[str]): Cancel URL (required for new subscription).

        Returns:
            Dict[str, Any]: API response with subscription details.
        """
        price = f"{price:.2f}"
        if not price or not subscriber_email or not return_url or not cancel_url:
            raise ValueError("Missing parameters required for subscription creation or update.")

        if self.subscription_exists(identifier) != False:
            updated_subscription = self.update_subscription_price(subscription_id=identifier, new_price=price, currency=currency)
            if os.getenv("DEBUG", False):
                print(f"Updated subscription {identifier} successfully.")
            return updated_subscription
        else:
            if os.getenv("DEBUG", False):
                print(f"Subscription {identifier} not found. Creating a new subscription.")
            product = self.create_product(name=name, description=description)
            plan = self.create_plan(product_id=product["id"], name=name, description=description, price=price, currency=currency)
            new_subscription = self.create_subscription(plan_id=plan["id"], subscriber_email=subscriber_email, return_url=return_url, cancel_url=cancel_url)
            return new_subscription
