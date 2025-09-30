# Daily Motivational Telegram Bot



---

## Project Overview

This project is a **Daily Motivational Telegram Bot** that delivers motivational quotes and stress-relief tips to users.  
The bot also integrates **AI (Groq API)** to respond to user messages with personalized encouragement and guidance.  

The main goal of this project is to demonstrate a real-world implementation of **Telegram bot development, scheduled tasks, SQLite database management, and AI integration**.

---

## Features

- **Daily Motivational Messages** – Sent automatically at 9 AM IST to subscribed users.
- **Random Motivational Quotes** – Users can request quotes anytime using `/quote`.
- **Subscription Management** – Users can subscribe (`/subscribe`) or unsubscribe (`/unsubscribe`) from daily messages.
- **AI-Powered Responses** – The bot uses **Groq AI** to answer stress-related messages or provide motivational replies.
- **Context-Aware Replies** – The AI remembers recent conversations to provide better responses.

---

## Tech Stack

- **Programming Language:** Python  
- **Telegram Bot Framework:** python-telegram-bot v20  
- **Database:** SQLite (for subscriber management)  
- **AI Integration:** Groq API (LLaMA 3.1 model)  
- **Other Libraries:** `python-dotenv` for environment variables, `zoneinfo` for timezone handling  

---

## Installation & Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/daily-motivational-bot.git
cd daily-motivational-bot

