#!/usr/bin/env python3
import asyncio
import json
import sys
import os
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class LLMWithMCP:
    def __init__(self):
        self.mcp_process = None
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
    async def start_mcp_server(self):
        """Start the MCP server for database queries"""
        print("[DEBUG] Starting MCP server...")
        self.mcp_process = await asyncio.create_subprocess_exec(
            sys.executable, "mcp_server_fallback.py",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Initialize MCP server
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "llm-client", "version": "1.0.0"}
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
        line = await self.mcp_process.stdout.readline()
        return json.loads(line.decode().strip())
        
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
    
    def should_use_database(self, user_query: str) -> bool:
        """Decide if query needs database search"""
        music_keywords = [
            'artist', 'singer', 'band', 'musician', 'album', 'song', 'track', 
            'music', 'genre', 'rock', 'jazz', 'pop', 'metal', 'classical',
            'metallica', 'beatles', 'queen', 'led zeppelin', 'playlist'
        ]
        
        query_lower = user_query.lower()
        return any(keyword in query_lower for keyword in music_keywords)
    
    async def chat(self, user_query: str) -> str:
        """Main chat function - decides whether to use LLM or database"""
        print(f"[DEBUG] Processing: {user_query}")
        
        if self.should_use_database(user_query):
            print("[DEBUG] Using database search via MCP")
            try:
                db_result = await self.search_database(user_query)
                
                # Use LLM to format the database results nicely
                format_prompt = f"""
                The user asked: "{user_query}"
                
                Database search results:
                {db_result}
                
                Please provide a helpful, conversational response based on these results. 
                If no results were found, suggest alternative searches.
                """
                
                response = self.model.generate_content(format_prompt)
                return response.text
                
            except Exception as e:
                print(f"[DEBUG] Database search failed: {e}")
                # Fall back to normal LLM response
                return await self.normal_chat(user_query)
        else:
            print("[DEBUG] Using normal LLM response")
            return await self.normal_chat(user_query)
    
    async def normal_chat(self, user_query: str) -> str:
        """Normal LLM conversation"""
        try:
            response = self.model.generate_content(user_query)
            return response.text
        except Exception as e:
            return f"Sorry, I encountered an error: {e}"
    
    async def close(self):
        """Clean up resources"""
        if self.mcp_process:
            self.mcp_process.terminate()
            await self.mcp_process.wait()

async def main():
    """Main application"""
    llm = LLMWithMCP()
    
    try:
        await llm.start_mcp_server()
        
        print("\n=== AI Assistant with Music Database ===")
        print("I can answer general questions AND search the music database!")
        print("Examples:")
        print("- General: 'What is the capital of France?'")
        print("- Music: 'rock artists', 'albums by metallica'")
        print("Type 'quit' to exit\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            if not user_input:
                continue
                
            try:
                response = await llm.chat(user_input)
                print(f"\nAI: {response}\n")
            except Exception as e:
                print(f"Error: {e}\n")
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        await llm.close()

if __name__ == "__main__":
    asyncio.run(main())