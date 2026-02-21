# 📧 Email Countdown Timer — No Branding, Free Forever

A self-hosted, timezone-aware animated GIF countdown timer for emails.
Deploy on Vercel in under 5 minutes. **Zero dependencies. Zero branding.**

---

## 🚀 Deploy to Vercel (Step-by-Step)

### Step 1 — Create a GitHub Repo
1. Go to **github.com** → click **New repository**
2. Name it `email-countdown`
3. Click **Create repository**
4. Upload all the files from this folder (drag & drop works)

### Step 2 — Deploy on Vercel
1. Go to **vercel.com** → Sign up free (use your GitHub account)
2. Click **"Add New Project"**
3. Select your `email-countdown` GitHub repo
4. Click **Deploy** — that's it! ✅

Vercel gives you a free URL like:
```
https://email-countdown-abc123.vercel.app
```

---

## 📌 How to Use in Mailchimp

Paste this `<img>` tag into a **Code block** in your Mailchimp email:

```html
<img src="https://YOUR-VERCEL-URL.vercel.app/?end=2026-03-15T23:59:59+05:30&tz=330" 
     width="320" height="90" alt="Offer ends soon!" style="display:block;margin:auto;" />
```

### URL Parameters

| Parameter | What it does | Example |
|-----------|-------------|---------|
| `end` | Your deadline (ISO format) | `2026-03-15T23:59:59+05:30` |
| `tz` | Recipient timezone offset in minutes | `330` for India (+5:30), `0` for UTC, `-300` for EST |
| `bg` | Background color (hex) | `1e1e1e` (dark) or `ffffff` (white) |
| `fg` | Number text color (hex) | `ffffff` |
| `label` | Label text color (hex) | `b4b4b4` |
| `box` | Box background color (hex) | `323232` |
| `accent` | Border & expired text color (hex) | `ff5050` (red) |

---

## 🌍 Timezone-Aware Setup (Per Recipient)

Since email clients can't auto-detect timezone, the best approach is to
**use Mailchimp merge tags** to pass the recipient's timezone offset.

If you store timezone offset in your audience as a custom field called `TZOFFSET`:

```html
<img src="https://YOUR-URL.vercel.app/?end=2026-03-15T23:59:59Z&tz=*|TZOFFSET|*" />
```

If you don't have per-recipient timezone data, just hardcode the offset
for your primary audience's timezone. Example for India (IST = +330 min):

```html
<img src="https://YOUR-URL.vercel.app/?end=2026-03-15T23:59:59Z&tz=330" />
```

---

## 🎨 Color Customization Examples

**White / Clean style:**
```
?bg=ffffff&fg=222222&label=888888&box=f5f5f5&accent=e63946
```

**Dark red urgency style:**
```
?bg=1a0000&fg=ffffff&label=ff9999&box=2d0000&accent=ff3333
```

**Brand blue:**
```
?bg=0a1628&fg=ffffff&label=90b4e0&box=122040&accent=3b82f6
```

---

## ✅ Common Timezone Offsets (tz= value in minutes)

| Timezone | Value |
|----------|-------|
| UTC | `0` |
| IST (India) | `330` |
| EST (US East) | `-300` |
| PST (US West) | `-480` |
| CET (Europe) | `60` |
| GST (Dubai) | `240` |
| SGT (Singapore) | `480` |
| AEST (Sydney) | `600` |

---

## 💡 Tips

- The timer updates every time the email is **opened** (not real-time in inbox)
- After the deadline, it shows "OFFER EXPIRED" automatically
- Works in Gmail, Outlook, Apple Mail, Yahoo Mail
- No external libraries needed — pure Python stdlib only
