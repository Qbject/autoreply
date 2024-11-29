# Autoreply

Autoreply is a cross-platform desktop application built on PyQt5 that allows users to connect their Telegram and VK accounts and automatically respond to incoming messages. The app offers a rich set of features, a verbose user-friendly GUI, and flexible configuration options.

https://github.com/user-attachments/assets/fad6bb6d-3c09-484e-bbc3-f9fd3f124def

## Table of Contents

1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Configuration](#configuration)
   - [Telegram Setup](#telegram-setup)
   - [VK Setup](#vk-setup)
   - [Google Sheets Logging](#google-sheets-logging)
   - [Telegram Bot for Logging](#telegram-bot-for-logging)
6. [Technical Details](#technical-details)

## Features

- **Verbose GUI:** The app provides detailed explanations of all actions and settings within the GUI.
- **Multi-Account Support:** Connect multiple Telegram and VK accounts, each running on separate threads.
- **Tray Functionality:** Minimize the app to the system tray and close it entirely from the tray icon.
- **Enable/Disable Accounts:** Enable or disable specific accounts at any time.
- **First Message Response:** Option to respond only to the first message in a chat.
- **Automatic Chat Deletion:** Automatically delete the chat after sending a response.
- **Attachment Support:** Add attachments, such as images, to reply messages.
- **Proxy Configuration:** Support for HTTP, SOCKS4, SOCKS5, and MTPROTO (Telegram only) proxies.
- **Logging:** Logs all actions and errors to separate log files.
- **Google Sheets Logging:** Send logs to Google Sheets for each automatic reply.
- **Telegram Bot Reporting:** Use a Telegram bot to send reports about autoresponses to specified chats or channels at configurable intervals.
- **Multithreading:** Efficiently handles tasks in parallel while maintaining a responsive GUI.
- **Cross-Platform Compatibility:** Runs on any platform.

## Prerequisites

- Python 3.6+
- Git

## Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/Qbject/autoreply.git
   cd autoreply
   ```

2. **Create a virtual environment:**
   ```sh
   python -m venv .venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```sh
     .venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```sh
     source .venv/bin/activate
     ```

4. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

5. **Build the application using PyInstaller:**
   ```sh
   # On Windows
   build.bat

   # On macOS/Linux
   ./build.sh
   ```

6. **The built app will be located in the `dist/Autoreply` directory. This directory is portable and contains all necessary data.**

## Usage

1. **Run the App:**
   ```sh
   python src/autoreply.py
   ```

2. **Tray Functionality:**
   - Minimize the main window to the system tray.
   - Close the app entirely using the tray icon.

3. **Data Directory:**
   - All app data, including Telegram sessions, Google API credentials, logs, and settings, are stored in the `data` directory.

## Configuration

### Telegram Setup

1. Register your application on Telegram:
   - Go to [my.telegram.org](https://my.telegram.org/).
   - Log in with any Telegram account (preferably one you won't lose access to).
   - Navigate to "API Development Tools" and create a new application.
   - Choose "Desktop" as the platform and fill in the required fields.
   - Copy the `api_id` and `api_hash` provided.

2. In the Autoreply app, input the `api_id` and `api_hash` in the corresponding fields and save the settings.

### VK Setup

1. VK does not require additional setup beyond providing the VK App ID. The default is set to Kate Mobile's App ID, but you can change it if needed.

### Google Sheets Logging

1. Create a new project in the [Google Developers Console](https://console.developers.google.com/).
2. Enable the Google Sheets API and Drive API for the project.
3. Create a new Service Account, generate a JSON key file, and download it.
4. Rename the file to `google.json` and place it in the `data` directory.
5. Share two Google Sheets named "Autoreply TG" and "Autoreply VK" with write access to the service account.

### Telegram Bot for Logging

1. Create a new bot using [BotFather](https://t.me/BotFather).
2. Copy the bot token and input it into the Autoreply app.
3. Specify the IDs of users or channels to receive reports, which can be obtained using [@myidbot](https://t.me/myidbot) and [@raw_data_bot](https://t.me/raw_data_bot).

## Technical Details

- **Telethon Library:** Used for interfacing with the Telegram API.
- **PyQt5:** Provides the graphical user interface.
- **Multithreading:** Ensures efficient handling of multiple accounts and tasks.
- **Cross-Platform:** Can be run on Windows, macOS, and Linux.
- **Qt Designer and UI Compilation:**
  - The app includes 2 UI files that can be edited using Qt Designer.
  - These UI files can be compiled into Python files using the provided `compile-ui.bat` (for Windows) or `compile-ui.sh` (for macOS/Linux) scripts.

## License

This project is licensed under the MIT License.
