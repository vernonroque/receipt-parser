# RapidAPI Setup Guide

## How It Works

RapidAPI acts as a **proxy gateway** — it does not inject a key into your backend directly. The flow is:

```
Consumer → RapidAPI (validates X-RapidAPI-Key) → Railway API (validates X-RapidAPI-Proxy-Secret)
```

- Consumers authenticate with RapidAPI using their own `X-RapidAPI-Key`
- RapidAPI forwards the request to your Railway URL and appends `X-RapidAPI-Proxy-Secret`
- Your backend validates that header to confirm the request came through RapidAPI

---

## Railway Setup (already done)

- `RAPIDAPI_PROXY_SECRET` is set as a Railway environment variable
- `app/services/auth_middleware.py` validates the `X-RapidAPI-Proxy-Secret` header
- Both RapidAPI proxy auth and direct Bearer token auth are supported simultaneously

---

## RapidAPI Provider Dashboard Steps

1. Go to [rapidapi.com](https://rapidapi.com) → **My APIs** → **Add New API**
2. Fill in your API name and description
3. Set the **Base URL** to your Railway service URL
   - Run `railway open` in the terminal to find it, or check your Railway dashboard
4. Find the **Proxy Secret** field and paste the secret:
   - Click the **Settings** tab at the top of your API dashboard
   - Scroll down to the **Gateway** section (may also appear as "Backend Configuration")
   - Find the field labeled **"X-RapidAPI-Proxy-Secret"** (newer UI may just call it "Proxy Secret")
   - Paste:
     ```
     74b5cf50-39fc-11f1-a3c9-6b26dff66c2a
     ```
   -The X-RAPIDAPI-Proxy-Secret was already there in Rapid API
   - Click **Save**
5. Add your endpoint:
   - Method: `POST`
   - Path: `/api/parse`
   - Parameter: `file` (form-data, binary — image/jpeg, image/png, or application/pdf)

---

## Pricing Plans (optional)

RapidAPI supports monetization via:
- **Free tier** — limited requests per month
- **Pay-per-use** — charge per API call
- **Subscriptions** — monthly plans with request quotas

Configure these in the **Pricing** tab of your API in the RapidAPI Provider dashboard.

---

## Verification

After listing the API, test it from the RapidAPI console:
- A successful request returns parsed receipt JSON with merchant info, line items, totals, etc.
- An unauthorized request (wrong or missing proxy secret) returns `401 Unauthorized`

To test the proxy secret directly against your Railway URL:
```bash
curl -X POST https://your-service.up.railway.app/api/parse \
  -H "X-RapidAPI-Proxy-Secret: eacd327f3c09792d3b77f5a8dfcb0f2a7cac36ac28530a531231ba998eeab792" \
  -F "file=@receipt.jpg"
```
