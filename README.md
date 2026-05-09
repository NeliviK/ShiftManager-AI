# 🤖 ShiftManager AI: Financial Automation Bot

An enterprise-grade Telegram bot designed for remote team management, shift tracking, role-based access control (RBAC), and automated financial reporting via external APIs. 

Built specifically for digital agencies, media buying teams, and remote content studios to eliminate manual profit calculation and streamline internal task delegation.

---

## 🌟 Key Features

**1. Seamless Internationalization (i18n)** The bot supports on-the-fly language switching. All FSM states and UI elements dynamically adapt to the user's preference without restarting the session.
 <img width="1104" height="177" alt="Снимок экрана 2026-05-09 в 14 56 03" src="https://github.com/user-attachments/assets/4ab50458-bd3e-4ff1-a416-e477b2564ed4" />

 **2. Core Dashboard & Dynamic RBAC** The main operational interface. Notice the "HR / Promotion" button — this is part of the Role-Based Access Control (RBAC) system and is dynamically rendered exclusively for the `SUPER_ADMIN`.
<img width="1110" height="243" alt="Снимок экрана 2026-05-09 в 14 58 16" src="https://github.com/user-attachments/assets/ff41a3ac-85f7-44f7-8caa-47341b4dd90b" />

**3. Automated API-Driven Financial Reporting** Cross-platform profit aggregation in action. The system fetches raw transaction data from external APIs, calculates the net shift profit across multiple accounts, and persists the record to the SQLite database.
Note: The screenshots below showcase the live production environment, which is currently localized for the CIS market. 
<img width="330" height="197" alt="image" src="https://github.com/user-attachments/assets/73d33a30-5a9c-4776-853a-4fbb29473b43" />


* **Automated Profit Tracking (API):** Direct asynchronous integration with platform APIs (via `aiohttp`) to calculate exact net profit generated during an employee's work shift.
* **Dynamic RBAC (Role-Based Access Control):** Includes an in-app "HR Management" dashboard for the System Owner (`SUPER_ADMIN`). Assign "Curator" or "TeamLead" roles directly via Telegram UI. These roles are dynamically injected into the approval workflows.
* **Custom Order FSM (Task Delegation):** A complex Finite State Machine for ordering media content. Managers navigate an interactive pipeline (duration, scenario, speech, references, payment status). The bot formats the brief and automatically routes it to the production department.
* **Financial Persistence:** Built-in SQLite database engine with asynchronous access (`aiosqlite`) for secure, long-term data storage.
* **Monthly Analytics:** Automated background task scheduler (`APScheduler`) aggregates performance metrics and pushes automated team-wide financial reports on the 1st of every month.

* ## 📸 System Showcase

 

## 🛠 Tech Stack

* **Language:** Python 3.12+
* **Framework:** Aiogram 3.x (Asyncio)
* **Database:** SQLite (`aiosqlite`)
* **Task Scheduling:** APScheduler
* **API Interaction:** Asynchronous `aiohttp` client

---

## 📂 Architecture Overview

The system is highly modular. The API interaction layer (`api_provider.py`) is decoupled from the main bot logic. This allows you to seamlessly swap the current API endpoint with any other data source (Stripe, custom CRM, Shopify, etc.) without rewriting the core business logic or FSM pipelines.

---

## 🚀 Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.11+ installed on your server/machine.

### 2. Clone and Install
```bash
git clone [https://github.com/YourUsername/ShiftManager-AI.git](https://github.com/YourUsername/ShiftManager-AI.git)
cd ShiftManager-AI
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt

Create a .env file in the root directory based on the provided .env.example:

Bash
cp .env.example .env
Open .env and fill in your specific tokens and Telegram IDs.

SUPER_ADMIN_ID: Has full access to the HR/Promotion menu to assign roles.

MANAGERS_IDS: Comma-separated list of IDs allowed to use the bot.

4. Run the Bot

Bash
python main.py
🔐 Security & Access Control
The bot is strictly private. Any user whose Telegram ID is not explicitly listed in the .env file will receive an "Access Denied" response.

📝 License
This project is licensed under the MIT License - see the LICENSE file for details.

