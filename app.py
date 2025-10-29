from flask import Flask, request, render_template, redirect, url_for
import subprocess
import json
import os
import uuid
import shutil
import logging
import time
from datetime import datetime

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

# ---- Check Requirements ----
def check_requirements():
    lh_path = shutil.which("lighthouse") or shutil.which("lighthouse.cmd")
    if not lh_path:
        return False, "Lighthouse not found. Install with: npm install -g lighthouse", None

    possible_chrome_paths = [
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
    ]
    chrome_path = next((p for p in possible_chrome_paths if p), None)
    if not chrome_path:
        return False, "Google Chrome not found. Please install Chrome.", None

    return True, None, chrome_path

@app.route("/", methods=["GET"])
def landing():
    req_status, req_error, _ = check_requirements()
    if not req_status:
        return render_template("landing.html", error=req_error)
    return render_template("landing.html")

# ---- New Loading Page ----
@app.route("/loading", methods=["GET"])
def loading():
    url = request.args.get("url", "").strip()
    if not url:
        return redirect(url_for("landing", error="Please provide a URL"))
    return render_template("loading.html", url=url)

# ---- Audit Page ----
@app.route("/audit", methods=["GET"])
def audit():
    url = request.args.get("url", "").strip()
    logger.info(f"Auditing URL: {url}")
    if not url.startswith(("http://", "https://")):
        return render_template("landing.html", error="Please include http:// or https:// in your URL")

    req_status, req_error, chrome_path = check_requirements()
    if not req_status:
        return render_template("landing.html", error=req_error)

    report_path = os.path.join(BASE_DIR, f"report_{uuid.uuid4().hex}.json")
    try:
        lh_path = shutil.which("lighthouse") or shutil.which("lighthouse.cmd")
        command = [
            lh_path, url,
            "--output=json",
            f"--output-path={report_path}",
            "--quiet",
            "--only-categories=performance,seo,accessibility,best-practices",
            "--chrome-flags=--headless --no-sandbox --disable-gpu --disable-web-security"
        ]
        if chrome_path:
            command += ["--chrome-path", chrome_path]

        start_time = time.time()
        result = subprocess.run(
            command,
            capture_output=True, text=True, timeout=300, cwd=BASE_DIR
        )
        logger.debug(f"Lighthouse run time: {time.time()-start_time:.2f}s")

        if result.returncode != 0:
            return render_template("landing.html", error=f"Lighthouse failed: {result.stderr[:200]}")

        if not os.path.exists(report_path):
            return render_template("landing.html", error="No report generated. Website may block headless browsers.")

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        # ---- Extract Insights ----
        categories = report.get("categories", {})
        scores = {}
        for cat, details in categories.items():
            score = details.get("score")
            if score is not None:
                scores[cat] = round(score * 100, 2)

        # Performance metrics
        audits = report.get("audits", {})
        perf_metrics = {
            "First Contentful Paint": audits.get("first-contentful-paint", {}).get("numericValue", "N/A"),
            "Largest Contentful Paint": audits.get("largest-contentful-paint", {}).get("numericValue", "N/A"),
            "Time to Interactive": audits.get("interactive", {}).get("numericValue", "N/A"),
            "Total Blocking Time": audits.get("total-blocking-time", {}).get("numericValue", "N/A"),
            "Cumulative Layout Shift": audits.get("cumulative-layout-shift", {}).get("numericValue", "N/A"),
        }

        # SEO insights
        seo_issues = []
        seo_category = categories.get("seo", {})
        for audit_ref in seo_category.get("auditRefs", []):
            audit = audits.get(audit_ref["id"])
            if audit and audit.get("score") is not None and audit["score"] < 1:
                seo_issues.append(audit["title"])

        # Accessibility issues
        a11y_issues = []
        a11y_category = categories.get("accessibility", {})
        for audit_ref in a11y_category.get("auditRefs", []):
            audit = audits.get(audit_ref["id"])
            if audit and audit.get("score") is not None and audit["score"] < 1:
                a11y_issues.append(audit["title"])

        # Best Practices / Security issues
        security_issues = []
        bp_category = categories.get("best-practices", {})
        for audit_ref in bp_category.get("auditRefs", []):
            audit = audits.get(audit_ref["id"])
            if audit and audit.get("score") is not None and audit["score"] < 1:
                security_issues.append(audit["title"])

        timestamp = datetime.now().strftime("%b %d, %Y %H:%M")
        return render_template(
            "results.html",
            url=url,
            scores=scores,
            perf_metrics=perf_metrics,
            seo_issues=seo_issues,
            a11y_issues=a11y_issues,
            security_issues=security_issues,
            timestamp=timestamp
        )

    except subprocess.TimeoutExpired:
        return render_template("landing.html", error="Audit timed out. Try again.")
    except json.JSONDecodeError:
        return render_template("landing.html", error="Failed to parse Lighthouse report.")
    except Exception as e:
        return render_template("landing.html", error=f"Unexpected error: {str(e)}")
    finally:
        if os.path.exists(report_path):
            os.remove(report_path)

if __name__ == "__main__":
    app.run(debug=True)