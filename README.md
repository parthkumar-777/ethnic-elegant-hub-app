# ETHNIC ELEGANT HUB — Setup, Hosting & App Guide

## Kya bana hai
- Flask website (Flipkart-style), women's ethnic wear only
- Login/Signup, Cart, Checkout, Order tracking
- Admin panel (`/admin`) — bina code touch kiye product add/edit/delete + orders dekho
- 25 dummy products already load ho chuke hain
- First-visit par animated character wala welcome popup
- Gold/Maroon/Charcoal premium theme, aapka logo laga hua hai

**Default Admin Login:** `admin@ethnicelegant.com` / `Admin@123`
(Pehle hi kaam se badal dena — Admin panel abhi khud ka password change karne ka option nahi deta, chahiye to bata dena, add kar dunga)

---

## PART 1 — Apne Laptop Par Chalana

### Step 1: Python check karo
Terminal/CMD kholo:
```
python3 --version
```
Agar nahi hai to python.org se install karo (3.10+ chalega).

### Step 2: Zip extract karo
Zip file ko kisi folder mein extract karo, jaise `Desktop/ethnic-elegant-hub`.

### Step 3: Terminal us folder mein le jao
```
cd Desktop/ethnic-elegant-hub
```

### Step 4: Virtual environment banao (recommended)
```
python3 -m venv venv
```
Activate karo:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

### Step 5: Dependencies install karo
```
pip install -r requirements.txt
```

### Step 6: Database seed karo (pehli baar hi)
```
python3 seed.py
```
Ye 25 products aur admin account bana dega.

### Step 7: Website chalao
```
python3 app.py
```
Browser mein kholo: **http://127.0.0.1:5000**

Bas — poori website chal rahi hai aapke laptop par!

### Naye products add karne ke liye (bina code touch kiye)
1. `/login` par admin se login karo
2. `/admin` par jao → Products → "+ Add Product"
3. Photo upload karo, price/category/size sab fill karo → Save

### Orders dekhne ke liye
`/admin/orders` par saare customer orders, unka address, phone aur status change karne ka option milega.

---

## PART 2 — Internet Par Host Karna (taaki koi bhi kahin se access kar sake)

Free/cheap options (beginner-friendly):

### Option A: Render.com (sabse aasan, free tier available)
1. GitHub account banao, is folder ko GitHub repo mein upload karo
2. Render.com par signup karo → "New Web Service" → apna GitHub repo connect karo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python3 seed.py && gunicorn app:app`
5. Deploy dabao — 2-3 min mein live link mil jayega (jaise `ethnic-elegant-hub.onrender.com`)

### Option B: PythonAnywhere (free tier, simple for Flask)
1. pythonanywhere.com par account banao
2. Files upload karo (ya GitHub se clone karo)
3. "Web" tab mein new Flask app configure karo, WSGI file mein apna app point karo
4. Reload dabao — live ho jayega

### Option C: Apna VPS (professional/paid — DigitalOcean, AWS, Hostinger)
Zyada control chahiye to VPS lo, Nginx + Gunicorn setup karo. Ye thoda technical hai — jab chaho to main step-by-step ye bhi bata sakta hu.

**Important:** Production mein jaane se pehle `app.py` mein `app.secret_key` ko ek random secure key se badal dena, aur admin password bhi change kar lena.

---

## PART 3 — Website Ko Mobile App Mein Convert Karna

Do tarike hain, dono legit hain:

### Option 1: PWA (Progressive Web App) — Sabse aasan, free
Website already installable ban sakti hai:
1. Website ko host karo (Part 2 se)
2. Ek `manifest.json` aur service worker file add karni hogi (bata do to main abhi add kar deta hu)
3. User apne phone browser (Chrome) mein website kholega → "Add to Home Screen" dabayega
4. Ye ekdum app jaisa icon aur experience dega — **bina Play Store ke bhi**

### Option 2: Real Android/iOS App (Play Store/App Store ke liye)
Website ko wrap karke real app banane ke liye **Median.co** ya **Capacitor** use hota hai:

**Median.co (sabse simple, no-code):**
1. median.co par account banao
2. Apna hosted website URL (jo Part 2 mein banaya) daalo
3. App icon (logo) aur naam set karo
4. Ye automatically Android APK aur iOS build de dega
5. Google Play Console (~$25 one-time) aur Apple Developer account (~$99/year) mein upload karke publish karo

**Capacitor (thoda technical, free, zyada control):**
1. `npm install -g @capacitor/cli`
2. Website ko Capacitor project mein wrap karo (`npx cap init`)
3. Android Studio/Xcode se APK/IPA build karo
4. Store par upload karo

Mera suggestion: pehle **PWA** try karo (free, instant, code-free) — agar Play Store par bhi chahiye to baad mein **Median.co** use kar lena.

---

## Agla Kya Karu Bata Do
- Password change feature admin panel mein chahiye?
- PWA manifest + service worker abhi add kar du?
- Product reviews/ratings feature chahiye?
- Real payment gateway (Razorpay/UPI) integrate karna hai (abhi COD/UPI sirf dummy hai)?
