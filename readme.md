# Music Database Search

A tool that allows chatting with an LLM, which calls an MCP tool whenever the query requires searching the database. It also includes spelling correction so the database can be searched even with incorrect spellings.



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

- `mcp_server_fallback.py` - Database search server
- `chinook.db` - Music database
- `.env` - API key

