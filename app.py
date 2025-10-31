from flask import Flask, render_template, request
import requests
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ----------------------------------------
# 🔹 GOOGLE PAGESPEED CONFIGURATION
# ----------------------------------------
API_KEY = "AIzaSyDR9U9zPn-QXuk4Ny0XZo83uryGh_aGjTI"  # Replace with your real Google API key

# ----------------------------------------
# 🔹 HOME ROUTE
# ----------------------------------------
@app.route("/")
def home():
    return render_template("landing.html")

# ----------------------------------------
# 🔹 AUDIT ROUTE
# ----------------------------------------
@app.route("/audit", methods=["GET"])
def audit():
    url = request.args.get("url", "").strip()
    if not url:
        return render_template("landing.html", error="Please enter a valid URL")

    try:
        # Fetch PageSpeed Insights data for all categories
        api_url = (
            f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={url}&key={API_KEY}&strategy=desktop"
            f"&category=performance&category=accessibility"
            f"&category=best-practices&category=seo"
        )
        response = requests.get(api_url)
        data = response.json()

        if "lighthouseResult" not in data:
            err_msg = data.get("error", {}).get("message", "Unknown API error.")
            return render_template(
                "results.html",
                url=url,
                scores={},
                seo_issues=[f"⚠ API Error: {err_msg}"],
                a11y_issues=[],
                timestamp=datetime.now().strftime("%b %d, %Y %H:%M"),
            )

        lighthouse = data["lighthouseResult"]
        categories = lighthouse.get("categories", {})
        audits = lighthouse.get("audits", {})

        # ✅ Extract category scores safely
        def get_score(cat):
            s = categories.get(cat, {}).get("score", 0)
            return round(s * 100) if s is not None else 0

        scores = {
            "Performance": get_score("performance"),
            "Accessibility": get_score("accessibility"),
            "Best Practices": get_score("best-practices"),
            "SEO": get_score("seo"),
        }

        # ✅ Extract issues safely
        seo_issues = []
        a11y_issues = []

        for audit_id, audit in audits.items():
            if not isinstance(audit, dict):
                continue

            score = audit.get("score", 1)
            if score is None:  # skip non-scored audits
                continue

            # If audit failed (score < 1)
            if score < 1:
                title = audit.get("title", "Untitled")
                description = audit.get("description", "")
                # SEO-related
                if any(x in audit_id.lower() for x in ["seo", "meta", "viewport", "robots", "title"]):
                    seo_issues.append(f"{title} — {description[:100]}...")
                # Accessibility-related
                if any(x in audit_id.lower() for x in ["accessibility", "contrast", "aria", "label", "alt", "button"]):
                    a11y_issues.append(f"{title} — {description[:100]}...")

        # Remove duplicates
        seo_issues = list(set(seo_issues))
        a11y_issues = list(set(a11y_issues))

        if not seo_issues:
            seo_issues = ["✅ No major SEO issues detected."]
        if not a11y_issues:
            a11y_issues = ["✅ No major Accessibility issues detected."]

        return render_template(
            "results.html",
            url=url,
            scores=scores,
            seo_issues=seo_issues,
            a11y_issues=a11y_issues,
            timestamp=datetime.now().strftime("%b %d, %Y %H:%M"),
        )

    except Exception as e:
        return render_template(
            "results.html",
            url=url,
            scores={},
            seo_issues=[f"⚠ Error: {str(e)}"],
            a11y_issues=[],
            timestamp=datetime.now().strftime("%b %d, %Y %H:%M"),
        )


# ----------------------------------------
# 🔹 RUN LOCALLY OR ON RENDER
# ----------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # ✅ for Render
    app.run(host="0.0.0.0", port=port, debug=True)
