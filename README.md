# DEBUG ARENA — Admin Edition

A local, admin-operated debugging competition manager.

## Features
- Admin password login
- Participant registration with automatic IDs
- Challenge setup with an individual duration per bug code
- Start, pause, resume and reset round timer
- Manual score entry for each participant and challenge
- Cumulative points and live leaderboard
- Score correction and deletion
- Projector leaderboard view
- SQLite database stored locally

## Requirements
- Python 3.10 or newer
- Flask

## Installation (Windows)
1. Extract the ZIP.
2. Open the extracted `debug_arena` folder.
3. Open Command Prompt in that folder.
4. Run:

   ```bash
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. Set a new admin password and secret key:

   ```bat
   set DEBUG_ARENA_PASSWORD=YourStrongPasswordHere
   set DEBUG_ARENA_SECRET=PutALongRandomSecretHere
   ```

6. Start the application:

   ```bash
   py app.py
   ```

7. Open `http://127.0.0.1:5000` in your browser.

## Default login
If you have not set the environment variable, the initial password is:

`ChangeMe123!`

**Change it before using the application at your event.**

## Event workflow
1. Log in as admin.
2. Add all participants in Participants.
3. Add each bug challenge and its duration in Challenges.
4. Start the current round timer from Challenges.
5. Open Score Entry and select a participant, challenge, result and points.
6. Check the Leaderboard; it recalculates from saved score records.
7. Open Projector to display the current leaderboard and timer.

## Important design notes
- Students do not get accounts or application access.
- The app binds to `127.0.0.1` only, so it is intended for one admin computer.
- Connect that computer to the projector using HDMI for public display.
- Scores are manually entered by the admin.
- A participant can have one score record per challenge. Use Edit to correct a record.
- The configured maximum points is a reference; manual scoring is intentionally allowed.
- Timer duration is per challenge. Starting another challenge replaces the current timer.
- Tie-break order: total points, number of positive Correct results, earliest score timestamp, then participant name.
- Data is stored in `debug_arena.db` beside `app.py`. Back up this file before and after the event.

## Safety and reliability
This starter application does not run or execute student-submitted code. Judges inspect solutions separately and the admin records the result. This avoids running untrusted code on the event computer.

For an event deployment, keep the computer physically controlled, use a strong password, disable sleep during the event, and make a backup copy of the database. This is a local starter application; test it with sample data before competition day.
