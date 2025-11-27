# Music Database Search

AI assistant with music database search using MCP.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add your Gemini API key to `.env` file:**
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
   Get a free API key from: https://makersuite.google.com/app/apikey

3. **Run the web interface:**
   ```bash
   python app.py
   ```

4. **Open browser to:**
   ```
   http://localhost:5000
   ```

## Usage

- Ask general questions: "What is AI?"
- Search music database: "rock artists", "albums by metallica"
- The system automatically decides when to use the database

## Files

- `app.py` - Web interface
- `mcp_server_fallback.py` - Database search server
- `chinook.db` - Music database
- `.env` - API key