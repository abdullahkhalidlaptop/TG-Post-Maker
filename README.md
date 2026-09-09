# 📝 Telegram Post Formatting Engine Bot

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2?logo=google&logoColor=white)
![PM2](https://img.shields.io/badge/PM2-Daemonized-2B037A?logo=pm2&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

An automated Telegram bot that leverages **Google Gemini 2.5 Flash** to extract metadata from raw forwarded Telegram text, media captions, or screenshots and convert them into clean, standardized post templates.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [How It Works](#-how-it-works)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [Running with PM2](#-running-with-pm2)
- [Bot Commands](#-bot-commands)
- [Managing Configuration](#-managing-configuration-via-telegram)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)

---

## 📸 Overview

This bot ingests forwarded channel messages, ignores promotional fluff, watermarks, and non-essential emojis, and reconstructs the data into a structured format ready for immediate publishing.

Whether you're a content curator, community manager, or developer, this tool streamlines the process of turning raw posts into clean, publishable content.

---

## ⚡ Key Features

- **High-Speed Extraction**: Async engine returns formatted JSON in just 2–4 seconds using the Gemini 2.5 Flash model.
- **Enforced Schema Validation**: Uses Gemini's Structured Outputs (`response_schema`) to guarantee valid JSON parsing every time.
- **Dynamic Multi-Key Failover**: Automatically rotates through multiple Gemini API keys to bypass rate limits and quota caps.
- **Interactive GUI Control Panel**: Manage API keys, update system prompts, and grant admin permissions on the fly via `/edit`.
- **Access Control**: Strictly restricted to authorized Telegram User IDs—only approved admins can interact with the bot.
- **Auto-Restart & Daemonization**: Built-in support for PM2 process management to ensure continuous, zero-downtime operation.

---

## 🧠 How It Works

1. **User forwards** a channel post, media caption, or screenshot to the bot.
2. **Gemini 2.5 Flash** processes the content, extracting key metadata (e.g., title, description, source, date).
3. The **Structured Output** feature ensures the response adheres to a predefined JSON schema.
4. The bot returns a **clean, standardized post template** ready for publication—no manual reformatting required.

---

## 📂 Project Structure

```
telegram-post-bot/
├── bot.py                # Main bot application logic
├── ecosystem.config.js   # PM2 configuration for daemon management
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules for sensitive files
├── config.json           # Dynamic storage for API keys, prompts, and admins
└── README.md             # Project documentation
```

---

## 🛠️ Prerequisites

- **Python** 3.10 or higher
- **Node.js & PM2** (optional, for daemonized production deployment)
- **Telegram Bot Token** – obtain from [@BotFather](https://t.me/BotFather)
- **Gemini API Key** – generate via [Google AI Studio](https://aistudio.google.com/)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/abdullahkhalidlaptop/TG-Post-Maker.git
cd TG-Post-Maker
```

### 2. Set Up Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
OWNER_ID=123456789
GEMINI_API_KEY=AIzaSyYourApiKeyHere
```

### 5. Run the Bot

```bash
python bot.py
```

For production, see the [PM2 section](#-running-with-pm2).

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | **Yes** | Token from Telegram's `@BotFather`. |
| `OWNER_ID` | **Yes** | Numerical Telegram User ID of the primary owner/admin. |
| `GEMINI_API_KEY` | Optional | Default Gemini API key (can also be added via `/edit`). |

---

## 🖥️ Running with PM2

PM2 ensures your bot runs in the background and auto-restarts on crashes or system reboots.

### Install Node Globally

```bash
curl -fsSL https://nodesource.com | sudo -E bash -
```

### Install Node.js and npm

```bash
apt install -y nodejs npm
```

### Install PM2 Globally

```bash
npm install -g pm2
```

### Management Commands

```bash
# Start the bot
pm2 start ecosystem.config.js

# View logs
pm2 logs telegram-post-bot

# Check status
pm2 status

# Restart or stop
pm2 restart telegram-post-bot
pm2 stop telegram-post-bot

# Persist across reboots
pm2 save
pm2 startup
```

---

## 🤖 Bot Commands

| Command | Permission | Description |
|---------|------------|-------------|
| `/start` | Authorized Users | Displays an operational guide and initializes interaction. |
| `/edit` | Authorized Users | Opens the inline management panel for keys, prompts, and admins. |
| `/id` | Everyone | Replies with the user's numerical Telegram ID. |

---

## 🔧 Managing Configuration via Telegram

Use the `/edit` command in a chat with the bot to access the interactive control menu:

- **🔑 API Keys**: Add, view, or remove multiple Gemini API keys for load balancing.
- **📝 System Prompt**: View or edit the instruction prompt that guides Gemini's extraction logic.
- **👥 Admins**: Add or remove additional Telegram User IDs authorized to use the bot (Owner only).

---

## 🤝 Contributing

Contributions are welcome! If you'd like to improve the bot or add features:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m 'Add some feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

Please ensure your code adheres to the existing style and includes appropriate documentation.

---

## 📄 License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.

---

## 💬 Support

- **Documentation**: Check the [README](README.md) and inline comments in `bot.py`.
- **Issues**: Open a ticket on [GitHub Issues](https://github.com/abdullahkhalidlaptop/TG-Post-Maker/issues).
- **Telegram**: Reach out to the maintainer via [Telegram](https://t.me/ak_modz_official).

---

Made with ❤️ by the AKM Community.
