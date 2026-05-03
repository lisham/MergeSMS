# SMS Sender Web App 🚀

A lightweight and easy-to-use local bulk SMS web application built with a **Flask** (Python) backend and a modern **Vue.js/Vuetify** frontend.

This project allows you to manage SMS campaigns via CSV lists, create customizable message templates (e.g., `{firstname}`, `{lastname}`), and send personalized messages locally using your Android phone via **KDE Connect**.

## ✨ Features

- **Project Management:** Organize CSV contacts and text templates into dedicated folders.
- **CSV Support:** Automatically parse contacts and dynamic fields.
- **Dynamic Templating:** Personalize messages per recipient using `{firstname}`, `{lastname}`, etc.
- **Local SMS Routing:** Sends SMS directly from your paired Android phone via `kdeconnect-cli`.
- **Dry-run Mode:** Safely test your templates and CSV mapping without sending actual SMS.
- **Phone Validation:** Built-in customizable rules to format and validate numbers.
- **Modern UI:** Responsive Single Page Application (SPA) with Dark/Light mode.

## 💻 Tech Stack

- **Backend:** Python, Flask
- **Frontend:** HTML/CSS, Vanilla JS, Vue 3, Vuetify, Axios
- **Architecture:** SPA (Single Page Application)

## 📋 Prerequisites

- **OS:** Ubuntu 24.04 LTS (Tested and highly recommended)
- **Python:** >= 3.12.3
- **External Tools:** `kdeconnect-cli` (Version 23.08.5 or higher) is required for sending SMS via your Android device.
- **Frontend:** Vue.js (3.5.27) and Vuetify (3.5.4) - Included as static files, no Node.js build required.
- **Hardware/Network:** An Android phone with the KDE Connect app installed. Your Ubuntu PC and the phone **must be on the same Wi-Fi network** and paired successfully.

## 📦 Installation & Setup

1. **Install KDE Connect (on Ubuntu):**

    sudo apt update
    sudo apt install kdeconnect

    Important: Open KDE Connect on your Ubuntu machine and your Android phone, then pair them together before running this app.

2. **Clone the repository**

    git clone https://github.com/lisham/MergeSMS.git
    cd MergeSMS

3. **Create a Virtual Environment (Recommended)**

    python3 -m venv .venv
    source .venv/bin/activate  # On Linux/macOS

4. **Install Python Dependencies**

    pip install -r requirements.txt

5. **Configuration**

    - Open `config.json` to adjust app settings (e.g., toggle dry-run mode or KDE Connect).
    - Modify `phone_rules.json` if you need custom phone number validation rules.

## 🔐 Important Notes

### KDE Connect Pairing & Permissions

When pairing KDE Connect between your Android phone and Ubuntu PC, make sure to:

- Grant all necessary permissions to the KDE Connect app on your Android phone (especially **SMS permission** and **Notification access**).
- On Ubuntu, ensure `kdeconnect-cli` has proper access to your desktop session.
- After pairing, test the connection by running:
    kdeconnect-cli --ping
- If the ping fails, check that both devices are on the **same Wi-Fi network** and that no firewall is blocking the connection (default ports: 1714-1764).

### CSV File Format Requirements

Your CSV files must follow these strict rules to work correctly:

- **Delimiter:** Only comma `,` is supported. Do **NOT** use semicolon `;` as delimiter.
- **Required columns:** You must have at least two columns named `send` and `mob` (case-sensitive). Additional columns for dynamic templating (e.g., `firstname`, `lastname`, `city`) are allowed and optional.
- **`send` column:** Must contain only `1` or `0`. Any other value will cause the row to be ignored.
    - `1` = recipient will receive the SMS
    - `0` = recipient will be skipped
- **`mob` column:** Contains the phone number(s) for each recipient.
    - For a single number: just write the number (e.g., `09123456789`)
    - For multiple numbers: separate them with semicolon `;` (e.g., `09123456789;09234567890`)
    - All numbers in this column will receive the same personalized message.

> Tip: You can add extra columns like `firstname`, `lastname`, etc. for dynamic templating. Only `send` and `mob` are mandatory.

## 🚀 Usage

1. Run the Flask backend:

    python3 app.py

2. Open your web browser and navigate to: **http://127.0.0.1:5000**

3. Create or edit your projects inside the `Project Manager` section. Upload, edit, or delete your CSV and TXT templates inside the `Lists Manager` and `Templates Manager` sections, then start your SMS campaigns.

## 📁 Project Structure

- **`app.py`** : Main Flask application and API endpoints.
- **`static/`** : Contains frontend assets (`index.html`, `app.js`, CSS, Vue/Vuetify libraries and required fonts).
- **`projects/`** : Directory where user projects, templates, and CSV files are stored.
- **`config.json`** & **`phone_rules.json`** : App configuration and validation rules.

## 📄 License

This project is licensed under the **MIT License**.
