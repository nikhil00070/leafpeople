# Deploying the RevenueCat → subscriber-claim Cloud Function

This function lives in the website repo but deploys to **Firebase** (project `leafpeople-1c8d1`),
not Vercel. It's excluded from the Vercel upload via `.vercelignore`.

## One-time setup
1. **Upgrade Firebase to the Blaze (pay-as-you-go) plan** — Cloud Functions require it. Firebase
   Console → ⚙️ Usage and billing → Modify plan → Blaze. (Free tier is generous; this function is tiny.)
2. Install the CLI if needed: `npm i -g firebase-tools`, then `firebase login`.
3. Install deps: `cd functions && npm install && cd ..`

## Set the webhook auth secret
Pick a long random string (this is the shared secret RevenueCat will send):
```
firebase functions:secrets:set RC_WEBHOOK_AUTH
# paste the random string when prompted
```

## Deploy
```
firebase deploy --only functions
```
Copy the deployed URL it prints, e.g.
`https://us-central1-leafpeople-1c8d1.cloudfunctions.net/revenuecatWebhook`

## Point RevenueCat at it
RevenueCat → Integrations → Webhooks → Add:
- **URL:** the deployed function URL
- **Authorization header:** the SAME random string you set as `RC_WEBHOOK_AUTH`
Send a test event; the function returns 200 and logs the result (`firebase functions:log`).

## How it works
`event.app_user_id` is the Firebase UID (the app sets RevenueCat's App User ID = Firebase UID).
Purchase/renewal → `subscriber: true` custom claim; expiration/refund → `false`. The website's
edge middleware reads that claim. Also mirrored to Firestore `users/{uid}.subscriber`.
