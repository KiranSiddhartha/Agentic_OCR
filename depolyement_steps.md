Below is a **clean production-ready summary you can paste directly into your `README.md` or deployment `.md` file**.
I structured it like a real **enterprise deployment guide**.

---

# Agentic OCR – IIS Deployment Guide

This document explains how to deploy the **Agentic OCR system (Next.js + FastAPI)** on **Windows IIS with a background backend service**.

---

# Architecture Overview

```
Browser
   ↓
IIS (Frontend – Next.js Static Build)
   ↓
IIS URL Rewrite / Reverse Proxy
   ↓
FastAPI Backend (Windows Service via NSSM)
   ↓
OCR Processing Engine
```

---

# System Components

| Component       | Technology              |
| --------------- | ----------------------- |
| Frontend        | Next.js (static export) |
| Backend         | FastAPI                 |
| Web Server      | IIS                     |
| Reverse Proxy   | IIS URL Rewrite + ARR   |
| Backend Runtime | Uvicorn                 |
| Service Manager | NSSM                    |

---

# 1. Install IIS

Enable IIS from Windows Features.

```
Control Panel
→ Programs
→ Turn Windows features on or off
```

Enable:

```
Internet Information Services
  ├── Web Management Tools
  └── World Wide Web Services
```

---

# 2. Install IIS Extensions

Install the following modules:

### URL Rewrite

[https://www.iis.net/downloads/microsoft/url-rewrite](https://www.iis.net/downloads/microsoft/url-rewrite)

### Application Request Routing (ARR)

[https://www.iis.net/downloads/microsoft/application-request-routing](https://www.iis.net/downloads/microsoft/application-request-routing)

Enable Proxy:

```
IIS Manager
→ Application Request Routing
→ Server Proxy Settings
→ Enable Proxy
```

---

# 3. Deploy Frontend (Next.js)

Build the project:

```bash
npm run build
```

Configure Next.js for static export.

Create `next.config.ts`

```ts
const nextConfig = {
  output: "export"
}

export default nextConfig
```

Then export:

```bash
npm run build
```

This creates:

```
/out
```

Copy contents to:

```
C:\inetpub\wwwroot
```

---

# 4. Configure IIS Site

Open **IIS Manager**

```
Sites
 → Default Web Site
```

Set physical path:

```
C:\inetpub\wwwroot
```

---

# 5. Configure Reverse Proxy

Open:

```
IIS Manager
→ Default Web Site
→ URL Rewrite
```

Add rule:

### Reverse Proxy Rule

```
Pattern: (.*)

Rewrite URL:
http://127.0.0.1:8000/{R:1}
```

Enable:

```
Append query string
Stop processing rules
```

---

# 6. Run FastAPI Backend as Windows Service

Install **NSSM (Non-Sucking Service Manager)**.

Download:

```
https://nssm.cc/download
```

Extract:

```
C:\Users\<user>\Desktop\nssm-Service
```

Use:

```
win64\nssm.exe
```

---

# 7. Create Backend Service

Run:

```powershell
nssm install AgenticOCRBackend
```

Fill configuration:

### Path

```
C:\Users\<user>\source\repos\Agentic_OCR\venv\Scripts\python.exe
```

### Startup Directory

```
C:\Users\<user>\source\repos\Agentic_OCR
```

### Arguments

```
-m uvicorn main:app --host 127.0.0.1 --port 8000
```

Install service.

---

# 8. Start Backend Service

```powershell
nssm start AgenticOCRBackend
```

Verify:

```powershell
nssm status AgenticOCRBackend
```

Expected:

```
SERVICE_RUNNING
```

---

# 9. Verify Deployment

### Backend API

```
http://localhost:8000/docs
```

### Full Application

```
http://localhost
```

Upload a document to test OCR pipeline.

---

# 10. Enable Service Auto Start

Ensure backend runs automatically after reboot.

```powershell
nssm set AgenticOCRBackend Start SERVICE_AUTO_START
```

---

# Optional: Enable Backend Logs

Edit service:

```
nssm edit AgenticOCRBackend
```

Set logs:

```
Output: C:\logs\ocr_stdout.log
Error:  C:\logs\ocr_error.log
```

Create folder:

```
C:\logs
```

---

# Production Improvements

### 1. Run Multiple Workers

Improve performance:

```
-m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
```

---

### 2. Increase IIS Upload Limits

Large OCR documents require larger upload size.

Edit `web.config`:

```xml
<system.webServer>
   <security>
      <requestFiltering>
         <requestLimits maxAllowedContentLength="524288000"/>
      </requestFiltering>
   </security>
</system.webServer>
```

(500MB limit)

---

### 3. Enable Compression

```
IIS Manager
→ Compression
→ Enable Static + Dynamic Compression
```

---

# Final Production Setup

| Layer           | System                               |
| --------------- | ------------------------------------ |
| Frontend        | IIS                                  |
| Backend         | FastAPI                              |
| Service Manager | NSSM                                 |
| Proxy           | IIS URL Rewrite                      |
| User Endpoint   | [http://localhost](http://localhost) |

---

# Result

The **Agentic OCR system now runs as a production-ready application**:

* IIS serves the frontend
* FastAPI runs as a background Windows service
* Reverse proxy connects frontend and backend
* Backend automatically starts with Windows
 


 Restart the backend service

Run:

& "C:\Users\xd5914\Desktop\nssm-Service\nssm-2.24-101-g897c7ad\win64\nssm.exe" restart AgenticOCRBackend

This will:

STOP service
START service

and reload your new backend code.

Alternative Commands

Stop service:

nssm stop AgenticOCRBackend

Start service:

nssm start AgenticOCRBackend

Restart (recommended):

nssm restart AgenticOCRBackend




How to Confirm Auto-Start Is Enabled

Run:

nssm get AgenticOCRBackend Start

Expected result:

SERVICE_AUTO_START

Or check in Services UI:

Win + R
services.msc

Find:

AgenticOCRBackend

Check:

Startup Type → Automatic
Status → Running
When You Need to Restart the Service

You only restart if:

Situation	Action
Backend code changed	Restart service
Python dependency installed	Restart service
Backend crashed	Restart service
Port changed	Restart service

Restart command:

nssm restart AgenticOCRBackend
Normal Operation (No Manual Steps)

After reboot:

http://localhost

will work immediately because:

IIS starts automatically
FastAPI service starts automatically
Reverse proxy connects them