#!/usr/bin/env python3
"""Wrap index.html with the 'wf' password gate (AES-GCM + PBKDF2).
Reads index.html, encrypts the body content, writes back with the gate shell.
Idempotent: detects already-gated files and re-encrypts the inner content.
"""
import os, base64, json, re, sys
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes

ROOT = Path(__file__).parent
HTML = ROOT / "index.html"
PASSWORD = "wf"
LOCAL_KEY = "wf_publishing_pw"
ITERATIONS = 100_000

GATE_MARK_START = "<!-- GATE_INNER_START -->"
GATE_MARK_END = "<!-- GATE_INNER_END -->"

def encrypt_payload(plaintext: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    key = kdf.derive(PASSWORD.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return {
        "v": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "iterations": ITERATIONS,
        "ciphertext": base64.b64encode(ct).decode("ascii"),
    }

# Read the current HTML
src = HTML.read_text(encoding="utf-8")

# If already gated, extract the inner content from an unencrypted backup
backup = ROOT / "_inner.html"
if "<script type=\"application/json\" id=\"payload\">" in src and backup.exists():
    inner = backup.read_text(encoding="utf-8")
else:
    # First time: extract the visible body content (everything between <body> and </body>)
    m = re.search(r"<body[^>]*>(.*)</body>", src, re.DOTALL)
    if not m:
        sys.exit("No <body> in source HTML.")
    inner = m.group(1).strip()
    # Save the unencrypted inner for re-builds
    backup.write_text(inner, encoding="utf-8")

# Extract original <head> (styles + meta etc.) to reuse outside the gate
head_match = re.search(r"<head[^>]*>(.*)</head>", src, re.DOTALL)
original_head = head_match.group(1).strip() if head_match else ""

# Strip the original <title> from the head (we'll set our own gate title)
original_head = re.sub(r"<title>.*?</title>", "", original_head, flags=re.DOTALL).strip()
# Strip any existing noindex meta (we'll add our own)
original_head = re.sub(r'<meta\s+name="robots"[^>]*>', "", original_head).strip()

blob = encrypt_payload(inner)
payload_json = json.dumps(blob)

GATE_TITLE = "WF publishing"

gate_html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex,nofollow" />
<title>{GATE_TITLE}</title>
{original_head}
<style>
  body.locked #content {{ display: none; }}
  #gate {{
    position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
    background: #f5f5f7; z-index: 9999;
  }}
  #gate-card {{
    background: #fff; border: 1px solid #e5e5ea; border-radius: 14px;
    padding: 32px 36px; max-width: 360px; width: 100%;
    box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", system-ui, sans-serif;
  }}
  #gate-card h2 {{
    font-size: 17px; font-weight: 600; margin: 0 0 6px; color: #1d1d1f; letter-spacing: -0.01em;
  }}
  #gate-card p {{
    font-size: 12.5px; color: #6e6e73; margin: 0 0 18px;
  }}
  #gate-form {{ display: flex; gap: 8px; }}
  #gate-input {{
    flex: 1; font-size: 14px; padding: 9px 12px;
    border: 1px solid #d2d2d7; border-radius: 7px; outline: none;
    font-family: inherit; color: #1d1d1f;
  }}
  #gate-input:focus {{ border-color: #1d1d1f; }}
  #gate-btn {{
    background: #1d1d1f; color: #fff; border: 0; border-radius: 7px;
    padding: 9px 16px; font-size: 13px; font-weight: 500; cursor: pointer;
    font-family: inherit;
  }}
  #gate-btn:hover {{ background: #000; }}
  #gate-err {{
    font-size: 12px; color: #b00020; margin-top: 10px; min-height: 16px;
  }}
  body.locked > *:not(#gate):not(script) {{ filter: blur(20px); pointer-events: none; }}
  #lock-link {{
    position: fixed; bottom: 12px; right: 16px; font-size: 11px; color: #86868b;
    text-decoration: none; font-family: -apple-system, sans-serif; z-index: 50;
  }}
  #lock-link:hover {{ color: #1d1d1f; }}
</style>
</head>
<body class="locked">

<div id="gate">
  <div id="gate-card">
    <h2>{GATE_TITLE}</h2>
    <p>Internal access only.</p>
    <form id="gate-form" onsubmit="return gateSubmit(event)">
      <input id="gate-input" type="password" placeholder="password" autocomplete="off" autofocus>
      <button id="gate-btn" type="submit">Enter</button>
    </form>
    <div id="gate-err"></div>
  </div>
</div>

<div id="content" hidden></div>

<a href="#" id="lock-link" onclick="localStorage.removeItem('{LOCAL_KEY}');location.reload();return false;" style="display:none;">lock device</a>

<script type="application/json" id="payload">{payload_json}</script>
<script>
function b64ToBytes(b64) {{
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}}
async function deriveKey(password, salt, iterations) {{
  const enc = new TextEncoder();
  const baseKey = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    {{ name: "PBKDF2", salt, iterations, hash: "SHA-256" }},
    baseKey,
    {{ name: "AES-GCM", length: 256 }},
    false, ["decrypt"]
  );
}}
async function decryptPayload(password) {{
  const blob = JSON.parse(document.getElementById('payload').textContent);
  const salt = b64ToBytes(blob.salt);
  const iv = b64ToBytes(blob.iv);
  const ct = b64ToBytes(blob.ciphertext);
  const key = await deriveKey(password, salt, blob.iterations);
  const plain = await crypto.subtle.decrypt({{ name: "AES-GCM", iv }}, key, ct);
  return new TextDecoder().decode(plain);
}}
function executeScriptsIn(container) {{
  // Re-create script tags so they actually execute (innerHTML script tags don't run)
  const scripts = Array.from(container.querySelectorAll("script"));
  for (const old of scripts) {{
    const fresh = document.createElement("script");
    if (old.type) fresh.type = old.type;
    if (old.src) fresh.src = old.src;
    fresh.textContent = old.textContent;
    old.parentNode.replaceChild(fresh, old);
  }}
}}
async function unlock(password) {{
  const innerHtml = await decryptPayload(password);
  const c = document.getElementById('content');
  c.innerHTML = innerHtml;
  c.hidden = false;
  document.getElementById('gate').style.display = 'none';
  document.body.classList.remove('locked');
  document.getElementById('lock-link').style.display = 'inline';
  executeScriptsIn(c);
}}
async function gateSubmit(e) {{
  e.preventDefault();
  const inp = document.getElementById('gate-input');
  const err = document.getElementById('gate-err');
  err.textContent = '';
  try {{
    await unlock(inp.value);
    try {{ localStorage.setItem('{LOCAL_KEY}', inp.value); }} catch (_) {{}}
  }} catch (ex) {{
    err.textContent = 'wrong password';
    inp.value = '';
    inp.focus();
  }}
  return false;
}}
// Auto-unlock on future visits
(async () => {{
  try {{
    const cached = localStorage.getItem('{LOCAL_KEY}');
    if (cached) await unlock(cached);
  }} catch (_) {{
    try {{ localStorage.removeItem('{LOCAL_KEY}'); }} catch (_) {{}}
  }}
}})();
</script>

</body>
</html>
"""

HTML.write_text(gate_html, encoding="utf-8")
print(f"Gated: {HTML}")
print(f"  password: {PASSWORD}")
print(f"  localStorage key: {LOCAL_KEY}")
print(f"  ciphertext size: {len(payload_json)} chars")
