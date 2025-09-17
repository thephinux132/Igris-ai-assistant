# Family Gift Registry

A lightweight, single-page gift registry crafted especially for organizing thoughtful surprises for my wife and kids.

## Features
- ✨ Curated inspiration section with filters for wife, kids, and gift types
- ✅ Interactive wishlist that tracks purchased items, budgets, and notes
- ➕ Form to add personalized gift ideas (saved locally in the browser)
- 🗓️ Planner timeline with upcoming celebrations and automatic countdown

## Getting started
This is a static website. To view it, open `index.html` in your browser or serve the folder with any static file server. For example:

```bash
python -m http.server --directory web/gift_registry 8000
```

Then visit [http://localhost:8000](http://localhost:8000) in your browser.

Your custom gifts are stored in `localStorage`, so they stay on the device you're using. Use the **Reset to starter list** button to restore the original ideas.
