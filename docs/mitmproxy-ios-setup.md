# Capturing iOS HTTP Traffic with mitmproxy

Use this guide to intercept and inspect HTTP/HTTPS traffic from an iOS app on your Mac.

## Requirements

- Mac and iPhone on the **same Wi-Fi network**
- [Homebrew](https://brew.sh) installed on your Mac

---

## Step 1 — Install and start mitmproxy

```bash
brew install mitmproxy
mitmweb
```

This opens the capture UI in your browser at `http://127.0.0.1:8081`. Keep the terminal open while capturing.

---

## Step 2 — Find your Mac's local IP address

```bash
ipconfig getifaddr en0
```

Note the IP address (e.g. `192.168.1.42`).

---

## Step 3 — Configure the proxy on your iPhone

1. **Settings → Wi-Fi → [your network name]** → tap the ⓘ icon
2. Scroll down to **HTTP Proxy → Configure Proxy → Manual**
3. Enter:
   - **Server**: your Mac's IP address
   - **Port**: `8080`
4. Tap **Save**

> **Note**: If `mitmweb` is not running on your Mac, your iPhone will lose internet access. Always start `mitmweb` before enabling the proxy.

---

## Step 4 — Install the mitmproxy certificate on your iPhone

The certificate allows mitmproxy to intercept HTTPS traffic.

1. On your iPhone, open **Safari** and navigate to `http://mitm.it`
2. Tap **Apple** → tap **Allow** to download the profile
3. **Settings → General → VPN & Device Management** → tap the mitmproxy profile → **Install** → enter your passcode if prompted
4. **Settings → General → About → Certificate Trust Settings** → toggle the mitmproxy certificate **ON**

> This last step (Certificate Trust Settings) is required for HTTPS interception. Without it, HTTPS requests will fail.

---

## Step 5 — Capture traffic

1. Confirm `mitmweb` is running on your Mac
2. Open the app you want to inspect on your iPhone
3. Open `http://127.0.0.1:8081` in your Mac browser
4. Use the **Search** box to filter requests (e.g. type `castr` to see only Castr CDN traffic)

---

## Step 6 — Save captured traffic

Save your captures to `docs/captures/` in this repository (the folder is gitignored, so files won't be committed).

In the mitmweb UI:

- **File → Save** to export a `.flows` file → save it to `docs/captures/`
- Right-click a request → **Copy as cURL** to share a specific request

To re-open a saved capture later:

```bash
mitmweb --rfile docs/captures/your-capture.flows
```

---

## Cleanup

When done, remove the proxy config from your iPhone to restore normal internet access:

**Settings → Wi-Fi → [your network name] → Configure Proxy → Off**

Optionally, also remove the certificate profile:

**Settings → General → VPN & Device Management** → tap the mitmproxy profile → **Remove**
