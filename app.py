#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import asyncio
import json
import sys
import os
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

class LLMWithMCP:
    def __init__(self):
        self.mcp_process = None
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.loop = None
        self.vocabulary = self._load_vocabulary()
        
    async def start_mcp_server(self):
        """Start the MCP server for database queries"""
        print("[DEBUG] Starting MCP server...")
        self.mcp_process = await asyncio.create_subprocess_exec(
            sys.executable, "mcp_server_fallback.py",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # Merge stderr with stdout to see debug prints
        )
        
        # Initialize MCP server
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "web-client", "version": "1.0.0"}
            }
        }
        
        await self.send_mcp_message(init_message)
        response = await self.receive_mcp_message()
        
        # Send initialized notification
        initialized_message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self.send_mcp_message(initialized_message)
        print("[DEBUG] MCP server ready")
        
    async def send_mcp_message(self, message: Dict[str, Any]):
        """Send message to MCP server"""
        message_str = json.dumps(message) + "\n"
        self.mcp_process.stdin.write(message_str.encode())
        await self.mcp_process.stdin.drain()
        
    async def receive_mcp_message(self) -> Dict[str, Any]:
        """Receive message from MCP server"""
        while True:
            line = await self.mcp_process.stdout.readline()
            line_str = line.decode().strip()
            print(f"[MCP-OUTPUT] {line_str}")  # Show all MCP server output
            
            # Skip debug lines, only process JSON responses
            if line_str.startswith('[') or line_str.startswith('{'):
                try:
                    return json.loads(line_str)
                except json.JSONDecodeError:
                    continue
            # If it's a debug print, just continue to next line
        
    async def search_database(self, query: str) -> str:
        """Search database using MCP"""
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_music_database",
                "arguments": {"query": query}
            }
        }
        
        await self.send_mcp_message(message)
        response = await self.receive_mcp_message()
        
        if "result" in response and "content" in response["result"]:
            return response["result"]["content"][0]["text"]
        else:
            return f"Database search failed: {response}"
    
    def _load_vocabulary(self):
        """Load vocabulary from file or generate basic one"""
        try:
            with open('vocabulary.json', 'r') as f:
                vocab = json.load(f)
                print(f"[WEB-APP] Loaded {len(vocab)} vocabulary terms from file")
                return vocab
        except FileNotFoundError:
            print("[WEB-APP] vocabulary.json not found, using basic vocabulary")
            return ['artist', 'singer', 'band', 'musician', 'album', 'song', 'track', 'music', 'rock', 'jazz', 'pop']
    
    def should_use_database(self, user_query: str) -> bool:
        """Smart detection using fuzzy matching with comprehensive vocabulary"""
        try:
            from fuzzywuzzy import process
            
            words = user_query.lower().split()
            music_score = 0
            
            for word in words:
                if len(word) < 3:
                    continue
                best_match, score = process.extractOne(word, self.vocabulary)
                if score > 60:
                    music_score += score
            
            should_use_db = music_score > 60
            
            print(f"[WEB-APP] Query: '{user_query}'")
            print(f"[WEB-APP] Music relevance score: {music_score}")
            print(f"[WEB-APP] Use database: {should_use_db}")
            
            return should_use_db
        except ImportError:
            # Fallback to simple keyword matching if fuzzywuzzy not available
            simple_keywords = ['artist', 'singer', 'band', 'album', 'song', 'music', 'rock', 'jazz', 'pop']
            return any(kw in user_query.lower() for kw in simple_keywords)
    
    async def chat(self, user_query: str) -> str:
        """Main chat function - decides whether to use LLM or database"""
        print(f"[WEB-APP] *** NEW USER QUERY ***")
        print(f"[WEB-APP] User asked: '{user_query}'")
        
        if self.should_use_database(user_query):
            print("[WEB-APP] *** USING DATABASE SEARCH ***")
            try:
                print("[WEB-APP] Calling MCP server for database search...")
                db_result = await self.search_database(user_query)
                print(f"[WEB-APP] Database search completed")
                print(f"[WEB-APP] Raw database result: {db_result[:200]}...")
                
                # Use LLM to format the database results nicely
                format_prompt = f"""
                The user asked: "{user_query}"
                
                Database search results:
                {db_result}
                
                Please provide a helpful, conversational response based on these results. 
                If no results were found, suggest alternative searches.
                """
                
                print("[WEB-APP] Formatting results with Gemini LLM...")
                response = self.model.generate_content(format_prompt)
                print(f"[WEB-APP] LLM formatting completed")
                print(f"[WEB-APP] Final response: {response.text[:100]}...")
                return response.text
                
            except Exception as e:
                print(f"[WEB-APP] *** DATABASE SEARCH FAILED ***")
                print(f"[WEB-APP] Error: {e}")
                print(f"[WEB-APP] Falling back to normal LLM response")
                return await self.normal_chat(user_query)
        else:
            print("[WEB-APP] *** USING NORMAL LLM RESPONSE ***")
            return await self.normal_chat(user_query)
    
    async def normal_chat(self, user_query: str) -> str:
        """Normal LLM conversation"""
        try:
            response = self.model.generate_content(user_query)
            return response.text
        except Exception as e:
            return f"Sorry, I encountered an error: {e}"

# Global LLM instance
llm = LLMWithMCP()

def run_async(coro):
    """Run async function in sync context"""
    if llm.loop is None:
        llm.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(llm.loop)
        threading.Thread(target=llm.loop.run_forever, daemon=True).start()
    
    future = asyncio.run_coroutine_threadsafe(coro, llm.loop)
    return future.result()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '')
    print(f"[FLASK] *** RECEIVED WEB REQUEST ***")
    print(f"[FLASK] User message: '{user_message}'")
    
    if not user_message:
        print(f"[FLASK] Error: No message provided")
        return jsonify({'error': 'No message provided'}), 400
    
    try:
        print(f"[FLASK] Calling LLM chat function...")
        response = run_async(llm.chat(user_message))
        print(f"[FLASK] *** SENDING RESPONSE TO WEB ***")
        print(f"[FLASK] Response: {response[:100]}...")
        return jsonify({'response': response})
    except Exception as e:
        print(f"[FLASK] *** ERROR OCCURRED ***")
        print(f"[FLASK] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize MCP server
    print("Initializing MCP server...")
    run_async(llm.start_mcp_server())
    print("Starting Flask app...")
    app.run(debug=True, host='0.0.0.0', port=5000)