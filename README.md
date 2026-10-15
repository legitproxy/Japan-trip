# Two Weeks in Japan

The kawaii trip itinerary, rebuilt every hour from TripIt.

- **Change a plan:** edit it in TripIt. The page picks it up within about an hour.
- **Refresh now:** Actions tab → "Update trip page from TripIt" → **Run workflow**.
- **Nicer names, little descriptions, extra rows** (like "Shopping spree"): `extras.json`.
- **Page design:** `template.html`.

The TripIt feed link is stored as the repository secret `TRIPIT_FEED_URL` and is never published.
Only plan names and times appear on the page, never addresses, phone numbers or confirmation details.
