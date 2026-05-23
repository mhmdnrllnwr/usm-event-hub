# USM Event Hub

A Telegram bot that automatically extracts structured event data from forwarded announcements. Built for Universiti Sains Malaysia event management.

## Architecture

```
Telegram → Bot (python-telegram-bot) → API (FastAPI) → MongoDB
```

- **Bot** — Telegram interface. Receives forwarded event messages, processes them via API, displays event list with inline keyboard UI.
- **API** — FastAPI backend. Extracts structured data from raw text using regex + spaCy NLP + DeepSeek AI fallback. CRUD endpoints for events.
- **MongoDB** — Event storage.

## Features

- **Auto-extraction** — Parse title, date, time, venue, fee, registration link from raw announcement text
- **Dual extraction engine** — spaCy NER + regex patterns, with AI fallback using DeepSeek when heuristics miss
- **Smart text cleanup** — Unicode normalization, emoji removal, speaker-role filtering
- **Duplicate detection** — Prevents duplicate events by title + date
- **Event status** — Computed as active/expired/upcoming based on date
- **Event management** — View, edit, delete events via inline buttons
- **Admin panel** — Special privileges for designated admin users
- **Poster images** — Telegram image upload and automatic serving via API
- **Search & filter** — Search by keyword, filter by fee status, MyCSD eligibility
- **Markdown-safe display** — All output uses HTML parse_mode to avoid Telegram MarkdownV2 escaping issues
- **Docker Compose** — One-command setup with hot-reload for development

## Quick Start

1. Clone the repo:
   ```bash
   git clone <repo-url>
   cd usm-event-hub
   ```

2. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

   Required variables:
   - `BOT_TOKEN` — Telegram Bot Token from [@BotFather](https://t.me/BotFather)
   - `DEEPSEEK_API_KEY` — DeepSeek API key (for AI fallback)
   - `ADMIN_IDS` — Comma-separated Telegram user IDs with admin access
   - `TELEGRAM_SUPERADMIN_ID` — Super admin user ID

3. Start all services:
   ```bash
   docker compose up -d --build
   ```

4. The bot should now be running. Forward an event announcement to start capturing.

## Usage

- **Forward a message** — Send any event announcement to the bot. It auto-extracts and saves the event.
- **Browse events** — Use `/browse` with filters (status, fee, MyCSD).
- **List events** — Shows only currently active events.
- **My Events** — View events you submitted.
- **Search** — `/search <keyword>` or use the Search button.
- **Edit/Delete** — Your events can be edited or deleted via inline buttons.
- **Admin Panel** — Admin-only commands for managing the system.

## Project Structure

```
├── api/                    # FastAPI backend
│   ├── main.py             # API routes (CRUD + process)
│   ├── database.py         # MongoDB queries
│   ├── models.py           # Pydantic models
│   ├── engine/
│   │   ├── nlp_handler.py  # spaCy title extraction + scoring
│   │   ├── regex_handler.py# Regex date/time/venue/fee extraction
│   │   ├── ai_handler.py   # DeepSeek AI validation fallback
│   │   └── config.py       # NLP config, labels, threshold
│   └── utils/
│       └── image_handler.py# Image download from Telegram
├── bot/                    # Telegram bot
│   ├── main.py             # Entry point + handlers registration
│   ├── config.py           # Bot config + conversation states
│   ├── handlers/           # Feature modules
│   │   ├── commands.py     # /start, /help, /browse, etc.
│   │   ├── callback.py     # Inline button routing
│   │   ├── menu.py         # Main menu display + event listing
│   │   ├── view.py         # Event detail + poster display
│   │   ├── edit.py         # Edit event flow
│   │   ├── delete.py       # Delete event flow
│   │   ├── create.py       # Manual event creation
│   │   ├── browse.py       # Browse with filters
│   │   ├── my_events.py    # User's submitted events
│   │   ├── push.py         # Forwarded message handling
│   │   └── admin.py        # Admin panel
│   ├── api_client.py       # HTTP client for API
│   ├── helpers.py          # Formatting utilities
│   └── keyboards.py        # Inline keyboard builders
├── docker-compose.yml      # 3-service setup (MongoDB + API + Bot)
└── .env                    # Environment variables (not committed)
```

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API
- **python-telegram-bot v20.8** — Bot framework
- **MongoDB + Motor** — Async database
- **spaCy** — NLP entity extraction
- **DeepSeek API** — AI validation fallback
- **Docker Compose** — Container orchestration
